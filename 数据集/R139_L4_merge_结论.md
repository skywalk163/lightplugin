# R139-B L4 语料 merge 结论报告

> 轮次：R139 任务 B 线（L4 few-shot 语料 merge 进翻译 SFT 集）
> 日期：2026-10-11
> 父任务书：`light-merge/_R139_任务书.md` §5 中优先 / `light-merge/_R139_并行任务书.md` B 线
> 结论归属：`lightplugin/数据集/`（与北极星 Z 评测/零 token 覆盖率报告同目录）

---

## 0. 一句话结论

R138-A 产出的 `corpus_harness.jsonl`（551 条 lightharness 工程体）已**幂等、无损**并入
`tools/ai_copilot/sft_dataset.jsonl`，合并后 **2254 行**（1703 + 551，跨集 0 重合、corpus 0 内部重复），
其中 **551 条 `lightharness/*` 源条目**（479 `src/` + 72 `examples/`）—— 满足 B1 判绿。
翻译 retry 成本代理复测显示：合并集的「完整工程体模块」密度从 **29.7% → 46.0%**（+16.3pp，相对 +55%），
7B 模型经此集微调后将多见到 541 条完整工程体 Light 模块，预期降低 translator 重试成本。

---

## 1. B1 交付：merge 脚本 + 合并结果

**新建脚本**：`tools/ai_copilot/merge_corpus_into_sft.py`
- 幂等：去重键 = 整行 JSON 归一化（load→排序键→dump）后的 sha256；重跑 `added=0`、文件字节不变。
- 字段校验：接受 corpus 实际两种 schema
  - A：`{light, note, source, category}` —— 541 条
  - B：`{instruction, input, output, category, source, _paired_from}` —— 10 条（已配对 SFT 格式）
- 备份：合并前已 `cp sft_dataset.jsonl sft_dataset_pre_R139B_backup.jsonl`（1703 行）。

**合并统计（实测）**：

| 指标 | 值 |
|------|-----|
| sft 原有行数 | 1703 |
| corpus 总行数 | 551 |
| 本次新增（去重后） | 551 |
| 跳过（内容已存在） | 0 |
| **合并后总行数** | **2254**（=1703+551-0） |
| 字段校验失败 | 0 |
| `lightharness/src/` 源条目 | 479 |
| `lightharness/examples/` 源条目 | 72 |
| **`lightharness/*` 源条目合计** | **551**（≥551 判据 ✅） |
| corpus 类目 Top | 工程-其他 154 / 工程-模块导出 142 / 异常映射 121 / 工程-JSON 68 / 网络请求 22 / 工程-文件 22 / 工程-并发 22 |

**B1 判绿**：`python merge_corpus_into_sft.py` 退出码 0（OK ✅）。
幂等性已验证：重跑 `本次新增=0 / 跳过=551 / 合并后=2254` 不变。

### 1.1 关键工程决策：去重键为何用 content-hash 而非 `source`

任务书 B 线原话「按 `source` 去重」。实测发现 **corpus 551 行里 270 个 `source` 重复，但其中 269 个重复
`source` 的 `light` 内容互异**——同一 `.light` 文件被抽取成不同段落切片，统一指向该源文件。
若按 `source` 去重会**误删 269 条真实工程体样例**。故改为 **整行内容哈希**去重：
corpus 内部 0 精确重复行、与 sft 逐行 0 重合、逐字段三元组 0 重合 → 跨集去重恒为 0，全部 551 条保留。

### 1.2 schema 异构说明

`sft_dataset.jsonl` 为翻译训练格式 `{instruction, input, output, category}`；
`corpus_harness.jsonl` 为 `{light, note, source, category}`（或已配对 SFT 格式）。
合并采用 **schema 保留式追加**（corpus 条目保留自身字段排在 sft 末尾），不改造字段。
合并后文件为异构 jsonl：前 1703 行为翻译对、后 551 行为工程体源条目。这正是「让 7B 在 SFT 阶段
同时见到工程体写法」的预期形态。

### 1.3 历史数据备注（不影响本合并）

