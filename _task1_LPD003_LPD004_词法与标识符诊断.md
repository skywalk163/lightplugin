# 路1 交付报告 · LP-D-003 + LP-D-004（词法 / 标识符诊断）

> 日期：2026-09-27 ｜ 改动仓库：`light-merge`（编译器）｜ lightplugin 仅作验证与绕法还原
> 基线：light-merge @c512a54c（7.0.0 工作树）

---

## 1. 缺陷根因

### LP-D-003（中文数字作标识符被当整数字面量）

两层根因，实测缺一不可：

1. **词法层**：未被「设」声明的中文数字（`六`）发成 `CHINESE_NUM(6)`，
   `六["级别"]` 静默编成 `6["级别"]`，编译期零提示，运行期才报英文
   `'int' object is not subscriptable` 且 SyntaxWarning 行号落在生成代码上。
2. **代码生成层（本次实测新发现，任务书未记录）**：legacy src 后端
   （`light run` / lightplugin 的生产路径）`code_generator.py` 的 Identifier
   分支把名字恰好是中文数字的标识符**无条件映射回数字字面量**——
   即使词法层已把声明过的 `六` 重分类为 IDENTIFIER，读取位仍被打回 `6`。
   unified 后端无此映射，**双后端行为分叉**。早期验证"声明过即可用"
   只在 unified 腿成立，生产路径一直是坏的。

### LP-D-004（保留字作变量名，诊断误导）

- `设 尝试 为 ...`：解析器设语句有「关键字作名」兼容分支（L-076 只挡了 `空`），
  把保留字静默收下，坑埋到后面。
- `尝试["次数"] 为 1`：语句分发把 `尝试` 认成 try 语句头，`_parse_try_stmt`
  死要冒号，报「期望 冒号「:」，但得到 左方括号」+「函数定义、条件、循环
  后面都需要冒号」——把人往完全错误方向带。

## 2. 修复点（全部在 light-merge）

| 文件 | 修复 |
|---|---|
| `src/lexer.py` | ① 新增 `_LPD_VALUE_TO_CN_NUMERAL` 反查表；② tokenize 出口新增 `_lpd003_check_cn_num_subscript`：`CHINESE_NUM` 后紧跟 `[`（跨 NEWLINE/INDENT 也算）→ 词法期报中文错误。声明过的中文数字走 IDENTIFIER 重分类，不进本分支 |
| `src/code_generator.py` | Identifier 分支的中文数字映射加**声明名豁免**：名字在 `_local_variables` / `_user_defined_functions` / 函数局部帧里时按名字发射，不再打回数字（未声明路径保留旧映射兜底，产物不变） |
| `src/keywords.py` | 新增 `RESERVED_NO_IDENTIFIER`（任务书 16 词，含语法角色）与 `reserved_word_identifier_error()`（诊断取表，不硬编码） |
| `src/parser_stmt.py` | `_parse_try_stmt` 消耗 `尝试` 后非 COLON → 直报保留字错误（try 头劫持形态的准确落点） |

**口径收窄（语料实况驱动）**：最初同时在 `设` 名字位拦截保留字，但全量测试
打红了存量合法用法——`设 尝试 为 0`（examples/harness/编排.light 重试计数、
lightharness/src/客户端.light、目标折叠.light）与 `设 类 为 节点[0]`
（stdlib/re.light:472）证明「关键字作名」兼容分支是承重的。故撤销 `设` 名字位
拦截，只保留 try 头守卫——误导性报错的真根因就是语句头被 try 劫持，此形态
拦准即修好缺陷，且不破坏任何存量程序（R13C 原生腿 17 用例复绿验证）。

## 3. 最小复现（修复前 → 修复后）

