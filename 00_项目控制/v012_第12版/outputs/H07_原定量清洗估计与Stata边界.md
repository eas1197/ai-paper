# H07 原定量清洗、估计与Stata边界

状态：verified（只读合同），基线 a72bb392c9baa921179b49679d35895c8898edd3。原定量代码未改、没有执行数据或Stata。

- data_adapters.py：DTA使用pyreadstat元数据（pandas受保护标签映射回退），pandas read_stata按列读取，Stata系统及扩展缺失明确掩码；SAV依赖缺失拒绝；CSV需绑定代码本。合并仅left/inner、1:1/m:1/1:m；拒绝空键及非键冲突；输出匹配计数。
- pipeline06.py：仅冻结的identity/recode/log/log1p/square，重编码须覆盖非缺失值，对数定义域不符失败；拒绝任意Python/Stata/R代码；样本筛选eq/ne/ge/gt/le/lt/in，缺失不进入ne。共同或逐模型完整案例、种子、全部预定模型和失败日志保留；不按p值筛选，不输出个案。
- engines.py：原内置StatsmodelsEngine，OLS、二元Logit、Poisson、NB、ZIP、ZINB、有序/多项Logit八类；冻结类别参照、交互及设计矩阵，秩亏不自动删变量；二元结局0/1、计数非负整数、exposure正值，SE nonrobust/HC1/HC3/cluster，复杂抽样/插补须可信专用提供方；不冒充Stata pweight。保留估计尺度、收敛、警告和诊断。
- stage06 原执行协议先锁定并复核、主分析后变更设计须转探索性；独立重读重估对照结果、样本流、失败及数值容差，G6 approve 仍需研究复核（见H01）。技术依据.md记录旧本机软件版本，不视为本次运行。
- 原路径所需目录的树清单未见.do脚本或Stata执行入口；实际默认是Python读取Stata格式并使用statsmodels，不把DTA读取当Stata运行。保留将来可信定量提供方的原接口，不新增Stata命令或改写模型。H09真实分析依用户另行授权。

依据：06/v004 tools/data_adapters.py、pipeline06.py、engines.py、stage06.py及技术依据.md；原数据契约。转H08。
