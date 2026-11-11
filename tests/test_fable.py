"""Approved real Fable integration and synthetic intake tests; no private evidence or Git required."""
import json
import re
import shutil
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from tools import build
from test_november import fixture as sonnet_fixture, encode


def fixture():
    value = sonnet_fixture()
    value.update(model=build.FABLE_MODEL, reasoning='adaptive-low', date='2026-11-10')
    for i, obs in enumerate(value['observations'], 1):
        obs['id'] = f'observation-{i}'
    return value


@patch.object(build, 'load_carbon', new=lambda: None)
class FableTests(unittest.TestCase):
    def test_closed_schema(self):
        self.assertEqual(build.parse_fable(*encode(fixture())), fixture())
        mutations = []
        for key, bad in [('schema_version', True), ('model', build.NOVEMBER_MODEL),
                ('provider', 'other'), ('endpoint', 'Messages'), ('reasoning', 'between_tools-low'),
                ('currency', 'EUR'), ('pricing_basis', 'other'), ('case_set', 'other'),
                ('source_revision', 'A'*40), ('date', '2026-11-09'), ('extra', 0),
                ('observations', []), ('observations', None)]:
            mutations.append(lambda v,k=key,b=bad: v.update({k:b}))
        for key, bad in [('id', 'test-only-1'), ('assigned', True), ('assigned', 43),
                ('scored', 0), ('scored', 44.0), ('excluded', -1), ('aborted', 2),
                ('goal_completed', 44), ('reliable', 41), ('incomplete_usage', 1),
                ('extra', 0), ('estimated_cost_low_usd', '9')]:
            mutations.append(lambda v,k=key,b=bad: v['observations'][0].update({k:b}))
        for bad in (None, True, 1, '-1', 'NaN', 'Infinity', '1e2', '01', '1.00', '0.0', '.1'):
            mutations.append(lambda v,b=bad: v['observations'][0].update(estimated_cost_high_usd=b))
        mutations.extend([lambda v:v['observations'][0].pop('reliable'),
            lambda v:v['observations'].__setitem__(1, v['observations'][0])])
        for mutate in mutations:
            value = fixture(); mutate(value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                build.parse_fable(*encode(value))
        raw, pin = encode(fixture())
        for bad in (None, True, '', 'g'*64, 'a'*63, '0'*64):
            with self.assertRaises(ValueError): build.parse_fable(raw, bad)
        for key in (b'"schema_version": 1', b'"id": "observation-1"', b'"model": "claude-fable-5-2"'):
            duplicate = raw.replace(key, key+b', '+key)
            with self.assertRaises(ValueError): build.parse_fable(duplicate, sha256(duplicate).hexdigest())
        with self.assertRaises(ValueError): build.parse_fable(raw+b' ', pin)

    def test_optional_render_export_and_preservation(self):
        with patch.object(build, 'load_fable', return_value=None):
            baseline = build.outputs()
        self.assertEqual(len(json.loads(baseline['MODEL_AVERAGES.json'])['models']), 28)
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('source', 'tools'): shutil.copytree(build.ROOT/name, root/name)
            shutil.copy(build.ROOT/'LICENSE-DATA', root/'LICENSE-DATA')
            (root/'source'/build.FABLE_FILE).unlink()
            with patch.object(build, 'ROOT', root):
                with patch.object(build, 'FABLE_DIGEST', None):
                    self.assertIsNone(build.load_fable())
                    self.assertEqual(build.outputs(), baseline)
                raw, pin = encode(fixture()); path = root/'source'/build.FABLE_FILE
                with patch.object(build, 'FABLE_DIGEST', pin), self.assertRaises(ValueError): build.outputs()
                path.write_bytes(raw)
                with self.assertRaises(ValueError): build.outputs()
                with patch.object(build, 'FABLE_DIGEST', pin):
                    files = build.outputs()
                    rows = json.loads(files['MODEL_AVERAGES.json'])['models']
                    self.assertEqual(len(rows), 29)
                    self.assertEqual([r for r in rows if r['model'] != build.FABLE_MODEL],
                                     json.loads(baseline['MODEL_AVERAGES.json'])['models'])
                    row = next(r for r in rows if r['model'] == build.FABLE_MODEL)
                    self.assertEqual(Fraction(**row['quality_rate']), Fraction(22,44))
                    self.assertEqual(Fraction(**row['goal_rate']), Fraction(1))
                    self.assertEqual(row['observation_count'], 1)
                    self.assertEqual(row['average_full_run_estimate']['mean_cost_high_usd'], '4.5')
                    self.assertFalse(row['average_full_run_estimate']['incomplete_usage'])
                    self.assertEqual(rows, sorted(rows, key=lambda r: (-Fraction(**r['quality_rate']),
                        -Fraction(**r['goal_rate']), r['model'].lower(), r['model'])))
                    with patch('sys.argv', ['build.py']): build.main()
                    with patch('sys.argv', ['build.py', '--check']): build.main()
                    self.assertEqual((root/'site'/build.FABLE_FILE).read_bytes(), raw)
                    self.assertEqual(files[build.FABLE_FILE], raw)
                    provenance = json.loads(files['MODEL_AVERAGES.json'])['fable_provenance']
                    self.assertEqual(provenance['sha256'], pin)
                    self.assertEqual(provenance['source_revision'], 'a'*40)
                    html = files['index.html'].decode()
                    chart = html.split('<ol class="chart">')[1].split('</ol>')[0]
                    self.assertEqual(chart.count('<li class="chart-row">'), 29)
                    self.assertIn('<strong>29</strong>', html)
                    self.assertIn('29 models', html)
                    self.assertIn('./'+build.FABLE_FILE, html)
                    self.assertIn('$4.50', chart)
                    self.assertNotRegex(chart.lower(), r'scored|assigned|badge|newcomer|experimental|\d+/\d+')
                    self.assertEqual(re.findall(r'<code>([^<]+)</code>', chart), [r['model'] for r in rows])
                    for name in baseline.keys()-{'index.html', 'MODEL_AVERAGES.json'}:
                        self.assertEqual(files[name], baseline[name])
                    original = Path.read_bytes; reads = []
                    def drift(p):
                        if p == path:
                            reads.append(p)
                            return raw if len(reads) <= 2 else raw+b' '
                        return original(p)
                    with patch.object(Path, 'read_bytes', drift), self.assertRaisesRegex(ValueError, 'Fable bytes drift'):
                        build.outputs()
                    path.write_bytes(raw+b' ')
                    with self.assertRaises(ValueError): build.outputs()

    def test_whole_run_selection_and_ties(self):
        packet = fixture()
        a, b = packet['observations']
        a.update(scored=20, reliable=19, goal_completed=19, incomplete_usage=False)
        b.update(scored=44, reliable=40, goal_completed=44, incomplete_usage=True)
        # Smaller raw pass count and worse goal rate still wins on exact quality.
        for observations in ([a, b], [b, a]):
            packet['observations'] = observations
            row, cost = build.fable_summary(packet)
            self.assertEqual(row.quality, Fraction(19,20))
            self.assertEqual(row.goal, Fraction(19,20))
            self.assertEqual(cost['mean_cost_low_usd'], a['estimated_cost_low_usd'])
            self.assertEqual(cost['mean_cost_high_usd'], a['estimated_cost_high_usd'])
            self.assertFalse(cost['incomplete_usage'])
        a.update(scored=44, reliable=40, goal_completed=43)
        self.assertEqual(build.select_fable_observation(packet)['id'], b['id'])
        a['goal_completed'] = 44
        self.assertEqual(build.select_fable_observation(packet)['id'], 'observation-1')
        packet['observations'].reverse()
        self.assertEqual(build.select_fable_observation(packet)['id'], 'observation-1')
        # Rates differing below display precision remain distinct.
        a.update(scored=10**30, reliable=5*10**29+1, goal_completed=10**30)
        b.update(scored=2, reliable=1, goal_completed=2)
        self.assertEqual(build.select_fable_observation(packet)['id'], a['id'])

    def test_shared_exact_math_and_ties(self):
        packet = fixture(); row = build.november_average(packet)
        better = build.Average('last', row.quality+Fraction(1,10**30), Fraction())
        goal = build.Average('later', row.quality, Fraction(1))
        tied = build.Average('Zulu', row.quality, row.goal)
        self.assertEqual(sorted([tied, row, goal, better], key=build.average_order), [better, goal, row, tied])
        for obs in packet['observations']:
            obs.update(estimated_cost_low_usd='0', estimated_cost_high_usd='0')
        self.assertEqual(build.money(build.november_cost(packet)), '$0.00')
        packet['observations'][0]['estimated_cost_high_usd'] = '123456789012345678901234567890.1'
        self.assertEqual(build.november_cost(packet)['mean_cost_high_usd'], '61728394506172839450617283945.05')

    def test_approved_real_packet_and_old_28_preservation(self):
        pin = '63d2878395c0030cd20cb30d1de46e820c49509074638f70db7ebe775290b515'
        raw = (build.ROOT/'source'/build.FABLE_FILE).read_bytes()
        self.assertEqual(len(raw), 955)
        self.assertEqual(build.FABLE_DIGEST, pin)
        self.assertEqual(sha256(raw).hexdigest(), pin)
        packet = build.load_fable()
        self.assertEqual(packet['source_revision'], '1c1cc3b005eaf7928400a0b50a1583826ea381c8')
        self.assertEqual([(o['assigned'], o['scored'], o['excluded'], o['aborted'],
            o['goal_completed'], o['reliable'], o['estimated_cost_low_usd'],
            o['estimated_cost_high_usd'], o['incomplete_usage']) for o in packet['observations']],
            [(44,44,0,0,44,31,'73.005296','73.005296',False),
             (44,44,0,0,44,30,'72.68744','72.68744',False)])
        with patch.object(build, 'load_fable', return_value=None):
            old = build.outputs()
        files = build.outputs()
        old_rows = json.loads(old['MODEL_AVERAGES.json'])['models']
        self.assertEqual(len(old_rows), 28)
        data = json.loads(files['MODEL_AVERAGES.json'])
        rows = data['models']
        self.assertEqual(len(rows), 29)
        self.assertEqual([r for r in rows if r['model'] != build.FABLE_MODEL], old_rows)
        self.assertEqual(set(files), set(old) | {build.FABLE_FILE})
        for name in old.keys() - {'index.html', 'MODEL_AVERAGES.json'}:
            self.assertEqual(files[name], old[name], name)
        self.assertEqual(files[build.FABLE_FILE], raw)
        self.assertEqual(data['fable_provenance'], dict(packet=build.FABLE_FILE, sha256=pin,
            **{k:v for k,v in packet.items() if k != 'observations'}))
        row = next(r for r in rows if r['model'] == build.FABLE_MODEL)
        self.assertEqual(Fraction(**row['quality_rate']), Fraction(31,44))
        self.assertEqual(Fraction(**row['goal_rate']), Fraction(1))
        self.assertEqual(row['aggregation_method'], 'best_quality_observation')
        self.assertEqual(row['selected_observation_id'], 'observation-1')
        self.assertEqual(row['available_observation_count'], 2)
        self.assertEqual(row['observation_count'], 1)
        self.assertEqual(row['average_quality_percent'], '70.5%')
        self.assertEqual(row['average_goal_achieved_percent'], '100.0%')
        self.assertEqual(row['average_full_run_estimate'], dict(model=build.FABLE_MODEL,
            mean_cost_low_usd='73.005296', mean_cost_high_usd='73.005296',
            incomplete_usage=False, pricing_basis='official_current_tariff_estimate'))
        self.assertEqual(rows, sorted(rows, key=lambda r: (-Fraction(**r['quality_rate']),
            -Fraction(**r['goal_rate']), r['model'].lower(), r['model'])))
        html = files['index.html'].decode()
        self.assertIn('Fable 5.2 uses the best-quality of two runs', html)
        self.assertIn('other models retain averages', html)
        rendered = build.render()
        self.assertEqual(rendered, html)
        self.assertNotIn('Both are average percentages across one or two observations.', rendered)
        self.assertNotIn('Both are average percentages across two observations.', rendered)
        self.assertIn('Percentages follow the per-model methodology above.', rendered)
        self.assertIn('Fable 5.2 uses the best-quality of two runs (one whole observation); other models retain averages,', rendered)
        self.assertNotIn('Download model averages', html)
        chart = html.split('<ol class="chart">')[1].split('</ol>')[0]
        self.assertEqual(chart.count('<li class="chart-row">'), 29)
        item = next(i for i in chart.split('<li class="chart-row">') if '<code>'+build.FABLE_MODEL+'</code>' in i)
        self.assertEqual(re.findall(r'<strong>(.*?)</strong>', item), ['70.5%', '100.0%', '$73.01'])
        self.assertNotRegex(chart.lower(), r'scored|assigned|badge|newcomer|experimental|\d+/\d+')
        for text in ('descriptive, not a controlled ranking', 'technical exclusions', 'not invoices', 'missing usage is excluded'):
            self.assertIn(text, html)
