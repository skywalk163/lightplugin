#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
覆盖率评测.py —— 光明（Light）语言项目「北极星覆盖率评测」脚本
====================================================================

【指标定义（计划书 v2.2 唯一口径，不得偏离）】
  覆盖率 = holdout 中被语料 token 覆盖的比例；目标 >= 0.95，且越高越好。

【分母口径（写死）】
  分母 = holdout 的「去重 token 种数」（distinct token 文本种数）；
  脚本同时输出 holdout token「总次数」（含重复出现）作为参考，不参与比值。

【必输出项】
  1) 覆盖率数值；
  2) 分母（holdout 去重 token 种数）；
  3) holdout token 总次数（参考）；
  4) 语料版本：语料文件行数/条数 + 语料文件清单（含 sha256，运行时实时统计）；
  5) 缺口明细：未覆盖 token 按出现次数降序 TopN，附来源文件与出现次数。
  达标不达标都如实输出，不虚报、不挑选样本。

【holdout 构造方式（写死，保证可复现）】
  默认全量：lightharness/src/ 下全部 .light 模块（递归）+
            lightharness/examples/ 下全部 .light（递归），排序后逐个读取。
  可选抽样：--sample N --seed 20261004（种子默认 20261004），用
            random.Random(seed).sample(排序后文件清单, N)，同参数必同结果。

【语料版本获取方式】
  运行时实时统计：逐文件统计物理行数与解析条数，并计算整文件 sha256，
  随摘要与 --json 报告一并输出——不写死版本号，语料文件一变版本即变。

【语料源与字段取舍（含理由）】
  1) lightplugin/数据集/代码数据集.jsonl（每行 JSON，字段 id/instruction/input/output）：
     仅 output 字段（光明代码正文）分词计入语料。
     理由：output 是唯一的光明代码正文，holdout 也是 .light 代码正文，二者同质对比
     才符合「语料 token 覆盖 holdout token」口径；id/instruction/input 是中文任务
     描述与上下文，计入会引入大量与代码无关的中文散文 token、虚增覆盖率，故不计入。
  2) 光明×LightHarness_调试问题数据集.json（顶层 dict，samples 列表，字段
     id/instruction/input/output/meta；--with-err 默认并入）：
     input 字段全文计入——其 schema 定义即「相关报错信息/复现代码」，本身是代码/报错
     片段；instruction/output 仅提取反引号内容（``` 围栏代码块与 ` 行内代码片段）计入。
     理由：该数据集 instruction/output 正文是中文根因分析散文，只有反引号内是光明
     代码/报错片段；散文不计入，保持「代码 token 对代码 token」的同质口径。

