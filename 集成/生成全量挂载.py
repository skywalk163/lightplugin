# -*- coding: utf-8 -*-
"""生成 lightplugin 集成层：

1) 集成/全量挂载.light —— 一个程序里 `导入` 全部插件并逐个挂载，
   运行时证明 60 个插件可共存，并**检测工具名冲突**。
2) 集成/工具总表.json —— 静态抽取每个插件注册的工具名（给 lightharness 用的机器可读清单），
   同样带冲突检测。

用法：
    python lightplugin/集成/生成全量挂载.py          # 生成两个产物
    python lightplugin/集成/生成全量挂载.py --只生成清单
"""
from __future__ import print_function
import io
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))          # lightplugin/集成
ROOT = os.path.dirname(BASE)                                # lightplugin
PLUGINS = os.path.join(ROOT, "插件")
OUT_LIGHT = os.path.join(BASE, "全量挂载.light")
OUT_JSON = os.path.join(BASE, "工具总表.json")

# 抓取 造工具定义("名字"  中的名字；也兼容 造工具定义('名字'
TOOL_RE = re.compile(u'造工具定义\\(\\s*["\']([^"\']+)["\']')


def 插件清单():
    """返回 [(模块名, 目录名)]，按目录名排序。要求存在 <目录名>/<目录名>.light。"""
    out = []
    if not os.path.isdir(PLUGINS):
        return out
    for name in sorted(os.listdir(PLUGINS)):
        d = os.path.join(PLUGINS, name)
        if not os.path.isdir(d) or name.startswith(("_", ".")):
            continue
        impl = os.path.join(d, name + ".light")
        if not os.path.isfile(impl):
            continue
        out.append((name, d))
    return out


def 静态工具表(清单):
    """静态抽取每个插件注册的工具名（按 造工具定义 的第一个实参）。"""
    表 = {}
    for name, d in 清单:
        text = io.open(os.path.join(d, name + ".light"), encoding="utf-8",
                       errors="replace").read()
        tools = []
        for m in TOOL_RE.finditer(text):
            t = m.group(1)
            if t not in tools:          # 同一插件内去重
                tools.append(t)
        表[name] = tools
    return 表


def 查冲突(表):
    """工具名 -> [插件...]，只返回出现 >1 次的。"""
    归属 = {}
    for plugin, tools in 表.items():
        for t in tools:
            归属.setdefault(t, []).append(plugin)
    return dict((t, ps) for t, ps in 归属.items() if len(ps) > 1)


