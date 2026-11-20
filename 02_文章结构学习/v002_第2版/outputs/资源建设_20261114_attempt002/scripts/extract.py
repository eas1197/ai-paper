from pathlib import Path
import json, hashlib, re, concurrent.futures, sys
import pdfplumber

ROOT=Path(__file__).resolve().parents[1]
KEYS='6V7LJIWN SCCKUUS9 J5XDE43I Y32DRMKW MY99VSIF J38BV4A5 S823QAM2 89UP6KH7 AVUPRP3F BA5F5I6L FK7SICYJ FQ7RQ5NC NLVHWHF6 CJB64WZK DD4I5QA4 NUR2L8DP ZLZANUD2 V3CA3AZW QIL2SNVK 3G222LKC'.split()
if len(sys.argv)>1: KEYS=sys.argv[1:]
inventory=json.loads((ROOT/'screening/inventory.json').read_text(encoding='utf-8'))
def extract(k):
    r=next(r.copy() for r in inventory if r['attachment_key']==k)
    path=Path(r['pdf_path']); dest=ROOT/'fulltext'/k; dest.mkdir(parents=True,exist_ok=True)
    pages=[]
    with pdfplumber.open(path) as doc:
        for i,page in enumerate(doc.pages,1):
            txt=page.extract_text(x_tolerance=2,y_tolerance=3) or ''
            lines=[]
            for line in page.extract_text_lines(x_tolerance=2,y_tolerance=3):
                lines.append({x:line[x] for x in ['text','x0','top','x1','bottom']})
            pages.append(dict(pdf_page=i,width=float(page.width),height=float(page.height),text=txt,lines=lines))
    (dest/'pages.json').write_text(json.dumps(pages,ensure_ascii=False,indent=2),encoding='utf-8')
    text='\n\n'.join(f'=== PDF第{p["pdf_page"]}页 ===\n'+p['text'] for p in pages)
    (dest/'全文.txt').write_text(text,encoding='utf-8')
    r.update(pdf_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),page_count=len(pages),page_char_counts=[len(p['text']) for p in pages],pdf_text_path=str(dest/'全文.txt'))
    (dest/'source.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
    # PDF-first identity, headings and ending for manual screening.
    brief=f'\n{k} | {r["filename"]} | PDF pages {len(pages)}\n'
    brief+='FIRST: '+re.sub(r'\s+','',pages[0]['text'])[:280]+'\n'
    brief+='JOURNAL: '+' | '.join(re.sub(r'\s+','',p['text'])[-150:] for p in pages[1:3])+'\n'
    brief+='HEADINGS: '+' | '.join(re.findall(r'(?m)^\s*[一二三四五六七八九十]+[、．.].{1,55}',text))+'\n'
    brief+='LAST: '+re.sub(r'\s+','',pages[-1]['text'])[-180:]+'\n'
    return brief
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
    for result in ex.map(extract,KEYS):
        print(result,flush=True)