【分词器选择（写死）】
  --tokenizer auto（默认）：优先复用 light-merge/antlrparser/light_tokenizer.py 的
    LightLangTokenizer（API：tokenize(source: str) -> List[Token]，取 token.text）。
    该模块顶层 `from antlr4 import *`，依赖第三方 antlr4 包且需临时注入 sys.path；
    缺依赖 / import 失败 / 运行异常时自动退化为自实现确定性分词，并在输出中如实注明。
  --tokenizer simple：直接用自实现确定性分词（纯标准库，零依赖，结果最稳定）：
    - 跳过 ``` 注释块、# 与 // 单行注释（对齐 light_tokenizer，注释不算代码 token）；
    - 字符串字面量（"…" / '…'，含转义）整体成单 token（含引号），对齐 light_tokenizer；
      f/F 字符串前缀跳过；
    - 中文字符单字成 token；
    - 连续 ASCII 字母/数字/下划线成一个 token（连续数字自然落入此规则）；
    - 其余每个标点符号单独成 token（==、-> 等多字符符号按单字符拆开，口径从简写死）；
    - 空白不计 token。

【其他】
  - 纯标准库（json/argparse/pathlib/collections/random/hashlib/datetime/sys/re），
    Python 3.12/3.13 兼容，读写均显式 encoding="utf-8"；
  - 路径从脚本位置推导：BASE = 本脚本所在目录（lightplugin/数据集），
    ROOT = BASE 上两级（仓库根），不写死盘符；
  - 幂等：不修改任何输入文件；--json 时将报告落盘 BASE/覆盖率报告.json（默认不落盘）；
  - 正常运行退出码 0；语料/holdout 缺失或全不可用时退出码 2 并给出明确报错信息。

用法：
  python lightplugin/数据集/覆盖率评测.py [--sample N] [--seed N]
      [--with-err|--no-err] [--top N] [--tokenizer auto|simple|project] [--json]
"""

from __future__ import annotations

import argparse
import collections
import datetime
import hashlib
import json
import pathlib
import random
import re
import sys

# ---------------------------------------------------------------------------
# 路径推导（不写死盘符）
# ---------------------------------------------------------------------------
BASE = pathlib.Path(__file__).resolve().parent            # lightplugin/数据集
ROOT = BASE.parent.parent                                 # 仓库根目录

CORPUS_JSONL = BASE / "代码数据集.jsonl"
CORPUS_ERR_JSON = ROOT / "光明×LightHarness_调试问题数据集.json"
HOLDOUT_DIRS = (ROOT / "lightharness" / "src", ROOT / "lightharness" / "examples")
REPORT_PATH = BASE / "覆盖率报告.json"
PROJECT_TOKENIZER_DIR = ROOT / "light-merge" / "antlrparser"

DEFAULT_SEED = 20261004
TARGET_COVERAGE = 0.95


def fatal(msg):
    """明确报错并退出（退出码 2）"""
    print(f"[错误] {msg}", file=sys.stderr)
    sys.exit(2)


def warn(msg):
    print(f"[警告] {msg}")


# ---------------------------------------------------------------------------
# 自实现确定性分词（退化路线，口径写死，见文件头注释）
# ---------------------------------------------------------------------------
def _is_cjk(ch):
    cp = ord(ch)
    return 0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF or 0xF900 <= cp <= 0xFAFF


def _is_word(ch):
    """ASCII 字母 / 数字 / 下划线"""
    return ("a" <= ch <= "z") or ("A" <= ch <= "Z") or ("0" <= ch <= "9") or ch == "_"


def tokenize_simple(text):
    """确定性分词：中文单字成 token，连续 ASCII 字母数字下划线成 token，
    每个标点符号单独成 token；跳过注释；字符串字面量整体成单 token。"""
    tokens = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        # ``` 代码块（对齐 light_tokenizer：整体跳过，不算代码 token）
        if text.startswith("```", i):
            end = text.find("```", i + 3)
            i = n if end < 0 else end + 3
            continue
        # 单行注释
        if ch == "#" or (ch == "/" and i + 1 < n and text[i + 1] == "/"):
            while i < n and text[i] != "\n":
                i += 1
            continue
        # f/F 字符串前缀（f"…"），跳过前缀，字符串下一轮整体成 token
        if ch in ("f", "F") and i + 1 < n and text[i + 1] in ("\"", "'"):
            i += 1
            continue
        # 字符串字面量：整体成单 token（含引号与转义），对齐 light_tokenizer
        if ch in ("\"", "'"):
            quote = ch
            j = i + 1
            buf = [quote]
            while j < n:
                if text[j] == "\\" and j + 1 < n:
                    buf.append(text[j])
                    buf.append(text[j + 1])
                    j += 2
                    continue
                buf.append(text[j])
                if text[j] == quote:
                    j += 1
                    break
                j += 1
            tokens.append("".join(buf))
            i = j
            continue
        # 空白不计 token
        if ch in " \t\r\n":
            i += 1
            continue
        # 中文字符单字成 token
        if _is_cjk(ch):
            tokens.append(ch)
            i += 1
            continue
        # 连续 ASCII 字母/数字/下划线成一个 token
        if _is_word(ch):
            j = i
            while j < n and _is_word(text[j]):
                j += 1
            tokens.append(text[i:j])
            i = j
            continue
        # 其余每个标点符号单独成 token
        tokens.append(ch)
        i += 1
    return tokens


