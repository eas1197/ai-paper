# E02：统一 CLI 任务入口

状态：verified（离线统一 CLI）。strict parser 提取 build_parser；新增 commands（实际 parser 枚举、无运行）、prepare（只读委托原 v009 prepare）、autopilot（显式调用内部原调度器共享 run_autopilot）。原单独脚本 main 仅保留兼容，使用同一执行函数；原循环上限、原门禁、原恢复检查及模型/timeout 参数不变。现有21个命令保留，新增3个，用户入口共24。模块说明改为统一命令。新增4项离线测试：命令查询无副作用、真实参数委托、原阻断状态透传、原失败退出2；等待CI，不执行真实模型。

实际验收：[strict CI 45340167224](https://github.com/eas1197/ai-paper/actions/runs/45340167224)，job 138261632267 success；新增4/4，v012 261/261，原模块63/63，共324项。原调度边界保持，未实际启动模型。
