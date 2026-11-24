# I17a doctor 静态合同与宿主登录探测边界

状态：implemented_unverified（离线子项待 CI，不计完成）。原 I17 的 I17b/c 真实环境验收继续按用户授权暂缓，GAP-F08 未关闭。

默认 doctor 仍执行原模块/九刊/数量/schema/hash 静态合同，仅报告 static_only；执行器、订阅登录、实时搜索均 not_checked，不运行任何 CLI 或网络。显式 doctor --probe-executor 使用原 11/v007 cli_executable、cli_environment、login_probe，通过原 v009 导入路径调用，只返回可枚举状态，不输出原诊断文本、凭证、用户路径，不执行搜索。即使原登录命令报告 ChatGPT 登录，也不能证明真实搜索或执行器就绪；live_search_verified / executor_ready_verified 始终 false。保留原 status 字段、默认调用、原研究门禁和预算。

新增3项离线测试：默认真实静态文件检查且无探测；显式探测的模拟结果（不证明真实宿主）；失败诊断隔离。真实登录 I17b 与真实一次合法搜索 I17c 尚未执行，原始 I17 未勾选；待实际环境与授权，不以模拟替代。
