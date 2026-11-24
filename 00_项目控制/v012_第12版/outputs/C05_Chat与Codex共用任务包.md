# C05 Chat 与 Codex 共用任务包

日期：2026-11-24；状态：verified（初查/补查任务生成的离线合同验收）。

- 代码提交：b36d7c9eaaf68c89222e8bf4967d8dbcc397fead；补充验收提交：9d9da85a1e3984e8dc9a88144c57621a26e70fca
- [CI](https://github.com/eas1197/ai-paper/actions/runs/45316240649)；strict run `45316240649` job `138183670291` success；C05新增4/4，v012 45/45，v009 41/41，04 10/10，06 2/2，V15 2/2，V16 7/7；合计107项（重复执行不重复计数）。
- `common_literature_task` 使用原 v009 prepare、原 workload、期刊范围、研究问题、输入文件哈希和原输出 schema，经过 C01–C04 结构/归属/冻结校验。`chat-task` 与 `codex-task` 在相同阶段、相同输入下返回完全相同的 task_packet 与 task_snapshot；旧 Chat prompt 保留，native advance 派发前生成冻结任务包、实际仍调用原 v009 CLI。
- 四项新增测试：初查双入口一致、补查双入口一致且绑定初查材料/事件比较、非法阶段拒绝、native 派发保持原 CLI（替身阻断真实搜索）。未真实执行 Chat/Codex 在线检索；pre-literature Chat 对接、执行器身份与结果接收仍待 C06–C11 等任务。
