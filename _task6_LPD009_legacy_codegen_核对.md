# 路6 交付报告 · LP-D-009 legacy 代码生成器 for 内提前 `返回` 核对

> 日期：2026-09-27 ｜ 仓库：`light-merge`（编译器）/ `lightplugin`（验证）
> 形式：**核对优先，不预设改代码** —— 结论为「已修复（疑于后续编译器轮次修复）」，未改动任何 `light-merge/src` 代码，仅补回归测试 + 数据集 + 缺陷账回填。
> 配套回归测试：`light-merge/tests/unit/test_lpd_009_legacy_codegen_for_early_return.py`（2 用例，全绿）

---

## 一、结论

**LP-D-009 在当前编译器（R98+，light-merge @`c512a54c`）已无法复现，按任务书口径销账为「已修复」。**

- 用最简变体（for 内函数调用作迭代源 / for 内提前 `返回` / for 内提前 `返回 空` / for 内嵌套 `段落`（闭包）提前 `返回`）构造纯光明模块，经 `_light_import_hook` 实际导入后，三个顶层 `段落` 全部进模块命名空间且可调用。
- 生成的 Python 源码中，三个 `def` 的缩进**全部为 `indent=0`**（模块级），不存在被前一函数体吞并的情况。
- 运行检视器插件（原始触发点）现 15 个顶层符号（含 `取差异`/`存基线`）全部 `indent=0`，导入正常。
- 因本路**未复现、未改代码**，lightplugin 侧零风险，12 插件测试门禁不受影响（见第四节）。

---

## 二、缺陷根因回顾（待核对项）

现象（原始报告）：在「运行检视器」复刻中 `从 运行检视器 导入 取差异` 报
`cannot import name '取差异'`（及 `name '存基线' is not defined`）。

推测机制：legacy 代码生成器（`_light_import_hook` 编译纯光明模块走此路径）在某 `段落` 的
`for` 体内有提前 `返回` 时，把后续顶层 `段落` 错误缩进嵌套进前一函数体（曾观察疑似 `nonlocal`
生成），导致这些函数不进模块命名空间。业务侧把 `取节点属性` 改写为「去掉 for 内提前 `返回` +
迭代源先赋临时变量」后导入恢复。

---

## 三、复现尝试记录（核对过程）

### 3.1 生成代码缩进核对（legacy `PythonCodeGenerator` 路径 = 钩子实际路径）

| 变体 | 结构 | 取节点属性 | 取差异 | 存基线 | 结论 |
|---|---|---|---|---|---|
| A 基本 | `遍历` + `如果` + 提前 `返回` | indent=0 | indent=0 | indent=0 | OK |
| B 闭包 | `遍历` 体内定义嵌套 `段落`（闭包）并提前 `返回`（「疑似 nonlocal」指向） | indent=0 | indent=0 | indent=0 | OK |
| C 嵌套遍历 | 两层 `遍历` + 内层提前 `返回` | indent=0 | indent=0 | indent=0 | OK |
| D for-range | `当` 循环 + 提前 `返回 空` | indent=0 | indent=0 | indent=0 | OK |
| E 闭包含 for | `段落` 内嵌套 `段落`，闭包内含 `遍历` + 提前 `返回` | indent=0 | indent=0 | indent=0 | OK |

→ **5 个变体全部 `indent=0`，均未复现吞并。**

### 3.2 端到端实际导入核对（经 `_light_import_hook`）

构造扁平纯光明模块 `lpd009_mod_N.light`（前一段落 for 体内提前 `返回`，后接两个顶层段落），
`install([临时目录])` → `importlib.import_module`：

```
import OK. names: ['取节点属性', '取差异', '存基线']
call 取差异('x') = x
call 存基线() = None
```

→ 两个后接段落均进模块命名空间、均可调用。

### 3.3 运行检视器（原始触发点）结构核对

编译 `lightplugin/插件/运行检视器/运行检视器.light` 经 legacy 生成器，核对文件末尾
`导出` 清单涉及的 15 个顶层符号（登记上下文/设属性/发布/观测数/取快照/取差异/存基线/
取与基线差异/导出/运行检视模式/运行检视处理/挂载/取节点属性/含于/查节点）——**全部 `indent=0`**，
未被吞并。

### 3.4 调试过程中踩到的「伪阳性」陷阱（已排除，非缺陷）

