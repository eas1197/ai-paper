"""09: reproducible 5+5 candidates, per-journal packages and exclusive submission ledger.

No background watcher. Network occurs only in the explicit send command.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import mimetypes
import os
import random
import shutil
import smtplib
import sqlite3
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
ROOT = MODULE.parents[1]
CONTROL = ROOT / '00_项目控制/v003_第3版'
reg = json.loads((CONTROL / 'module_registry.json').read_text(encoding='utf-8-sig'))
JOURNALS = ROOT / next(m['path'] for m in reg['modules'] if m['module_id'] == '01')
sys.path.insert(0, str(JOURNALS / 'tools'))
from journal_common import (csv_write, date_ok, hash_value, inside, load, lock, locks_ok, now,
                            output, sha, valid_id, write)
import journals

ACTIVE = ('sending', 'delivery_unknown', 'submitted', 'under_review', 'withdrawal_requested')
TRANSITIONS = {'candidate': ('prepared', 'superseded'), 'prepared': ('ready_to_send', 'superseded'),
               'ready_to_send': ('sending', 'superseded'), 'sending': ('submitted', 'delivery_unknown'),
               'delivery_unknown': ('submitted', 'not_delivered_confirmed'),
               'submitted': ('under_review', 'rejected', 'accepted', 'withdrawal_requested'),
               'under_review': ('rejected', 'accepted', 'withdrawal_requested'),
               'withdrawal_requested': ('withdrawal_confirmed', 'rejected', 'accepted')}

def ledger(path):
    path = inside(ROOT, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=20, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.executescript('''CREATE TABLE IF NOT EXISTS submissions(
      submission_id TEXT PRIMARY KEY,family_id TEXT NOT NULL,journal_id TEXT NOT NULL,
      state TEXT NOT NULL,package TEXT NOT NULL,updated_at TEXT NOT NULL);
    CREATE UNIQUE INDEX IF NOT EXISTS one_active ON submissions(family_id)
      WHERE state IN ('sending','delivery_unknown','submitted','under_review','withdrawal_requested');
    CREATE TABLE IF NOT EXISTS families(family_id TEXT PRIMARY KEY, run_id TEXT UNIQUE NOT NULL,manuscript_sha256 TEXT UNIQUE NOT NULL);
    CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,submission_id TEXT NOT NULL,
      previous_state TEXT,new_state TEXT NOT NULL,at TEXT NOT NULL,evidence_json TEXT NOT NULL);''')
    return db

def central_ledger():
    # Shared across all attempts/runs/versions of the same paper family.
    return CONTROL / 'private/submissions.sqlite'

def sample_candidates(pool, seed):
    ids, names = set(), set()
    for j in pool:
        if j['journal_id'] in ids or journals.norm_name(j['journal_name']) in names:
            raise ValueError('候选池重复期刊，禁止重复占名额')
        ids.add(j['journal_id']); names.add(journals.norm_name(j['journal_name']))
    rng = random.Random(seed)
    selected = []
    for group in ('CSSCI', 'PKU'):
        rows = sorted((j for j in pool if j['quota_group'] == group), key=lambda j: j['journal_id'])
        if len(rows) < 5:
            raise ValueError(f'{group}合格池仅{len(rows)}家，至少需要5家；不补不合格记录')
        selected.extend(rng.sample(rows, 5))
    return selected

def stage_gate(path, stage_id, run_id, locks):
    path = inside(ROOT, path)
    mf = load(path)
    if mf.get('stage_id') != stage_id or mf.get('run_id') != run_id or mf.get('status') != 'passed':
        raise ValueError(f'G{int(stage_id)}未通过/不属于同一次研究')
    if not mf.get('output_files') or not mf.get('gate_report'):
        raise ValueError('上游manifest未锁定输出/业务验收报告')
    problems = locks_ok(mf.get('input_files', []) + mf['output_files'])
    if problems:
        raise ValueError('上游已失效: ' + ';'.join(problems))
    gp = Path(mf['gate_report'])
    gp = gp if gp.is_absolute() else path.parent / gp
    gp = inside(ROOT, gp)
    if load(gp).get('status') != 'passed' or str(gp.relative_to(ROOT)).replace('\\', '/') not in {str(inside(ROOT, i['path']).relative_to(ROOT)).replace('\\', '/') for i in mf['output_files']}:
        raise ValueError('上游关卡报告未通过或不在哈希锁内')
    locks.append(lock(path)); locks.extend(mf['output_files'])

def plan(inputs, config=None):
    return {'stage_id': '09', 'module_version': 3, 'inputs': inputs, 'config': config or {},
            'operations': ['verify_upstream', 'verify_current_resource', 'filter', 'sample_5_5',
                           'adaptation_tasks', 'package_checks', 'sequential_queue'],
            'network_execution': False, 'seed': inputs.get('seed', 20261116)}


def attachments_digest(files):
    """Content/role digest independent of the new attempt's output path."""
    return hash_value(sorted([{'role': f['role'], 'sha256': f['sha256']} for f in files], key=lambda f: f['role']))

