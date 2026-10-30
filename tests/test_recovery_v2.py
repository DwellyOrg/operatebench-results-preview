"""Temporary synthetic values only; no campaign outcomes are asserted."""
import copy
import unittest
from unittest.mock import patch
from test_selected_six import fixture, encode
from tools import build


def recovery():
    p = fixture()
    p.update(schema_version=2, source_revision=build.CORRECTION_SOURCE)
    rows = []
    for i, m in enumerate(p['models']):
        original, excluded, aborted = [(44,0,0),(13,31,0),(24,20,0),(15,29,0),(28,12,4),(38,6,0)][i]
        technical = excluded + aborted
        corrected = int(technical > 0)
        goal, reliable = [(44,38),(0,0),(0,0),(15,5),(25,5),(16,0)][i]
        m.update(scored=original+corrected, excluded=technical-corrected, aborted=0,
            goal_completed=goal, reliable=reliable)
        rows.append(dict(model=m['model'], original_scored=original,
            original_excluded=excluded, original_aborted=aborted, technical_selected=technical,
            distinct_attempted=technical, total_attempts=technical, terminal_attempts=technical, effective_original=original,
            effective_corrected=corrected, effective_unresolved=technical-corrected,
            attempt_groups=[dict(phase=phase, source_revision=source, basis="admitted-attempt-contract",
                registry_mapping_sha256=str(i)*64, count=count)
                for phase, source, count in [('original',build.ORIGINAL_SOURCE,44),
                    ('correction',build.CORRECTION_SOURCE,technical)] if count > 0]))
    p['provenance'] = dict(original_source_revision=build.ORIGINAL_SOURCE,
        correction_source_revision=build.CORRECTION_SOURCE, models=rows)
    return p


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        for name, value in [('ORIGINAL_SOURCE', 'a' * 40), ('CORRECTION_SOURCE', 'b' * 40)]:
            patcher = patch.object(build, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_valid_and_adverse(self):
        p = recovery()
        self.assertEqual(build.parse_selected_six(*encode(p)), p)
        mutations = [lambda p:p['provenance'].update(extra=1),
            lambda p:p['provenance'].update(original_source_revision='invalid'),
            lambda p:p['provenance']['models'].append(p['provenance']['models'][1]),
            lambda p:p['provenance']['models'][1].update(technical_selected=16),
            lambda p:p['provenance']['models'][1].update(distinct_attempted=True),
            lambda p:p['provenance']['models'][1].update(distinct_attempted=0),
            lambda p:p['provenance']['models'][1].update(effective_corrected=32),
            lambda p:p['models'][0].update(reliable=37),
            lambda p:p['provenance']['models'][1]['attempt_groups'][0].update(source_revision='b'*40),
            lambda p:p['provenance']['models'][1]['attempt_groups'][0].update(registry_mapping_sha256='B'*64),
            lambda p:p['provenance']['models'][1].update(effective_original=28),
            lambda p:p['provenance']['models'][1].update(terminal_attempts=16),
            lambda p:p['provenance']['models'][1]['attempt_groups'].append(p['provenance']['models'][1]['attempt_groups'][0]),
            lambda p:p['provenance']['models'][1]['attempt_groups'][0].update(count=45),
            lambda p:p['provenance']['models'][1]['attempt_groups'][0].update(extra='private'),
            lambda p:p['provenance']['models'][1]['attempt_groups'][1].update(source_revision='c'*40),
            lambda p:p['provenance']['models'][1]['attempt_groups'][1].update(basis='observed-request'),
            lambda p:p['provenance']['models'][1].update(model=p['models'][0]['model'])]
        for mutate in mutations:
            bad=copy.deepcopy(p); mutate(bad)
            with self.assertRaises(ValueError):
                build.parse_selected_six(*encode(bad))

    def test_final_coverage_and_terminal_disposition(self):
        for changes in (dict(distinct_attempted=1), dict(total_attempts=32),
                        dict(terminal_attempts=32), dict(total_attempts=True)):
            p = recovery()
            p['provenance']['models'][1].update(changes)
            with self.assertRaises(ValueError):
                build.parse_selected_six(*encode(p))

    def test_same_source_correction_group(self):
        p = recovery()
        groups = p['provenance']['models'][1]['attempt_groups']
        groups[1]['count'] -= 1
        groups.append(dict(groups[1], source_revision=build.ORIGINAL_SOURCE, count=1))
        self.assertEqual(build.parse_selected_six(*encode(p)), p)

    def test_export_and_shared_chart(self):
        from unittest.mock import patch
        p = recovery()
        original = build.average_rows()
        rows = sorted(original + build.selected_averages(p), key=build.average_order)
        costs = build.combined_costs(build.load_costs(r.model for r in original))
        import json
        exported = json.loads(build.aggregate_data(rows, costs, p))
        self.assertEqual(exported['selected_six_provenance']['provenance'], p['provenance'])
        self.assertEqual(len(exported['models']), 27)
        self.assertEqual([r for r in rows if r.model not in build.SELECTED_SIX_ROUTES], original)
        with patch.object(build, 'load_selected_six', return_value=p):
            html = build.render()
        self.assertEqual(html.count('<ol class="chart">'), 1)
        self.assertIn('Corrected technical attempts replace only excluded or aborted', html)
        self.assertIn('source revisions and admission registry mappings differ', html)
        for row in exported['models']:
            if row['model'] in build.SELECTED_SIX_ROUTES:
                self.assertIsNotNone(row['average_full_run_estimate'])
                self.assertEqual(row['observation_count'], 1)
