# -*- coding: utf-8 -*-
"""北极星指标（Z）· 零 LLM token 跑通率评测（轨道 A，2026-10-02 口径决策）

口径（team lead 2026-10-02 决策）：
- 北极星 Z = holdout（lightharness/src 生产模块固定种子抽样）中可「零 LLM token 跑通」的模块比例。
- 分母 = 抽样模块数（种子默认 20261004，默认抽 64/全量，可 --sample 0 表示全量）。
- 两级判定，分开出数：
  * Z_跑通（主数值）：模块挂有真实示例（examples/ 中显式 `从 <模块> 导入` 的 .light），
    取最小的一个示例用 lightharness/运行.py 实跑，退出码 0 → 覆盖。
    示例全部走 mock/无 API Key 路径，评测过程不调用任何大模型。
  * Z_导入（下限参考）：模块可被编译导入（探针 `从 <模块> 导入 <顶层符号>`，rc=0 且输出 IMPORT_OK）。
    无真实示例的模块按导入级判定并在明细中标注。
- 无顶层可导入符号、探针超时/报错的模块计入分母、按未覆盖记录（理由如实附上）。
- token 覆盖率（旧口径）已降为附录，见 覆盖率评测.py / 覆盖率报告.json。

纯标准库；路径从脚本位置推导；确定性可复现；不改任何输入文件。
"""
import argparse
import collections
import concurrent.futures
import datetime
import io
import json
import os
import random
import re
import subprocess
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent          # lightplugin/数据集
ROOT = BASE.parent.parent                        # duan-light-merge
LH = ROOT / "lightharness"
SRC = LH / "src"
EXAMPLES = LH / "examples"
RUNNER = LH / "运行.py"
REPORT = BASE / "零token覆盖率报告.json"

IDENT = r"[\u4e00-\u9fffA-Za-z_][0-9A-Za-z_\u4e00-\u9fff]*"
RE_SYM = re.compile(r"^(?:段落 (%s)\s*\(|设 (%s)\s*[=为]|类 (%s)\s*[:：]?)" % (IDENT, IDENT, IDENT))
RE_IMPORT = re.compile(r"^从\s+(%s)\s+导入" % IDENT)


def _eprint(*a):
    print(*a)
    try:
        sys.stdout.flush()
    except Exception:
        pass


def list_modules():
    return sorted(p for p in SRC.glob("*.light"))


def top_symbol(path):
    """模块第一个顶层可导入符号（段落/设），无则返回 None。"""
    try:
        text = io.open(str(path), encoding="utf-8", errors="replace").read()
    except OSError:
        return None
    for line in text.split("\n"):
        m = RE_SYM.match(line)
        if m:
            return m.group(1) or m.group(2) or m.group(3)
    return None


