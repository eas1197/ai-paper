# 运行手册

## 当前开发候选的操作顺序

在开发分支仓库根目录运行（Python 3.11+，Windows/其他平台用相同参数；路径有空格时加引号）。下文 `<CLI>` 代表 `python "00_项目控制/v012_第12版/tools/ai_paper5_strict.py"`，尖括号是占位符而非可直接运行字符。

| 意图 | 实际 strict 命令 |
|---|---|
| 只读发现与静态合同 | `<CLI> commands`；`<CLI> doctor`；`<CLI> <子命令> --help` |
| 真实本地登录诊断（另需授权） | `<CLI> doctor --probe-executor`，仅登录状态，不核验实时搜索 |
| 创建全新实验（不得覆盖已有run） | `<CLI> init --run-id <新ID> --theme <主题>` |
| 原检查点、任务及运行摘要 | `<CLI> status --run-id <ID>`；`<CLI> prepare --run-id <ID>`；`<CLI> run-summary --run-id <ID>`（导出已有观察，不重跑） |
| 真实原推进/有限步调度 | `<CLI> advance --run-id <ID>`；`<CLI> autopilot --run-id <ID> --max-steps <次数>`（原预算仍生效） |
| 原报告及真实事件 | `<CLI> reality/exchange/issue/review --run-id <ID> --report <报告>`（选其中实际子命令）；`<CLI> event-compare --run-id <ID> --report <报告> --events-jsonl <原事件>` |
| 同一文献任务 | `<CLI> chat-task --run-id <ID> --phase initial --output <新任务JSON>` 或 `codex-task`；补查时 phase=supplemental |
| 审计/接收与合并 | `<CLI> chat-audit --task <任务JSON> --response <响应JSON> --output <新审计JSON>`；`<CLI> literature-receive --run-id <ID> --task <选定任务JSON> --result <run内包路径> --execution-binding <真实绑定JSON> --output <新审计JSON>`；Chat实际动作另供 `--observed-actions`；各宿主专用 chat-receive/codex-receive 与 merge-results 参数以 commands/help 为准 |
| 审查等待与观察计数 | `<CLI> review-task --run-id <ID> --output <新任务JSON>`；`<CLI> review-counts --run-id <ID>`；候选准备并非实际独立派发 |
| 明确用户等待/恢复/停止 | `<CLI> advance --run-id <ID> --wait-for-user materials`（也可question/budget）；`--user-decision-file <真实决定JSON>`；`--cancel <原因>` 三者互斥 |
| 定性材料及分析候选 | `<CLI> materials --run-id <ID> --task-output <新任务JSON>`（可选 `--analysis-kind framework/matrix`）；已核验原材料报告通过相应conversion/review/matrix等参数接收 |
| 定性方案及V16 | `<CLI> resume-writing --run-id <ID> --attempt attempt_001`；`<CLI> writer4 --action route/prepare/submit --packet <已复核V15包>`（实际选一action，prepare/submit按help给workspace及稿件/主张） |
| 定量候选 | `<CLI> quantitative-plan --run-id <ID> --input <原同run输入> --output <新计划JSON>`；只准备原06/v004 plan，不运行Stata或正式分析 |

输出候选若位于运行目录内，必须用选定run的 `cli_outputs` 下新文件；不覆盖原状态或原门禁产物。C04任务快照、原输入、来源、回执与预算不一致时停止。接收/合并输出不自动授予学术通过，真实独立审查尚需原执行者与可信回执。恢复已有run先核身份、原快照与实际失败类型，不盲目调用autopilot或新建同名run；失败重试遵循原预算与I15保护。

### 离线验收

```sh
python -m unittest discover -s "00_项目控制/v012_第12版/tests" -v
python -m unittest discover -s "00_项目控制/v009_第9版/tests" -v
python -m unittest discover -s "06_数据方法与分析/v005_第5版/tests" -v
python -m unittest discover -s "07_三稿独立写作/v015_第15版/tests" -v
python -m unittest discover -s "07_三稿独立写作/v016_第16版/tests" -v
python -m unittest discover -s ".github/scripts" -p "test_archive_provenance.py"
python .github/scripts/verify_handoff.py
```

完整严格回归以 `.github/workflows/ai-paper5-strict-v3.yml` 实际配置为准（若文件名变更，以Actions中 ai-paper strict v3 regression 为准），发布前执行I21候选文件检查。实际运行工具记录与CI结论分列，不能以静态 doctor、离线mock或归档回放冒充真实宿主验收。

**5.0 唯一用户入口（开发分支候选）：** `python "00_项目控制/v012_第12版/tools/ai_paper5_strict.py"`，先执行 `doctor` 或 `--help`。原 v009/06/07 是受控业务模块，autopilot_v3.py 是内部调度实现；v010/v011 只保留为历史实验，不用于新研究或接续正式候选。当前完整自动运行与真实独立学术验收尚未通过。见 [命令索引](00_项目控制/v012_第12版/outputs/E01_唯一用户入口与命令索引.md)。
以下旧运行说明补充：Python 3.11。离线运行 `python .github/scripts/verify_handoff.py`，以及 `python -m unittest discover -s "00_项目控制/v009_第9版/tests"`。06/v005、07/v015 同样使用 unittest discover。离线工作流安装 beautifulsoup4，实际研究入口的其他依赖按模块说明。Actions 仅测试与回放，产物保留 14 天。长期制品放 handoff_runs。
本地恢复前核对运行 ID、注册表、输入和回执哈希。从 v012 strict 的 status/advance 接续；原 staged_topic.py 的 prepare/advance/status、06/v005 qual_materials.py、resume_writing.py 是受控内部业务模块。需要实际网页调用时依赖已授权 Codex CLI、订阅、网络及本地配置；定量使用相应数据和 Stata 等所需工具。归档中脱敏条目不能直接替换原始凭证，严格校验需要在合法保有原件的环境按原路径恢复。Actions 不继承本地登录、Windows 工具和个案数据。

