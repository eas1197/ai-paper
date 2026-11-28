# 6.0A 与 6.0B 研究实验

6.0A 沿用 staged_topic.py 的默认入口。6.0B 仅用于实验：初始化加 --research-route B，prepare 返回探索任务和冻结预算。在提交候选前，研究者可以自行重排研究动作、回到旧证据或另选候选。不同批次使用独立 run_id。

用 research <run_id> --report <JSON> 一次提交 B 的现实观察 reality、事件包 event_packet、独立反诘 exchange、检索议题 issue_plan、论证成果 topic_reasoning。上述字段复用原契约。exchange.critical_receipt 包含同一运行内的 events、response、events_sha256 和 response_sha256，critical_actor 为实际独立调用的 thread ID。证据落盘后一次进入初查；后续 prepare 同时提交文献、理论、完整研究包和历史审查，研究者仍可重新论证。初查、独立学术审查、方法分流、材料证据、补查和最终审查门槛照旧。S08、06、V14 及交付实现沿用 A。

配对实验入口 research_experiment.py <运行目录> <共同材料 JSON> --arm A 或 B。A 的实验提示按现有步骤组织；B 提示允许自主安排。两组使用同一个冻结输入、GPT-6.2 Sol、medium、相同调用与联网预算。实验固定提案、独立反诘、修订三个观测点，用于比较同资源下的探索策略。它不代替正式的 staged_topic 学术与材料门禁。原始调用、请求、响应和资源用量留在各自运行目录。技术不合规调用保留凭证并计入预算，可在额度内以 --retry 重试。
