from pathlib import Path
import json,re,unicodedata,collections,sys
from pdfminer.high_level import extract_pages
from pdfminer.layout import LAParams,LTTextContainer,LTTextLine

ROOT=Path(__file__).resolve().parents[1]
KEYS='6V7LJIWN SCCKUUS9 J5XDE43I Y32DRMKW MY99VSIF J38BV4A5 S823QAM2 89UP6KH7 AVUPRP3F FQ7RQ5NC NLVHWHF6 CJB64WZK DD4I5QA4 NUR2L8DP ZLZANUD2 V3CA3AZW QIL2SNVK 3G222LKC GTUTSZDI GUQJU4JA'.split()
if len(sys.argv)>1:KEYS=sys.argv[1:]
def norm(t):
    return re.sub(r'\s+','',unicodedata.normalize('NFKC',re.sub(r'[\ue000-\uf8ff]','',t))).replace('\x82','，')
def traverse(obj):
    if isinstance(obj,LTTextLine): yield obj
    elif hasattr(obj,'__iter__'):
        for c in obj:yield from traverse(c)
for k in KEYS:
    folder=ROOT/'fulltext'/k
    src=json.loads((folder/'source.json').read_text(encoding='utf8'))
    cache=(ROOT/'screening'/f'{k}_cache.txt').read_text(encoding='utf8')
    out=[]; review=[]; idx=0; section='引入/未编号引言'; started=False; ended=False
    for pi,layout in enumerate(extract_pages(src['pdf_path'],laparams=LAParams(all_texts=True,line_overlap=.1,line_margin=.2)),1):
        lines=[]
        for l in traverse(layout):
            tx=norm(l.get_text())
            if tx: lines.append(dict(text=tx,x0=round(l.x0,2),x1=round(l.x1,2),top=round(layout.height-l.y1,2),height=round(l.height,2)))
        lines.sort(key=lambda l:(round(l['top']/3),l['x0']))
        # Choose the body text left margin from sufficiently long Chinese lines.
        body=[l for l in lines if len(re.findall(r'[\u4e00-\u9fff]',l['text']))>12 and l['top']>layout.height*.08 and l['top']<layout.height*.86]
        margin=collections.Counter(round(l['x0']/4)*4 for l in body).most_common(1)
        margin=margin[0][0] if margin else 0
        h=collections.Counter(round(l['height']) for l in body).most_common(1)
        h=h[0][0] if h else 10
        blocks=[]; buf=[]
        def flush():
            if buf: blocks.append(buf.copy());buf.clear()
        for l in lines:
            tx=l['text']; chinese=len(re.findall(r'[\u4e00-\u9fff]',tx))
            if l['top']<layout.height*.075 or l['top']>layout.height*.93:continue
            if chinese==0 and len(tx)<8:continue
            heading=bool(re.match(r'^[一二三四五六七八九十]+[、,，.]',tx))
            sub=bool(re.match(r'^[（(][一二三四五六七八九十\d]+[)）]',tx))
            indented=(margin+12<=l['x0']<=margin+38 and chinese>6)
            gap=buf and l['top']-buf[-1]['top']>h*2.2
            if heading or sub or indented or gap:flush()
            buf.append(l)
            if heading or sub:flush()
        flush()
        for block in blocks:
            tx=''.join(l['text'] for l in block)
            if not started:
                if re.match(r'^[一二三四五六七八九十]+[、,，.]',tx):started=True
                elif pi==1 and any(s in tx for s in ['以户口登记','近年来,','代际间的职业','对城乡流动人口','在中国市场化进程','党的二十大报告']):started=True
                else:continue
            if ended:continue
            if re.match(r'^(参考文献[:：]?|英文摘要|Abstract|ABSTRACT)',tx):ended=True;continue
            if len(re.findall(r'[\u4e00-\u9fff]',tx))<6:continue
            if re.match(r'^[一二三四五六七八九十]+[、,，.]',tx) and len(tx)<90:section=tx;kind='section'
            elif re.match(r'^[（(][一二三四五六七八九十\d]+[)）]',tx) and len(tx)<90:kind='subsection'
            elif block[0]['height']<h*.85:kind='note_or_table'
            else:kind='paragraph_candidate'
            idx+=1
            record=dict(block_id=f'{k}_B{idx:03}',pdf_page=pi,section=section,kind=kind,text=tx,top=block[0]['top'],bottom=block[-1]['top']+block[-1]['height'],segmentation_status='geometry_candidate_requires_review')
            out.append(record)
            if kind in ('section','subsection'):review.append(f'\n[p{pi}] {record["block_id"]} {tx}')
            elif kind=='paragraph_candidate':
                # Structural reading packet preserves starts, shifts and conclusions; full text stays adjacent.
                ss=re.split(r'(?<=[。！？!?])',tx)
                if len(tx)<=450: excerpt=tx
                else:excerpt=tx[:200]+' […] '+tx[-200:]
                review.append(f'[p{pi}] {record["block_id"]} {excerpt}')
    (folder/'paragraph_candidates.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
    (folder/'结构阅读包.txt').write_text('\n'.join(review),encoding='utf8')
    print(k,len(out),'blocks',len('\n'.join(review)),'chars',flush=True)
