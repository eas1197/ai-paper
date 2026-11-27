# 6.0 定性实跑接续记录

日期：2026-11-27（Asia/Shanghai）  
基线：`d758cf22771a34c1ff37eb5c6a6139a1522366ea`  
需求：恢复 `backup_3x_live_01`，沿原 3.x 独立审查机制接通 main V14；不重选题，不启用 Stata。

## 第 1 项：恢复完整 S08（阻塞，未验收）

已检查远端全部十个分支的文件树和当前工作区历史运行目录。目标运行仅在 6.0 分支 `docs/v6.0/backup_3x_live_01` 有五份公开归档 JSON，未发现完整运行目录。已存在的其他研究运行不能替代本研究。

已验证两份文件原始 SHA-256 与归档中的绑定一致：

- `s08_topic.json`：`5e3684ab606a8188f3b772d03325fba3f40641b0fa1d18958c682d80c3cb70c2`
- `material_receipt.json`：`b20cfc2462a914db77541f5b2eb997d4d905aa0383cd180d4d066e870060039c`

归档研究为美国雇主返岗规则中居家办公例外的审批权限与适用条件比较，`online_qualitative/public_text`，实验级，`formal_eligible=false`。历史核验结论保留，不视为本轮重新重放成功。

`07_三稿独立写作/v014_第14版/tools/s08_inputs07.py:frozen_source` 要求完整 `staged_topic.json`（含独立终审 invocation）、`merged_literature.json`、`initial/theories.json`、`reality.json`、`event_comparison.json`、`explanation_exchange.json`、`issue_plan.json`、`run_manifest.json`，以及 `qualitative/attempt_001/{conversion.json,material_receipt.json,events.jsonl,response.json}`。现有公开归档不足以重算原始证据、终审与原生搜索记录绑定。

恢复条件：取得未经改写的原始 `backup_3x_live_01` 运行目录，通过 `frozen_source` 重新核验原始哈希、审查身份及材料回执重放。不得补造缺失文件或将新检索冒充历史记录。

## 2026-11-27：切换新定性实跑

按用户指令暂缓历史恢复，不计完成，保留上节恢复条件。新实验 `v6_qual_live_20261127` 已由原 `staged_topic.py init --full-paper` 初始化，主题为公共服务中的制度规则与例外安排（开放选题）。运行目录保留 manifest、状态及本次 CLI 尝试的原始日志。当前状态 `reality`，没有产生搜索结果或审查凭证。

原生 Codex CLI 0.171.0-alpha.13.2 登录状态确认 ChatGPT；实际 `exec` 退出码 1，在初始化 in-process app-server client 时出现 Windows access denied (os error 5)，并记录 goals DB 无法打开。恢复条件：在可正常启动 Codex 子进程的授权环境运行同一批次，保留实际原生事件；不得将失败日志当作检索或 S08 凭证。

### 独立开发：V14 定性准备任务

已扩展现有 S08 接口：绑定冻结理论框架与原 V14 文字要求全文，明确六项正文任务及标题、摘要、关键词、参考文献和证据附录；仍依赖原 S08、材料矩阵与独立审查的门禁。V14 离线回归 12 项（11 通过，1 跳过），定性与定量 S08 接入夹具均通过；Windows 检出造成的 CRLF 哈希差异按 Git 原始字节恢复，未改资源哈希。此项仅为写作准备接口子任务，不等同于正文生成或研究验收。

### 下一任务指针

新批次从 `reality` 接续至 S08。可独立开发的剩余 V14 定性正文接收、独立审查返修和交付门禁可继续施工；真实材料采集、分析、论文及端到端验收仍待实际运行。Stata 暂缓，不新增控制器。