def 生成_light(清单):
    """生成一个把全部插件挂进**各自注册表**再汇总的程序（用于冲突检测 + 统一挂载）。"""
    L = []
    A = L.append
    A(u"# 全量挂载.light —— lightplugin 集成层（由 集成/生成全量挂载.py 生成，勿手改）")
    A(u"#")
    A(u"# 作用：在一个程序里导入并挂载全部插件，运行时证明它们可共存；")
    A(u"#       逐个插件单独挂载以**检测工具名冲突**（统一注册表按名覆盖会静默丢工具）。")
    A(u"#")
    A(u"# 运行：")
    A(u"#   python lightplugin/运行.py 集成/全量挂载.light")
    A(u"")
    A(u"从 工具 导入 工具注册表")
    A(u"从 内置核心字典 导入 字典键列表")
    A(u"")
    for name, _d in 清单:
        A(u"导入 " + name)
    A(u"")
    A(u"设 总表 为 []")        # 每项 ["插件":名, "工具":工具名]
    A(u"设 统计 为 {}")        # 插件 -> 工具数
    A(u"")
    A(u"段落 记插件(插件名, 注册表):")
    A(u"  设 键们 为 字典键列表(注册表.登记表)")
    A(u"  统计[插件名] 为 长(键们)")
    A(u"  遍历 名 之 键们:")
    A(u"    设 项 为 [\"插件\": 插件名, \"工具\": 名]")
    A(u"    总表.追加(项)")
    A(u"")
    A(u"# ---- 逐个插件单独挂载（隔离各自的注册表，才能发现同名覆盖）----")
    A(u"段落 逐插件挂载():")
    for name, _d in 清单:
        var = u"注" + name
        A(u"  设 " + var + u" 为 新建 工具注册表()")
        A(u"  " + name + u".挂载(" + var + u")")
        A(u"  记插件(\"" + name + u"\", " + var + u")")
    A(u"  返回 长(字典键列表(统计))")
    A(u"")
    A(u"# ---- 冲突检测：同一工具名被多个插件注册 ----")
    A(u"段落 冲突表():")
    A(u"  设 归属 为 {}")
    A(u"  遍历 项 之 总表:")
    A(u"    设 名 为 项[\"工具\"]")
    A(u"    如果 归属.包含(名) == 假:")
    A(u"      归属[名] 为 [项[\"插件\"]]")
    A(u"    否则:")
    A(u"      归属[名].追加(项[\"插件\"])")
    A(u"  返回 归属")
    A(u"")
    A(u"段落 报冲突():")
    A(u"  设 归属 为 冲突表()")
    A(u"  设 键们 为 字典键列表(归属)")
    A(u"  设 冲突数 为 0")
    A(u"  遍历 名 之 键们:")
    A(u"    如果 长(归属[名]) > 1:")
    A(u"      打印 \"[冲突] 工具名『\" + 名 + \"』被多个插件注册: \" + 连接字符串(归属[名], \", \")")
    A(u"      设 冲突数 为 冲突数 + 1")
    A(u"  返回 冲突数")
    A(u"")
    A(u"# ---- 统一挂载：全部插件挂进同一个注册表，得到模型可见的最终工具面 ----")
    A(u"段落 统一挂载():")
    A(u"  设 注册表 为 新建 工具注册表()")
    for name, _d in 清单:
        A(u"  " + name + u".挂载(注册表)")
    A(u"  返回 注册表")
    A(u"")
    # ---- 端到端执行冒烟：挑无需宿主注入的纯逻辑工具，真调用一次 ----
    # 说明：多数插件的执行体依赖注入式 executor（未注入时按设计软失败），
    #       这里只挑 5 个「不注入也能正确工作」的工具做执行级证明。
    A(u"# ---- 端到端执行冒烟：真正调用工具，证明挂进去的工具可执行 ----")
    A(u"段落 冒烟(注册表):")
    A(u"  设 通过 为 0")
    A(u"  设 失败 为 0")
    A(u"")
    A(u"  设 参1 为 [\"命令\": \"ls -la\", \"路径\": \"/tmp\", \"网址\": \"https://example.com\"]")
    A(u"  设 出1 为 注册表.登记表[\"风险判定\"][\"execute\"](参1)")
    A(u"  如果 出1[\"isError\"] == 假:")
    A(u"    设 通过 为 通过 + 1")
    A(u"  否则:")
    A(u"    设 失败 为 失败 + 1")
    A(u"    打印 \"[冒烟失败] 风险判定 -> \" + 出1[\"content\"]")
    A(u"")
    A(u"  设 参2 为 [\"值\": 42]")
    A(u"  设 出2 为 注册表.登记表[\"判定类型\"][\"execute\"](参2)")
    A(u"  如果 出2[\"isError\"] == 假:")
    A(u"    设 通过 为 通过 + 1")
    A(u"  否则:")
    A(u"    设 失败 为 失败 + 1")
    A(u"    打印 \"[冒烟失败] 判定类型 -> \" + 出2[\"content\"]")
    A(u"")
    A(u"  设 参3 为 [\"预算\": 100]")
    A(u"  设 出3 为 注册表.登记表[\"上下文装配\"][\"execute\"](参3)")
    A(u"  如果 出3[\"isError\"] == 假:")
    A(u"    设 通过 为 通过 + 1")
    A(u"  否则:")
    A(u"    设 失败 为 失败 + 1")
    A(u"    打印 \"[冒烟失败] 上下文装配 -> \" + 出3[\"content\"]")
    A(u"")
    A(u"  设 基 为 [\"甲\": 1, \"乙\": 2]")
    A(u"  设 覆盖 为 [\"乙\": 9, \"丙\": 3]")
    A(u"  设 参4 为 [\"基\": 基, \"覆盖\": 覆盖]")
    A(u"  设 出4 为 注册表.登记表[\"合并字典\"][\"execute\"](参4)")
    A(u"  如果 出4[\"isError\"] == 假:")
    A(u"    设 通过 为 通过 + 1")
    A(u"  否则:")
    A(u"    设 失败 为 失败 + 1")
    A(u"    打印 \"[冒烟失败] 合并字典 -> \" + 出4[\"content\"]")
    A(u"")
    A(u"  设 名单 为 [\"甲\", \"乙\", \"甲\", \"丙\"]")
    A(u"  设 参5 为 [\"列表\": 名单]")
    A(u"  设 出5 为 注册表.登记表[\"去重列表\"][\"execute\"](参5)")
    A(u"  如果 出5[\"isError\"] == 假:")
    A(u"    设 通过 为 通过 + 1")
    A(u"  否则:")
    A(u"    设 失败 为 失败 + 1")
    A(u"    打印 \"[冒烟失败] 去重列表 -> \" + 出5[\"content\"]")
    A(u"")
    A(u"  打印 \"端到端冒烟: 通过=\"")
    A(u"  打印 通过")
    A(u"  打印 \"端到端冒烟: 失败=\"")
    A(u"  打印 失败")
    A(u"  返回 失败")
    A(u"")
    A(u"段落 主:")
    A(u"  设 插件数 为 逐插件挂载()")
    A(u"  打印 \"插件数=\"")
    A(u"  打印 插件数")
    A(u"  设 工具总数 为 长(总表)")
    A(u"  打印 \"各插件注册工具总数（逐个挂载求和）=\"")
    A(u"  打印 工具总数")
    A(u"  设 冲突数 为 报冲突()")
    A(u"  打印 \"工具名冲突数=\"")
    A(u"  打印 冲突数")
    A(u"  设 注册表 为 统一挂载()")
    A(u"  设 最终键 为 字典键列表(注册表.登记表)")
    A(u"  打印 \"统一注册表最终工具数=\"")
    A(u"  打印 长(最终键)")
    A(u"  如果 长(最终键) < 工具总数:")
    A(u"    打印 \"[警告] 统一挂载后工具数少于求和 -> 存在同名覆盖，最终工具面已丢工具\"")
    A(u"  否则:")
    A(u"    打印 \"[ok] 统一挂载无同名覆盖\"")
    A(u"  设 冒烟失败 为 冒烟(注册表)")
    A(u"  如果 冒烟失败 == 0:")
    A(u"    打印 \"[ok] 端到端冒烟全通过\"")
    A(u"  否则:")
    A(u"    打印 \"[警告] 端到端冒烟有失败，见上方明细\"")
    A(u"  打印 \"集成冒烟结束\"")
    A(u"")
    A(u"主()")
    return u"\r\n".join(L) + u"\r\n"


