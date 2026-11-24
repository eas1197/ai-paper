# G13 V16 原prepare逐节任务验收

状态：verified（离线实际原入口调用）。

- `test_g13_v012_prepare_real_writer_artifacts` 通过 v012 CLI 的 writer4 prepare、G06 接续门禁及 G12 route，真实 subprocess 调用 V16。测试夹具不是正式研究审查凭证。
- 实际生成 5 个逐节任务；核对章节来源 ID、来源详情、逐段要求、ST/V003规则、写作约束；manifest 绑定输入/计划哈希和13项资源锁，formal_eligible=false，状态 awaiting_draft，未产生写作审查请求。
- strict `45382609308` success（v012 327/327 两轮；v009 46、04 10、06 4、V15 7、V16 14，共408项去重），Handoff `45382609392` success；代码 `7864778`。 Job `138405218050` 两轮新增测试均 ok。
- 未执行模型正文起草。下一项 G14。
