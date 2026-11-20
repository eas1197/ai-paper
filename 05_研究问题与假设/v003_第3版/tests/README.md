# 联合测试入口

05的端到端测试统一放在04第4版tests/test_workflow.py，以避免复制上游证据夹具。运行04第4版的unittest discover即可覆盖05的问题卡、全文对话、测量核查、设计冻结、返回04及失效传播。

测试使用纯TEST夹具，不认证真实G4或G5研究质量。各模块验收结论见outputs/technical_validation.json。
