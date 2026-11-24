# C11 共用结果信封与身份边界

结果使用 schema_version=1，task_snapshot 复用 C04 的 research_id/stage_id/task_id/snapshot_sha256。executor 与 provenance.kind 必须严格一致。chat_native_web、codex_cli、manual 三类原始凭证字段互斥，缺失文件/命令/会话显式 null 或空数组加 missing_fields，不填造。manual 只能申报人工核验状态；结构有效不等于核验真实。

文件引用统一为运行目录相对 path 与 SHA-256；实际文件核验、当前版本绑定和拒绝规则由 C15 完成，逐来源真实性由 C19–C24 完成。现阶段 schema 不含正式资格字段，不允许提交者自报通过。C12 再增加执行时间、搜索动作及来源条目。

## C12 统一结果字段

- execution_time：started_at、finished_at 为带时区 ISO 8601 或 null；不知道不可猜测。failure_reasons 保存真实失败及缺失原因。
- search_actions：action_id、action_type、occurred_at、query、original_url、record_locator、source_ids、failure_reason；均为归一化声明，不代替对应执行器原始日志。
- sources：source_id、source_type、original_url/metadata_url/abstract_url、title、authors、publication、publication_date、doi、abstract_locator、open_status、excerpt、paraphrase、relevance_reason、dedup_key、limits、failure_reasons、action_ids。日期可保留原始年/年月/日期精度；未取得用 null/空数组并写原因。
- opened/not_opened/unknown 仅表达打开状态声明；不自动证明实读，C13 分拆各证据阶段。source_id 和 dedup_key 的生成规则留 C16；状态细分留 C17。原 native_response schema 的题录、摘要 URL、摘录长度、转述和相关性等正式规则保持独立，统一结构不得放宽原准入。

C12 首次 CI 45316989400 发现 jsonschema 默认未安装 RFC3339 日期校验依赖；加入 rfc3339-validator 并对 date-time 加显式带时区格式 pattern，缺失格式插件时仍拒绝明显非法时间。运行时应安装同一依赖；实际结果接收 C15 使用 FormatChecker。

## C13 五阶段独立记录

每条 literature 来源必须包含 discovery_status（发现）、原 open_status（打开）、abstract_read_status（摘要读取）、fulltext_read_status（全文读取）、formal_inclusion_status（正式纳入）五个独立字段。后四个中不由其他状态自动推定；打开、摘要或全文读取的声明均非学术门禁回执。人工文件阅读可能不涉及网页打开，故不硬编码先后关系。未核实记录 unknown/pending_original_gate，未纳入为 not_included；执行器提交包禁止 included/verified 等自报正式通过，原 gate 的最终纳入由接收器独立记录，C18/C21 后续接入。非 literature 来源的 literature_stages 必须为 null。遵守 B09 原 v009 摘要级与生产 G4 全文资格的不同边界。

## C14 经验材料独立字段

empirical 来源必须具有 empirical_material：来源说明、事件或对象、事件日期/时间（保留原始精度）、具体定位、内容类型、情境、采集路径、访问边界、可核实事实候选、研究者解释及不能支持的判断。公共 source 中仍保留原始 URL、作者/媒介、打开声明、行动 ID 和失败原因。内容类型沿用原 06/v005 的 actor_statement/reporter_account/official_rule/documented_action；other/unknown 仅为统一候选承载，不能替代原 06 资格，researcher_inference 只能放解释字段。事实候选独立包含 statement/locator/status/limits，status 只允许 reported/needs_verification/contradicted，不得自报 verified；实际事实级凭证和独立核验仍由原 event_protocol/06 接收及后续 C19–C24 判断。未知值显式 null/空数组，保留失败和不能支持的判断，不补造材料。非经验来源 empirical_material 为 null。

## C15 原始记录与当前结果绑定

- 新接收器 tools/result_bundle.py 的 audit_result_bundle 读取当前运行内的实际 result 文件，计算原始字节 SHA-256；先核 C04 当前快照，再核共用结果 schema 与身份。
- 每个原始记录引用必须在同一 run 内真实存在，哈希重新计算；拒绝路径越界、符号链接越界、缺文件、重复/自引用、篡改、Codex events/response 跨 attempt。原始结果及记录文件均不改写。
- expected_execution 由独立接收器/调度器选取，包含 task_snapshot、executor、provenance、result_sha256；与提交的包严格对照。不能由模型自己提交此参数或自动从模型自述生成。当前任务只定义和验收该接收合同，真实执行器提供独立记录的接入仍待 C19–C24。
- 未取得原始文件/字段为 pending_missing_original_records；仅自报且哈希相符为 pending_independent_execution_binding；独立选取记录且文件哈希匹配仍为 records_hash_bound_pending_source_verification，非零退出记录为 execution_failed。所有返回 formal_eligible=false，实际工具真实性、来源打开/内容定位、原学术门禁均须后续核验。
- 该模块不会创建原始事件，不把合成 fixture 或哈希一致当真实检索。采用单任务串行合同；真实接入及防并发状态处理后续完成。

