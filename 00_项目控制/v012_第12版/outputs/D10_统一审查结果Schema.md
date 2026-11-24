# D10：统一审查结果 Schema

状态：verified（JSON Schema 定义及离线结构验收；不是独立审查或原门禁运行验收）。

机器可读合同：[review_result.schema.json](../schemas/review_result.schema.json)，Draft 2020-12，显式 schema_version=1。对照 D09 十一类审查与 C 系列 task_snapshot；不修改 C result_bundle schema 或原 v009/06/V15/V16/V14 报告合同。统一结果独立保存，作为受审查的候选裁决；其文件及实际执行回执的绑定由后续接收器实施。不能由结构通过推导独立身份、事实真实性或正式资格。

## 裁决语义

| 决策 | 最低约束 | 边界 |
|---|---|---|
| pass | 理由非空；issues 为空或仅非阻断 suggestion | 候选通过；原门禁、独立凭证及全部前置仍必须核验 |
| revise | 至少一个阻断性 academic_defect 或 technical_defect | 技术和实质缺陷分开记录；不在此定义返修路由或自动扣预算 |
| need_evidence | 至少一个阻断性 evidence_gap | 不足以作审查裁决；不得视为已证不可行或擅自搜集 |
| reject | 至少一个阻断性 academic_defect | 实质拒绝建议；归档/淘汰须由原门禁判断 |
| unable_to_review | 至少一个阻断性 execution_blocker | 无法实际执行或取得必需独立凭证；停止，不得通过 |

阻断性 execution_blocker 优先于任何其他结论；阻断性 evidence_gap 排除 pass/revise/reject。若实际独立执行无法核实，接收方后续须停止，而非信任提交者填写的 pass。字段结构不证明提交者完成审查。

必填：版本、task_snapshot（research_id/stage_id/task_id/snapshot_sha256）、review_kind、decision、reason、issues、assessment_scope；issues 的每项含 issue_id、dimension_id、category、blocking、detail、evidence_ids、required_action。空白理由拒绝，未知顶层字段拒绝，不能提交 formal_pass 或评分。实际 ID 是否来自当前输入、是否重复、证据位置/支持/反例与实际执行记录核验属于 D11/D12，不能在本任务静态 schema 中冒充已实现。

原裁决语义不被覆盖：academic_pass 不等于完整 pass；材料未查与不可得分开；原 revision routing、conditional pass、stop、旧 G7 signoff 不做机械同名转换。原始报告与裁决保留；后续按 D08 原节点适配并由原状态机作权威决定。此 schema 不作为原 CLI 直接输入。

## 验收

本次使用 Python jsonschema Draft202012Validator.check_schema 及 is_valid 对同一结构执行 14 个合成 fixture，14/14 符合预期：空 issues pass、建议 pass、证据阻断拒绝 pass、四种非通过合法样例、缺 blocker 拒绝 unable、技术缺陷拒绝 reject、执行阻断拒绝 revise、拒绝自填 formal_pass、空白理由、非法快照哈希、执行阻断拒绝 need_evidence。未执行真实 CLI、CI、独立审查或原门禁；未新增真实凭证。D10 verified；下一 D11（具体证据 ID、文件位置、哈希、支持范围、反例与未决问题）。

依据：[D08](D08_D01-D07原3x门禁映射表.md)、[D09](D09_统一审查任务包合同.md)、[C result bundle](../schemas/result_bundle.schema.json)、[C 字段](../schemas/result_bundle_fields.md)。
