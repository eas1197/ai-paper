# 联合程序测试

在项目根执行：

```powershell
python -m unittest discover -s .\04_议题文献与现实\v004_第4版\tests -v
```

测试全部使用TemporaryDirectory内的TEST夹具，run路径也在测试内替换，不读取真实Zotero或调查个案数据。TestPdfReader只解析明确标记的TEST假文件以隔离状态机测试；生产默认PdfReader使用pdfplumber验证真实PDF。夹具里的100摘要/25全文仅用于关卡分支测试，不能计作任何科研成果。

覆盖：JSON/CSV/RIS/Zotero导入、Zotero只读且连接释放、传递去重与ID持久化、冲突隔离、两步正向放行和设计冻结、无材料时不误通过、原文和页码绑定、完整阅读计数、错误PDF、重复PDF、推断循环、旧新闻、模型未验证提案与调用上限、同层级桥接、问卷补造拦截、事后假设拦截、输入变更、新attempt、并发锁、上游失效及导出限制。
