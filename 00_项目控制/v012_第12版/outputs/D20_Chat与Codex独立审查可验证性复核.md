# D20：Chat 与 Codex 独立审查执行可验证性复核

状态：verified（能力边界静态复核）；真实独立会话及正向授权验收仍按用户要求暂缓。基线 6cdc52bc82ef0e7008acff76895aebf385c5a3ef。不改变原门禁、预算、模型或生产注册。

| 核验维度 | Chat | Codex CLI |
|---|---|---|
| 任务与输入 | C04冻结快照、接收方独立指定的上下文和可见记录哈希；C19只核实际可见文本 | D15–D17冻结快照、launch/runtime、实际stdin、同attempt原始文件 |
| 会话身份 | C19明确 host_authenticated=false；D15不采用模型自报session；本会话无独立启动及宿主认证接口 | 原 dispatch 新attempt、非resume、--ephemeral/read-only；D16要求唯一thread.started/turn.completed、无turn.failed，核实际模型与原始响应 |
| 可验证边界 | 可核字节、来源位置、观察者选择的真实工具记录；不能据此证明独立身份、隐藏上下文隔离或正式裁决 | 可核接收者独立采集的原始文件、不同thread、任务哈希和实际请求白名单；文件自洽不能独自证明宿主真实启动、实际沙箱隔离 |
| 当前正式入口 | 禁止同一对话角色扮演、模型自报身份、复制对话和合成CLI事件冒充独立审查 | 缺真实登录、原生记录、可信宿主与正向授权时停止；历史缓存相同request仅可恢复原实例，不是新复审 |
| 当前运行 | 未启动独立Chat审查 | 未启动真实Codex；不生成模拟凭证 |

逐项静态核对：
1. D14启动合同、D15记录器报告与原v009 resume_writing.dispatch：原代码保存request/login/events/stderr/response，要求ChatGPT登录，实际以request.model写validated.model，不能将该字段等同观测模型；缓存按request匹配，不独立证明新调用。
2. C19 chat_receiving.audit_chat_records 明确拒绝Codex事件作为Chat记录，返回host_authenticated=false、formal_eligible=false。C20 codex_receiving.audit_codex_records 属原生检索回执核对，不能替代学术独立审查。
3. D16调用绑定、D17线程与输入隔离均只能形成待核候选；D18 receive_review_or_wait 对缺失、重复、篡改及候选均保留unable_to_review、advance_gate=false、automatic_retry=false。
4. 实读 review_gate_guard.require_original_review：无intake即拒绝；同run intake交D18后仍抛出unable_to_review。现无真实正向授权路径；不得把离线79项回归或历史报告称为正向验收。

恢复条件：有授权的真实独立宿主启动；受信调度者捕获实际模型、登录/执行状态、会话标识、白名单输入、原始事件、响应及哈希；核不同研究者会话和真实隔离；由接收方独立选择凭证，通过D12/D16/D17及后续可信授权适配，再委托原门禁。缺任一关键条件停止并记录，不允许无限重试。Chat未取得宿主认证适配前仅保留候选；Codex真实运行仍deferred_by_user_instruction。静态复核验收四项：可核证据、不可核证据、失败封闭、恢复条件均有对应源码/报告；无新增代码或测试、未运行真实模型。D20仅为复核任务，不能关闭GAP-F02/F03或宣称已认证独立性。

依据：[C19](../tools/chat_receiving.py)、[C20](../tools/codex_receiving.py)、[D14](D14_独立审查会话启动与身份记录合同.md)、[D15](D15_独立审查执行记录持久化.md)、[D16](D16_审查调用与原始事件绑定.md)、[D17](D17_审查会话与输入隔离.md)、[D18](D18_独立审查失败封闭与等待.md)、[D19 guard](../tools/review_gate_guard.py)、[v009 dispatch](../../v009_第9版/tools/resume_writing.py#L50-L91)。

下一项 D21：按原阶段自动生成审查任务包；仅离线生成/验收，不启动独立会话。