# ---------------------------------------------------------------------------
# 复用 light-merge 项目分词器（优先路线，import 失败自动退化）
# ---------------------------------------------------------------------------
def load_project_tokenizer():
    """尝试加载 light_tokenizer.LightLangTokenizer。

    返回 (tokenize 函数, 描述) 或 (None, 失败原因)。
    该模块顶层 `from antlr4 import *`，依赖第三方 antlr4 包；
    light-merge 为编译器冻结区，此处只读 import，不做任何写入。
    """
    if not (PROJECT_TOKENIZER_DIR / "light_tokenizer.py").exists():
        return None, f"未找到 {PROJECT_TOKENIZER_DIR / 'light_tokenizer.py'}"
    dir_str = str(PROJECT_TOKENIZER_DIR)
    if dir_str not in sys.path:
        sys.path.insert(0, dir_str)
    try:
        import light_tokenizer  # noqa: E402  type: ignore
    except Exception as exc:  # antlr4 缺失或其他 import 依赖问题
        return None, f"import light_tokenizer 失败（{exc.__class__.__name__}: {exc}）"
    try:
        tok = light_tokenizer.LightLangTokenizer()

        def _tokenize(source):
            return [t.text for t in tok.tokenize(source)]

        return _tokenize, "light-merge/antlrparser/light_tokenizer.py :: LightLangTokenizer（复用项目分词器）"
    except Exception as exc:
        return None, f"LightLangTokenizer 初始化失败（{exc.__class__.__name__}: {exc}）"


def resolve_tokenizer(mode):
    """按 --tokenizer 解析出实际使用的分词器，返回 (tokenize, 描述, 备注)"""
    if mode == "simple":
        return tokenize_simple, "自实现确定性分词（simple，纯标准库）", ""
    if mode == "project":
        fn, note = load_project_tokenizer()
        if fn is None:
            fatal(f"--tokenizer project 加载失败：{note}")
        return fn, note, ""
    # auto：优先复用，失败退化为 simple，并如实备注
    fn, note = load_project_tokenizer()
    if fn is not None:
        return fn, note, ""
    return (tokenize_simple,
            "自实现确定性分词（simple，纯标准库）",
            f"auto 复用项目分词器失败，已退化为 simple。原因：{note}")


