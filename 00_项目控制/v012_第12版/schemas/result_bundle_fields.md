# C11 共用结果信封与身份边界

结果使用 schema_version=1，task_snapshot 复用 C04 的 research_id/stage_id/task_id/snapshot_sha256。executor 与 provenance.kind 必须严格一致。chat_native_web、codex_cli、manual 三类原始凭证字段互斥，缺失文件/命令/会话显式 null 或空数组加 missing_fields，不填造。manual 只能申报人工核验状态；结构有效不等于核验真实。

文件引用统一为运行目录相对 path 与 SHA-256；实际文件核验、当前版本绑定和拒绝规则由 C15 完成，逐来源真实性由 C19–C24 完成。现阶段 schema 不含正式资格字段，不允许提交者自报通过。C12 再增加执行时间、搜索动作及来源条目。

## C12 统一结果字段

- execution_time：started_at、finished_at 为带时区 ISO 8601 或 null；不知道不可猜测。failure_reasons 保存真实失败及缺失原因。
- search_actions：action_id、action_type、occurred_at、query、original_url、record_locator、source_ids、failure_reason；均为归一化声明，不代替对应执行器原始日志。
- sources：source_id、source_type、original_url/metadata_url/abstract_url、title、authors、publication、publication_date、doi、abstract_locator、open_status、excerpt、paraphrase、relevance_reason、dedup_key、limits、failure_reasons、action_ids。日期可保留原始年/年月/日期精度；未取得用 null/空数组并写原因。
- opened/not_opened/unknown 仅表达打开状态声明；不自动证明实读，C13 分拆各证据阶段。source_id 和 dedup_key 的生成规则留 C16；状态细分留 C17。原 native_response schema 的题录、摘要 URL、摘录长度、转述和相关性等正式规则保持独立，统一结构不得放宽原准入。

C12 首次 CI 45316989400 发现 jsonschema 默认未安装 RFC3339 日期校验依赖；加入 rfc3339-validator 并对 date-time 加显式带时区格式 pattern，缺失格式插件时仍拒绝明显非法时间。运行时应安装同一依赖；实际结果接收 C15 使用 FormatChecker。
