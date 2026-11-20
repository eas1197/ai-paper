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


def check_application(records, text, style_ids, errors):
    from manuscript07 import HEADING

    required = set()
    headings = list(HEADING.finditer(text))
    top = [section for section in headings if section[1] == "##"]
    for index, section in enumerate(top):
        name = section[2].strip()
        if name in ("参考文献", "附录") or name.startswith("附录"):
            break
        end = top[index+1].start() if index+1 < len(top) else len(text)
        required.add(name)
        report = records.get(name, {})
        anchor = report.get("text")
        applied = report.get("style_ids")
        note = report.get("application")
        if (not isinstance(anchor, str) or not anchor.strip() or anchor not in text[section.end():end]
                or not isinstance(applied, list) or not applied or not set(applied) <= style_ids
                or not isinstance(note, str) or not note.strip()):
            errors.append(f"{name}: 须定位本节实际表达，说明运用了03语料的哪项风格及如何运用")
    for name in sorted(set(records) - required):
        errors.append(f"语言审查位置不在实际摘要或正文中: {name}")
