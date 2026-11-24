# C06｜Chat 原生网页执行器规范

状态：verified（文档合同，2026-11-24；与远端原实现核对，不代表真实在线执行）。

## 标识与边界
- 唯一执行器类型：chat_native_web；现有 ai_paper5_strict.py 的 chat_task/audit_chat 使用 source_mode=chat_native_web，profile=original_v3.2。
- Chat 任务由当前实际可用网页工具执行。可记录实际查询文本、搜索返回来源/标题/URL、实际页面打开或查找操作、返回的可见内容及定位、可见引用标识、访问失败/登录墙等。仅记录实际工具返回；工具没有提供的字段为缺失，不编造。
- 搜索结果发现不等于页面打开；打开不等于摘要或全文实读。仅在实际可见摘要/正文时记录短摘与定位；搜索摘要片段不能冒充原文。引用标识只在原会话可核对时有效，不等于持久、可独立认证的事件凭证。
- 允许保存真实工具结果的用户可见记录或合法导出文件（如环境确实支持），必须注明来源和取得方式；Chat 自述、手工 JSON 或转录不能证明原始工具调用真实发生。缺乏独立可核对凭证时保留 pending。
- 禁止填造 Codex command/thread/events.jsonl/event ID、原始文件哈希、独立审查身份；不把 Chat 引用编号转换成 Codex 原始事件。
- 当前 audit_chat 仍只做原 v3 结构、期刊、作者年份、HTTPS、摘要定位、相关性、摘录长度及去重检查；返回 pending_independent_url_and_abstract_provenance，native_cli_receipt=false、formal_eligible=false。不得因本规范改变正式准入。

## 静态验收
核对源文件 tools/ai_paper5_strict.py 的 chat_task、audit_chat：标识一致、原始证据边界及 pending/false 返回一致。未运行真实检索，未修改执行器或研究规则。后续 C07–C11 分别定义其他执行器与统一结果身份合同。
