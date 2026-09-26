# -*- coding: utf-8 -*-
"""lightplugin 归档工具：把复刻产物归档进两条数据集。

用法：
    python lightplugin/归档.py code    # 插件源码 -> 数据集/代码数据集.jsonl
    python lightplugin/归档.py err     # 报错队列 -> 光明×LightHarness_调试问题数据集.json
    python lightplugin/归档.py status  # 查看两条数据集当前规模

设计约束：
- **幂等**：按 (source, sha256) / (instruction+output 哈希) 去重，重复执行不产生重复样本。
- **可回溯**：每条样本都带 source 与 sha256。
- **字节哈希**：源码按原始字节算 sha256，避免编码/行尾差异造成假差异。
"""
import io
import json
import os
import hashlib
import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
PLUGINS = os.path.join(BASE, "插件")
DATASET = os.path.join(BASE, "数据集")
CODE_DS = os.path.join(DATASET, "代码数据集.jsonl")
ERR_QUEUE = os.path.join(DATASET, "报错待归档.jsonl")
ARCHIVED = os.path.join(DATASET, "已归档")
MANIFEST = os.path.join(BASE, "插件清单.json")
MAIN_ERR_DS = os.path.join(ROOT, "光明×LightHarness_调试问题数据集.json")


def _ensure_dirs():
    for d in (DATASET, ARCHIVED):
        if not os.path.isdir(d):
            os.makedirs(d)
    # 兜底创建空的数据集文件，方便直接追加
    for f in (CODE_DS, ERR_QUEUE):
        if not os.path.isfile(f):
            io.open(f, "w", encoding="utf-8").close()


def _read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def _read_text(path):
    return io.open(path, encoding="utf-8").read()


def _write_text(path, text):
    io.open(path, "w", encoding="utf-8", newline="").write(text)


def _load_manifest():
    """插件清单 -> {插件名: {...}}"""
    if not os.path.isfile(MANIFEST):
        return {}
    data = json.loads(_read_text(MANIFEST))
    return {p["name"]: p for p in data.get("plugins", [])}


def _read_jsonl(path):
    """逐行解析 JSONL；单行坏数据只跳过并告警，不拖垮整批归档。

    教训：队列里一条未转义引号就曾让 `归档.py err` 整体崩溃。
    追加型工具必须容忍局部坏数据，否则一条笔误会挡住其余样本入库。
    """
    if not os.path.isfile(path):
        return []
    out = []
    for n, line in enumerate(io.open(path, encoding="utf-8"), 1):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError as exc:
            print("[warn] 跳过第 %d 行坏 JSON（%s）；修正后重跑即可补归档" % (n, exc))
    return out


def cmd_code(dry_run=False):
    """扫描插件源码，增量追加到代码数据集。"""
    _ensure_dirs()
    mani = _load_manifest()
    existing = _read_jsonl(CODE_DS)
    # 去重键必须取 meta 下的 source/sha256（顶层取不到会让去重判据恒空 -> 重复追加）
    known = set()
    for r in existing:
        m = r.get("meta", {})
        if m.get("source") and m.get("sha256"):
            known.add((m["source"], m["sha256"]))

    new_records, skipped, missing = [], 0, []
    if not os.path.isdir(PLUGINS):
        print("[err] 插件目录不存在：%s" % PLUGINS)
        return 1

    for dirpath, _dirs, files in os.walk(PLUGINS):
        for fn in sorted(files):
            if not fn.endswith((".light", ".py")):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, BASE).replace("\\", "/")
            raw = _read_bytes(full)
            sha = hashlib.sha256(raw).hexdigest()
            if (rel, sha) in known:
                skipped += 1
                continue
            # 归属插件 = 插件/<名>/ 的第一层目录名
            parts = rel.split("/")
            plugin_name = parts[1] if len(parts) > 2 else "(未归类)"
            info = mani.get(plugin_name, {})
            if not info:
                missing.append(rel)
            role = "test" if fn.startswith("测试_") else ("doc" if fn.endswith(".md") else "impl")
            text = raw.decode("utf-8", errors="replace")
            lines = text.count("\n") + (0 if text.endswith("\n") or not text else 1)
            capability = info.get("capability", "")
            dsh_pkg = info.get("dsh_package", "")
            if role == "test":
                instruction = "用光明语言为「%s」插件编写测试：覆盖正例与非法参数反例。" % plugin_name
            else:
                instruction = "用光明语言实现「%s」插件：%s" % (plugin_name, capability or info.get("description", ""))
            new_records.append({
                "id": "LP-C-%03d" % (len(existing) + len(new_records) + 1),
                "instruction": instruction,
                "input": "对标 dsh 包：%s；挂接契约：造工具定义 / 绳装配；边界：%s"
                         % (dsh_pkg or "-", info.get("gap", "-")),
                "output": text,
                "meta": {
                    "plugin": plugin_name,
                    "lang": "light",
                    "role": role,
                    "source": rel,
                    "sha256": sha,
                    "lines": lines,
                    "priority": info.get("priority", ""),
                    "batch": info.get("batch", ""),
                    "dsh_package": dsh_pkg,
                    "tags": ["lightplugin", plugin_name, "dsh复刻"],
                },
            })

    print("[code] 已存在 %d 条，跳过未变更 %d 个文件，新增 %d 条"
          % (len(existing), skipped, len(new_records)))
    if missing:
        print("[warn] 以下文件未在 插件清单.json 登记（按目录名归类）：%s"
              % ", ".join(sorted(set(missing))[:6]))
    if new_records and not dry_run:
        with io.open(CODE_DS, "a", encoding="utf-8", newline="") as f:
            for r in new_records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print("[ok] 写入 %s -> %s" % (CODE_DS, len(new_records)))
    elif dry_run:
        print("[dry-run] 未落盘")
    return 0