初次用 `importlib.import_module("运行检视器")` 验证时，模块返回为空、`hasattr` 全 False。
根因不是 LP-D-009，而是**导入解析路径问题**：插件以目录形式存在
（`插件/运行检视器/运行检视器.light`），`import 运行检视器` 被 Python PathFinder 解析成
`插件/运行检视器/` 这个**命名空间包（空目录）**，而非 `.light` 文件。真实 dsh 运行时由钩子在
`sys.meta_path` 前置拦截、按 `search_paths` 找 `<名>.light` 解析，与本缺陷无关。本核对改以
「生成代码缩进 + 导入扁平 `.light`」两种方式验证，避免该陷阱。该排查路径已沉淀为报错队列知识对。

---

## 四、验证结果

1. **回归测试**：`tests/unit/test_lpd_009_legacy_codegen_for_early_return.py`
   - `test_生成代码_后续顶层段落缩进为模块级` —— PASS（两变体，def 全部 indent=0）
   - `test_实际导入_后续段落进模块命名空间` —— PASS（扁平模块经钩子导入，两后接段落可取可调用）
   - 运行：`python -m pytest tests/unit/test_lpd_009_legacy_codegen_for_early_return.py -v -o "addopts="` → **2 passed**
2. **运行检视器导入正常**：15 顶层符号全部 indent=0（见 3.3）。
3. **lightplugin 12 插件测试门禁**：本路未改动 `light-merge/src` 任何代码（纯核对 + 测试），
   编译器产物语义不变，12 插件全绿基线不受任何影响；运行检视器原绕法（去 for 内提前返回）现可保留也可还原，均正确。

---

## 五、修复点

**无需修改代码。** 当前编译器（R98+，light-merge @`c512a54c`）已正确处理「顶层段落 for 体内提前返回」
场景，疑于后续编译器轮次（for/return/闭包 缩进与块栈处理相关）修复。本次仅：
- 新增回归测试守住不再回潮；
- 回填缺陷账、追加数据集（见第六节）。

---

## 六、反跑判据（守住不再回潮）

若有人让 legacy codegen 的「顶层段落缩进」未复位（例如把顶层 `段落` 的 `def` 多缩进一级，
模拟被前一段落吞并）：

- `test_生成代码_后续顶层段落缩进为模块级` 中 `_top_level_def_indents(py)` 对 `取差异`/`存基线`
  取到的 indent 将 `!= 0` → 断言 `ind.get(f) == 0` 失败 → 该用例**变红**，回到「被前一段落吞并」的复现态。
- `test_实际导入_后续段落进模块命名空间` 中 `hasattr(mod, "取差异")` 将失败 → 该用例变红。

两条用例共同构成 LP-D-009 的回归护栏。

---

## 七、数据集追加条数（数据集工作流）

- **代码数据集** `数据集/代码数据集.jsonl`：+1 条
  - `LP-C-063`：演示 for 内提前 `返回` 不再吞并后续顶层段落（完整可运行 `.light` 演示 + 回归测试 source/sha256）。
- **报错队列** `数据集/报错待归档.jsonl`：+1 条知识对
  - `cannot import name '取差异'` 的核对调试路径（现象→根因→调试关键→结论→教训，category=`codegen`，project=`light-merge`）。
  - 注：按任务书，队列由收口路（路M）统一 `python lightplugin/归档.py err` 合并进主数据集。

---

## 八、最小复现（已固化）

`light-merge/tests/unit/test_lpd_009_legacy_codegen_for_early_return.py` 内的
`_MODULE_SRC_BASIC` / `_MODULE_SRC_CLOSURE`：模拟经 `_light_import_hook` 导入的纯光明模块，
前一段落 `for` 体含提前 `返回`，后接两个顶层 `段落`，验证两者都进模块命名空间。

---

## 九、遗留 / 备注

- 原始触发代码（`取节点属性` 含 for 内提前 `返回` 的版本）在 git 前已被改写为绕法，无法取回做「回放复现」；
  本次以结构化变体（A~E）+ 运行检视器当前结构双重核对，结论稳健。
- 若后续确要在 legacy codegen 动「顶层段落缩进 / 闭包 nonlocal」相关逻辑，务必先跑本回归测试，防止 LP-D-009 回潮。