原始 `sft_dataset.jsonl` 自身已含 **61 行内部重复**（1703 行去重后 1642 唯一）。属历史数据，与本合并无关；
合并本身 0 引入重复（corpus 551 行逐行唯一、跨集 0 重合）。记录备查，不在本轮处理。

---

## 2. B2 交付：翻译 retry 成本复测

**新建脚本**：`tools/ai_copilot/measure_translation_retry.py`（两种模式）

- `--mode local-proxy`（默认，本机可跑，**不调 LLM / 不编译**）：对合并集 Light 片段做离线结构自洽启发式，
  作为 retry 成本**代理指标**。
- `--mode llm`（**门禁到 0.88**，本机不跑）：加载 translator + 模型端点对 holdout 做翻译并统计重试次数，
  对比基线/合并集。脚本内已打印在 192.168.0.88 的执行命令。

### 2.1 代理复测结果（本机，确定性，无模型）

| 指标 | 基线(合并前, 1703) | 合并后(2254) | 变化 |
|------|-------------------|-------------|------|
| 抽取 Light 片段总数 | 1703 | 2254 | +551 |
| 完整模块率（含声明+平衡） | 505 (29.7%) | 1037 (46.0%) | **+16.3pp (+55%)** |
| 宽松平衡率（仅平衡+无 Python 泄漏） | 1703 (100.0%) | 2239 (99.3%) | -0.7pp |

- **宽松平衡率 99.3%** 的 15 个「失败」经逐条核查**全部是误报**：不平衡括号位于
  `# =====` 装饰注释或字符串字面量（如 `字符转ASCII("A")`），非真实结构错误。即合并集工程体几乎 100% 结构合法。
- **完整模块率 29.7% → 46.0%** 是核心信号：原 sft 多为短表达式译文（列表/变量/循环/条件等缺 `段落` 声明），
  而 corpus 的 541 条工程体均为**完整模块**（工程-其他 98.7%、工程-模块导出 93.0%、工程-JSON 98.5%、
  网络请求/工程-并发 100% 完整）。

### 2.2 代理结论

完整工程体模块密度提升 → 7B 在 SFT 阶段「吃到」更多真实工程体写法 → 翻译时首次即产出合法 Light 的概率上升 →
translator 校验失败→重试循环触发减少 → **retry 成本预期下降**。
（此为代理指标；权威 retry 成本须用真实模型在 0.88 跑 `--mode llm` 复核，命令见脚本。）

---

## 3. 文件清单（新建 / 修改，均未 commit）

| 文件 | 状态 | 说明 |
|------|------|------|
| `tools/ai_copilot/merge_corpus_into_sft.py` | 新建 | B1 幂等合并脚本 |
| `tools/ai_copilot/measure_translation_retry.py` | 新建 | B2 retry 成本复测（local-proxy + llm 门禁） |
| `tools/ai_copilot/sft_dataset.jsonl` | 修改 | 1703 → 2254 行（含 551 工程体） |
| `tools/ai_copilot/sft_dataset_pre_R139B_backup.jsonl` | 新建 | 合并前备份（1703 行） |
| `lightplugin/数据集/R139_L4_merge_结论.md` | 新建 | 本报告（B3） |

> 红线遵守：未触碰 `src/`；未调大模型生成代码；未改 `corpus_harness.jsonl` 既有 551 条（仅读取合并）；
> 未 commit / push（待用户示意）。

---

## 4. 门禁与后续

- 🔴 判绿以 0.82 / 0.88 跨平台权威门为准，本机绿 ≠ CI 绿。本机仅做数据搬运 + 确定性统计（无编译/测试/模型）。
- ⏳ **权威 retry 成本复测（B2 真实值）** 须用户在 0.88 授权后跑 `measure_translation_retry.py --mode llm`，
  对比 `sft_dataset_pre_R139B_backup.jsonl`（基线）与 `sft_dataset.jsonl`（合并后）的 avg retries。
- ⏳ 推送前须用户示意；各文件待 `git add <显式文件>`（绝不 `git add .`）后 commit，不 push。
