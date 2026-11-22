# 当前状态
唯一开发入口：`dev/v3.1-abstract-acquisition`。`main` 及 v005 注册表属于生产历史基线。读取 [运行索引](handoff_runs/manifest.json) 和 [技术接续](NEXT_TASKS.md)。

| 远端引用 | 审计时提交 | 与开发入口共同祖先 | 提交主题 |
| --- | --- | --- | --- |
| origin/backup/pre-glm-integration-20261122 | 231f9eb5ca01f25f9ca11085bc4695f6e725f9a4 | 231f9eb5ca01 | Separate academic and local revisions and add development API adapter |
| origin/dev/glm-api-adapter-20261122 | e91ef327daebe84ed0da14bad9a331ed400cb4b2 | 231f9eb5ca01 | feat: add bounded opt-in GLM API adapter and smoke test |
| origin/dev/v3.1-abstract-acquisition | 231f9eb5ca01f25f9ca11085bc4695f6e725f9a4 | 231f9eb5ca01 | Separate academic and local revisions and add development API adapter |
| origin/experiment/full-script-live-20261122 | 9a0292ba2a007be015c96748787dcc929f05d759 | 231f9eb5ca01 | Install missing bs4 and rerun exact registered literature entry point |
| origin/experiment/offline-smoke-20261122 | 08cf37701fdc7a0c1f2611e363e53cd4b7077477 | 231f9eb5ca01 | ci: test unreviewed metadata-only matrix correction against real archived evidence |
| origin/experiment/persistent-topic-20261122 | 6018913fe5d8723cf0dcf5c4d586084b8623b0eb | 231f9eb5ca01 | docs: clarify non-default branch workflow rerun trigger |
| origin/experiment/single-model-paper-20261122 | 01b287ba4dab4623d5b3a316424eaa877acd010c | 231f9eb5ca01 | docs: append final CI run, delivery validation and provenance to process audit |
| origin/main | 8971798289a424f8bd2c47f56735525e3f34d53e | 8971798289a4 | Revise v3.1 design for autonomous paper research and writing |
| origin/research-state/topic-20261122 | b2a860fff6ccfbd13041f1d7f7f862a02265b961 | 231f9eb5ca01 | checkpoint: bike_fresh_20261122 next-stage source records and hashes |

候选依赖为 v007 实验总控、v008 选题任务、v009 分阶段控制、04/v012 原生文献、11/v007 采集、06/v005 定性材料与矩阵、07/v015 写作方案。正式模块逐项查看 v005 注册表。共享单车已冻结、完成十篇文献及探索矩阵，方案已生成，独立审查要求修订，未完成正式写作验收。云端单模型稿、云端持久化、离线 smoke 和真实脚本试验分别保留在各自分支，未合并为正式能力。
