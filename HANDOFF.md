# Chat 开发交接
先切换到开发入口，再读 AGENTS、CURRENT_STATE、WORKFLOW、RUNBOOK 和 NEXT_TASKS。通过 handoff_runs/manifest.json 定位历史运行、原路径、字节哈希和遗漏原因。历史输入和输出按原证据绑定解读。历史工具事件摘要只用于查阅，不能替代新调用凭证。Chat 维护代码及计划，Actions 执行无模型校验，现有 Windows Codex CLI 负责支持的原生搜索，GPT-6.2 Sol 负责独立学术审查。智谱是授权后使用的开发辅助，默认候选 glm-5.3-flash；免费 glm-4.7-flash 曾返回 429。密钥仅从本地 ZHIPUAI_API_KEY 读取。正式研究模型另行授权。
实验和云端研究状态分支的最新提交及共同祖先见 CURRENT_STATE。单模型探索稿和 process_log 在 experiment/single-model-paper-20261122 分支 research_outputs/；真实脚本及失败修复见 experiment/full-script-live-20261122。
