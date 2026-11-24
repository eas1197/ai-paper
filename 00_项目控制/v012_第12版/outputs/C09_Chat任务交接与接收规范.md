# C09｜Chat 任务交接与接收边界

状态：verified（文档合同，2026-11-24；不代表真实运行）。

- 在原阶段门禁允许时执行 ai_paper5_strict.py chat-task --run-id <id> --phase initial|supplemental --output <task.json>；得到 C05 共用 task_packet/task_snapshot 和原 Chat prompt。
- 通过真实用户/宿主交接交给当前可使用网页工具的 ChatGPT 会话。会话读取冻结任务和预算，按原三层策略真实搜索、打开，保存可取得的来源/定位/失败记录。工具或权限不可用时标明阻塞。
- 将可取得的原始记录及原 schema response.json 交回接收流程；现有 chat-audit --task <task.json> --response <response.json> --output <audit.json> 只作候选结构审计。不得复制为 Codex events.jsonl 或称为独立审查。
- Python/GitHub Actions 能生成、保存、校验、等待任务文件，不具备直接唤醒当前 ChatGPT 内置搜索、读取任意会话原始工具日志或取得独立审查的能力。不新增虚假 API/宿主调用。
- 任务变更按 C04 重新冻结；当前接收器接入快照校验仍待 C15/C19。

## 验收
核对实际 chat-task/chat-audit 参数和 C06 pending 边界；静态交接规范通过，未调用真实 Chat 搜索。
