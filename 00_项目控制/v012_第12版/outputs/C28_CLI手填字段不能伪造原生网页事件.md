# C28 CLI 手填字段不能伪造原生网页事件

状态：verified（离线负向合同，2026-11-24；非真实 CLI 运行验收）。

- 最终代码提交：`ec3780b69144ab25b7ecceb8bc1fc9db0ee63a3f`
- [strict CI](https://github.com/eas1197/ai-paper/actions/runs/45326485614)：strict run `45326485614` job `138217206004` success；C28 新增1/1，v012 97/97，其他62项通过；合计159项（不重复计数）。
- fixture 保留完整手填 normalized `search_actions`、source `action_ids`、成功登录字段、命令 argv、零退出码，并使 invocation record 与当前任务/原始文件完全匹配；但 events.jsonl 只有 `thread.started`，没有原生网页事件。
- 结果：`command_record_matched=true` 但 `native_event_count=0`、`native_cli_receipt=false`、`acceptance_status=pending_candidate`；原 v009 接收返回 `pending_original_native_receipt`，无 `original_abstract_eligible_ids`、无 `original_verified_rows`、不推进阶段、不生成 literature_matrix。
- 另外向结果包手填 `native_cli_receipt=true` 被 Schema 的额外字段规则拒绝。
- 此为离线伪造防护；没有执行真实 Codex CLI，也不替代 C25。
- 首次运行发现 NDJSON fixture 误写成字面 `\\n`，已修正为真实行分隔符；最终 CI 成功。
