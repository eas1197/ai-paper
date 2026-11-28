"""Rebuild TWO deliverable Word files from a frozen, sourced single-model study.

The script is a deterministic export/validation step, not an LLM runtime or an
independent academic review. All role outputs are disclosed as one model.
"""
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT=Path(__file__).resolve().parents[2]
RESEARCH=ROOT/"research_outputs/bike_paper_single_model_20261122"

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def parts(text):
    lines=text.splitlines()
    i=0
    while i<len(lines):
        l=lines[i].rstrip()
        if not l:
            i+=1; continue
        if l.startswith("|") and i+1<len(lines) and lines[i+1].startswith("|"):
            table=[]
            while i<len(lines) and lines[i].startswith("|"):
                row=[x.strip() for x in lines[i].strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?",x) for x in row):
                    table.append(row)
                i+=1
            yield "table",table
            continue
        if l.startswith("# "): yield "title",l[2:]
        elif l.startswith("### "):yield "h2",l[4:]
        elif l.startswith("## "):yield "h1",l[3:]
        elif l.startswith("- "):yield "bullet",l[2:]
        else:yield "p",l
        i+=1

def add_marked(p,text):
    for bit in re.split(r"(\*\*[^*]+\*\*)",text):
        if not bit: continue
        emph=bit.startswith("**") and bit.endswith("**")
        run=p.add_run(bit[2:-2] if emph else bit)
        run.bold=emph

def make_doc(source,target,kind):
    doc=Document()
    sec=doc.sections[0]
    sec.top_margin=sec.bottom_margin=Cm(2.4)
    sec.left_margin=sec.right_margin=Cm(2.5)
    body=doc.styles["Normal"]
    body.font.name="Noto Serif CJK SC";body.font.size=Pt(10.5)
    body.paragraph_format.line_spacing=1.4
    body.paragraph_format.space_after=Pt(4)
    body.paragraph_format.first_line_indent=Cm(.72)
    for name in ["Title","Heading 1","Heading 2"]:
        st=doc.styles[name];st.font.name="Noto Sans CJK SC";st.font.bold=True
        st.paragraph_format.keep_with_next=True
    h=sec.header.paragraphs[0];h.alignment=WD_ALIGN_PARAGRAPH.RIGHT
    h.add_run("单模型多角色研究 · "+kind)
    f=sec.footer.paragraphs[0];f.alignment=WD_ALIGN_PARAGRAPH.CENTER
    field=OxmlElement("w:fldSimple");field.set(qn("w:instr"),"PAGE");f._p.append(field)
    for k,v in parts(source.read_text(encoding="utf-8")):
        if k=="table":
            t=doc.add_table(rows=0,cols=max(map(len,v)))
            t.style="Light Shading Accent 1"
            for row in v:
                cells=t.add_row().cells
                for i,x in enumerate(row):
                    cells[i].text=x
                    for p in cells[i].paragraphs:
                        p.paragraph_format.first_line_indent=Cm(0)
            continue
        name={"title":"Title","h1":"Heading 1","h2":"Heading 2","bullet":"List Bullet"}.get(k)
        p=doc.add_paragraph(style=name)
        if name in ("Title","Heading 1","Heading 2"):
            p.paragraph_format.first_line_indent=Cm(0)
        if k=="title":p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        if k=="p" and re.match(r"^\[\d+\]",v):
            p.paragraph_format.first_line_indent=Cm(0)
        add_marked(p,v)
    doc.core_properties.author="ChatGPT 单模型多角色研究"
    doc.save(target)

def validate(paper,log):
    p=paper.read_text(encoding="utf-8");l=log.read_text(encoding="utf-8")
    a,b=p.split("## 参考文献与资料来源",1)
    for i in range(1,9):
        assert f"[{i}]" in a and f"[{i}]" in b, f"Missing citation {i}"
    assert len(re.findall(r"^\[\d+\]",b,flags=re.M))==8
    assert sum(t in p for t in ["一、问题的提出","二、已有研究","三、资料来源","四、经验分析","五、讨论","六、结论"])==6
    for name in ["现实观察角色","材料比较角色","解释建构角色","反方批评角色","文献审计角色","方法与研究设计角色","写作角色","事实和论证复核角色"]:
        assert name in l
    assert "不具备独立性" in l and "未取得独立模型" in p
    assert "单模型" in l
    return dict(bibliography=8,study_sections=6,roles=8,approved_independent_reviewer=False)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    p=RESEARCH/"manuscript.md";l=RESEARCH/"process_log.md"
    status=validate(p,l)
    outputs=[
        (p,args.output/"共享单车数字治理_论文成品_探索性研究稿.docx","论文成品"),
        (l,args.output/"自动论文_完整过程详细日志_20261122.docx","过程日志"),
    ]
    for src,dst,kind in outputs:make_doc(src,dst,kind)
    for _,dst,_ in outputs:
        reread=Document(dst)
        assert len(reread.paragraphs)>25 and len(reread.tables)>=1
    summary=dict(status,run_id="bike_paper_single_model_20261122",
                 model_roles="single_model_roleplay",api_calls=0,
                 source_paths={p.name:digest(p),l.name:digest(l)},
                 deliverables={dst.name:{"sha256":digest(dst),"bytes":dst.stat().st_size} for _,dst,_ in outputs})
    (args.output/"build_manifest.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