def prepare_package(folder, j, inputs, source, files):
    folder.mkdir(parents=True)
    jid = j['journal_id']
    adaptation = inputs.get('adaptations', {}).get(jid, {})
    checks = []
    supplied = adaptation.get('files', {})
    # All transformations are supplied and reviewed per target. A copied master is never certified formatted.
    names = ('manuscript', 'anonymous_manuscript', 'cover_letter', 'author_information', 'declarations')
    copied = []
    for role in names:
        raw = supplied.get(role)
        if raw:
            p = inside(ROOT, raw)
            if not p.is_file():
                raise ValueError('附件不存在: ' + raw)
            dest = folder / (role + p.suffix)
            shutil.copyfile(p, dest); files.append(lock(p)); copied.append({'role': role, **lock(dest)})
        else:
            checks.append({'item': role, 'status': 'missing', 'reason': '需提供该刊实际材料'})
    if not supplied.get('manuscript'):
        shutil.copyfile(source, folder / ('source_manuscript' + source.suffix))
    required = j.get('requirements', {})
    reviewed = adaptation.get('checks', {})
    for key in journals.REQUIREMENTS:
        cell = reviewed.get(key, {})
        rule = required.get(key, {})
        ok = (cell.get('status') in ('passed', 'not_applicable') and bool(cell.get('reviewer'))
              and bool(cell.get('assessment')) and date_ok(cell.get('reviewed_at'), inputs['as_of'])
              and cell.get('source_manuscript_sha256') == sha(source)
              and cell.get('attachments_sha256') == attachments_digest(copied))
        checks.append({'item': key, 'status': 'passed' if ok else 'needs_review',
                       'rule': rule, 'review': cell})
    channel = j['submission_channel']['value']
    # A same-day explicit target recheck is required even for a recently built library.
    recheck = inputs.get('target_rechecks', {}).get(jid, {})
    refresh_ok = (recheck.get('reviewed_on') == inputs['as_of'] and recheck.get('journal_profile_sha256') == hash_value(j)
                  and recheck.get('reviewer') and not locks_ok(recheck.get('evidence_files', []))
                  and bool(recheck.get('evidence_files'))
                  and all(recheck.get(k) is True for k in ('indexing', 'guidelines', 'channel', 'fees', 'ai_policy')))
    checks.append({'item': 'target_recheck', 'status': 'passed' if refresh_ok else 'needs_review'})
    files.extend(recheck.get('evidence_files', []))
    ready = all(c['status'] == 'passed' for c in checks)
    sid = valid_id(inputs['family_id']) + '_' + jid + '_' + folder.parent.name
    package = {'submission_id': sid, 'family_id': inputs['family_id'], 'journal_id': jid,
               'journal_name': j['journal_name'], 'channel': channel,
               'recipient': j['submission_email']['value'] if channel == 'email' else j['submission_url']['value'],
               'state': 'ready_to_send' if ready else 'prepared', 'files': copied,
               'source_manuscript_sha256': sha(source), 'checks': checks,
               'as_of': inputs['as_of'], 'author_confirmations': inputs.get('author_confirmations', {}),
               'subject': adaptation.get('subject'), 'body': adaptation.get('body'),
               'sender': inputs.get('sender'), 'journal_profile_sha256': hash_value(j)}
    package['content_sha256'] = hash_value(package)
    write(folder / 'package.json', package)
    csv_write(folder / 'journal_adaptation.csv', checks, ['item', 'status', 'reason', 'rule', 'review'])
    (folder / '适配说明.md').write_text(f"# {j['journal_name']}\n\n状态：{package['state']}。\n\n原稿保留；逐刊版必须逐项检查并锁定附件，不能把复制原稿认定为适配完成。\n\n官方入口：{j['submission_url']['value']}\n", encoding='utf-8')
    return package

