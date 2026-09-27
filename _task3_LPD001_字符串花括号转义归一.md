# 路3 交付报告 —— LP-D-001 字符串花括号转义归一

> 批次：LP-D ｜ 路3 ｜ 日期：2026-09-27 ｜ 仓库：`light-merge`（编译器）

## 1. 缺陷根因

双引号字符串支持 `{变量}` 插值。要写字面花括号（CSS/JSON/模板）时，既有两种写法
`\{x\}` 与 `{{x}}` 只是被"不当成插值"，但**转义符没有归一**：

- 词法层 `lexer._tokenize_string` 把未识别转义 `\{` 原样留在 token value（反斜杠+花括号两字符）。
- 解析层 `_parse_string_interpolation` 把 `\{...\}` 当字面文本并入，却把前导反斜杠、
  内部 `\}` 反斜杠一起带进产物；`{{x}}` 因无法解析为表达式回退成普通 StringLiteral，
  双花括号原样保留。
- 结果：`"反斜杠转义 \{x\}"` 运行输出仍是 `反斜杠转义 \{x\}`，`"{{x}}"` 仍是 `{{x}}`。

## 2. 修复点

| 文件 | 改动 |
|---|---|
| `src/parser_expr.py` | 新增 `_lp_normalize_braces` / `_lp_restore_braces`：扫描插值前把 `\{` `\}` `{{` `}}` 换成不可见占位符（`\x01`/`\x02`），使字面花括号不被 `{…}` 正则误命中；扫描后在字面文本段还原为真花括号。无插值时回退的 `StringLiteral` 也做同样归一。 |
| `src/code_generator.py`（legacy） | StringInterpolation 字面量段在 f-string 产物里把 `{`→`{{`、`}`→`}}` 翻倍（此前缺这一步，与 unified 后端 `code_generator_unified.py:2881` 对齐）。 |

未动：`code_generator_unified.py`（本就翻倍）、LLVM 后端（字符串常量拼接，天然支持字面花括号）、
f-string `f"..."` 路径、legacy codegen 顶层段落缩进（路6 区域）。

## 3. 最小复现

出错版本（`_smoke/缺陷探针_LPD001_复现.light`）：
```light
段落 主:
  设 s 为 "body{color:red}"   # → name 'color' is not defined
  打印 s
主()
```
修复后正确写法（`_smoke/_lp001_verify.light`）：
```light
设 a 为 "反斜杠转义 \{x\}"     # → 反斜杠转义 {x}
设 b 为 "双写花括号 {{x}}"     # → 双写花括号 {x}
设 c 为 "你好 {名字}"          # → 你好 小明（插值不变）
设 e 为 "混合 {名字} 花括号\{literal\}"  # → 混合 小明 花括号{literal}
```

## 4. 验证结果

- `light-merge/tests/test_lpd_001_braces.py`：6 条全过（反斜杠/双花括号/闭花括号/插值不变/混合/CSS）。
- 既有相关测试 100 passed / 4 skipped（string/interpol/fstring 关键词集）。
- lightplugin：`测试_网页抓取` 把样本里 `body-color-red` 改回真实 CSS `body\{color:red\}`，测试全过（绕法可删）。
- 探针 `缺陷探针3/探针2` 重跑：转义产物归一、插值 `你好 小明` 不变。

## 5. 反跑判据

把 `parser_expr.py` 顶部的 `value = _lp_normalize_braces(value)` 与回退 `StringLiteral` 的归一调用
去掉、并把 `code_generator.py` f-string 字面量段的 `.replace('{','{{').replace('}','}}')` 去掉，
即回到旧行为：`"a\{x\}"` 输出 `a\{x\}`、`"{{x}}"` 输出 `{{x}}`，复现红。

## 6. 数据集追加

- 代码数据集：LP-C-049（修复后正确写法）、LP-C-050（出错复现）。
- 报错队列：CSS 花括号踩坑 1 条。