def cmd_err(dry_run=False):
    """把 报错待归档.jsonl 合并进主报错数据集。"""
    _ensure_dirs()
    if not os.path.isfile(MAIN_ERR_DS):
        print("[err] 主数据集不存在：%s" % MAIN_ERR_DS)
        return 1
    queue = _read_jsonl(ERR_QUEUE)
    if not queue:
        print("[err] 队列为空：%s（复刻时遇到报错先往这里丢一行）" % ERR_QUEUE)
        return 0

    ds = json.loads(_read_text(MAIN_ERR_DS))
    samples = ds.get("samples", [])

    def _sig(s):
        return hashlib.sha256((s.get("instruction", "") + "||" + s.get("output", ""))
                              .encode("utf-8")).hexdigest()

    have = {_sig(s) for s in samples}
    # 下一个 LP 编号：跳过已存在的 LP-xxx
    n = 0
    for s in samples:
        sid = s.get("id", "")
        if sid.startswith("LP-"):
            try:
                n = max(n, int(sid.split("-")[1]))
            except (IndexError, ValueError):
                pass

    added, dup = 0, 0
    for q in queue:
        s = {
            "id": "LP-%03d" % (n + added + 1),
            "instruction": q.get("instruction", ""),
            "input": q.get("input", ""),
            "output": q.get("output", ""),
            "meta": {
                "category": q.get("category", "runtime_error"),
                "project": q.get("project", "lightharness"),
                "severity": q.get("severity", "major"),
                "tags": q.get("tags", ["lightplugin"]),
                "source": q.get("source", "lightplugin/数据集/报错待归档.jsonl"),
            },
        }
        if not s["instruction"] or not s["output"]:
            print("[warn] 跳过缺字段（instruction/output 必填）的队列条目")
            continue
        if _sig(s) in have:
            dup += 1
            continue
        samples.append(s)
        have.add(_sig(s))
        added += 1

    ds["samples"] = samples
    ds["count"] = len(samples)
    print("[err] 队列 %d 条 -> 新增 %d 条，去重 %d 条，数据集现共 %d 条"
          % (len(queue), added, dup, len(samples)))
    if added and not dry_run:
        _write_text(MAIN_ERR_DS, json.dumps(ds, ensure_ascii=False, indent=2))
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        dest = os.path.join(ARCHIVED, "报错队列-%s.jsonl" % stamp)
        os.replace(ERR_QUEUE, dest)
        io.open(ERR_QUEUE, "w", encoding="utf-8").close()
        print("[ok] 主数据集已更新；队列归档为 %s 并已清空" % dest)
    elif dry_run:
        print("[dry-run] 未落盘")
    return 0


def cmd_status(dry_run=False):
    _ensure_dirs()
    code_n = len(_read_jsonl(CODE_DS))
    q_n = len(_read_jsonl(ERR_QUEUE))
    print("== lightplugin 数据集现状 ==")
    print("代码数据集      : %d 条  %s" % (code_n, CODE_DS))
    print("报错待归档队列  : %d 条  %s" % (q_n, ERR_QUEUE))
    if os.path.isfile(MAIN_ERR_DS):
        ds = json.loads(_read_text(MAIN_ERR_DS))
        lp = [s for s in ds.get("samples", []) if s.get("id", "").startswith("LP-")]
        print("主报错数据集    : %d 条（其中 LP 系列 %d 条）  %s"
              % (ds.get("count", len(ds.get("samples", []))), len(lp), MAIN_ERR_DS))
    else:
        print("主报错数据集    : 不存在 %s" % MAIN_ERR_DS)
    return 0


def main():
    import sys
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    dry = "--dry-run" in sys.argv
    cmd = args[0] if args else "status"
    fn = {"code": cmd_code, "err": cmd_err, "status": cmd_status}.get(cmd)
    if fn is None:
        print(__doc__)
        return 2
    return fn(dry_run=dry)


if __name__ == "__main__":
    raise SystemExit(main())