def execute(planned, context=None):
    inputs = planned['inputs']
    if inputs.get('enabled') is not True:
        return {'status': 'skipped', 'reason': '未显式启用投稿材料准备'}
    valid_id(inputs['run_id']); valid_id(inputs['family_id'])
    if inputs.get('writing_mode') not in ('single', 'three_plus_review'):
        raise ValueError('写作模式无效')
    locks = []
    stage_gate(inputs['stage07_manifest'], '07', inputs['run_id'], locks)
    if inputs['writing_mode'] == 'three_plus_review':
        stage_gate(inputs['stage08_manifest'], '08', inputs['run_id'], locks)
    resource = inside(ROOT, inputs['resource'])
    report = journals.validate(resource)
    if report['status'] != 'passed':
        raise ValueError('期刊库G1未通过/已失效，不能抽取可投十刊')
    locks.append(lock(resource / 'resource_snapshot.json'))
    locks.extend(load(resource / 'resource_snapshot.json')['files'])
    bundle = load(resource / 'journal_profiles.json')
    source = inside(ROOT, inputs['manuscript'])
    # Master must be exactly one of G7's validated outputs.
    if lock(source) not in load(inside(ROOT, inputs['stage07_manifest']))['output_files']:
        raise ValueError('稿件不是G7哈希锁定的产物')
    if inputs['writing_mode'] == 'three_plus_review':
        selected_path = inside(ROOT, inputs['selection_file'])
        selection = load(selected_path)
        stage08 = load(inside(ROOT, inputs['stage08_manifest']))
        if (lock(selected_path) not in stage08['output_files'] or selection.get('status') != 'passed'
            or selection.get('run_id') != inputs['run_id'] or not selection.get('winner')
            or selection.get('selected_manuscript_sha256') != sha(source)):
            raise ValueError('三稿模式须使用G8锁定选优记录中的实际稿件')
        locks.append(lock(selected_path))
    pool = []
    for j in bundle['journals']:
        decision = inputs.get('eligibility', {}).get(j['journal_id'], {})
        if (j['journal_id'] in report['eligible_ids'] and decision.get('topic_method_match') is True
            and decision.get('author_eligible') is True and decision.get('within_budget') is True
            and decision.get('basis') and decision.get('reviewer')):
            pool.append(j)
    selected = sample_candidates(pool, planned['seed'])
    target = output(inputs['output']); target.mkdir(parents=True)
    write(target / 'pool_snapshot.json', {'seed': planned['seed'], 'algorithm': 'Python Random(seed).sample; sorted journal_id; CSSCI then PKU',
          'python': sys.version, 'pool': pool, 'pool_sha256': hash_value(pool), 'selected_ids': [j['journal_id'] for j in selected]})
    packages = [prepare_package(target / j['journal_id'], j, inputs, source, locks) for j in selected]
    csv_write(target / 'candidates.csv', [{'position': i+1, 'journal_id': j['journal_id'], 'journal_name': j['journal_name'], 'quota_group': j['quota_group']} for i,j in enumerate(selected)], ['position','journal_id','journal_name','quota_group'])
    # Preparing a new queue must not reset existing active submissions.
    db = ledger(central_ledger())
    try:
        db.execute('BEGIN IMMEDIATE')
        bound = db.execute('SELECT * FROM families WHERE family_id=? OR run_id=? OR manuscript_sha256=?',
                           (inputs['family_id'], inputs['run_id'], sha(source))).fetchall()
        if bound and any(r['family_id'] != inputs['family_id'] or r['run_id'] != inputs['run_id'] for r in bound):
            raise ValueError('同一研究运行或原稿已绑定其他稿件族，不能换ID绕过在审锁')
        if not bound:
            db.execute('INSERT INTO families VALUES(?,?,?)', (inputs['family_id'],inputs['run_id'],sha(source)))
        for j, pkg in zip(selected, packages):
            db.execute('INSERT INTO submissions VALUES(?,?,?,?,?,?)', (pkg['submission_id'], pkg['family_id'], j['journal_id'], pkg['state'], str(target / j['journal_id'] / 'package.json'), now()))
            db.execute('INSERT INTO events(submission_id,new_state,at,evidence_json) VALUES(?,?,?,?)', (pkg['submission_id'], pkg['state'], now(), '{}'))
        db.commit()
    except Exception:
        db.rollback(); raise
    finally:
        db.close()
    csv_write(target / 'submission_ledger.csv', [{'submission_id': p['submission_id'], 'journal_id': p['journal_id'], 'family_id': p['family_id'], 'state': p['state']} for p in packages], ['submission_id','journal_id','family_id','state'])
    report = {'stage_id': '09', 'status': 'needs_review', 'materials_ready': all(p['state']=='ready_to_send' for p in packages),
              'candidate_count': 10, 'external_messages_sent': 0, 'reason': '仅生成材料；实际外发另行核对具体内容与声明'}
    write(target / 'gate_report.json', report)
    write(target / 'plan.json', planned)
    write(target / 'stage_manifest.json', {'run_id': inputs['run_id'], 'stage_id': '09', 'module_version': 3,
          'status': report['status'], 'created_at': now(), 'seed': planned['seed'], 'input_files': locks,
          'config_sha256': hash_value(planned), 'code_files': [lock(p) for m in (MODULE, JOURNALS) for p in (m / 'tools').glob('*.py')],
          'output_files': [lock(p) for p in target.rglob('*') if p.is_file()], 'gate_report': str(target / 'gate_report.json')})
    return {**report, 'path': str(target)}

