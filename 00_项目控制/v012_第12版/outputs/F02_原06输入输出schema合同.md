# F02 原06输入输出 schema 合同

状态：verified（原生 schema/验证器核对）。不是重新设计原06。

| 输入/操作 | 原验证字段 | 原输出 |
|---|---|---|
| --conversion | core_question、prior_question、new_question、theoretical_concern、reason_for_conversion、framework、literature、context 非空；新旧具体问题不同 | conversion.json、response.schema.json、实际原生搜索 response/events、material_receipt.json |
| 原搜索响应 | materials/search_notes/gaps；每材料 url/date/subject/context/kind/path/locator/relation/limits/access；原 kind 枚举及两定性路径；不允许 inference 冒充材料 | material_id、event_id；原事件预算、排除理由、原始哈希及 pending_independent_review |
| --review | 原独立执行门禁；model/invocation_id/reason/conversion_sha256/academic_value；outcome 为 pass/missing_data/materials_pending；method_assessment 全三路径、ready 须 verified access 与已核材料 IDs | review.json（禁止覆盖），原 qualitative_design_ready/materials_insufficient/materials_pending |
| --conversion + --framework | FRAMEWORK_CONTEXT 九字段、DIMENSION_FIELDS 六字段；非空维度、唯一 ID；同 run 初查材料原回执、转换哈希一致 | qualitative_framework/attempt_NNN/framework.json 与原 framework_collection receipt |
| --matrix | finding.dimension_id、conclusion/boundary/unresolved/alternatives、status、evidence[].material_id/relation/reason；证据关系 support/counterexample/competing/context，引用原材料 ID、url/locator/kind；每维度唯一且齐全；无证据保持 unresolved | analysis_matrix.json；pending_independent_review，framework/collection canonical digest |
| --matrix + --framework-revision | prior_framework_sha256、reason、framework；同 core_question，原局部修订上限 | 新哈希后缀 framework/analysis_matrix 文件，保留原产物 |

原验证器是 qual_materials.validate_conversion/schema/record_review、method_paths.select_method/verify_material_review、framework.validate_framework/analysis_matrix；未额外创建并行 JSON 语义标准。原 conversion/review/matrix 输入为原函数校验而非全部独立 JSON Schema 文件；不得伪称存在未有的 schema 文件。

CI 45348695079/job 138289453469 success：原 method_paths 5/5、framework 2/2、CLI contract 4/4 均通过。实际采集/独立执行仍暂缓。