历史数字互助恢复（非当前开发任务）读取 handoff_runs/digital_mutual_aid_20261122。真实试跑的子会话启动异常属工具限制，提交独立反诘必须使用真实可执行会话及原有研究包。脱敏归档仅可读取和回放，直接恢复需要受控环境中的原凭证。

## Chat 会话实际研究运行（不调用 CLI 搜索器）
1. 从 `CURRENT_STATE.md`、`handoff_runs/manifest.json` 和现有 run 检查点恢复，先读该阶段规范、冻结的数量/纳入规则、`search_policy.json` 和 run `workload`。不可把历史试跑重算为本次新检索。
2. 需要新联网证据时，在本对话调用 ChatGPT 内置网页搜索，自主决定对象、议题、理论三层检索及交叉核实。严格区分查得题录、打开摘要、阅读全文、二手访谈及事实核验；未知项保持未知。
3. 真实结果按已有数据结构的可复用字段记录，附 `chat_native_web` 来源说明、原始 URL、日期、定位、片段与边界、去重关系和实际搜索动作/阶段预算。程序特有的 CLI 事件字段不予伪造。实验模式、返修次数、材料适足性及学术失败分流仍然生效。
4. 本对话不能以同一上下文自审代替独立反诘或独立学术审查；若缺独立执行凭证，保留运行状态与待办并标记工具能力限制，不触发后续正式关卡。新增成果只追加归档，更新 manifest 与根交接；归档原始已核查来源，测试与科研质量验收分别标记。
5. Chat 模式不意味着 GitHub Actions 可以直接调用本聊天搜索。后续原 CLI 运行及其形式化接收器继续适用自身原生凭证校验；没有真实对应凭证的 Chat 成果需保持待衔接状态。

## 原写作模块接口（内部/历史调用记录）
原内部实现 `07_三稿独立写作/v016_第16版/tools/ai_writer4.py`（用户统一走 v012 writer4 --action），完整说明见模块说明。以V15写作任务JSON为输入，执行 `route --packet 文件`、`prepare --packet 文件 --workspace 新空目录 --mode exploratory`、`submit --packet 文件 --workspace 同目录 --manuscript 正文.md --claims 主张证据台账.json`。本次用户现有示例位于 `handoff_runs/digital_mutual_aid_20261122/chat_native_20261122/writing/`。离线测试 `python -m unittest discover -s '07_三稿独立写作/v016_第16版/tests' -v`，无模型调用；GitHub Actions `.github/workflows/ai-writer4-offline.yml` 只进行离线检查。两个来源都要保留原始哈希及现有审查状态；源码提交不等于自动起草与正式G7运行。本聊天写作仅作探索性A稿和样本语言修订，不接管原研究冻结检查点。

历史实验中 ai-writer 4.0 曾通过实验总控显式入口 `run_mode.py --mode dev --run-id <有效实验> --writer4 route|prepare|submit <对应参数>` 调用。该添加仅针对定性writer4试验，其他`--topic`、`--writing-plan`、定量及formal逻辑保持原样。真实实验运行目录不得用脱敏GitHub归档冒名替换。

## 历史 v010 实验操作与回放（不作为现行入口）
历史实验曾从`00_项目控制/v010_第10版/模块说明.md`开始，调用`tools/ai_paper5.py init --work <新实验目录> --run-id <id>`，依14个固定阶段`ingest --stage <阶段> --input <真实研究记录.json>`，`status --work`校验全部阶段文件及哈希。由ChatGPT内置联网工具检索并在真实输入记录来源；Python不得冒充网页调用。完成定性写作包并取得实际文稿后，`writer-prepare`/`writer-submit`会调用真正V16写作接口（必须在全仓库环境）。2026-11-23历史实验本地5/5单测通过、运行真实记录14/14；**完整仓库上的V16调用与GitHub Actions成功尚未确认**。正式学术审查仍是not_passed，不得以内部自审代替。代码只提交开发分支，main保持不变。

## 历史单 AI 启动记录（v011，不作为当前入口）
历史实验曾用 00/v011/tools/ai_paper5_auto.py doctor 检查环境，然后 run --work <不存在的新实验目录> --run-id <唯一ID>。重新运行同一条命令只接续未冻结阶段；自动检索走 Codex CLI --search，不会调用 ChatGPT 当前会话的网页工具。详情见 00/v011/模块说明.md。未认证实跑不算全流程验收。

## 当前唯一用户入口：严格3.x兼容 v012
python 00_项目控制/v012_第12版/tools/ai_paper5_strict.py doctor；后续init/status/advance路由原00/v009，Chat用chat-task/chat-audit按九刊、三层定位、真实摘要规范生成候选。无独立来源回执或学术审查时应保留待核，不能冒充原CLI搜索验收。
