# B23｜Chat-native 与 strict 执行入口合同对照

**状态：verified（同一数字互助 fixture 的状态/门禁/产物对照及自动化测试通过；未执行新搜索）。**  
**分支：** dev/v3.1-abstract-acquisition

## 一、同一 fixture 的父状态

原始运行 digital_mutual_aid_20261122：

- parent staged_topic.json：status=explanation_exchange，formal_eligible=false。
- autonomy_output.md：现实观察和双事件比较已落盘；独立反诘 Codex CLI 启动失败，critical_response.md 为空；文献初查、正式独立学术审查和写作方案尚未执行。
- run_manifest.json 的后续模块仍为 planned。
- 原始研究父状态未被 Chat-native 子实验改写。

## 二、Chat-native 子实验实际状态

chat_native_20261122/Chat实验状态.json 明确记录：

- mode=experimental_chat_native_single_model_adversarial。
- parent_staged_topic_status=explanation_exchange，parent_modified=false。
- independent_model_invocation_id=null，independent_review_verified=false，cli_tool_receipts=null。
- web_search_mode=ChatGPT native browsing, not Codex CLI。
- S03 仅为 single-model adversarial，independence_not_met。
- S04–S12 产生了文献初查/补查、内部审查、探索性材料矩阵和段落级写作方案，但 S08 不是正式冻结，S10 未通过独立材料适足性，S11 是 provisional plan。
- final_gate=not_passed_due_to_missing_independent_review_and_empirical_limitations；writing_deliverable=provisional_plan_not_full_paper。

因此 Chat-native 的 S01–S12 是隔离探索子实验，不等于原 v009 父流程已从 S03 通过独立反诘，更不等于正式学术冻结。

## 三、两种入口的真实合同

| 维度 | v012 strict / Codex CLI | Chat-native handoff |
|---|---|---|
| 规则来源 | ai_paper5_strict 调用原 v009 staged_topic；autopilot 调用原 11/v007 Codex collector 与原 v009 event_protocol | chat_task 读取原 v009 policy/prompt/schema hash，输出 chat_native_web task |
| 搜索来源 | Codex CLI 原生 web events、thread.started、events.jsonl、response.json、SHA | ChatGPT 原生网页搜索、页面 URL/过程日志；不是 Codex CLI 事件 |
| 来源身份 | 可绑定 thread、raw events、response 和页面打开事件 | cli_tool_receipts=null；不能伪造 CLI thread 或原始事件 |
| 独立审查 | 必须真实独立会话与可核验 receipt | 同模型角色反诘，不满足独立性 |
| 文献结果 | 原 v009/11-v007 原生 collector 与正式接收合同 | 独立文献检索矩阵；audit_chat 只做结构/范围/去重检查，结果仍 provisional |
| 材料结果 | 原 06/v005 采集、修复、独立适足性门禁 | Chat 探索性经验材料与分析矩阵，无独立适足性 receipt |
| 写作结果 | 原 V15/V16 正式写作路径，需前置门禁 | 论文段落级 provisional writing plan，不是正式 V15/V16 交付 |
| 父状态写入 | 只能由原 v009 状态机推进 | parent_modified=false，不得合并为父状态完成 |

## 四、产物 schema 的不可互换边界

Chat-native 子目录中的：
- 文献检索矩阵.json：acquisition_mode=chat_native_web，targets.formal=false。
- 经验材料与分析矩阵.json：acquisition_mode=chat_native_web，材料类型为公开二手采访/报道过程比较。
- 论文写作方案.md：明确“未获独立审查放行”，并保留原创性、材料适足性和因果推断边界。

这些文件可作为探索性研究材料，不能直接替代原 v009 的 literature_matrix、event_comparison source receipts、06 正式材料矩阵或 V15/V16 写作 receipt。ai_paper5_strict.audit_chat() 返回 native_cli_receipt=false、formal_eligible=false；即使通过结构检查，也不会自动取得正式来源凭证或独立审查资格。

## 五、测试与 GitHub Actions

新增两项共享 fixture 合同测试：
1. Chat-native 子实验不修改 parent staged_topic，且独立 invocation/CLI receipt 缺失时 final gate 保持未通过。
2. Chat 文献矩阵、经验材料矩阵和写作方案明确标记 chat_native_web / exploratory，不被当作正式 v009 receipt。

GitHub Actions：
- strict v3 regression run 45198496360：success。
- Handoff offline verification run 45198496321：success。
- v012 strict tests：18/18。
- v009 tests：41/41。
- 04/v012 tests：10/10。
- 06 tests：2/2。
- V15 tests：2/2。
- V16 tests：7/7。

## 结论

B23 verified。两条路径共享原 v009 研究规范，但不是同一种执行凭证：Chat-native 可用于受限探索和结构预审，不能冒充 Codex CLI 原生搜索、独立审查或正式门禁；strict 路径继续以原 v009 状态机为唯一权威。没有把 Chat-native 的探索性成果回写成原研究已通过阶段。
