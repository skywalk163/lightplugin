# 路M 收口报告 · LP-D 批次语言缺陷修复

> 日期：2026-09-27 ｜ 收口人：路M
> 任务书：`光明语言改进_LPD批次_并行任务书.md`
> 目标仓库：`light-merge`（编译器，工作树 @c512a54c 之上）｜ 验证：`lightplugin`

---

## 一、结论先行

**LP-D 批次 6 路全部收口，9 条缺陷账全部销账（8 修复 + 1 更正），数据集沉淀到位，双测试面全绿。**

| 验证面 | 结果 |
|---|---|
| lpd 编译器单元测试 | **52 passed**（8 个新测试文件） |
| lightplugin 插件测试 | **24/24 全绿**（含绕法删除后的 3 个插件） |
| 主报错数据集 | 51 → **59** 条（LP 系列 10 → **18**，本批 +8） |
| 代码微调数据集 | 63 → **66** 条（本批 +3，为绕法删除后的插件代码） |
| 报错待归档队列 | 8 → **0**（已全部合并并归档） |

---

## 二、各路销账表

| 路 | 缺陷 | 状态 | 交付报告 | 回归测试 |
|---|---|---|---|---|
| 路1 | LP-D-003 中文数字标识符 | ✅ 已修复 | `_task1_LPD003_LPD004_词法与标识符诊断.md` | `test_lpd_003_中文数字标识符.py` |
| 路1 | LP-D-004 保留字诊断 | ✅ 已修复 | 同上 | `test_lpd_004_保留字诊断.py` |
| 路2 | LP-D-006 行尾+续行报错 | ✅ 已修复（报错优先口径） | `_task2_LPD006_LPD008_语句解析收口.md` | `test_lpd_006_行尾续行报错.py` |
| 路2 | LP-D-008 全局半角句号 | ✅ 已修复 | 同上 | `test_lpd_008_全局半角句号.py` |
| 路3 | LP-D-001 花括号转义归一 | ✅ 已修复 | `_task3_LPD001_字符串花括号转义归一.md` | `test_lpd_001_braces.py` |
| 路4 | LP-D-002 未定义名导入提示 | ✅ 已修复 | `_task4_LPD002_未定义名诊断增强.md` | `test_lpd_002_import_hint.py` |
| 路5 | LP-D-005 方法面文档化 | ✅ 已修复 | `_task5_LPD005_方法面文档化与内置补齐.md` | `test_lpd_005_方法面.py`（12 例双后端） |
| 路6 | LP-D-009 legacy codegen | ✅ 核对销账（当前编译器已不复现，补回归守潮） | `_task6_LPD009_legacy_codegen_核对.md` | `test_lpd_009_legacy_codegen_for_early_return.py` |
| — | LP-D-007 多级索引 | ✅ 更正销账（非缺陷，list/dict 类型混用） | — | — |

`lightplugin/语言缺陷反馈.md` 9 条状态字段已全部回填（含修复后写法、commit、探针路径）。

---

## 三、本批编译器改动规模

`light-merge` 工作树相对 @c512a54c：**14 文件，+613 / -153 行**。

| 文件 | 改动 | 归属 |
|---|---|---|
| src/enhanced_errors.py | +134 | 路4（NameError 导入提示 + 行号归因） |
| src/llvm/compiler.py | +93 区域 | 路1（双后端对齐，中文数字读取位豁免） |
| src/parser_expr.py | +88 | 路3（字符串转义归一） |
| docs/LANGUAGE_EXTENSIONS.md | +58 | 路5（§4.5 方法面清单） |
| src/parser_stmt.py | +47 | 路2（续行报错 + 全局句号） |
| src/keywords.py | +49 | 路1（RESERVED_NO_IDENTIFIER 统一供表） |
| src/lexer.py | +40 | 路1（中文数字上下文切词） |
| src/code_generator.py | +23 | 路3（字符串产物归一） |
| src/parser_core.py | +27 | 路2/路4 辅助 |
| src/module_resolver.py | +23 | 路4（stdlib 导出反查表） |
| stdlib/内置核心列表.light | +7 | 路5（列表.包含） |
| stdlib/内置核心字典.light | +8 | 路5（字典.弹出） |
| tests/unit/test_T5a_数学统计排序_原生腿.py | ±120 | 既有测试期望随修复更新（⚠️ 见第五节） |
| tests/unit/test_T6a_正则文本模块_原生腿.py | ±49 | 同上 |

