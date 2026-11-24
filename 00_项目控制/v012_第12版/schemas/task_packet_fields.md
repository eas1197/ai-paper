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
