"""First real author-feedback regression suite derived from 《亲密而不承诺》 revisions."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE / "tools"))

import stage07  # noqa: F401 - initializes shared runtime sys.path
from language07 import style_findings
from manuscript07 import read_checklist
from runtime import value_hash
import qualitative07 as qual


def intimacy_fixture():
    names = ['问题的提出', '文献回顾', '理论分析框架', '资料与方法', '经验发现', '讨论与结论']
    row = {
        'dimension_id': 'D1',
        'status': 'tentative',
        'evidence': [{'material_id': 'M1', 'relation': 'support'}],
    }
    task = {
        'input_files': [],
        'sections': [{'section': n} for n in names],
        'materials': [{'material_id': 'M1'}],
        'literature': {'rows': [{'article_id': 'L1'}]},
        'theories': [{'theory_id': 'T1'}],
        'matrix': {'rows': [row]},
        'findings': [row],
    }
    headings = [f'{i}、{n}' for i, n in zip('一二三四五六', names)]
    s_abs = '暧昧并非亲密行为自动生成，而是在互动意义解释与预期成本评估中延续（案例一）。'
    s_lit = '婚姻市场与社会交换视角解释了伴侣匹配和回报互动，但缺少对关系确认前边界协商的连续分析（文献一）。'
    s_theory = '效用选择框架将情感收益与承诺成本的不确定性纳入同一判断链条（理论一）。'
    s_emp = '在大学阶段的连续交往中，当事人先经历了频繁日常陪伴与试探，再因承诺责任的不确定性维持既有边界（案例一）。'
    s_con = '关系确认的延迟源于情感收益与承诺风险的不对称预期，这一机制适用于关系身份尚未明晰的亲密交往（案例一）。'
    body = {
        headings[0]: '亲密互动与关系承诺并不同步，构成当代青年暧昧关系的核心张力。',
        headings[1]: s_lit,
        headings[2]: s_theory,
        headings[3]: '本文采用自我民族志方法，聚焦单段完整交往过程并按阶段性时间整理记录。',
        headings[4]: s_emp,
        headings[5]: s_con,
    }
    text = f'# 亲密而不承诺：青年暧昧关系中的风险与选择\n\n## 摘要\n{s_abs}\n关键词：青年暧昧；效用选择；情感风险；关系承诺\n'
    text += ''.join(f'\n## {h}\n{body[h]}\n' for h in headings)
    text += '\n## 参考文献\n文献一：亲密关系研究。\n理论一：效用选择理论。\n案例一：自我民族志记录。\n'
    draft = {
        'pack_id': value_hash(task),
        'authorship': 'author-feedback-fixture',
        'manuscript': text,
        'references': [
            {'source_id': 'L1', 'marker': '（文献一）', 'entry': '文献一：亲密关系研究。'},
            {'source_id': 'T1', 'marker': '（理论一）', 'entry': '理论一：效用选择理论。'},
            {'source_id': 'M1', 'marker': '（案例一）', 'entry': '案例一：自我民族志记录。'},
        ],
        'claims': [
            {'claim_id': 'C1', 'section': '摘要', 'text': s_abs, 'claim_type': 'result',
             'scope_limit': '关系确认前的亲密交往', 'source_ids': ['M1'], 'dimension_id': 'D1'},
            {'claim_id': 'C2', 'section': headings[1], 'text': s_lit, 'claim_type': 'synthesis',
             'scope_limit': '既有亲密关系理论路径', 'source_ids': ['L1'], 'dimension_id': ''},
            {'claim_id': 'C3', 'section': headings[2], 'text': s_theory, 'claim_type': 'inference',
             'scope_limit': '效用选择分析框架', 'source_ids': ['T1'], 'dimension_id': ''},
            {'claim_id': 'C4', 'section': headings[4], 'text': s_emp, 'claim_type': 'result',
             'scope_limit': '单段完整交往过程', 'source_ids': ['M1'], 'dimension_id': 'D1'},
            {'claim_id': 'C5', 'section': headings[5], 'text': s_con, 'claim_type': 'result',
             'scope_limit': '关系身份尚未明晰的交往', 'source_ids': ['M1'], 'dimension_id': 'D1'},
        ],
    }
    return task, draft


def make_review(folder, intake, decision='accepted', overrides=None, issues=None, thread='af-review'):
    folder.mkdir(parents=True, exist_ok=True)
    checks = {k: {'status': 'pass', 'reason': '已逐项核验符合递进与实质要求'} for k in qual.REVIEW_CHECKS}
    if overrides:
        checks.update(overrides)
    result = {
        'content_sha256': intake['content_sha256'],
        'decision': decision,
        'assessment': '真实作者反馈回归测试审查记录',
        'checks': checks,
        'issues': issues if issues is not None else ([] if decision == 'accepted' else [
            {'location': '五、经验发现', 'reason': '章节并列拼接，调换顺序不影响阅读', 'action': '重写递进衔接并聚焦主案例'}
        ]),
    }
    (folder / 'response.json').write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
    (folder / 'login_status.json').write_text('{"chatgpt": true}', encoding='utf-8')
    (folder / 'prompt.txt').write_text(intake['content_sha256'], encoding='utf-8')
    (folder / 'events.jsonl').write_text('\n'.join(map(json.dumps, [
        {'type': 'thread.started', 'thread_id': thread},
        {'type': 'turn.completed'},
    ])), encoding='utf-8')
    return result, qual.native_receipt(folder)


class AuthorFeedbackRegressionTests(unittest.TestCase):
    def test_checklist_and_substantive_questions_cover_all_eight_gates(self):
        rows = read_checklist(MODULE / 'templates/architecture_self_check.csv')
        ids = {row['check_id'] for row in rows}
        self.assertTrue({f'A{i}' for i in range(23, 31)} <= ids)
        self.assertEqual(len(qual.SUBSTANTIVE_REVIEW_QUESTIONS), 8)
        self.assertIn('chapter_swap_test', qual.REVIEW_CHECKS)
        self.assertIn('progression_and_coherence', qual.REVIEW_CHECKS)
        self.assertIn('narrative_integrity', qual.REVIEW_CHECKS)

    def test_defensive_prose_and_author_led_narration_are_flagged_while_scoped_judgment_passes(self):
        bad = (
            '本文并不是说亲密互动必然导向暧昧，也并不意味着承诺毫无作用。\n'
            '但这只是推测，这个解释没法证明当事人的真实动机。\n'
            '张小明（2020）指出，青年婚恋观念正在发生变化。\n'
            '## 参考文献\n- 张小明，2020，《青年婚恋》。\n'
        )
        hits = style_findings(bad)
        rule_ids = {h['rule_id'] for h in hits}
        self.assertIn('L06', rule_ids)
        self.assertIn('L05', rule_ids)

        good = (
            '在关系身份尚未确认的交往阶段，情感收益与承诺风险的不对称预期延缓了关系确认（张小明，2020）。\n'
            '该结论适用于尚未建立正式恋人身份的亲密互动。\n'
            '## 参考文献\n- 张小明，2020，《青年婚恋》。\n'
        )
        self.assertEqual(style_findings(good), [])

    def test_intimacy_positive_case_passes_and_chapter_swap_failure_blocks_acceptance(self):
        task, draft = intimacy_fixture()
        intake = qual.receive(task, draft)
        self.assertEqual(intake['status'], 'needs_review', intake['errors'])

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            ok_resp, ok_rec = make_review(root / 'pass_case', intake, decision='accepted', thread='af-pass')
            signoff = qual.independent_review(intake, ok_resp, ok_rec, set())
            self.assertEqual(signoff['decision'], 'accepted')

            bad_resp, bad_rec = make_review(
                root / 'swap_fail_accepted',
                intake,
                decision='accepted',
                overrides={'chapter_swap_test': {'status': 'revise', 'reason': '调换第三、四节顺序不影响阅读，属于并列拼接'}},
                issues=[],
                thread='af-swap-illegal',
            )
            with self.assertRaisesRegex(ValueError, '存在未修问题'):
                qual.independent_review(intake, bad_resp, bad_rec, set())

            rev_resp, rev_rec = make_review(
                root / 'swap_revise',
                intake,
                decision='revise',
                overrides={'chapter_swap_test': {'status': 'revise', 'reason': '调换章节顺序不影响论证推进'}},
                thread='af-swap-revise',
            )
            rev_signoff = qual.independent_review(intake, rev_resp, rev_rec, set())
            self.assertEqual(rev_signoff['decision'], 'revise')

    def test_defensive_manuscript_is_blocked_at_machine_intake(self):
        task, draft = intimacy_fixture()
        bad_draft = copy.deepcopy(draft)
        bad_draft['manuscript'] = bad_draft['manuscript'].replace(
            '亲密互动与关系承诺并不同步，构成当代青年暧昧关系的核心张力。',
            '本文并不是说所有青年都回避承诺，也并不意味着亲密必然导致暧昧。',
        )
        intake = qual.receive(task, bad_draft)
        self.assertEqual(intake['status'], 'needs_revision')
        self.assertTrue(any('L06' in err for err in intake['errors']))


if __name__ == '__main__':
    unittest.main()