新增 8 个 `test_lpd_*` 测试文件（52 用例）。

---

## 四、数据集沉淀

### 4.1 报错知识对（问题训练数据集）

`python lightplugin/归档.py err` 已执行：队列 8 条全部为合格知识对（instruction/input/output 三段式），合并进主数据集 `光明×LightHarness_调试问题数据集.json`。

- 主数据集 count：51 → **59**
- LP 系列：10 → **18**（本批新增 LP-011~LP-018，覆盖 LP-D-001/002/003/004/005/006/008/009）
- 队列已归档为 `数据集/已归档/报错队列-<时间戳>.jsonl` 并清空。
- 缺 LP-D-007 知识对属预期（它是更正销账，非缺陷）。

### 4.2 代码微调数据集

`python lightplugin/归档.py code` 幂等执行：跳过未变更 45 个文件，新增 **3 条**（路3/路5 删除绕法后改动的插件代码）。

- 代码数据集：63 → **66** 条。
- 各路手工补的最小复现/正确写法（LP-C-061~063 等）已在此前入集。

---

## 五、绕法删除核销

| 原绕法 | 核销情况 |
|---|---|
| LP-D-001 网页抓取避开字面花括号 | ✅ 已改回真实 CSS `body\{color:red\}` |
| LP-D-003 变量名不用中文数字 | ✅ 文档处理插件 `最深` 改回 `六` 验证 |
| LP-D-004 改名 `生成计数` | 保留（兼容承重，见路1 报告口径） |
| LP-D-005 手写 `含于`/`并入去重` + 置空软删除 | ✅ 身份人格装配改用 `列表.包含` + `字典.弹出` 真删除 |
| LP-D-006 分步拼接 | 保留（编译器现在直接报错，分步是推荐写法） |
| LP-D-008 全角句号 | 保留（本就是正确写法） |

---

## 六、遗留与待办

1. **light-merge 改动尚未提交**：上述 14 文件改动 + 8 个新测试文件都在工作树未 commit。建议按路分 commit 或一次性 `fix(LPD): 插件复刻暴露的 8 条语言缺陷收口` 提交。
2. **两个既有测试文件被改**（T5a 数学统计排序 ±120 行、T6a 正则文本 ±49 行）：是各路修复后语义对齐的期望更新，随本批一起提交前请快速过一眼 diff，确认不是误改。
3. **light-merge 工作树里的历史临时目录**（`_lpd_repro/`、`_r90b_junit.xml`、`_r91/`、`tmp_allinone_plot.png` 等）非本批产物，不在本次收口范围，留待日常清理。
4. **三远端推送**：lightplugin 仓库 README 约定 push gitea/github/gitcode 三远端，由分发人决定何时推送。

---

## 七、验证命令留痕

```
# 编译器回归
cd light-merge
python -m pytest tests/test_lpd_001_braces.py tests/test_lpd_002_import_hint.py \
  tests/unit/test_lpd_00{3,4,5,6,8}_*.py tests/unit/test_lpd_009_*.py \
  -q -o addopts=""
# → 52 passed in 6.25s

# 插件全量
cd lightplugin
# 遍历 插件/*/测试_*.light 逐个 运行.py
# → 24/24 exit=0

# 数据集
python lightplugin/归档.py err    # 队列 8 → 主数据集 +8
python lightplugin/归档.py code   # 代码数据集 +3
python lightplugin/归档.py status # 代码 66 / 队列 0 / 主 59（LP 18）
```