def build_example_graph(mod_names):
    """模块名 -> 挂它的示例列表 [(示例路径, 行数)]（按显式 `从 <模块> 导入` 匹配）。"""
    graph = collections.defaultdict(list)
    names = set(mod_names)
    for ex in sorted(EXAMPLES.rglob("*.light")):
        try:
            text = io.open(str(ex), encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        lines = text.split("\n")
        hits = set()
        for line in lines:
            m = RE_IMPORT.match(line)
            if m and m.group(1) in names:
                hits.add(m.group(1))
        for name in hits:
            graph[name].append((ex, len(lines)))
    for k in graph:
        graph[k].sort(key=lambda t: (t[1], str(t[0])))
    return graph


def run_cmd(cmd, cwd, timeout):
    try:
        p = subprocess.run(cmd, cwd=str(cwd), capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return p.returncode, (p.stdout or ""), (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "", "TIMEOUT %ss" % timeout
    except OSError as exc:
        return 127, "", str(exc)


def probe_module(mod, sym, tmpdir, timeout):
    """返回 (级, rc, stdout, stderr) ；级 = '跑通' | '导入' | '未覆盖'"""
    if sym:
        # 1) 跑通级：实跑挂该模块的最小示例
        p = mod.stem
        exs = EXAMPLE_GRAPH.get(p)
        if exs:
            ex = exs[0][0]
            rc, out, err = run_cmd([sys.executable, str(RUNNER), str(ex)], LH, timeout)
            if rc == 0:
                return "跑通", rc, out, err
            # 示例失败 → 记录，仍做导入级兜底
        # 2) 导入级：最小导入探针
        probe = Path(tmpdir) / ("probe_%s.light" % mod.stem)
        probe.write_text(u"从 %s 导入 %s\n打印(\"IMPORT_OK\")\n" % (mod.stem, sym), encoding="utf-8")
        rc2, out2, err2 = run_cmd([sys.executable, str(RUNNER), str(probe)], LH, timeout)
        if rc2 == 0 and "IMPORT_OK" in out2:
            return "导入", rc2, out2, err2
        return "未覆盖", rc2 or 1, out2, (err2 or ("示例失败: " + err if exs else ""))
    return "未覆盖", 127, "", "模块无顶层可导入符号，无法构造探针"


def main():
    ap = argparse.ArgumentParser(description="北极星 Z · 零 LLM token 跑通率")
    ap.add_argument("--sample", type=int, default=64, help="抽样模块数；0=全量")
    ap.add_argument("--seed", type=int, default=20261004, help="抽样种子（写进口径）")
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--json", action="store_true", help="落盘 零token覆盖率报告.json")
    args = ap.parse_args()

    mods = list_modules()
    if not mods:
        print("错误: lightharness/src 下没有 .light 模块"); sys.exit(2)
    if args.sample and args.sample < len(mods):
        sampled = sorted(random.Random(args.seed).sample(mods, args.sample))
        sampling = "抽样 %d/%d（seed=%d）" % (len(sampled), len(mods), args.seed)
    else:
        sampled = mods
        sampling = "全量 %d/%d" % (len(sampled), len(mods))

    global EXAMPLE_GRAPH
    EXAMPLE_GRAPH = build_example_graph([m.stem for m in mods])

    tasks = [(m, top_symbol(m)) for m in sampled]
    tmpdir = tempfile.mkdtemp(prefix="lzprobe_")
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futs = {pool.submit(probe_module, m, s, tmpdir, args.timeout): m for m, s in tasks}
        done = 0
        for fut in concurrent.futures.as_completed(futs):
            m = futs[fut]
            try:
                level, rc, out, err = fut.result()
            except Exception as exc:  # 评测器自身缺陷不冒充语言问题
                level, rc, out, err = "未覆盖", 1, "", "评测器异常: %r" % (exc,)
            results.append({"module": m.stem, "level": level, "rc": rc,
                            "out_tail": out.strip()[-120:], "err_tail": err.strip()[-200:]})
            done += 1
            _eprint("[%3d/%3d] %-8s %s" % (done, len(tasks), level, m.stem))

    n = len(results)
    n_run = sum(1 for r in results if r["level"] == "跑通")
    n_imp = sum(1 for r in results if r["level"] == "导入")
    n_fail = n - n_run - n_imp
    z_run = n_run / n if n else 0.0
    z_floor = (n_run + n_imp) / n if n else 0.0
    fails = sorted((r for r in results if r["level"] == "未覆盖"),
                   key=lambda r: r["module"])
    imp_only = sorted((r for r in results if r["level"] == "导入"), key=lambda r: r["module"])

    print()
    print("=" * 62)
    print("北极星 Z · 零 LLM token 跑通率（lightharness/src 生产模块）")
    print("=" * 62)
    print("评测时间   :", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("口径       : Z = holdout 中可零 LLM token 跑通的模块比例（跑通级=真实示例 mock 实跑 rc=0）")
    print("holdout    :", sampling, "  seed=%d" % args.seed)
    print("分母       :", n, "（抽样模块数；全量 %d）" % len(mods))
    print("Z_跑通     : %.4f  （%d/%d）" % (z_run, n_run, n))
    print("Z_导入下限 : %.4f  （%d/%d，跑通+仅导入）" % (z_floor, n_run + n_imp, n))
    print("未覆盖     :", n_fail)
    if imp_only:
        print("仅导入级模块:", "、".join(r["module"] for r in imp_only[:20]) + ("…" if len(imp_only) > 20 else ""))
    if fails:
        print("-" * 62)
        print("未覆盖明细（含理由，如实记录）:")
        for r in fails:
            print("  %-24s rc=%s %s" % (r["module"], r["rc"], (r["err_tail"] or r["out_tail"])[:100]))
    print("说明       : 全程仅编译器编译+运行 mock 路径，不调用任何大模型 API；token 覆盖率旧口径已降为附录")

    if args.json:
        report = {
            "报告时间": datetime.datetime.now().isoformat(timespec="seconds"),
            "指标": "北极星 Z · 零 LLM token 跑通率",
            "口径": "Z = holdout 中可零 LLM token 跑通的模块比例；跑通级=真实示例 mock 实跑 rc=0；导入级=编译导入 rc=0",
            "holdout": sampling, "种子": args.seed,
            "分母_抽样模块数": n, "全量模块数": len(mods),
            "Z_跑通": z_run, "跑通数": n_run,
            "Z_导入下限": z_floor, "导入级数": n_imp, "未覆盖数": n_fail,
            "未覆盖明细": fails, "仅导入级": [r["module"] for r in imp_only],
            "说明": "屏障 D 验收口径 = Z_跑通；token 覆盖率（0.0638/附录）见 覆盖率报告.json",
        }
        io.open(str(REPORT), "w", encoding="utf-8", newline="").write(
            json.dumps(report, ensure_ascii=False, indent=2))
        print("已写:", REPORT)
    sys.exit(0)


if __name__ == "__main__":
    main()