def transition(submission_id, new_state, evidence, db_path=None):
    # No elapsed-time automatic release. Rejection/withdrawal/delivery recovery require a dated receipt.
    db = ledger(db_path or central_ledger())
    try:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM submissions WHERE submission_id=?', (submission_id,)).fetchone()
        if not row or new_state not in TRANSITIONS.get(row['state'], ()):
            raise ValueError('非法状态转换')
        if new_state == 'sending':
            if db.execute("SELECT 1 FROM submissions WHERE family_id=? AND state='accepted'", (row['family_id'],)).fetchone():
                raise ValueError('稿件族已录用，停止整个顺序队列')
            earlier = db.execute('SELECT * FROM submissions WHERE family_id=? AND rowid < (SELECT rowid FROM submissions WHERE submission_id=?)',
                                 (row['family_id'],submission_id)).fetchall()
            if any(r['state'] not in ('rejected','withdrawal_confirmed','not_delivered_confirmed','superseded') for r in earlier):
                raise ValueError('顺序队列的前刊尚未结束；禁止跳过或重复投递')
        if new_state == 'superseded' and not evidence.get('reason'):
            raise ValueError('替换未发送材料须记录原因；在审稿件不能使用此状态')
        if new_state in ('rejected','withdrawal_confirmed','accepted','not_delivered_confirmed','submitted','under_review'):
            if not evidence.get('files') or locks_ok(evidence['files']) or not evidence.get('reference') or not evidence.get('recorded_by'):
                raise ValueError('缺少有哈希锁定的编辑部回执/外发结果证据')
        db.execute('UPDATE submissions SET state=?,updated_at=? WHERE submission_id=?', (new_state, now(), submission_id))
        db.execute('INSERT INTO events(submission_id,previous_state,new_state,at,evidence_json) VALUES(?,?,?,?,?)',
                   (submission_id,row['state'],new_state,now(),json.dumps(evidence, ensure_ascii=False)))
        db.commit()
    except Exception:
        db.rollback(); raise
    finally:
        db.close()
    return {'submission_id': submission_id, 'state': new_state}

def validate(artifacts, evidence=None):
    work = inside(ROOT, artifacts); mf = load(work / 'stage_manifest.json')
    problems = locks_ok(mf['input_files'] + mf['output_files'] + mf['code_files'])
    report = load(work / 'gate_report.json')
    return {**report, 'status': 'stale' if problems else report['status'], 'integrity_errors': problems}

def export(artifacts, target_profile=None):
    report = validate(artifacts)
    if report.get('integrity_errors'):
        raise ValueError('材料已失效，禁止导出')
    return {'path': str(inside(ROOT, artifacts)), 'status': report['status'], 'external_messages_sent': 0}

