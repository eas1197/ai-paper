# 当前状态
唯一开发入口：`dev/v3.1-abstract-acquisition`。`main` 及 v005 注册表属于生产历史基线。读取 [运行索引](handoff_runs/manifest.json) 和 [技术接续](NEXT_TASKS.md)。

| 远端引用 | 审计时提交 | 与开发入口共同祖先 | 提交主题 |
| --- | --- | --- | --- |
| origin/backup/pre-glm-integration-20261122 | 231f9eb5ca01f25f9ca11085bc4695f6e725f9a4 | 231f9eb5ca01 | Separate academic and local revisions and add development API adapter |
| origin/dev/glm-api-adapter-20261122 | e91ef327daebe84ed0da14bad9a331ed400cb4b2 | 231f9eb5ca01 | feat: add bounded opt-in GLM API adapter and smoke test |
| origin/dev/v3.1-abstract-acquisition | 231f9eb5ca01f25f9ca11085bc4695f6e725f9a4 | 231f9eb5ca01 | Separate academic and local revisions and add development API adapter |
| origin/experiment/full-script-live-20261122 | 9a0292ba2a007be015c96748787dcc929f05d759 | 231f9eb5ca01 | Install missing bs4 and rerun exact registered literature entry point |
| origin/experiment/offline-smoke-20261122 | 08cf37701fdc7a0c1f2611e363e53cd4b7077477 | 231f9eb5ca01 | ci: test unreviewed metadata-only matrix correction against real archived evidence |
| origin/experiment/persistent-topic-20261122 | 6018913fe5d8723cf0dcf5c4d586084b8623b0eb | 231f9eb5ca01 | docs: clarify non-default branch workflow rerun trigger |
| origin/experiment/single-model-paper-20261122 | 01b287ba4dab4623d5b3a316424eaa877acd010c | 231f9eb5ca01 | docs: append final CI run, delivery validation and provenance to process audit |
| origin/main | 8971798289a424f8bd2c47f56735525e3f34d53e | 8971798289a4 | Revise v3.1 design for autonomous paper research and writing |
| origin/research-state/topic-20261122 | b2a860fff6ccfbd13041f1d7f7f862a02265b961 | 231f9eb5ca01 | checkpoint: bike_fresh_20261122 next-stage source records and hashes |

候选依赖为 v007 实验总控、v008 选题任务、v009 分阶段控制、04/v012 原生文献、11/v007 采集、06/v005 定性材料与矩阵、07/v015 写作方案。正式模块逐项查看 v005 注册表。共享单车按 plan_review_0 收尾。确认符合冻结设计的核心事件为零，保留未通过方案及探索矩阵。数字互助实验已落盘现实与双事件比较，停在独立反诘 CLI 创建失败。云端单模型稿、云端持久化、离线 smoke 和真实脚本试验分别保留在各自分支，未合并为正式能力。

## 2026-11-22 Chat 研究模式决定
本对话执行采用 ChatGPT 原生网页搜索，不再模拟本地 Codex CLI 检索，也不新增爬虫或为适配 Chat 改写既有学术阶段。规则见 HANDOFF 与 RUNBOOK。当前 `digital_mutual_aid_20261122` 的 `reality.json`、`event_comparison.json` 均保留，`staged_topic.json` 仍为 `explanation_exchange`；本次仅落实执行约定，尚未新增独立反诘凭证、未重跑搜索、未冻结新研究问题，现有学术门槛与预算未改变。Chat 后续新增实际搜索结果须以真实网页来源归档，不得以 CLI 事件冒充。

## 2026-11-22 Chat 自主研究完整流程演练（数字互助，非正式放行）
当前开发分支实际已超过旧表中 231f9eb5，最新以远端分支为准，勿把旧表当实时 HEAD。单模型 Chat 从 `digital_mutual_aid_20261122` 的有效 reality 和 event_comparison 接续，使用内置网页搜索开展完整研究角色演练，产物单独归档在 `handoff_runs/digital_mutual_aid_20261122/chat_native_20261122/`，清单索引 `handoff_runs/manifest.json`。新增5个文件：`文献检索矩阵.json`、`经验材料与分析矩阵.json`、`研究全过程日志.md`、`论文写作方案.md` 和 `Chat实验状态.json`。

实际：初查5篇+补查5篇有可追查摘要/全文页面，8篇符合候选核心九刊或可核验优秀专业刊范围、2篇仅专题辅助；另2篇郑州直近邻研究仅索引摘要，仍须核实正文。采访资料涉及两条可描述的组织障碍—调整序列及独立边界个案，但未取得外部核实的逐项执行结局；可完成探索矩阵和八章段落方案，不得写成已识别的因果机制。**当前独立反诘、最终学术审查和写作前材料适足性独立放行均缺真实调用，原始 `staged_topic.json` 仍为 `explanation_exchange`；此次所有多角色审查明确为同一模型演练。** 无 Codex CLI、无额外付费 API、无正文全文生成；运行工具用量与本对话的精确套餐Token未知。此项工作没有修改生产模块、学术预算或原始研究文件。

## 2026-11-23 写作连接实验：main V14 → dev V15（单模型、非正式G7）
本轮实际读取了 `main` 的 `07_三稿独立写作/v014_第14版/tools/stage07.py`、`模块说明.md`、`使用说明.md`、`templates/文字要求.md` 和 `templates/定量社会学论文逐段写作与语言规则.md`，并核对候选 `07/v015/tools/writing_plan.py` 的 `render()` 输入合同。原 main V14 的正式 G7 需旧 G4 100篇摘要和25篇核心全文、G5/G6冻结的正式定量研究结果，不能直接接收尚未独立审查的定性 Chat 资料；V15 当前只实现定性写作方案，不是定性正文起草器。

因此本次不改主程序与 main，不降低关卡，在 `handoff_runs/digital_mutual_aid_20261122/chat_native_20261122/writing/` 创建五项研究阶段产物：`写作任务V15输入.json`、`A稿_探索性正文.md`、`主张证据台账.json`、`写作自检.md`、`写作状态.json`。原8章论证计划的讨论并入结论，整理为V15七章14节任务，16个来源ID；D1—D3各含理论与经验材料。A稿在单模型探索范围约2172汉字（不含参考文献），12条关键主张逐字定位并绑定材料ID。输入已作字段/来源/维度覆盖JS静态核查，**没有实际执行V15 Python渲染器或V14 G7，也没有独立学术审查**。归档manifest目前共447项文件索引。原`staged_topic.json`检查点仍在`explanation_exchange`。
