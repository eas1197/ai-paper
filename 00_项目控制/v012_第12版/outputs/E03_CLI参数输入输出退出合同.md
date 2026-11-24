# E03：逐命令 CLI 参数、输入输出、退出与副作用合同

状态：implemented_unverified（待CI）。依据 E02 的实际24个命令、原调用构建器及原接口 smoke。参数列表以 `commands` 的实时 `parameters` 字段和逐命令 --help 为准（由实际 argparse 生成，不维护第二套参数表）。

| 命令 | 输入/必要参数 | 输出与状态副作用 |
|---|---|---|
| commands / doctor | 无 | stdout JSON；只读；doctor 校验原组件 |
| init | run-id/theme | 原 run/manifest/state 创建 |
| status / prepare | run-id | 原状态/任务 stdout，只读 |
| advance | run-id | 原授权文献阶段或S08；不直接修改状态 |
| autopilot | run-id，可选theme/model/timeout/max-steps | 原有有界调度，checkpoint/原门禁阻断 |
| reality / exchange / issue / review | run-id/report | 原业务模块接受才修改原状态；review仍需D19认证 |
| event-compare | run-id/report，可选events-jsonl | 原event_protocol写事实比较，缺证据不补造 |
| materials | run-id，conversion/review/matrix三选一，原attempt等参数 | 原06材料/框架/矩阵文件；原校验预算 |
| resume-writing | run-id/attempt | 原矩阵复核与V15方案；需原条件 |
| writer4 | action/packet；prepare或submit需workspace，submit需manuscript/claims | 原V16产物、定量仍原V14；不自动正式通过 |
| chat-task / codex-task | run-id/phase/output | 冻结原任务、输出候选JSON，不调用模型 |
| review-task | run-id/output，可选对象、稿件、返修谱系 | 冻结候选，不派发/正式授权 |
| review-counts | run-id | 只读原记录观测 |
| chat-audit | task/response/output | 候选结构审计JSON |
| chat-receive / codex-receive / literature-receive | run-id/task/result/output；按需提供独立记录 | 候选/原文献核验JSON，保留未认证状态 |
| merge-results | run-id/task/selection/output，可选aliases | 原C合并索引，不覆盖旧文件；run内相对路径 |

退出0仅代表该技术命令成功执行（结果可能为等待、checkpoint或候选），不得理解为原学术pass。argparse缺参数/非法参数退出2；原模块阻断或已知输入/Schema/文件异常返回 blocked JSON、退出2。未知编程异常不伪装成功。修复候选输出覆盖风险：外部新文件或所选run的cli_outputs/新文件，先校验再执行，exclusive create；merge保留原独立exclusive合同。暴露原 event_protocol 可选原始events-jsonl；不改变事件核验规则。新增4项测试，覆盖24个命令的help/必填参数、输出保护、Schema错误和实际原路由。未运行真实AI。
