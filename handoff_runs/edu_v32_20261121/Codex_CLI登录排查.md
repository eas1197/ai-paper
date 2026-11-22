# Codex CLI 登录诊断与恢复

此前 20 篇验收记录使用 Codex CLI 0.171.0-alpha.13，登录状态为 `Logged in using ChatGPT`，运行产生原生 `web_search` 事件。本次桌面子进程使用同版本，`USERPROFILE`、`HOMEDRIVE`、`HOMEPATH` 均存在，默认 PATH 找不到 Codex，且没有继承 `CODEX_HOME`。此前验收记录没有逐项环境快照，不能据此还原当时全部环境变量。

同一个桌面安装目录中的 `codex.exe` 运行 `login status`，原环境退出 1，stdout 为空，脱敏 stderr 为：

```text
WARNING: proceeding, even though we could not create PATH aliases: Could not find home directory
Error loading configuration: Could not find home directory
```

仅向子进程传入指向现有用户配置目录的 `CODEX_HOME` 后，登录状态退出 0，并确认使用 ChatGPT。受限环境仍无法写入 CLI 状态目录，`exec` 会退出 1；通过系统授权运行时，最小真实搜索退出 0，记录 1 个原生 `web_search` 事件，返回 [《人口研究》官网](https://rkyj.ruc.edu.cn/)。

修复在 PATH 缺失时查找桌面安装；保留显式 `CODEX_HOME`，Windows 缺省时使用已存在的用户配置目录。登录验收仍要求退出 0 和肯定的 ChatGPT 登录标志，容忍大小写、空白、ANSI 样式和句末标点。登录状态的正向文字原本能够匹配，本次根因是 CLI 在读取配置前就退出，并未产生这行文字。真实退出码和脱敏 stdout、stderr 单独落盘，旧验证凭证格式保持。

恢复仅迁移与旧实现指纹相符、没有启动网页搜索、没有收录任何数据的登录失败检查点。原第 1 批保留，失败预检不占一次真实检索预算。恢复不修改研究主题配置、问题版本或查询策略，沿用实验清单的 10 篇目标。没有复制凭据，继续使用现有订阅。

恢复后的 `batch_002` 已完成，登录退出 0，程序记录 6 个原生搜索事件，按冻结的宽主题“教育”收录 4 条去重摘要记录，其中 2 条短摘可从工具记录直接定位。4 条均围绕教育分层或教育机会，未建立与 Q1 家校沟通及学校回应的实质相关性，不计为 Q1 的文献成果。本轮消耗了冻结配置允许的一批真实检索，停在 4/10、`incomplete`；未修改预算或检索策略。已有 Q1 选题仍保留。4 项自动化测试通过。
