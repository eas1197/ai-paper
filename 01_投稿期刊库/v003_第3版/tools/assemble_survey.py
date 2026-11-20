"""Rebuild this survey from archived web-tool text, without inventing missing facts.

Web search records are leads; only opened publisher pages support extracted facts.
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from urllib.parse import urlsplit
from journal_common import MODULE, now, sha, write, norm_name, csv_write
from journals import FIELDS, REQUIREMENTS, unknown

BASE = MODULE / 'assets/survey_20261116'
AS_OF = '2026-11-16'

def sections(text):
    return [s.strip() for s in re.split(r'-{20,}', text) if s.strip()]

def cell(value, eid, locator=None):
    return {'value': value, 'evidence_ids': [eid], 'unknown_reason': None, 'locator': locator,
            'evidence_role': 'direct_extracted_text'}

def main():
    seeds = json.loads((BASE / 'seeds.json').read_text(encoding='utf-8'))
    urls = []
    for name in ('official_urls.json','more_urls.json','final_urls.json'):
        if (BASE / name).exists():
            urls.extend(json.loads((BASE / name).read_text(encoding='utf-8')))
    mapping = {}
    for jid, url in urls:
        mapping.setdefault(jid, []).append(url)
    docs, evidence = [], []
    for f in sorted((BASE / 'views').glob('*.txt')):
        for n, part in enumerate(sections(f.read_text(encoding='utf-8'))):
            m = re.search(r'^.*?\((https?://[^\n]+)\)\n', part)
            if not m or 'Failed to fetch' in part or 'Content type:' not in part:
                continue
            url = m.group(1)
            lines = [(int(k),v) for k,v in re.findall(r'^L(\d+): ?(.*)$', part, re.M)]
            total = re.search(r'Total lines: (\d+)', part)
            complete = bool(total) and {k for k,v in lines} == set(range(int(total.group(1))))
            eid = 'E_' + f.stem + '_' + str(n)
            docs.append({'url': url, 'lines': lines, 'complete': complete, 'eid': eid, 'part': part, 'title': part.split('\n')[0]})
            evidence.append({'evidence_id': eid, 'source_url': url, 'retrieved_at': AS_OF,
                             'locator': 'L0—L' + str(lines[-1][0]) if lines else 'no_extracted_lines',
                             'snapshot_path': f.relative_to(BASE).as_posix(), 'sha256': sha(f),
                             'authority': 'index_owner' if 'cssrac.nju.edu.cn' in url else 'publisher',
                             'kind': 'publisher_page', 'representation': 'web_tool_rendered_text',
                             'complete_rendered_view': complete, 'not_original_html_or_pdf': True})
    # Integrate locally archived, readable publisher text with stable source hashes.
    for record in json.loads((BASE/'primary_http/collection_log.json').read_text(encoding='utf-8')):
        if record['status'] != 'archived' or record['line_count'] < 5:
            continue
        if urlsplit(record['final_url']).hostname != urlsplit(record['source_url']).hostname:
            continue
        path=BASE/record['snapshot_path']
        if sha(path)!=record['sha256']:
            raise ValueError('Archived publisher text changed: '+str(path))
        raw=path.read_text(encoding='utf-8')
        lines=[(int(k),v) for k,v in re.findall(r'^L(\d+): (.*)$',raw,re.M)]
        eid='HTTP_'+path.parent.name
        if any(e['evidence_id']==eid for e in evidence): continue
        url=record['source_url']
        mapping.setdefault(record['journal_id'],[]).append(url)
        docs.append(dict(url=url,lines=lines,complete=True,eid=eid,title=record['title']))
        evidence.append(dict(evidence_id=eid,source_url=url,retrieved_at=record['retrieved_at'],
            locator='L0-L'+str(lines[-1][0]),snapshot_path=record['snapshot_path'],sha256=record['sha256'],
            authority='publisher',kind='publisher_page',representation='html_text'))
    scan=BASE/'catalogues/cssci_2025_2026_original_mirror.pdf'
    if sha(scan)!='05a549a1542d44807ea2e019519e536f909b7f296176d5e2d6eb62e96ce78fd4':
        raise ValueError('CSSCI scan changed')
    cssci=json.loads((BASE/'catalogues/cssci_readback.json').read_text(encoding='utf8'))
    evidence.append(dict(evidence_id='CSSCI_SCAN',source_url=json.loads((BASE/'catalogues/download_log.json').read_text(encoding='utf8'))[0]['source_url'],
        retrieved_at=AS_OF,locator='逐刊页码和序号见indexing.CSSCI',snapshot_path=scan.relative_to(BASE).as_posix(),
        sha256=sha(scan),authority='index_owner',kind='catalogue',representation='南京大学评价中心署名目录，高校图书馆镜像'))
    evidence_by_id = {e['evidence_id']:e for e in evidence}
    journals = []
    for seed in seeds:
        jid = seed['journal_id']; name = seed['journal_name']
        j = dict(seed, **{k:unknown() for k in FIELDS}, requirements={k:unknown() for k in REQUIREMENTS},
                 guideline={'evidence_ids':[], 'full_snapshot':False},
                 indexing={k:{'status':'unverified','edition':edition,'evidence_ids':[],
                              'unknown_reason':'尚未取得该版官方逐刊收录证据，旧版/无版次标签不推定延续'}
                           for k,edition in [('CSSCI','2025-2026'),('PKU','2023')]},
                 as_of=AS_OF, last_surveyed_at=AS_OF, status='needs_review',
                 selection_role='待核验候选；quota_group是计划分配，不代表收录认证',
                 survey_search_files=['searches/batch_' + str((int(jid[1:])-1)//4+1).zfill(2)+'.txt'])
        sup = 'searches/' + jid + '_supplement.txt'
        if (BASE / sup).exists(): j['survey_search_files'].append(sup)
        jdocs = [d for d in docs if d['url'] in mapping.get(jid, [])]
        j['official_pages_opened'] = len(jdocs)
        j['official_urls_attempted'] = mapping.get(jid, [])
        for d in jdocs:
            # A source shared by several journals must mention this journal explicitly.
            text = '\n'.join(v for _,v in d['lines'])
            if norm_name(name) not in norm_name(text):
                continue
            eid = d['eid']; lines = d['lines']
            j['official_url'] = cell(d['url'], eid)
            for field, regex in [('issn',r'(?i)ISSN[^\d\n]{0,20}(\d{4}-\d{3}[\dXx])'),
                                 ('cn',r'(?i)(?:CN|国内统一刊号)[^\d\n]{0,20}(\d{2}-\d{4}/[A-Z0-9]+)')]:
                found = set(re.findall(regex, text))
                if len(found) == 1: j[field] = cell(next(iter(found)),eid)
            for field, pattern in [('columns',r'主要栏目|开设.*栏目|设有.*栏目'),
                                   ('directions',r'办刊宗旨|主要刊登|主要发表|主要报道'),
                                   ('quantitative_fit',r'定量|实证研究|回归分析|CFPS|CGSS|调查数据'),
                                   ('review_duration',r'审稿.*(?:个月|天)|(?:个月|天).*自行处理'),
                                   ('ai_policy',r'生成式人工智能|AI工具|AIGC|人工智能.*(?:写作|生成|声明)'),
                                   ('exclusive_review_policy',r'一稿多投|一稿两|独家|首发稿')]:
                relevant=[(k,v) for k,v in lines if re.search(pattern,v)]
                if relevant:
                    j[field]=cell('\n'.join(v for _,v in relevant),eid,','.join('L'+str(k) for k,v in relevant))
            # Undergraduate claims must explicitly mention undergraduate authors, never young scholars.
            ug = [(k,v) for k,v in lines if re.search(r'本科生.*(?:作者|投稿|发表)|(?:作者|投稿).*本科生',v)]
            if ug: j['undergraduate_policy']=cell({'classification':'requires_review','text':'\n'.join(v for _,v in ug)},eid)
            fee = [(k,v) for k,v in lines if re.search(r'收取.*(?:版面费|审稿费)|不收.*(?:版面费|审稿费)|不以任何.*收.*费',v)]
            if fee:
                j['fees'] = cell([{'fee_type':'official_policy_text','amount':None,'currency':None,'unit':None,
                                  'waiver':None,'policy_text':v,'locator':'L'+str(k),'unknown_reason':'金额/单位仅在原文明确时单列，待结构复核'} for k,v in fee],eid)
            isguide = bool(re.search(r'投稿须知|投稿指南|征稿简则|征稿启事|投稿要求',text))
            # Homepages with a "submission guidelines" link are not the guideline document.
            guide_body = sum(bool(re.search(p,text)) for p in (r'来稿|稿件要求',r'摘要|关键词',r'参考文献|注释',r'字数|[0-9]{4,5}字')) >= 3
            if d['complete'] and isguide and guide_body:
                j['guideline']={'evidence_ids':[eid], 'full_snapshot':True,'representation':'complete_rendered_text',
                                'original_file_downloaded':False}
                evidence_by_id[eid]['kind']='full_guideline'
            for key, pattern in {
                'length':r'字数|[0-9]{4,5}字|字符',
                'title_abstract_keywords':r'摘要|关键词|题名|标题',
                'structure':r'章节|层次|一级标题|二级标题|正文',
                'reference_style':r'参考文献|引注|注释|著录',
                'tables_figures':r'图表|三线表|图序|表序|表格',
                'anonymization':r'匿名|盲审|隐去|泄露.*身份',
                'author_funding':r'作者简介|基金|作者信息|署名',
                'attachments':r'附件|版权协议|承诺书',
                'ethics':r'伦理|学术不端|学术规范|抄袭',
                'ai_disclosure':r'生成式人工智能|AIGC|AI工具',
                'copyright':r'版权|著作权',
                'exclusive_review':r'一稿多投|一稿两|首发稿|独家'
            }.items():
                found=[(k,v) for k,v in lines if re.search(pattern,v)]
                if found and isguide and guide_body:
                    j['requirements'][key]=cell('\n'.join(v for _,v in found),eid,','.join('L'+str(k) for k,v in found))
            # Conservative channel recognition: online systems take precedence; a contact mailbox is never enough.
            if re.search(r'唯一投稿.*(?:网站|渠道|网址)|只接受.*(?:系统|网上)|不接受电子邮件|投稿方式.*(?:网上|在线)|注册.*投稿|投稿.*注册',text):
                j['submission_channel']=cell('system',eid)
                j['submission_url']=cell(d['url'],eid)
                # This is the official instructions page, not a guessed login endpoint.
                j['submission_url']['entry_role']='official_instructions; follow publisher login link'
                j['registration_required']=cell(True,eid) if '注册' in text else unknown('官方系统要求是否注册仍待核验')
            # Indexing only when edition, category, journal title and source statement coexist on an official page.
            if re.search(r'CSSCI.{0,25}2025.{0,8}2026|2025.{0,8}2026.{0,40}CSSCI',text,re.I) and '来源期刊' in text:
                if not re.search(r'扩展版|来源集刊',text):
                    j['indexing']['CSSCI']={'status':'verified','edition':'2025-2026','category':'source',
                                            'evidence_ids':[eid],'verified_at':AS_OF,'unknown_reason':None}
            if re.search(r'(?:中文核心期刊要目总览|北大核心).{0,25}2023|2023.{0,25}(?:中文核心期刊要目总览|北大核心)',text):
                j['indexing']['PKU']={'status':'verified','edition':'2023','category':'core',
                                      'evidence_ids':[eid],'verified_at':AS_OF,'unknown_reason':None}
        if jid in cssci and cssci[jid]['name']==name:
            j['indexing']['CSSCI']=dict(status='verified',edition='2025-2026',category='source',evidence_ids=['CSSCI_SCAN'],
                verified_at=AS_OF,locator=cssci[jid],unknown_reason=None)
        if not jdocs:
            j['official_page_gap']='已逐刊检索；尚无可读官方页面或访问失败，检索摘要不计全文'
        j['field_review_status']='machine_extracted_pending_readback'
        journals.append(j)
    bundle={'schema_version':2,'as_of':AS_OF,'data_version':1,'journals':journals,'evidence':evidence,
            'scope':'100家候选逐刊首轮检索与可访问官方页面核对；未完成的硬门槛保持needs_review',
            'latest_edition_decision':{'CSSCI':'2025-2026','PKU':'2023','checked_on':AS_OF,
                'user_instruction':'采用最新已正式出版版本，并注明2026年核验日期'},
            'extraction_method':'deterministic source-line extraction; no inferred fees, acceptance rates, or author eligibility'}
    write(BASE/'survey_bundle.json',bundle)
    write(BASE/'collection_manifest.json',{'as_of':AS_OF,'journal_count':len(journals),
          'search_file_count':len(list((BASE/'searches').glob('*.txt'))),'opened_primary_view_count':len(docs),
          'complete_rendered_view_count':sum(d['complete'] for d in docs),
          'journal_with_opened_primary_page':sum(bool(j['official_pages_opened']) for j in journals),
          'full_guideline_journals':sum(j['guideline']['full_snapshot'] for j in journals),
          'note':'检索、页面读取、全文稿约、资质核验分别计数，不能互换'})
    print(json.dumps(json.loads((BASE/'collection_manifest.json').read_text(encoding='utf-8')),ensure_ascii=False))

if __name__=='__main__':
    main()
