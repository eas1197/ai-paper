"""Check author-led narration and other disallowed prose patterns."""
import re


RULES = (
    ("L01", re.compile(r"(?:这个|这一|上述)结果表明[，,]?"), "直接写发现及量级"),
    ("L02", re.compile(r"样本(?:能够|只能)辨认"), "用人群、组间对比和结果作主语"),
    ("L03", re.compile(r"不能把[^。！？\n]{1,45}(?:当成|读成|理解为|误读为)"), "直接交代变量口径或适用范围"),
    ("L04", re.compile(r"每升一级就增加多少|每升一级(?:就)?[^。！？\n]{0,23}剂量关系"), "说明比较的组与观测结果"),
    ("L06", re.compile(r"(?:本文|本研究|这|上述发现)?并(?:不是说|不意味着|非主张|不否认)[^。！？\n]{0,28}(?:也并(?:不意味着|不是说|非说明))?|但这只是推测|这个解释(?:没法|无法)证明|因此无法证明"), "直接提出判断并将适用范围自然融入论证，避免防御性自我反驳"),
)

THEORY_AUTHORS = {"费孝通", "韦伯", "马克斯·韦伯"}
THEORY_TOPIC = re.compile(r"理论|概念|框架|理想类型|差序格局|乡土社会|科层制|理性化|社会行动")
REFERENCES = re.compile(r"^\s*#{1,6}\s*(?:参考文献|References|Bibliography)\s*$", re.I)
BACK_MATTER = re.compile(r"^\s*#{1,6}\s*(?:附录|参考文献|References|Bibliography)(?:\s|$)", re.I)
REFERENCE_AUTHORS = re.compile(
    r"^\s*(?:[-*]\s+|\[\d+\]\s*|\d+[.)、]\s*)?\s*"
    r"([\u4e00-\u9fff·、，,；;\s]+?)"
    r"(?:[，,（(]\s*(?:18|19|20)\d{2}|[.．]\s*)"
)
CHINESE_NAMES = re.compile(r"[\u4e00-\u9fff·]{2,10}")
PARENTHESES = re.compile(r"（([^（）]*)）|\(([^()]*)\)")
YEAR = re.compile(r"(?<!\d)(?:18|19|20)\d{2}[a-z]?(?!\d)", re.I)
CITATION = re.compile(
    r"^(?:见|参见|另见)?\s*(?:[\u4e00-\u9fff·A-Za-z.\s&、，,]+?\s*[,，]?\s*)?"
    r"(?:18|19|20)\d{2}[a-z]?(?:\s*[:：,，]\s*\d+(?:[—–-]\d+)?)?$", re.I
)
REPORTING = r"(?:说|指出|认为|发现|提出|表明|写道|报告|的(?:一项)?(?:研究|分析|调查|文章|论文))"
SURNAME = r"(?:欧阳|司马|上官|诸葛|[赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦许何吕张孔曹严华金魏陶姜谢邹喻柏窦章云苏潘葛范彭韦马方任袁柳鲍史唐薛雷贺倪汤罗毕郝安常傅齐康伍余顾孟黄萧尹姚邵汪祁朴乔邱段陆洪宋蔡田胡凌霍柯晏席谭江童颜郭梅林徐钟高夏梁杜程肖刘邓董蓝白石俞侯邵姜文崔曾翟费贾牛覃骆易向温廖祝])"
UNLISTED_AUTHOR = re.compile(
    rf"^\s*(?:\*\*)?(?:在|根据|据)?(?P<name>某某|{SURNAME}[\u4e00-\u9fff]{{1,3}}?)"
    rf"(?:等(?:人)?)?\s*(?:[（(](?:18|19|20)\d{{2}}[a-z]?[）)])?\s*{REPORTING}"
)
NOT_PERSON = {"作者", "佚名", "课题组", "编辑部", "现有", "已有", "前人"}


def citation_content(match):
    body = match.group(1) if match.group(1) is not None else match.group(2)
    if YEAR.search(body) and all(CITATION.fullmatch(part.strip()) for part in re.split(r"[；;]", body)):
        return body
    return None


def split_prose(text):
    lines = text.splitlines()
    end = next((i for i, line in enumerate(lines) if BACK_MATTER.match(line)), len(lines))
    return [(i, line.strip()) for i, line in enumerate(lines[:end], 1)
            if line.strip() and not line.lstrip().startswith(("#", "|", ">"))]


def cited_names(text, prose):
    lines = text.splitlines()
    references = next((i for i, line in enumerate(lines) if REFERENCES.match(line)), len(lines))
    names = set(THEORY_AUTHORS)
    for line in lines[references + 1:]:
        if line.lstrip().startswith("#"):
            break
        match = REFERENCE_AUTHORS.match(line)
        if match:
            names.update(CHINESE_NAMES.findall(match.group(1).replace("等", "")))
    for _, line in prose:
        for match in PARENTHESES.finditer(line):
            if body := citation_content(match):
                for part in re.split(r"[；;]", body):
                    prefix = YEAR.split(part, maxsplit=1)[0].strip().removeprefix("参见").removeprefix("另见").lstrip()
                    names.update(CHINESE_NAMES.findall(prefix.replace("等", "")))
    return {name for name in names - NOT_PERSON
            if len(name) <= 4 or "·" in name or name in THEORY_AUTHORS}


def author_findings(text, prose):
    names = cited_names(text, prose)
    known = re.compile("|".join(re.escape(name) for name in sorted(names, key=lambda n: (-len(n), n))))
    for number, line in prose:
        visible = PARENTHESES.sub(lambda match: " " if citation_content(match) else match.group(), line)
        for body in re.split(r"[。！？；;]", visible):
            unlisted = UNLISTED_AUTHOR.match(body)
            matches = set(known.findall(body))
            if unlisted:
                name = unlisted.group("name")
                if name not in NOT_PERSON:
                    matches.add(name)
            for name in sorted(matches):
                if name in THEORY_AUTHORS and THEORY_TOPIC.search(body):
                    continue
                yield dict(rule_id="L05", line=number, match=name,
                           action="先写研究对象、比较或发现，普通作者姓名随出处放进括号引文")


def style_findings(text):
    prose = split_prose(text)
    findings = [dict(rule_id=rule_id, line=lineno, match=match.group(), action=fix)
                for lineno, line in prose for rule_id, pattern, fix in RULES
                for match in pattern.finditer(line)]
    return findings + list(author_findings(text, prose))
