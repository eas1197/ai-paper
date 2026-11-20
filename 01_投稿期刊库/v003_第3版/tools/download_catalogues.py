"""Archive public catalogues for screening; preserve original bytes and retrieval failures."""
from __future__ import annotations
import json
from pathlib import Path
import requests
import pdfplumber
from journal_common import MODULE, now, sha, write

TARGETS = {
 'cssci_2025_2026_original_mirror': 'https://lib.zjyc.edu.cn/__local/4/25/EF/0BC3C22796EF3A3BB0AA036B7DA_483BD9BA_7BBAD6.pdf',
 'cssci_2025_2026_institutional_compilation': 'https://tsgdag.jhun.edu.cn/_upload/article/files/c9/b6/69146849425d8445bb35e97b4546/fae0bc7d-bf19-4538-868f-f7606bfe4f33.pdf',
 'pku_2023_institutional_transcription': 'https://www.wifa.edu.cn/upload/20240923/d4b8a60dc932f2593f8fb7322a2aa0b2.pdf',
}
def main():
    base=MODULE/'assets/survey_20261116/catalogues';base.mkdir(parents=True,exist_ok=True)
    log=[]
    for name,url in TARGETS.items():
        dest=base/(name+'.pdf')
        item={'source_url':url,'retrieved_at':now(),'tls_verification':True,'role':'institutional_mirror_or_transcription; primary authenticity requires review'}
        try:
            if not dest.exists():
                r=requests.get(url,timeout=30);r.raise_for_status()
                if not r.content.startswith(b'%PDF-'):
                    raise ValueError('not a PDF; no login/captcha page accepted')
                dest.write_bytes(r.content)
            with pdfplumber.open(dest) as pdf:
                pages=[{'page':i+1,'text':p.extract_text() or ''} for i,p in enumerate(pdf.pages)]
            write(base/(name+'_pages.json'),pages)
            item.update(status='downloaded',path=dest.name,sha256=sha(dest),page_count=len(pages),preview=pages[0]['text'][:500])
        except Exception as exc:
            item.update(status='failed',error_type=type(exc).__name__,reason=str(exc))
        log.append(item)
        write(base/'download_log.json',log)
        print(json.dumps(item,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
