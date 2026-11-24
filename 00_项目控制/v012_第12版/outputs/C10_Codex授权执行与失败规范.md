# C10｜Codex CLI 授权执行与真实失败规范

状态：verified（文档合同，2026-11-24；不代表真实运行）。

- 仅在用户授权、CLI 可用、真实 ChatGPT 登录通过、原始阶段与工作量门禁允许的本地环境执行；保留原 11/v007 cli_executable/login_probe/invoke，不绕过登录、不注入 API 密钥、不改沙箱。CI 离线回归不等于账户授权。
- 执行前读原任务/预算/停止条件并冻结 C05 任务包；原 CLI 是实际文献搜索权威入口，native advance 先生成任务快照后派发原 v009。
- CLI 不存在、登录探测失败、权限不足、超时、非零退出码、无必需原始日志/工具事件、工具不可用或缺少响应时：不报完成。保留真实错误与日志；blocked/failed/pending（统一枚举留 C17），不编造 thread、URL、事件或 response。
- 原 invoke 在登录失败写 login_diagnostics.json/login_status.json 后抛异常；autopilot Executor 对异常记录 technical_block，对非零退出码或 must_search 缺 trace 记录 failed。原 collect 有自身批次及登录预检处理。沿用其预算、失败记录；技术失败不自动视为学术失败或正式成功。
- 修复环境后依原检查点、批次与恢复规则继续；不把旧失败批次改为独立凭证，不在本任务启动真实搜索。

## 验收
静态核对 cli_executable/login_probe/invoke 与 Executor 真实异常和失败分支；无真实登录/搜索或正式 run。
