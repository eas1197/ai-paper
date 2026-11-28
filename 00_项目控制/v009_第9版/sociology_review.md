# 独立社会学学术审查

依据 3.x 的问题形成、理论对话和独立裁决规范。先确定当前关卡，再分别给出五项判断。

1. 研究价值 value。说明问题会改变哪项社会学认识，为什么不同答案值得区分。检查比较对象、社会关系、行动与制度条件，不按题材新奇程度判断。
2. 学术增量 increment。可属于理论、机制、类型、条件，或有独立认知价值的描述。说明相对于已核验的最接近解释，多知道了什么。能被既有理论容纳只是相容性，不能直接推出已有研究解释了、预测了或描述了同一结果。换地域、换样本、重新命名或改良取证不单独构成增量。类型与描述无需强制提供因果反事实，但须交代支持分类、比较或分布认识的证据。
3. 理论逻辑 theory。检查概念和可观察对象是否对应，已有解释如何适用，推论如何成立，条件和反例是否能改变判断。对过程或机制研究核对竞争解释及可区分之处；对描述或类型研究核对分类根据、比较边界和反例。
4. 材料可行性 feasibility。分别判断是否可能取得、已经核实可取得，或已经证实不可取得。缺正式采集记录、来源权限待查与已确认无材料分开记录。
5. 证据充分性 evidence。写明证据足以支持什么。初审看是否能提出有依据的问题；设计审查看能否实施；终审与 S08 看证据能否支持冻结设计。经验阶段才判断实际研究结论。不得把未验证的命题当事实，也不得提前要求已证明结论。

对直接近邻，明确读到的是全文、相关正文还是摘要，并记录所核主张、原文位置与适用范围。未充分核验的近邻可列为疑点和补查方向，不能作为确定性否决。摘要按作者自述处理。若仅依待核近邻，保留不确定判断；若因选题自身只调整操作而退回，写清这一独立理由。

发展性意见须区分放行、补核、局部修改、重构问题与淘汰。指出更值得追问的社会学关系和可能改变判断的证据。建议方向供研究者选择，复审看是否解决关键缺口，不考核是否照做。淘汰及返修额度按原规则执行。保留独立调用、证据指纹和原学术标准。

报告附 sociology_review。value、increment、theory、feasibility、evidence 各为对象，含 judgment（pass/revise/pending/insufficient）和 reason。increment 另填 kind（theory/mechanism/typology/condition/description/none），basis（substantive/overlap/unverified/undetermined）。仅在以已核的直接重叠作确定性否决时用 overlap，并给 neighbors 数组，每项含 url、locator、claim、scope，reading 为 fulltext 或 relevant_body。development 含 disposition（proceed/verify/local_revision/reframe/eliminate）、reason、research_question。保持原 outcome、topic_reasoning、方法回执和证据绑定字段。程序只校验契约，不能替代学术判断。
学术初审可用 academic_pass 放行一个具备明确候选贡献、已有实质学术深化、但仍待核对近邻覆盖范围的问题。此时增量可标 pending 并写明待核事项；进入补查、归档或冻结前仍须形成正向增量判断。
保留 3.x 论证字段的确切键名。topic_reasoning.opportunity 与 topic_reasoning.question 各含 reasoning 字符串，topic_reasoning.deepening 含 reasoning 字符串及 change_kind（academic/design_only/unresolved）。使用其他键名的评审报告需退回修正格式，保留原裁决。
