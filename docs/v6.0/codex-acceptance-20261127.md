# Codex 接续验收检查点

日期 2026-11-27。基线 3a03df7e5eade3d34d5b5e55aad6bdc68d43838b。运行 v6_qual_live_20261127，沿用原实验清单，Stata 暂缓。

- 控制 v009 17 项、定性分析 v005 2 项、文献 v012 3 项、写作 V14 18 项。共 39 通过、1 跳过。第一次 Windows CRLF 检出触发 V14 资源锁异常，按 Git 原始字节重新检出后四组退出码均为 0。
- Codex CLI 0.171.0-alpha.13.2 使用既有 ChatGPT 登录。受限环境复现 Windows os error 5，授权只读探针返回 CODEX_V6_OK 和 turn.completed，退出码为 0。
- 真实联网调用产生 web_search 及 turn.completed，现实资料和两案比较已通过现有记录入口。案例来自英格兰地方监察专员公开决定 25-014-325 与 21-010-100。当前续跑点为 explanation_exchange，后续仍需独立反诘、S08、定向采集、矩阵审查、写作与复验。
- 原检查点和原始日志保存在本地运行目录。以下为本阶段文件哈希。
- "run_manifest.json" SHA-256 "37e0e541a7902324dba83a3140069fb37475953f44017c208d511a2aee9dc1de"
- "reality.json" SHA-256 "8dbaffd379b3d0d5f6fc5cc1aec4bd348ce9edcb93f98f145af657fa5348e4a9"
- "event_comparison.json" SHA-256 "c545b5428b1e2ef85b14993436df82495e9a5a25e6adea76187f9947246e5d86"
- "reality_retry_events.jsonl" SHA-256 "e8702d3bc2ca530d55d3c23f86a3d90fe213bdee18ae4050c1e828c222443828"

