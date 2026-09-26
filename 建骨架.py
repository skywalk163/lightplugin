# -*- coding: utf-8 -*-
"""按 插件清单.json 生成/补齐插件目录骨架（幂等）。

用法：
    python lightplugin/建骨架.py            # 为清单里所有插件生成目录与任务卡
    python lightplugin/建骨架.py 文档处理   # 只处理指定插件

只生成**任务卡**（说明.md），不生成可被误当成成品的 .light 占位实现：
半成品的光明源码会污染代码数据集，也可能编译不过。实现由认领者按卡片逐项完成。
"""
import io
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
PLUGINS = os.path.join(BASE, "插件")
MANIFEST = os.path.join(BASE, "插件清单.json")

CARD = u"""# {name} · 复刻任务卡

- **对标 dsh**：`{dsh}`
- **能力**：{cap}
- **缺口核验**：{gap}
- **优先级**：{pri}　**批次**：第 {batch} 批　**状态**：{status}
- **依赖**：{dep}
- **挂接契约**：`造工具定义(名字, 描述, 参数, 执行函数, ...)` + `工具注册表`；需宿主服务时用 `绳构造注册` / `绳装配`

## 收口清单（缺任一不算完成）

- [ ] `{name}.light` 主实现，导出统一入口段落 `挂载`
- [ ] 经 `造工具定义` 注册到 `工具注册表`，可被模型看到
- [ ] `测试_{name}.light`：至少 1 条正例 + 1 条非法参数反例
- [ ] 本机跑通（注意三后端语义未完全对齐：転译腿 / unified / 原生 LLVM）
- [ ] 撞到的光明语言问题登记到 `../../语言缺陷反馈.md`
- [ ] 跑 `python ../../归档.py code` 与 `python ../../归档.py err`
- [ ] 回到 `../../插件清单.json` 把本插件状态置为 `done`
- [ ] 在本文件回填「已知缺口」（对不齐 dsh 的地方，如实写，不谎报对齐度）

## 边界：不要重复造轮子

以下能力 lightharness **已有**，本插件只做联动、不重实现：
待办 · 技能清单 · 网页搜索 · 计划模式 · 目标折叠 · 定时 · 重复提醒 · 反馈 ·
附件准入 · 交付 · 语言服务器 · 凭据 · 审批 · 预设 · 真实HTTP客户端 · 网络钩子GitHub ·
工具_读文件 / 写文件 / 搜索文件 / bash / 路径安全 · 文件系统工具 · 核心工具 · 宿主工具 ·
团队工具 · 查询工具 · 时间工具 · 推理工具 · 交互工具 · 值工具

## 红线

不放宽断言、不 skip 失败用例、不改光明源码来迁就本插件 —— 缺陷走 `语言缺陷反馈.md` 上报 A9 泳道。

---

## 复刻记录

_（实现过程中填写：挂接方式、踩到的坑、验证结果、已知缺口）_
"""


def main():
    targets = sys.argv[1:]
    if not os.path.isfile(MANIFEST):
        print("[err] 缺少 " + MANIFEST)
        return 1
    data = json.loads(io.open(MANIFEST, encoding="utf-8").read())
    made, existed = 0, 0
    for p in data.get("plugins", []):
        name = p["name"]
        if targets and name not in targets:
            continue
        d = os.path.join(PLUGINS, name)
        if os.path.isdir(d):
            existed += 1
        else:
            os.makedirs(d)
            made += 1
        card = os.path.join(d, "说明.md")
        body = CARD.format(
            name=name,
            dsh=p.get("dsh_package", "-"),
            cap=p.get("capability", "-"),
            gap=p.get("gap", "-"),
            pri=p.get("priority", "-"),
            batch=p.get("batch", "-"),
            status=p.get("status", "pending"),
            dep=u"、".join(p.get("depends", [])) or u"无",
        )
        io.open(card, "w", encoding="utf-8", newline="").write(body)
        print("[ok] " + os.path.relpath(card, BASE).replace("\\", "/"))
    print("[done] 新建 %d 个，已存在 %d 个" % (made, existed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