# ---------------------------------------------------------------------------
# 语料加载
# ---------------------------------------------------------------------------
_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_OPEN_FENCE_RE = re.compile(r"```.*\Z", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")


def _extract_backtick_snippets(text):
    """提取反引号内容：``` 围栏代码块（整体）+ ` 行内代码片段。"""
    out = []
    pos = 0
    # 先整体吃掉闭合围栏块，块间空隙只取行内代码
    for m in _FENCE_RE.finditer(text):
        out.extend(_INLINE_CODE_RE.findall(text[pos:m.start()]))
        out.append(m.group(0))
        pos = m.end()
    tail = text[pos:]
    tail_m = _OPEN_FENCE_RE.search(tail)
    if tail_m:
        # 未闭合的尾部围栏块整体计入，剩余部分取行内代码
        out.extend(_INLINE_CODE_RE.findall(tail[: tail_m.start()]))
        out.append(tail_m.group(0))
        rest = tail[tail_m.end():]
    else:
        rest = tail
    out.extend(_INLINE_CODE_RE.findall(rest))
    return out


def _file_sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def iter_jsonl(path):
    """逐行解析 JSONL；跳过空行，坏行跳过并警告。yield (行号, 对象)。"""
    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield lineno, json.loads(line)
            except json.JSONDecodeError as exc:
                warn(f"{path.name} 第 {lineno} 行 JSON 解析失败，已跳过：{exc}")


def load_corpus(with_err):
    """加载语料，返回 (语料片段列表, 语料版本 dict, 警告列表)。

    - 代码数据集.jsonl：仅 output 字段（光明代码正文）分词计入；
      id/instruction/input 为中文描述，不计入（理由见头注释）。
    - 调试问题数据集.json（--with-err 时并入）：input 全文计入（schema 定义即
      报错信息/复现代码）+ instruction/output 反引号片段计入；中文散文不计入。
    语料版本 dict：文件名 -> {行数, 条数, sha256, ...}。
    """
    items = []      # 语料文本片段（逐个独立分词）
    version = {}
    warns = []

    # ---- 1) 代码数据集.jsonl ----
    if not CORPUS_JSONL.exists():
        fatal(f"语料文件缺失：{CORPUS_JSONL}")
    with CORPUS_JSONL.open("r", encoding="utf-8") as f:
        physical_lines = sum(1 for _ in f)
    count = 0
    for lineno, obj in iter_jsonl(CORPUS_JSONL):
        if not isinstance(obj, dict):
            warns.append(f"{CORPUS_JSONL.name} 第 {lineno} 行不是 JSON 对象，已跳过")
            continue
        output = obj.get("output")
        if isinstance(output, str) and output.strip():
            items.append(output)
            count += 1
        else:
            warns.append(f"{CORPUS_JSONL.name} 第 {lineno} 行 output 为空，已跳过")
    if count == 0:
        fatal(f"语料文件为空或无有效 output 字段：{CORPUS_JSONL}")
    version[CORPUS_JSONL.name] = {
        "行数": physical_lines,
        "条数": count,
        "sha256": _file_sha256(CORPUS_JSONL),
    }
    print(f"[语料] {CORPUS_JSONL.name}：物理行数 {physical_lines}，有效条数 {count}（仅 output 计入）")

    # ---- 2) 调试问题数据集.json（可选，默认并入） ----
    if with_err:
        if not CORPUS_ERR_JSON.exists():
            warns.append(f"报错数据集缺失，未并入：{CORPUS_ERR_JSON}")
        else:
            raw = CORPUS_ERR_JSON.read_text(encoding="utf-8")
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                data = None
                warns.append(f"报错数据集解析失败，未并入：{exc}")
            if isinstance(data, dict):
                samples = data.get("samples") or []
                err_count = 0
                lp_count = 0
                for s in samples:
                    if not isinstance(s, dict):
                        continue
                    if str(s.get("id", "")).startswith("LP"):
                        lp_count += 1
                    pieces = []
                    inp = s.get("input")
                    if isinstance(inp, str) and inp.strip():
                        pieces.append(inp)  # input 全文计入（报错信息/复现代码）
                    for key in ("instruction", "output"):
                        v = s.get(key)
                        if isinstance(v, str) and v.strip():
                            pieces.extend(_extract_backtick_snippets(v))
                    if any(p.strip() for p in pieces):
                        items.extend(pieces)
                        err_count += 1
                if err_count == 0:
                    warns.append("报错数据集无有效样本片段，未并入语料")
                else:
                    version[CORPUS_ERR_JSON.name] = {
                        "行数": len(raw.splitlines()),
                        "条数": err_count,
                        "总条数": len(samples),
                        "LP系列条数": lp_count,
                        "version字段": data.get("version", ""),
                        "sha256": _file_sha256(CORPUS_ERR_JSON),
                    }
                    print(f"[语料] {CORPUS_ERR_JSON.name}：并入 {err_count}/{len(samples)} 条"
                          f"（LP 系列 {lp_count} 条；input 全文 + instruction/output 反引号片段）")

    return items, version, warns


# ---------------------------------------------------------------------------
# holdout 收集
# ---------------------------------------------------------------------------
def collect_holdout(sample, seed):
    """收集 holdout .light 文件。默认全量（排序后）；--sample N 用
    random.Random(seed).sample 抽样，保证可复现。返回 (文件列表, 全量数, 是否抽样, 说明)。"""
    notes = []
    files = []
    for d in HOLDOUT_DIRS:
        if not d.exists():
            notes.append(f"holdout 目录不存在，已跳过：{d}")
            continue
        found = sorted(p for p in d.rglob("*.light") if p.is_file())
        if not found:
            notes.append(f"holdout 目录下无 .light 文件：{d}")
        files.extend(found)
    files = sorted(set(files))
    if not files:
        fatal("holdout 为空：lightharness/src 与 lightharness/examples 下均无 .light 文件")
    total = len(files)
    sampled = False
    if sample and sample > 0:
        if sample >= total:
            notes.append(f"--sample {sample} >= holdout 总数 {total}，退化为全量评测")
        else:
            rng = random.Random(seed)
            files = sorted(rng.sample(files, sample))
            sampled = True
            notes.append(f"抽样：{sample}/{total} 个文件，seed={seed}（random.Random({seed}).sample，排序后抽取）")
    return files, total, sampled, notes


# ---------------------------------------------------------------------------
# 评测计算
# ---------------------------------------------------------------------------
def evaluate(holdout_files, tokenize, corpus_token_set):
    """计算覆盖率。

    分母 = holdout 去重 token 种数；分子 = 其中被语料 token 集覆盖的种数；
    token 总次数（含重复出现）仅作参考输出，不参与比值。
    """
    holdout_counter = collections.Counter()       # token -> 出现次数
    token_sources = collections.defaultdict(set)  # token -> 来源文件相对路径集合

    for path in holdout_files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # 个别文件非纯 UTF-8：容错读取并继续，不让单文件中断评测
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                warn(f"读取失败，已跳过 {path}：{exc}")
                continue
        except OSError as exc:
            warn(f"读取失败，已跳过 {path}：{exc}")
            continue
        try:
            rel = str(path.relative_to(ROOT))
        except ValueError:
            rel = str(path)
        for tok in tokenize(text):
            holdout_counter[tok] += 1
            token_sources[tok].add(rel)

    denom = len(holdout_counter)                       # 分母：去重 token 种数
    numerator = sum(1 for t in holdout_counter if t in corpus_token_set)
    total_occurrences = sum(holdout_counter.values())  # token 总次数（参考）
    coverage = (numerator / denom) if denom else 0.0
    missing = [t for t in holdout_counter if t not in corpus_token_set]
    missing.sort(key=lambda t: (-holdout_counter[t], t))
    return {
        "counter": holdout_counter,
        "sources": token_sources,
        "denom": denom,
        "numerator": numerator,
        "total_occurrences": total_occurrences,
        "coverage": coverage,
        "missing": missing,
    }


# ---------------------------------------------------------------------------
# 报告输出
# ---------------------------------------------------------------------------
def build_report(args, tokenizer_desc, tokenizer_note, corpus_items,
                 corpus_token_set, corpus_version, holdout_files,
                 holdout_total, sampled, stats, warns, notes):
    """组装评测结果，输出人类可读摘要；--json 时落盘报告。"""
    denom = stats["denom"]
    numerator = stats["numerator"]
    coverage = stats["coverage"]
    total_occurrences = stats["total_occurrences"]
    missing = stats["missing"]
    sources = stats["sources"]
    passed = denom > 0 and coverage >= TARGET_COVERAGE

    # 缺口明细：未覆盖 token 按出现次数降序 TopN，附来源文件与出现次数
    top = args.top if args.top and args.top > 0 else 20
    gaps = [
        {
            "token": t,
            "出现次数": stats["counter"][t],
            "来源文件": sorted(sources[t]),
        }
        for t in missing[:top]
    ]

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print()
    print("=" * 62)
    print("光明（Light）语言 · 北极星覆盖率评测报告")
    print("=" * 62)
    print(f"评测时间       ：{now}")
    print("指标口径       ：覆盖率 = holdout 中被语料 token 覆盖的比例（计划书 v2.2）")
    print(f"目标           ：覆盖率 >= {TARGET_COVERAGE}，越高越好")
    print("分母口径       ：holdout 去重 token 种数")
    print(f"分词器         ：{tokenizer_desc}")
    if tokenizer_note:
        print(f"分词器备注     ：{tokenizer_note}")
    print("-" * 62)
    print(f"覆盖率         ：{coverage:.4f}  （{numerator}/{denom}）")
    print(f"分母           ：{denom}  （holdout 去重 token 种数）")
    print(f"token 总次数   ：{total_occurrences}  （含重复，仅作参考）")
    print(f"holdout 文件数 ：{len(holdout_files)}"
          + (f"（全量 {holdout_total}，抽样 seed={args.seed}）" if sampled
             else "（全量，未抽样）"))
    print(f"语料 token 种数：{len(corpus_token_set)}（语料片段 {len(corpus_items)} 个）")
    print(f"未覆盖 token   ：{len(missing)} 种")
    print("-" * 62)
    verdict = "达标" if passed else "未达标"
    print(f"达标判定       ：{verdict}（目标 >= {TARGET_COVERAGE}；达标不达标如实记录，不虚报）")
    print("-" * 62)
    print(f"缺口明细 Top{len(gaps)}（未覆盖 token 按出现次数降序，附来源文件与出现次数）：")
    if not gaps:
        print("  （无未覆盖 token）")
    for i, g in enumerate(gaps, 1):
        srcs = "、".join(g["来源文件"][:3]) + ("…" if len(g["来源文件"]) > 3 else "")
        print(f"  {i:>3}. {g['token']!r}  出现 {g['出现次数']} 次  来源：{srcs}")
    print("-" * 62)
    print("语料版本（运行时实时统计，行数/条数 + 文件清单）：")
    for name, v in corpus_version.items():
        extra = ""
        if "LP系列条数" in v:
            extra = f"，总条数 {v['总条数']}，LP 系列 {v['LP系列条数']}，version={v['version字段']}"
        print(f"  - {name}：行数 {v['行数']}，条数 {v['条数']}{extra}，sha256={v['sha256'][:16]}…")
    print("  holdout 目录：" + "、".join(str(d) for d in HOLDOUT_DIRS))
    for n in notes:
        print(f"[说明] {n}")
    for w in warns:
        print(f"[警告] {w}")
    print("=" * 62)

    if args.json:
        report = {
            "报告时间": now,
            "指标口径": "覆盖率 = holdout 中被语料 token 覆盖的比例（计划书 v2.2）",
            "目标": TARGET_COVERAGE,
            "分母口径": "holdout 去重 token 种数",
            "分词器": tokenizer_desc,
            "分词器备注": tokenizer_note,
            "覆盖率": round(coverage, 6),
            "分子_被覆盖token种数": numerator,
            "分母_holdout去重token种数": denom,
            "holdout_token总次数_参考": total_occurrences,
            "holdout_文件数": len(holdout_files),
            "holdout_全量文件数": holdout_total,
            "holdout_抽样": {"sample": args.sample, "seed": args.seed, "已抽样": sampled},
            "语料token种数": len(corpus_token_set),
            "语料片段数": len(corpus_items),
            "未覆盖token种数": len(missing),
            "达标": passed,
            "语料版本": corpus_version,
            "缺口明细TopN": gaps,
            "说明": notes,
            "警告": warns,
        }
        REPORT_PATH.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[输出] JSON 报告已落盘：{REPORT_PATH}")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # 兼容 GBK 控制台
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(
        description="光明（Light）语言北极星覆盖率评测：holdout 中被语料 token 覆盖的比例（目标 >= 0.95）")
    parser.add_argument("--sample", type=int, default=0,
                        help="holdout 抽样文件数（默认 0 = 全量不抽样）")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED,
                        help=f"抽样随机种子（默认 {DEFAULT_SEED}）")
    parser.add_argument("--with-err", action=argparse.BooleanOptionalAction, default=True,
                        help="是否并入调试问题数据集语料（默认 --with-err 并入）")
    parser.add_argument("--top", type=int, default=20,
                        help="缺口明细输出条数（默认 20）")
    parser.add_argument("--tokenizer", choices=["auto", "simple", "project"], default="auto",
                        help="分词器：auto=优先复用项目分词器，失败退化 simple（默认）；"
                             "simple=自实现确定性分词；project=强制复用项目分词器")
    parser.add_argument("--json", action="store_true",
                        help=f"将 JSON 报告落盘 {REPORT_PATH}（默认不落盘）")
    args = parser.parse_args()

    tokenize, tokenizer_desc, tokenizer_note = resolve_tokenizer(args.tokenizer)
    if tokenizer_note:
        print(f"[说明] {tokenizer_note}")
    print(f"[分词器] {tokenizer_desc}")

    corpus_items, corpus_version, warns = load_corpus(args.with_err)
    # 语料 token 集：语料片段逐个分词后取并集（去重 token 种数）
    corpus_token_set = set()
    for piece in corpus_items:
        corpus_token_set.update(tokenize(piece))
    if not corpus_token_set:
        fatal("语料 token 集为空：请检查语料文件内容")

    holdout_files, holdout_total, sampled, notes = collect_holdout(args.sample, args.seed)
    stats = evaluate(holdout_files, tokenize, corpus_token_set)
    build_report(args, tokenizer_desc, tokenizer_note, corpus_items,
                 corpus_token_set, corpus_version, holdout_files,
                 holdout_total, sampled, stats, warns, notes)


if __name__ == "__main__":
    main()
