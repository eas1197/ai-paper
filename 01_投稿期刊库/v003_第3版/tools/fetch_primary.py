"""Archive known publisher URLs and their explicit guideline links; no login or CAPTCHA bypass."""
from __future__ import annotations
import concurrent.futures
import json
import re
from pathlib import Path
from urllib.parse import urljoin,urlsplit
import requests
from bs4 import BeautifulSoup
from journal_common import MODULE, now, sha, write

BASE=MODULE/'assets/survey_20261116'

def fetch(item):
    jid,url=item
    key=jid+'_'+__import__('hashlib').sha256(url.encode()).hexdigest()[:12]
    folder=BASE/'primary_http'/key
    record=folder/'record.json'
    if record.exists(): return json.loads(record.read_text(encoding='utf-8'))
    folder.mkdir(parents=True,exist_ok=True)
    row={'journal_id':jid,'source_url':url,'retrieved_at':now(),'tls_verified':True}
    try:
        r=requests.get(url,timeout=(8,16),headers={'User-Agent':'AcademicJournalSurvey/1.0 (public pages only)'})
        row.update(status_code=r.status_code,final_url=r.url,content_type=r.headers.get('Content-Type'))
        if r.status_code!=200: raise ValueError('HTTP '+str(r.status_code))
        original=folder/'response.html';original.write_bytes(r.content)
        if r.encoding and r.encoding.lower()=='iso-8859-1': r.encoding=r.apparent_encoding
        soup=BeautifulSoup(r.text,'html.parser')
        for x in soup(['script','style','noscript','svg']):x.decompose()
        links=[]
        for a in soup.find_all('a',href=True):
            if re.search(r'投稿须知|投稿指南|征稿简则|投稿要求|征稿启事',a.get_text()):
                link=urljoin(r.url,a['href'])
                if urlsplit(link).hostname==urlsplit(r.url).hostname and link.startswith(('http://','https://')):
                    links.append(link)
        lines=[v.strip() for v in soup.get_text('\n').splitlines() if v.strip()]
        textfile=folder/'text.txt';textfile.write_text('\n'.join(f'L{i}: {v}' for i,v in enumerate(lines)),encoding='utf-8')
        row.update(status='archived',snapshot_path=textfile.relative_to(BASE).as_posix(),sha256=sha(textfile),
                   original_path=original.relative_to(BASE).as_posix(),original_sha256=sha(original),
                   line_count=len(lines),title=soup.title.get_text() if soup.title else '',guideline_links=sorted(set(links)),
                   review_status='awaiting_source_readback')
    except Exception as exc:
        row.update(status='failed',error_type=type(exc).__name__,reason=str(exc))
    write(record,row);return row

def main():
    urls=[]
    for n in ('official_urls.json','more_urls.json','final_urls.json'):
        urls.extend(json.loads((BASE/n).read_text(encoding='utf-8')))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        first=list(pool.map(fetch,urls))
        follow=[(r['journal_id'],u) for r in first for u in r.get('guideline_links',[])[:2] if [r['journal_id'],u] not in urls]
        second=list(pool.map(fetch,sorted(set(follow))))
    result=first+second
    write(BASE/'primary_http/collection_log.json',result)
    print(json.dumps({'attempted':len(result),'archived':sum(r['status']=='archived' for r in result),'failed':sum(r['status']=='failed' for r in result)},ensure_ascii=False))

if __name__=='__main__':main()
