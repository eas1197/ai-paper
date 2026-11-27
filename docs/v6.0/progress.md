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

## 下一任务指针

唯一接续点仍为第 1 项。第 2–6 项尚未正式执行或验收：理论框架与定向采集、独立矩阵审查、V14 定性写作、完整论文审查返修、全新课题端到端实跑。Stata 暂缓。不新增控制器版本。

