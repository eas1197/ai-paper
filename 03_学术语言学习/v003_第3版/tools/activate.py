"""Explicitly activate module 03 v003 as a candidate, not a passed resource."""
import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
OUT = BASE / 'outputs/资源建设_attempt001'
CONTROL = ROOT / '00_项目控制/v003_第3版'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    record = OUT / 'activation_record.json'
    if record.exists():
        raise SystemExit('Already activated; do not overwrite the activation record.')
    regpath, confpath = CONTROL / 'module_registry.json', CONTROL / 'project_config.json'
    reg = json.loads(regpath.read_text(encoding='utf-8-sig'))
    conf = json.loads(confpath.read_text(encoding='utf-8-sig'))
    m = next(m for m in reg['modules'] if m['module_id'] == '03')
    assert m['version'] == 2, 'Review current activation before migration.'
    backup = OUT / 'integration_before'
    backup.mkdir(exist_ok=False)
    paths = [regpath, confpath, BASE.parent / '版本索引.md', CONTROL / 'CHANGELOG.md', ROOT / 'README.md']
    before = []
    for i, p in enumerate(paths):
        b = backup / f'{i:02d}_{p.name}'
        b.write_bytes(p.read_bytes())
        before.append({'path': p.relative_to(ROOT).as_posix(), 'sha256': sha(p),
                       'backup_path': b.relative_to(ROOT).as_posix()})
    m['version'] = 3
    m['path'] = BASE.relative_to(ROOT).as_posix()
    conf['shared_resources']['resource_manifests']['03'] = (BASE / 'outputs/resource_snapshot.json').relative_to(ROOT).as_posix()
    regpath.write_text(json.dumps(reg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    confpath.write_text(json.dumps(conf, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (BASE.parent / '版本索引.md').write_text('''# 版本索引

当前版本：`v003_第3版`；由00第3版注册表启用，业务状态needs_review。

- [第3版](v003_第3版/模块说明.md)：20篇同一全文来源的语言定向审读、27条规则与原创例句、证据和措辞审查；G2未通过，G3不放行。
- [第2版](v002_第2版/模块说明.md)：一次性资源生命周期与框架占位，历史保留。
- [第1版](v001_第1版/模块说明.md)：初始框架，历史保留。
''', encoding='utf-8')
    changelog = CONTROL / 'CHANGELOG.md'
    with changelog.open('a', encoding='utf-8') as stream:
        stream.write('''
## 第三步语言资源激活

- 新增：03第3版真实语言定向审读候选、27条规则、原创示例与逐篇证据。
- 修改：注册表03版本及shared_resources入口；旧研究不迁移，旧版本保留。
- 兼容：保留CSV旧列，新增字段追加；默认single和投稿关闭保持原配置。
- 验收：03/outputs/resource_snapshot.json为needs_review，不认证G3；上游G2精读与段界验收未通过。技术记录见03第3版outputs/资源建设_attempt001/technical_validation.json。
''')
    with (ROOT / 'README.md').open('a', encoding='utf-8') as stream:
        stream.write('''
## 第三步语言学习成果

[语言手册](03_学术语言学习/v003_第3版/outputs/资源建设_attempt001/language_handbook.md)与[原创例句/反例](03_学术语言学习/v003_第3版/outputs/资源建设_attempt001/original_examples.md)已建立，覆盖第二步同一20篇正文的定向语言审读；[验收报告](03_学术语言学习/v003_第3版/outputs/资源建设_attempt001/验收报告.md)说明范围与缺口。03当前为第3版、needs_review；本轮没有认证20篇连续全文精读，G2未通过，因此G3正式放行仍待完成。
''')
    payload = {'activated_at': datetime.now(timezone(timedelta(hours=8))).isoformat(),
               'module_id': '03', 'from_version': 2, 'to_version': 3,
               'activated_as': 'needs_review_candidate', 'old_research_runs_migrated': False,
               'before': before,
               'after': [{'path': p.relative_to(ROOT).as_posix(), 'sha256': sha(p)} for p in paths]}
    record.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Activated module 03 v003 as needs_review candidate.')

if __name__ == '__main__':
    main()
