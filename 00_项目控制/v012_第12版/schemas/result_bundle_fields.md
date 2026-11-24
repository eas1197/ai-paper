# C11 共用结果信封与身份边界

结果使用 schema_version=1，task_snapshot 复用 C04 的 research_id/stage_id/task_id/snapshot_sha256。executor 与 provenance.kind 必须严格一致。chat_native_web、codex_cli、manual 三类原始凭证字段互斥，缺失文件/命令/会话显式 null 或空数组加 missing_fields，不填造。manual 只能申报人工核验状态；结构有效不等于核验真实。

文件引用统一为运行目录相对 path 与 SHA-256；实际文件核验、当前版本绑定和拒绝规则由 C15 完成，逐来源真实性由 C19–C24 完成。现阶段 schema 不含正式资格字段，不允许提交者自报通过。C12 再增加执行时间、搜索动作及来源条目。
