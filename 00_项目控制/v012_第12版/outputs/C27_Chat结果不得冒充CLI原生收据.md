# C27 Chat 结果不得冒充 CLI 原生收据

状态：verified（离线负向合同，2026-11-24）。

- 最终代码提交：`bf74fdb8cacb25b124188c8f0f5fe146e78a1d97`
- [strict CI](https://github.com/eas1197/ai-paper/actions/runs/45326144115)：strict run `45326144115` job `138216092458` success；C27 新增1/1，v012 96/96，其他62项通过；合计158项（不重复计数）。
- 以 Chat 结果为输入调用原 v009 文献接收路径，必须保持 `original_gate_status=pending_original_native_receipt`、`native_cli_receipt=false`、`original_abstract_eligible_ids=[]`、`original_verified_rows=null`、`stage_advanced=false`。
- 负向修改1：在 Chat 结果顶层注入 `native_cli_receipt=true`，Schema `additionalProperties=false` 拒绝。
- 负向修改2：将 `executor` 改为 `codex_cli` 但保留 `chat_native_web` provenance，executor 条件 Schema 拒绝。
- 最终 fixture 检查未生成 `initial/literature_matrix.json`，原阶段状态保持 `initial`。这是离线伪造防护，不等于真实 Chat/CLI 执行。
- 初次 CI 发现测试 fixture 漏掉 `setup_ref()`，已修正；最终 CI 全部通过。