```
# LP-D-003：设 六 为 ["级别": 6]  +  打印 六["级别"]
#   修复前（生产路径）：运行期 'int' object is not subscriptable + SyntaxWarning
#   修复后：正常输出 6；未声明写 六["级别"] → 词法期：
#   「六」是中文数字（值 6），会被当成数字字面量，不可作标识符/下标名使用。
#    若要用它作变量名，请先声明：设 六 为 …（声明后会按标识符处理）；否则请改用非数字名称。

# LP-D-004：设 尝试 为 ["次数": 0]  +  尝试["次数"] 为 1
#   修复前：期望 冒号「:」，但得到 左方括号（+误导建议）
#   修复后（语句头下标目标处）：「尝试」是保留字（try 语句（异常捕获）），不可作标识符
#   （变量名/下标名）。请改用其他名称。常用保留字清单：从、全局、如果、导入、导出、尝试、
#   属性、当、抛出、捕获、段落、类、设、跳出、返回、遍历。
#   （`设 尝试 为 0` 标量计数器是存量合法用法，保持兼容不拦。）
```

固化位置：
- 编译器测试：`light-merge/tests/unit/test_lpd_003_中文数字标识符.py`（8 用例）、
  `tests/unit/test_lpd_004_保留字诊断.py`（6 用例）
- 探针副本：`lightplugin/_smoke/缺陷探针5_中文数字标识符.light`（运行 PASS）、
  `_smoke/缺陷探针6_保留字变量名.light`（运行报「保留字」= 预期形态）

## 4. 验证结果

| 项 | 结果 |
|---|---|
| 新增回归测试（2 文件 15 用例） | ✅ 15/15 绿（003 文件 8 用例 + 004 文件 7 用例） |
| light-merge 全量 pytest | ✅ 8175 passed / 15 failed，失败全部为**既有可选依赖环境红**（lunar_python 农历库 ×8、http 客户端依赖 ×2、antlr4 ×5），无断言失败、无解析错误，与本路改动无关 |
| 与本路直接相关的存量子集复跑 | ✅ test_lexer 系 88 passed + R13C 原生腿 18 passed（含曾被打红的 `设 类 为 节点[0]` 语料，口径收窄后复绿） |
| lightplugin 24 个插件测试 | ✅ 24/24 全绿 |
| 绕法还原（验收 4） | ✅ `插件/文档处理/测试_文档处理.light` 的 `最深` 改回 `六`（含下标读写），测试通过 |
| 双后端对齐 | ✅ legacy `PythonCodeGenerator` 与 unified `UnifiedCodeGenerator` 产物均正确发射 `六["级别"]` |

## 5. 反跑判据（改回修复 → 复现红）

1. 撤 `lexer.py::_lpd003_check_cn_num_subscript` →
   `test_未声明下标名_编译期中文报错` / `test_未声明下标名_不再漏到运行期` 变红（静默放行）。
2. 撤 `code_generator.py` Identifier 分支的声明名豁免（改回无条件映射）→
   `test_legacy后端_声明过可下标读`、`test_codegen_声明名豁免_反跑哨兵` 变红
   （`六` 读取位又变 `6`，探针5 运行期复现 int subscriptable）。
3. 撤 `_parse_try_stmt` 非 COLON 守卫 → `test_尝试当下标目标_报保留字不误导冒号` 变红
   （回到「期望冒号」误导）。

## 6. 数据集追加（工作流 A/B）

- **代码数据集**（`lightplugin/数据集/代码数据集.jsonl`）：追加 **LP-C-053 ~ LP-C-056**，共 **4 条**
  （003 正确写法 / 003 出错形态 / 004 出错形态 / 004 正确写法）。规模 52 → 56（本路贡献）。
- **报错队列**（`lightplugin/数据集/报错待归档.jsonl`）：追加 **2 条**知识对
  （中文数字 int subscriptable 双后端分叉排查路径；保留字冒号误导诊断经历）。
  队列 2 → 6（含路2 的 2 条）。收口路统一 `python lightplugin/归档.py err` 合并。

## 7. 备注

- light-merge 工作树同时有路3（parser_expr/code_generator 字符串区）、路4（module_resolver）
  的在途改动，全量 pytest 以合并态跑通为准；本路 hunk 与上述区域无交集。
- 本路未改 `lightplugin` 插件源码语义，仅按验收 4 做了一处绕法还原（改名回 `六`）。
