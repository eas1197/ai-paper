# C07｜Codex CLI 执行器与原始凭证

状态：verified（文档合同，2026-11-24；不代表真实运行）。

- 执行器标识 codex_cli；原 11/v007 codex_literature.invoke 负责登录探测、只读 ephemeral CLI、原生搜索及真实退出码。
- 记录实际 argv（参数和工作目录，脱敏、不记录凭据）、执行开始/结束时间、退出码、登录检查结果；原实现构造 argv，但未单独持久化完整命令时必须记为缺失，不能由模板反推成实际凭证。
- 原始文件为 prompt.txt、schema（实际传入文件）、events.jsonl（stdout）、stderr.log、response.json；保留真实文件路径/哈希，不能覆盖失败 attempt。thread/session 从真实 thread.started 解析，不能从模型自报值生成。
- 工具事件来自 item.completed/web_search；保留原 ID、action、results、URL。原 evidence() 拒绝 command_execution/mcp_tool_call/file_change；url_event 可关联结果，但命中不等于打开，原摘要接收规则与 B19 事实级打开门禁仍分别适用。
- autopilot_v3 的调用台账保存实际 rc、events/response 哈希、thread_id、web_actions；旧文献接收与新统一凭证不是等价证明。缺失记录保留 pending；失败、超时或缺登录不冒充成功。独立学术审查另验。

## 验收
静态核对 11/v007 invoke/evidence/url_event/login_probe 与 v012 transcript_session/Executor/completed_call；原实现未持久化字段明确标缺；无真实调用。
