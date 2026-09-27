# lightplugin —— 光明插件仓库

用**光明语言**复刻 dsh（DeepSeek Harness）插件能力，供 lightharness 加载。

**当前状态：60/60 插件复刻完成**（24 个前置 + 第 7/8/9 批各 12 个），60 个测试文件全绿，全程未改一行 `light-merge/src/`。
**第 10 批（横向补深 + 集成）已完成**：6 个薄实现插件补深完毕，并新增 `集成/` 层验证 60 个插件可共存
——**100 个工具、工具名冲突 0 组、统一挂载 100/100、端到端冒烟 5/5**。

数据集：代码数据集 150 条；主报错数据集 67 条（其中 LP 系列 26 条）。

## 仓库与远端

本目录是**独立 git 仓**（不是 monorepo 子仓），分支 `main`，三个远端同步：

| 远端 | 地址 |
|---|---|
| gitea | http://192.168.1.5:3000/skywalk/lightplugin.git |
| github | https://github.com/skywalk163/lightplugin.git |
| gitcode | https://gitcode.com/skywalk163/lightplugin.git |

```bash
git push gitea main && git push github main && git push gitcode main
```

## 为什么是"复刻"而不是"直接用"

dsh 插件是 TypeScript 模块，挂真 Cordis 容器、跑在 Node 22+ 上；lightharness 是光明实现，
跑的是光明编译产物，容器也是重写的（`lightharness/src/toolcordis.light`）。
**语言 / 运行时 / 宿主服务三道墙**，所以 dsh 的 `.ts` 插件搬不过来。

本目录做的事：**用光明重写插件逻辑，挂到 lightharness 自己的工具注册表**。

## 关键文件

| 文件 | 用途 |
|---|---|
| `复刻计划.md` | 主计划：12 个插件的选择依据、复刻规范、反馈与数据集机制、分批节奏 |
| `插件清单.json` | 60 个插件的机器可读登记表（状态、优先级、对标包） |
| `语言缺陷反馈.md` | 复刻中撞到的光明语言缺陷 → 移交光明团队 A9 泳道 |
| `归档.py` | 一键归档：插件代码 → 代码数据集；报错 → 报错数据集 |
| `数据集/` | `代码数据集.jsonl`（代码微调）+ `报错待归档.jsonl`（报错暂存队列） |
| `插件/<名>/` | 各插件源码：`<名>.light` + `说明.md` + `测试_<名>.light` |
| `集成/生成全量挂载.py` | 扫描全部插件，**静态抽取工具名、检测重名冲突**，生成统一挂载脚本与工具总表 |
| `集成/全量挂载.light` | 生成物（勿手改）：逐插件隔离挂载 + 统一挂载 + 端到端冒烟 |
| `集成/工具总表.json` | 生成物：每插件注册的工具清单 + 冲突表 + 注册总数 |

## 复刻一个插件的标准动作

```bash
# 1. 建骨架（可用 归档.py 的模板目录）
#    插件/<名>/<名>.light   主实现，导出统一入口段落 `挂载`
#    插件/<名>/说明.md      对标包 / 参数 / 边界
#    插件/<名>/测试_<名>.light  正例 + 反例

# 2. 撞到光明报错 → 当场丢一行到数据集/报错待归档.jsonl
# 3. 落成后归档（幂等，可重复执行）
python lightplugin/归档.py code          # 代码 → 数据集/代码数据集.jsonl
python lightplugin/归档.py err           # 报错 → 主_dataset 光明×LightHarness_调试问题数据集.json

# 4. 更新 插件清单.json 状态为 done

# 5. 集成层回归（增删插件 / 改工具名后必跑）
python light-merge/.venv/Scripts/python.exe lightplugin/集成/生成全量挂载.py
python light-merge/.venv/Scripts/python.exe lightplugin/运行.py 集成/全量挂载.light
#   判据：工具名冲突数 == 0 且 统一注册表最终工具数 == 各插件注册工具总数
```

## 挂接契约（实读 `lightharness/src/工具.light`、`toolcordis.light` 得出）

```light
段落 造工具定义(名字, 描述, 参数, 执行函数, 策略="exclusive", 准备=空, 收尾=空)
段落 造工具模式(名字, 描述, 参数)
段落 造工具结果(内容, 是否错误, 结论=假)
类  工具注册表
段落 绳构造注册(id, 描述, 方法, 输入字段, 输入模式, 输出模式)
段落 绳装配(宿主钩子)
```

## 红线

不放宽断言、不 skip 失败用例、不改光明源码来迁就插件 —— 缺陷走 `语言缺陷反馈.md` 上报。
