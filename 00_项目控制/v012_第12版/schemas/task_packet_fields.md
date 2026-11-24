# 共用任务包字段规范（C02）

版本：`schema_version: 1`，必须显式给出。不支持的版本、缺失版本和未声明顶层字段均拒绝；这不是自动迁移器。C01 草案不作为已投入运行的旧协议。

| 字段 | 必填 | 约束/默认 |
|---|---|---|
| schema_version | 是 | 整数 1；无隐式默认 |
| research_id / stage_id / task_id | 是 | 非空字符串；C03 校验运行归属 |
| purpose / research_question | 是 | 非空字符串 |
| search_levels | 是 | 原检索层级数组；非检索任务显式 [] |
| input_files | 是 | 文件路径与 SHA-256；无输入显式 [] |
| source_scope | 是 | 对象；可选子字段 journals、source_types、policy_refs，缺失不扩张权限 |
| quantity_budget | 是 | 原具名非负整数预算；零合法；无正向预算显式 {} |
| time_budget_seconds | 是 | 非负整数秒；无隐式默认 |
| output_schema | 是 | file+路径/哈希或 inline+schema |
| stop_conditions | 是 | 至少一条非空停止条件 |
| notes | 否 | 说明数组，语义默认 []，不具备授权作用 |

JSON Schema 的 `default` 是描述性注解，验证不自动注入字段。关键字段不得默认补齐。来源范围、预算、门禁仍以原始权威模块为准；空数组/对象不代表无限制，结构验证不等于授权。C03–C05 分别负责运行归属、输入冻结和执行器接入。

## C04 快照与版本

- input_files 相对于原 dev run 根目录；policy_refs 与文件型 output_schema 相对于仓库根目录。路径不得越界，文件及 SHA-256 必须匹配。
- freeze_packet 使用调用方独立选择的 research_id；快照包含完整 packet、原研究问题/主题、原 v3 搜索政策/提示词/schema 哈希及显式上游快照引用。快照版本是规范 JSON 的 SHA-256，与 wire schema_version 分开。
- 每个 (research_id, stage_id, task_id) 保留不可覆盖的版本记录和当前指针；相同输入幂等；变更生成新版本，旧版本不可重新激活。受影响的下游由显式依赖链递归拒绝，独立任务不受无关任务变更影响；原问题或政策改变则共同失效。
- validate_result_snapshot 要求结果引用独立指定的当前版本；旧结果保留但不能被接收为当前结果。该函数不验证执行者或学术资格。
- 本合同采用单任务串行写入；并发调度及原模块状态路由待后续整合。C05 接入前不宣称旧执行器已执行这些校验。
