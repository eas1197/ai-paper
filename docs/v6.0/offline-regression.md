# S08 离线接入回归

导入基线 3158f3e，接入提交 bcc0516。未发起模型调用。

实际运行 backup_3x_live_01 的冻结证据、独立终审原始事件与原 06 的 7 条初步材料已核验。方法为 online_qualitative / public_text，资格为 experimental。第七步状态 needs_review。缺框架、正式定向采集回执和原始记录、经验矩阵及独立矩阵审查。具体缺项见 backup_3x_live_01-status.json。

离线夹具覆盖定量 V14 原门禁与写作任务，覆盖定性原 06 回执重放、矩阵定位和经验写作任务。V14 最终重跑 12 项含 1 项跳过，v009 17 项、原 06 v005 2 项、文献 v012 3 项通过。V14 首次完整重跑出现一次 Windows 文件替换访问错误，随后同组重跑通过。

另跑现行定量 06 v004 的 19 项历史测试，1 项失败，13 项报错。阻塞包括环境缺少 statsmodels 和旧五刊资源锁不能通过。当前仓库 G6 使用 StatsmodelsEngine，可读取 Stata DTA。未发现现成 Stata 估计入口，未验证 Stata 执行或真实定量结果。
