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
    return findings + author_findings(text)

# Conventional attributions stay in parenthetical citations. These names may
# serve as sentence subjects when the text is explaining their own theory.
THEORY_AUTHORS = {"费孝通", "韦伯", "马克斯·韦伯"}
REFERENCES = re.compile(r"^\s*#{1,6}\s*(?:参考文献|References)\s*$", re.I)
AUTHOR_HEADER = re.compile(r"^\s*(?:[-*]|\[\d+\]|\d+[.)、])?\s*(.+?)[，,（(]\s*(?:18|19|20)\d{2}")


def author_findings(text):
    lines = text.splitlines()
    end = next((i for i, line in enumerate(lines) if REFERENCES.match(line)), len(lines))
    authors = set()
    for line in lines[end + 1:]:
        match = AUTHOR_HEADER.match(line)
        if match:
            names = re.split(r"[、，,；;]", match[1].replace("等", ""))
            authors.update(name.strip() for name in names if re.fullmatch(r"[一-鿿·]{2,10}", name.strip()))
    authors.difference_update({"作者", "佚名", "课题组", "编辑部"})
    findings = []
    for number, line in enumerate(lines[:end], 1):
        if not line.strip() or line.lstrip().startswith(("#", "|", ">")):
            continue
        prose = re.sub(r"（[^（）]*）|\([^()]*\)", "", line)
        for name in sorted(authors - THEORY_AUTHORS):
            if name in prose:
                findings.append(dict(rule_id="L05", line=number, match=name,
                                     action="用研究对象、比较或发现领句，普通作者姓名移入括号引文"))
    return findings
