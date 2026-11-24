# D23：pass 原门禁路由与防绕过

状态：verified（离线原路由及防绕过；真实正向授权仍暂缓）。拆出 D12 内部候选读取/审计函数，原执行回执要求不变；新增 review_route_plan.plan_candidate_pass，仅从接收方选定、C04 有效、D10–D13 一致的候选报告和原当前状态描述原路由，不调用业务 gate、不写原状态。v009 preliminary 原生 academic_pass→design_review，原 combined pass→supplemental；设计 pass→supplemental；最终 pass→s08_ready，实际冻结仍由原 S08。06 pass 只进入本模块状态；矩阵仍需原 material_adequacy；V15 仅原实验性 reviewed_plan；V16 不存在正式正向接收，不伪造。统一 pass 不生成原 native academic_value/data_feasibility/method/adequacy 等字段，真实授权及原 native report 缺失时 advance_gate=false，D19 guard 仍失败封闭。离线测试包含映射、错 stage、模块隔离、候选不得放行、冻结 context 篡改；原 v009 既有业务状态转移测试仅 mock 授权用于离线验证，非真实独立 pass。5项新增，待本次完整 CI。

实际验收：strict run [45337750998](https://github.com/eas1197/ai-paper/actions/runs/45337750998)，job 138253756222 success；新增5/5，v012 238/238（重复两次不重复计数），原模块63/63，共301项；原 v009 测试实际回归通过。D23 完成离线路由合同及负向隔离，未执行真实独立 pass，未推进真实研究状态。