def send(package_path, approval_path, smtp, transport=None):
    package_path = inside(ROOT, package_path); package = load(package_path)
    # Re-hash the whole package, including body and recipient, excluding the digest field.
    original = dict(package); digest = original.pop('content_sha256', None)
    approval = load(inside(ROOT, approval_path))
    if digest != hash_value(original) or approval.get('content_sha256') != digest:
        raise ValueError('外发审批未绑定当前完整材料')
    if package['state'] != 'ready_to_send' or not all(c['status']=='passed' for c in package['checks']):
        raise ValueError('逐刊材料未就绪')
    if package['channel'] != 'email':
        raise ValueError('该刊要求系统投稿；使用官方入口完成注册/验证码/提交，不冒用邮箱')
    if not all(approval.get(k) is True for k in ('approved','recipient_checked','authors_checked','declarations_checked')) or not approval.get('approved_by'):
        raise ValueError('缺少具体稿件、收件人、作者和声明核对')
    if not all(package.get('author_confirmations', {}).get(k) is True for k in ('real_identity','all_authors_consent','original_work','exclusive_submission','ai_disclosure_accurate')):
        raise ValueError('作者声明未确认')
    if not package.get('sender') or not package.get('recipient') or not package.get('subject') or not package.get('body'):
        raise ValueError('邮件内容/发送人/收件人缺失')
    if not date_ok(approval.get('approved_at'), package['as_of']) or package['as_of'] != now()[:10]:
        raise ValueError('需发送当日的目标刊复核与材料核对')
    problems = locks_ok(package['files'])
    if problems:
        raise ValueError(';'.join(problems))
    parent_report = validate(package_path.parent.parent)
    if parent_report.get('integrity_errors'):
        raise ValueError('上游或材料包已失效')
    message = EmailMessage()
    message['From'] = package['sender']; message['To'] = package['recipient']; message['Subject'] = package['subject']
    from email.utils import make_msgid
    message['Message-ID'] = make_msgid()
    message.set_content(package['body'])
    for item in package['files']:
        p = inside(ROOT, item['path']); mime = mimetypes.guess_type(p.name)[0] or 'application/octet-stream'
        main, sub = mime.split('/', 1); message.add_attachment(p.read_bytes(), maintype=main, subtype=sub, filename=p.name)
    # Preflight must finish before reserving the unique active-family slot.
    if transport is None:
        for k in ('host','port','username_env','password_env'):
            if not smtp.get(k):
                raise ValueError('缺SMTP配置: ' + k)
        if not os.environ.get(smtp['username_env']) or not os.environ.get(smtp['password_env']):
            raise ValueError('未配置SMTP凭据环境变量；不保存令牌')
    transition(package['submission_id'], 'sending', {'approval': lock(inside(ROOT, approval_path)), 'message_id': message['Message-ID']})
    try:
        if transport is not None:
            receipt = transport(message)
        else:
            with smtplib.SMTP_SSL(smtp['host'], smtp['port'], timeout=30, context=ssl.create_default_context()) as conn:
                conn.login(os.environ[smtp['username_env']], os.environ[smtp['password_env']])
                refused = conn.send_message(message)
                if refused:
                    raise RuntimeError('SMTP返回拒收，需核对投递状态')
            receipt = {'accepted_by_smtp': True, 'message_id': message['Message-ID']}
        receipt_path = package_path.parent / ('receipt_' + str(os.urandom(6).hex()) + '.json')
        write(receipt_path, {'at': now(), 'receipt': receipt, 'meaning': 'SMTP接受不代表编辑部受理'})
        return transition(package['submission_id'], 'submitted', {'files': [lock(receipt_path)], 'reference': message['Message-ID'], 'recorded_by': 'smtp_provider'})
    except Exception:
        # A timeout may have occurred after delivery: never retry/advance automatically.
        transition(package['submission_id'], 'delivery_unknown', {'reason': '发送异常，须核对是否已投递；禁止自动重发/转投'})
        raise

def main():
    sys.stdout.reconfigure(encoding='utf-8'); sys.stderr.reconfigure(encoding='utf-8')
    p = argparse.ArgumentParser(description=__doc__); s = p.add_subparsers(dest='command', required=True)
    b=s.add_parser('prepare'); b.add_argument('--input', required=True)
    for name in ('validate','export'):
        b=s.add_parser(name); b.add_argument('--attempt', required=True)
    b=s.add_parser('status')
    b=s.add_parser('transition'); b.add_argument('--id', required=True); b.add_argument('--state', required=True); b.add_argument('--evidence', required=True)
    b=s.add_parser('send'); b.add_argument('--package', required=True); b.add_argument('--approval', required=True); b.add_argument('--smtp-config', required=True)
    a=p.parse_args()
    try:
        if a.command=='prepare': result=execute(plan(load(a.input)))
        elif a.command=='send': result=send(a.package,a.approval,load(a.smtp_config))
        elif a.command=='transition': result=transition(a.id,a.state,load(a.evidence))
        elif a.command=='status':
            db=ledger(central_ledger()); result=[dict(r) for r in db.execute('SELECT * FROM submissions')]; db.close()
        else: result=(validate if a.command=='validate' else export)(a.attempt)
        print(json.dumps(result, ensure_ascii=False, indent=2)); return 0
    except (ValueError,OSError,KeyError,sqlite3.Error,smtplib.SMTPException) as exc:
        print(str(exc),file=sys.stderr); return 2

if __name__=='__main__':
    raise SystemExit(main())