## C16 来源候选身份与去重

- tools/source_identity.py：文献候选沿用原 11/v006 verified_identity.resolve/MATCH；同 DOI 必须复核刊物、作者、年份和题名，同题不同年份/DOI 不自动归并；身份冲突及不兼容桥接隔离。归一化 DOI 及原题录身份生成稳定候选 ID，保留原始成员和 action_ids。
- 经验来源按保守 HTTPS URL 规范化（仅去 utm、fragment、默认端口；保留内容参数及顺序），同 URL 可聚为同报道候选。转载/多 URL 只在接收方独立核对并提供 reviewed_report_aliases 时合并；同事件或标题相同不自动合并、不等同独立报道。没有身份信息的材料保持独立候选。
- 输出为候选分组、冲突、隔离成员，保留各原记录及索引；不覆盖执行者原始凭证，不改原文献 group/事件接收器，不授予正式资格。跨执行器合并/原始凭证持久化留 C24。

## C17 执行状态及问题编码

- execution_status：not_executed/unknown/no_results/partial_results/completed/failed；completed 仅指执行器报告本次工作结束，不表示资料达标、接收通过或正式资格。no_results 必须没有来源并记录同名问题；partial_results 有候选且保留问题；failed 必须有失败原因。运行级超时、预算耗尽、登录失败等不得同时声明 completed。
- execution_issues：code（无结果、部分结果、摘要缺失、访问失败、登录墙、超时、来源冲突、预算耗尽、登录/权限/工具失败、缺原始记录及 other）、scope（run/source/action）、target_id、detail、original_status。保留真实旧状态及失败原文；不强行从未知状态推断成功。原 11/v007 verification_pending/incomplete/experimental_budget_exceeded、技术异常和原始状态仍独立保存；C18 另定义接收裁决。原 B14 真实采集仍暂停。
- 接收器报告保留执行状态与问题，failed 不可升级为正式资格；所有 C15 返回仍 formal_eligible=false。

## C18 接收裁决（独立于执行状态）

接收器生成 acceptance_status/reason，提交 schema 不允许执行者自填。pending_candidate：缺独立绑定、原始记录或运行状态不明；reviewable：绑定和实际字节哈希已核、执行声明完成、有候选且无已报告缺口，仍须原始来源真实性及原学术门禁核验；needs_supplement：未运行、无结果、部分结果或存在缺口；rejected：执行失败（非法/篡改/越界/错任务等直接拒绝异常，不写通过记录）；formal_qualified：保留给原有权威学术门禁真正放行后的接收裁决，本模块禁止生成此状态，C21 后续接入。任何 C15/C18 审计返回 formal_eligible=false；不能由 reviewable 推导正式资格。真实状态、缺口与原因保留，不自动重试或扩大搜索预算。

## C19 Chat 原始网页记录接收

`ai_paper5_strict.py chat-receive --run-id <id> --task <独立选择的chat-task文件> --result <run相对结果路径> --output <审计文件>` 可选 `--execution-binding`（接收方独立选定的 C15 绑定）与 `--observed-actions`（接收方从真实可见工具记录独立提取的动作清单）。原始记录为实际保存的 UTF-8 可见文本/合法导出，必须有文件引用和哈希，不制造所谓 Chat 原始 API 格式。动作提取仅为接收方审计索引，字段为 action_id/action_type/record_ref/line_start/line_end/query/urls；匹配原记录所在行、URL、搜索词或目标页、来源及动作 ID。缺原始独立记录保持 pending；不得让执行模型自行生成独立绑定或提取索引。可核对的字节和可见记录不等于宿主认证，所有输出 host_authenticated/native_cli_receipt/formal_eligible 均 false。拒绝 Codex events.jsonl、原生事件流及其他执行器，不生成 CLI 记录。原 chat-audit 结构审查独立保留；C22 再专门验摘要定位与缺凭证边界。
