# 当前唯一开发待办入口

唯一开发分支：`dev/v3.1-abstract-acquisition`；唯一5.0开发候选00/v012 strict。v009原研究引擎权威，v005生产不变。

[详细待完成事项总清单](00_项目控制/v012_第12版/待完成事项总清单.md) · [交接](HANDOFF.md) · [状态快照](CURRENT_STATE.md) · [运行规范](RUNBOOK.md)

每次刷新远端HEAD，仅执行当前任务；按实测证据独立验收、提交、同步总清单和下一指针。用户授权连续数量时逐项推进；遇阻塞如实记录，不计未验收。

---

# 当前唯一任务

1. **K05（当前唯一最小任务）**：记录初始代码 HEAD、模块版本、配置哈希和预算。
   - 状态：pending；核对K03实际执行HEAD和同run原manifest及原依赖版本/配置，禁止用当前HEAD替代。
   - 完成后：提交并转 K06。

**当前统计：** 原始203/253，合并208/258。A01–A06、B01–B13、B15–B25、C01–C24、C26–C30、D01–D14、D16–D21、D23–D29、E01–E06、E08、E10–E26、F01–F06、F08–F16、F18、F20–F23、G01–G13、G15–G20、G22、G25、H01–H08、I01–I02、I04–I16、I18–I22、J01–J20、K01–K04 verified；C25、D15、D22、D30、E07、E09、F07、F17、F19、G14、G21、G23、H09、I17 真实验收 deferred_by_user_instruction（不计数）；G24 正式授权 blocked（保留未完成）；G24a 补充离线任务 verified；I03 原始预算适用范围 blocked；I03a、I17a 补充离线任务 verified；K05 当前。B14-07/08 与 P 系列暂缓；GAP-F01 开放。

最近验收：[K04_同run执行范围与预算冻结](00_项目控制/v012_第12版/outputs/K04_同run执行范围与预算冻结.md)；K04 verified（同run授权执行合同冻结，绑定原run_manifest SHA256 aa125a3a43aac8eb972ea77b3370b30bc8ba22db58a83d2c696143c54df20d03；原dev 5+5、九刊、三层定位、3批/24动作原规则；Chat/Codex来源与独立审查分离；I03不扩大；写作plan保持原政策；不执行检索或S08）。

## 历史与阻塞说明

详细验收、暂缓和blocked项目见总清单对应行。GAP-F01/F08保留开放，真实宿主、真实独立审查、正式授权及P系列依此前指令暂缓或阻塞；不重复执行已经验收的事项。v010/v011历史路线不再作为待办执行入口。

旧待办全文（含历史运行恢复、验收记录和旧路线）保留在 [J12之前的Git快照](https://github.com/eas1197/ai-paper/blob/7b810d1feb386c7c69362947375051a5b8174c46/NEXT_TASKS.md)，仅供追溯；历史运行按 [handoff manifest](handoff_runs/manifest.json) 查验，不算新执行。
