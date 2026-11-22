# 运行手册
Python 3.11。离线运行 `python .github/scripts/verify_handoff.py`，以及 `python -m unittest discover -s "00_项目控制/v009_第9版/tests"`。06/v005、07/v015 同样使用 unittest discover。离线工作流安装 beautifulsoup4，实际研究入口的其他依赖按模块说明。Actions 仅测试与回放，产物保留 14 天。长期制品放 handoff_runs。
本地恢复前核对运行 ID、注册表、输入和回执哈希。候选入口 staged_topic.py 的 prepare/advance/status 用于选题接续；定性材料和框架走 06/v005 qual_materials.py；冻结后定性写作走 resume_writing.py。需要实际网页调用时依赖已授权 Codex CLI、订阅、网络及本地配置；定量使用相应数据和 Stata 等所需工具。归档中脱敏条目不能直接替换原始凭证，严格校验需要在合法保有原件的环境按原路径恢复。Actions 不继承本地登录、Windows 工具和个案数据。
