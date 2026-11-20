# 技术验证

在项目根目录运行：

    python -m unittest discover -s "06_数据方法与分析/v002_第2版/tests" -p "test_*.py" -v

测试只使用临时合成数据、TEST文献与模拟PDF；真实CFPS/CGSS与Zotero原始目录不写入、不读个案。涵盖独立OLS解、计数/分类模型、特殊缺失/标签、合并键、冻结/复算/复核/导出/失效链及外键。

模拟PDF读取器只在测试patch中注入；生产默认PdfReader验证真实PDF，不能把TEST资料作为论文证据。成功仅说明程序行为，不能证明任何正式研究的G6通过。
