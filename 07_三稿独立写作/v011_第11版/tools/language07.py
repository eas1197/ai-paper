"""识别用户明确反对的表达，登记语料风格在稿件中的实际运用。"""
import re


RULES = (
    ("L01", re.compile(r"(?:这个|这一|上述)结果表明[，,]?"), "直接写发现及量级"),
    ("L02", re.compile(r"样本(?:能够|只能)辨认"), "用人群、组间对比和结果作主语"),
    ("L03", re.compile(r"不能把[^。！？\n]{1,45}(?:当成|读成|理解为|误读为)"), "直接交代变量口径或适用范围"),
    ("L04", re.compile(r"每升一级就增加多少|每升一级(?:就)?[^。！？\n]{0,23}剂量关系"), "说明比较的组与观测结果"),
)


def style_findings(text):
    findings = []
    for lineno, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if line.startswith("## ") and line[3:].strip() in ("参考文献", "附录"):
            break
        if not line or line.startswith(("#", "|", ">")):
            continue
        for rule_id, pattern, fix in RULES:
            for match in pattern.finditer(line):
                findings.append(dict(rule_id=rule_id, line=lineno, match=match.group(), action=fix))
    return findings
