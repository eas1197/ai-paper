# C20 Codex 原始执行凭证接收

状态：verified（离线接收合同，2026-11-24）。

- 代码提交：0ba0672a50f4d94b7b4d067aacf24bc999f08b4e
- [CI](https://github.com/eas1197/ai-paper/actions/runs/45322697084)；strict run `45322697084` job `138204762776` success；C20新增3/3，v012 78/78，其他62项通过；合计140项（不重复计数）。
- 新增 codex-receive 入口与 codex_receiving.py：实际文件/快照及独立绑定、thread.started、原 11/v007 evidence/proof/web_url、登录诊断、命令记录及只读参数/路径核对、来源 URL 与原生事件匹配。旧记录未保存真实 argv 时仍 pending，不补造。独立绑定且完整记录才能标记 native_cli_receipt；仍 formal_eligible=false。
- 三项离线定向测试覆盖完整匹配、缺命令/错 thread、错误命令/不匹配来源；未真实 CLI 运行，不改原采集器。C21 再接入原权威门禁。
