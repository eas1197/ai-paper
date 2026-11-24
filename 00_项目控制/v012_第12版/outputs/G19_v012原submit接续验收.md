# G19 v012 原 submit 接续验收

状态：verified（实际离线入口调用；非真实起草或独立审查）。

- `test_g19_v012_submit_real_original_writer` 用明确的合成夹具，通过 v012 prepare 和 submit 调用原 V16 子进程。正常提交绑定10个段落、10项主张、原始来源定位及正文/台账哈希；产生 style_review 和待独立审查请求，不授予 formal_pass。
- 伪造定位、缺失章节均真实触发拒绝；拒绝后请求保持 technical_revisions_needed。
- strict `45404670651` success（329/329 两轮及原模块84项，共413项去重），Handoff `45404670705` success；代码 `81881e9`。 Job `138482019530` 两轮 G19 均 ok。
- 下一项 G20。
