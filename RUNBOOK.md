# 运行手册
Python 3.11。离线运行 `python .github/scripts/verify_handoff.py`，以及 `python -m unittest discover -s "00_项目控制/v009_第9版/tests"`。06/v005、07/v015 同样使用 unittest discover。离线工作流安装 beautifulsoup4，实际研究入口的其他依赖按模块说明。Actions 仅测试与回放，产物保留 14 天。长期制品放 handoff_runs。
本地恢复前核对运行 ID、注册表、输入和回执哈希。候选入口 staged_topic.py 的 prepare/advance/status 用于选题接续；定性材料和框架走 06/v005 qual_materials.py；冻结后定性写作走 resume_writing.py。需要实际网页调用时依赖已授权 Codex CLI、订阅、网络及本地配置；定量使用相应数据和 Stata 等所需工具。归档中脱敏条目不能直接替换原始凭证，严格校验需要在合法保有原件的环境按原路径恢复。Actions 不继承本地登录、Windows 工具和个案数据。

数字互助读取 handoff_runs/digital_mutual_aid_20261122。真实试跑的子会话启动异常属工具限制，提交独立反诘必须使用真实可执行会话及原有研究包。脱敏归档仅可读取和回放，直接恢复需要受控环境中的原凭证。

## Chat 会话实际研究运行（不调用 CLI 搜索器）
1. 从 `CURRENT_STATE.md`、`handoff_runs/manifest.json` 和现有 run 检查点恢复，先读该阶段规范、冻结的数量/纳入规则、`search_policy.json` 和 run `workload`。不可把历史试跑重算为本次新检索。
2. 需要新联网证据时，在本对话调用 ChatGPT 内置网页搜索，自主决定对象、议题、理论三层检索及交叉核实。严格区分查得题录、打开摘要、阅读全文、二手访谈及事实核验；未知项保持未知。
3. 真实结果按已有数据结构的可复用字段记录，附 `chat_native_web` 来源说明、原始 URL、日期、定位、片段与边界、去重关系和实际搜索动作/阶段预算。程序特有的 CLI 事件字段不予伪造。实验模式、返修次数、材料适足性及学术失败分流仍然生效。
4. 本对话不能以同一上下文自审代替独立反诘或独立学术审查；若缺独立执行凭证，保留运行状态与待办并标记工具能力限制，不触发后续正式关卡。新增成果只追加归档，更新 manifest 与根交接；归档原始已核查来源，测试与科研质量验收分别标记。
5. Chat 模式不意味着 GitHub Actions 可以直接调用本聊天搜索。后续原 CLI 运行及其形式化接收器继续适用自身原生凭证校验；没有真实对应凭证的 Chat 成果需保持待衔接状态。

## ai-writer 4.0定性写作候选
当前入口 `07_三稿独立写作/v016_第16版/tools/ai_writer4.py`，完整说明见模块说明。以V15写作任务JSON为输入，执行 `route --packet 文件`、`prepare --packet 文件 --workspace 新空目录 --mode exploratory`、`submit --packet 文件 --workspace 同目录 --manuscript 正文.md --claims 主张证据台账.json`。本次用户现有示例位于 `handoff_runs/digital_mutual_aid_20261122/chat_native_20261122/writing/`。离线测试 `python -m unittest discover -s '07_三稿独立写作/v016_第16版/tests' -v`，无模型调用；GitHub Actions `.github/workflows/ai-writer4-offline.yml` 只进行离线检查。两个来源都要保留原始哈希及现有审查状态；源码提交不等于自动起草与正式G7运行。本聊天写作仅作探索性A稿和样本语言修订，不接管原研究冻结检查点。

ai-writer 4.0现也通过实验总控显式入口 `run_mode.py --mode dev --run-id <有效实验> --writer4 route|prepare|submit <对应参数>` 调用。该添加仅针对定性writer4试验，其他`--topic`、`--writing-plan`、定量及formal逻辑保持原样。真实实验运行目录不得用脱敏GitHub归档冒名替换。
