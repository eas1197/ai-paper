# Chat 开发交接
先切换到开发入口，再读 AGENTS、CURRENT_STATE、WORKFLOW、RUNBOOK 和 NEXT_TASKS。通过 handoff_runs/manifest.json 定位历史运行、原路径、字节哈希和遗漏原因。历史输入和输出按原证据绑定解读。历史工具事件摘要只用于查阅，不能替代新调用凭证。Chat 维护研究、代码及计划；当前 Chat 会话的联网研究直接使用 ChatGPT 自带网页搜索，Windows Codex CLI 只负责其本地执行路径，Actions 执行无模型校验。真实独立学术审查须有可验证的独立执行者及回执，同一 Chat 会话内的自审不算独立审查。智谱是授权后使用的开发辅助，默认候选 glm-5.3-flash；免费 glm-4.7-flash 曾返回 429。密钥仅从本地 ZHIPUAI_API_KEY 读取。正式研究模型另行授权。
实验和云端研究状态分支的最新提交及共同祖先见 CURRENT_STATE。单模型探索稿和 process_log 在 experiment/single-model-paper-20261122 分支 research_outputs/；真实脚本及失败修复见 experiment/full-script-live-20261122。

## 最新恢复点
共享单车读取 plan_review_0 与 material_feasibility_closeout.json，保留原裁决和预算。数字互助读取已有 reality.json、event_comparison.json 与 resume_status.md，先修复独立会话启动，再继续，避免重新浏览已取得事件。

## Chat 原生研究模式（2026-11-22 用户指定）
此模式是当前 Chat 会话的实际执行方式，不是 Codex CLI 模拟层，也不改变生产注册表、候选阶段或既有学术门槛。研究者从当前真实检查点恢复。遇联网任务直接使用 ChatGPT 当前会话内置网页搜索；不调用项目 CLI 搜索器、不经 Python 发起搜索、不编写新爬虫，不额外使用付费 API。原 Codex 检索入口只在其本地模式继续有效。

每次搜索前读取对应阶段的项目规范、检索策略、期刊及来源范围、纳入与去重标准、数量目标，以及现有 run_manifest/dev_profile 剩余预算。记录搜索目的、三层议题定位、关键词策略、实际查询与网页阅读、来源 URL、作者/时间/题名、具体材料定位、原文短摘或摘要转述、证据边界、验证级别、重复合并关系和搜索调用/批次消耗；不能把发现 URL 当作已读摘要。允许学术需要驱动检索策略调整，但不得超预算、绕过学术关卡或人为充数。

Chat 搜索成果按现有研究资料字段和原 run_id 保存到 handoff_runs 与 manifest，逐条声明 `acquisition_mode=chat_native_web`、实际来源链接及检索/核验日期。Chat 没有产生的 Codex `web_search` 事件、`thread_id`、CLI 原始日志或 `invocation_id` 必须留空或标不可用，不能伪造、冒名或直接登记为 Codex 校验通过。Chat 原生检索与 CLI 调用动作不作虚假的一比一折算；实际搜索动作和预算口径一并记录，无法验证对应额度时保守停止。旧接收器若只认 CLI 凭证，保持该技术关卡待衔接，不为过关重新编造结果。

当前 `digital_mutual_aid_20261122` 的现实观察与事件比较已留存，状态仍为 `explanation_exchange`。先保留已有材料；若独立反诘会话在 Chat 不可用，记录 `tool_limitation` 并等待真实独立回执。不得将同一对话内的研究者自审作为 `critical_receipt` 或独立学术通过。后续由 Codex 依据同一原始检查点及归档记录接续，不重复有效检索。

## 数字互助 Chat 自主研究 2026-11-22 交接
实际运行成果保存在 `handoff_runs/digital_mutual_aid_20261122/chat_native_20261122/`，按 `研究全过程日志.md` → `文献检索矩阵.json` → `经验材料与分析矩阵.json` → `论文写作方案.md` → `Chat实验状态.json` 的顺序读取。总索引已更新SHA-256。当前为单模型真实网页检索加角色反诘的**探索性平行研究产物**，不是调用过原控制器各学术门禁的正式验收。源文件 `reality.json`、`event_comparison.json` 和 `staged_topic.json` 均未覆盖；正式恢复点仍是 `explanation_exchange`。文献数量10的原始阅读计数与期刊严格资格8分开；直接竞争郑州论文尚有索引阅读与全文查证差距。Codex接续须提供真正独立反诘证据、补足文献严选和材料交叉验证，不能把本次角色扮演当作 `critical_receipt` 或正式 `invocation_id`。
