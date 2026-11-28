# 原 3.x 实跑执行与回归

基线 f9e1fdf。对照资料为原运行 edu_v32_20261121、bike_parking_20261122、resale_events_20261122、community_meals_20261122 的任务输入、独立意见和状态证据。

## 原执行顺序

- 教育使用 v008 topic32。执行者组织概念化、核心及具体问题、检索与理论深化问题包。原独立 GPT-6.2 Sol 一次调用分别审三包，总控依次记录 PASS、PASS、READY。READY 表示可进入后续核验，历史未冻结。该轮台账的逻辑工作单元与真实调用分开。
- 共享单车、二手交易、社区食堂使用 v009 staged_topic。公开亲历优先，现实观察后比较独立事件，登记自主解释与独立反方，形成候选问题和议题定位，再按对象、议题、理论三层检索。反方区分哪些现象有证据、哪些解释暂待检验。程序由原初查门槛决定能否继续。共享单车之后独立学术初审、材料核验、设计审查、补查、终审及 S08 顺序仍适用。
- 6.0 上一轮将两个原入口串行叠加，把机会审查的可验证概念边界变成预先核实机制的证据门槛，并为每次补证和复审另发调用。最后才通过机会审查，原预算 6/3 已用完。原流程允许暂存待检验机制和缺口，将因果及材料适足性留给对应关卡。

## 恢复执行方式

新开放网络定性从 v009 staged_topic 的 prepare 领取任务。阶段执行者在一份研究包里依次记录观察、概念边界、可观察指标、抽象社会关系、并列竞争解释，再明确上位问题及具体研究情境。说明从具体情境转换时保留的理论关系与变化的取证办法。用独立反方检验这些内容，先排除假定相同但未核实的条件，然后才提交候选问题。使用既有 issue、initial、review、supplemental、s08 命令及原判断标准。正向审查报告沿现行 topic_reasoning 保存三个分项理由。课题只是有可检验的解释线索时，可以进入相应阶段，适足性由实际材料审查裁决。不得以理论名称、检索命中或规则文书直接填补证据缺口。

只有单独复现教育型 v008 任务时才使用 topic32 的 opportunity、question、deepening。执行者可以依原教育做法用一次独立调用分别审阅三个单独问题包，按原顺序录入。任一阶段未通过，后续裁决不得录入；保留实际调用与台账差别。开放定性 v009 批次独立运行，不另外启动 v008 状态机。此调整恢复原执行分工，保持原代码、阈值和预算。

## 历史功能回归

使用现分支代码、原运行凭证和隔离副本，未启动新模型调用。教育重放三个真实裁决，经 topic32.check 和 topic_run.record 依次进入 question、deepening、formal。共享单车重算 3 个事件、初查 5 篇、复核终审与 S08 哈希。二手交易重算 4 个事件及初查 1/5，刊外对话与后来人工补得文献不计入。社区食堂重算 3 个事件及初查 2/5，人工核验和理论另计。后三案均通过原独立反诘凭证结构校验；重放确认原结果，未重新执行学术审查或把两项历史缺额改为过关。

## 新批次真实验收点

v6_qual_open_20261128_002 按 v009 入口完成无主题预设的真实联网观察、5 个独立事件比较及独立反诘。反方指出合同条件及实际损失无法视为可比，收窄为书面通知、证据出示与结算报价在交涉中如何相互作用。上位条件是有预付款、退出触发可核验、对方仍掌握结算、结清结果可观察。情境转换提出预付服务解约，用申请回执及生效日替换退租通知指标。上述为研究设计与适用边界，未经该替代场域实证。恢复点为文献初查，正式定题、材料适足性审查和 S08 未完成。

- run_manifest.json 736ead4dcdc531275747a246ce877eb7f4b5d430546ae60668c76c36f2c4ad78
- reality_prompt.txt f24d913328fa0fd60597406161c7fa40142f0a46e4e953d23326fe6cf322340b
- reality_events.jsonl 1ae8c193059b83ffc1cd8271a9f94b397dc284839b9ddd35497f57a1330fee06
- reality_response.json e320217471e092f09161b5d35b4cf6149201bf9761293a5b9db1cc0a985bb17c
- event_comparison.json 5daa7674e91e9e04497f42bc679316bea514f8be19ff40c69eb743462e8444dc
- critical_prompt.txt a17d628192448cc32d4fefbe8b796748c81a1cf5dc1d33c95456f9df55812378
- critical_events.jsonl 2948387ae3526969e7bc604fcf33abe0268c467a92f023ffd6a6a955fde44e5a
- critical_response.json 95a7e3b7d6d8f96b8f94071373fbaefdc8eb0df7f981458b6bfc4875d357e677
- explanation_exchange.json d50d1070241d87ea9abe222b0131be4871fa372ba4f464a4decea2bb85187095
- issue_plan.json ab2a0e14f116312a122ea555611b7f20c35e24171b79faf87501cce7781fde93

## 三层初查接续

同一原生批次核实 5 条摘要。理论笔记使用 DOI，而原生结果给出唯一同标题出版社原作页面，旧入口未入账。修复为 DOI 无匹配时仅接受带摘要片段且唯一同标题的原生 URL，继续绑定事件，原批次重放未新增检索。状态 preliminary_review。原控制模块回归 17 通过。

- initial/batch_001/events.jsonl 014a7faa6730d50266cbf24964f52adcd3ee016cfb412b1dbcf39e27e30a20bb
- initial/checkpoint.json cccb6d78160a5589fb2928bfd43bce01bcee198a67533874f46bd5a06c51cf92
- initial/literature_matrix.json e207e60b0b303a059e69ab8ed0949f8c780857e4d1c00fb17c7e01db631ef362
- initial/theories.json 12f7cf09634a68b19791612cb37252f06b0da78d58aca6dd9ec4e0bc5e2603e3