def main():
    argv = sys.argv[1:]
    清单 = 插件清单()
    if not 清单:
        print("[err] 未找到插件目录内容：" + PLUGINS)
        return 1
    表 = 静态工具表(清单)
    冲突 = 查冲突(表)

    if "--只生成清单" not in argv:
        text = 生成_light(清单)
        io.open(OUT_LIGHT, "w", encoding="utf-8", newline="").write(text)
        print("[ok] 生成 %s（%d 个插件）" % (OUT_LIGHT, len(清单)))

    manifest = {
        "repo": "lightplugin",
        "generated_by": "lightplugin/集成/生成全量挂载.py",
        "plugin_count": len(清单),
        "plugins": dict((n, {"tools": 表.get(n, []),
                             "tool_count": len(表.get(n, []))}) for n, _d in 清单),
        "tool_name_conflicts": 冲突,
        "conflict_count": len(冲突),
        "total_tools_registered": sum(len(v) for v in 表.values()),
    }
    io.open(OUT_JSON, "w", encoding="utf-8", newline="").write(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print("[ok] 生成 %s：插件 %d 个，工具声明 %d 条，冲突 %d 组"
          % (OUT_JSON, len(清单), manifest["total_tools_registered"], len(冲突)))
    for t, ps in sorted(冲突.items()):
        print("    [冲突] %s <- %s" % (t, ", ".join(ps)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
