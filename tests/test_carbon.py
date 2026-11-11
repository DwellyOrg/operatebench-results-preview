"""Approved Carbon packet, portable historical parity, and adverse intake tests."""
import copy
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
from test_november import fixture as november_fixture, encode


def fixture():
    packet = november_fixture()
    packet.update(model='gemini-4-carbon', provider='gemini', endpoint='generateContent',
                  reasoning='low', date='2026-11-11')
    for i, obs in enumerate(packet['observations'], 1):
        obs['id'] = f'observation-{i}'
    return packet


class CarbonTests(unittest.TestCase):
    def test_closed_schema_and_byte_controls(self):
        packet = fixture()
        self.assertEqual(build.parse_carbon(*encode(packet)), packet)
        mutations = [(k, v) for k, v in [('schema_version', True), ('model', 'other'),
            ('provider', 'anthropic'), ('endpoint', 'messages'), ('reasoning', 'LOW'),
            ('date', '2026-11-10'), ('source_revision', 'A'*40), ('case_set', 'other'),
            ('currency', 'EUR'), ('pricing_basis', 'other'), ('extra', 1), ('observations', [])]]
        for key, value in mutations:
            bad = copy.deepcopy(packet); bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                build.parse_carbon(*encode(bad))
        for key, value in [('id', 'other'), ('assigned', 43), ('scored', True),
                ('scored', 0), ('excluded', -1), ('aborted', 1), ('goal_completed', 44),
                ('reliable', 41), ('extra', 0), ('incomplete_usage', 1),
                ('estimated_cost_low_usd', '9')]:
            bad = copy.deepcopy(packet); bad['observations'][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                build.parse_carbon(*encode(bad))
        for value in (None, True, 1, '-1', 'NaN', 'Infinity', '1e2', '01', '1.00', '0.0', '.1'):
            bad = copy.deepcopy(packet); bad['observations'][0]['estimated_cost_high_usd'] = value
            with self.assertRaises(ValueError): build.parse_carbon(*encode(bad))
        bad = copy.deepcopy(packet); bad['observations'][1] = bad['observations'][0]
        with self.assertRaises(ValueError): build.parse_carbon(*encode(bad))
        bad = copy.deepcopy(packet); del bad['observations'][0]['reliable']
        with self.assertRaises(ValueError): build.parse_carbon(*encode(bad))
        raw, pin = encode(packet)
        for bad in (None, True, '', 'g'*64, 'a'*63, '0'*64):
            with self.assertRaises(ValueError): build.parse_carbon(raw, bad)
        for key in (b'"schema_version": 1', b'"id": "observation-1"', b'"model": "gemini-4-carbon"'):
            duplicate = raw.replace(key, key+b', '+key)
            with self.assertRaises(ValueError): build.parse_carbon(duplicate, sha256(duplicate).hexdigest())
        with self.assertRaises(ValueError): build.parse_carbon(raw+b' ', pin)

    def test_synthetic_activation_and_disabled_parity(self):
        with patch.object(build, 'load_carbon', return_value=None): baseline = build.outputs()
        old = json.loads(baseline['MODEL_AVERAGES.json'])['models']
        self.assertEqual(len(old), 29)
        with TemporaryDirectory(prefix='synthetic-carbon-') as directory:
            root = Path(directory)
            for name in ('source', 'tools'): shutil.copytree(build.ROOT/name, root/name)
            shutil.copy(build.ROOT/'LICENSE-DATA', root/'LICENSE-DATA')
            path = root/'source'/build.CARBON_FILE
            path.unlink(missing_ok=True)
            with patch.object(build, 'ROOT', root), patch.object(build, 'CARBON_DIGEST', None):
                self.assertIsNone(build.load_carbon())
                self.assertEqual(build.outputs(), baseline)
                raw, pin = encode(fixture())
                with patch.object(build, 'CARBON_DIGEST', pin), self.assertRaises(ValueError): build.outputs()
                path.write_bytes(raw)
                with self.assertRaises(ValueError): build.outputs()
                with patch.object(build, 'CARBON_DIGEST', pin):
                    files = build.outputs(); data = json.loads(files['MODEL_AVERAGES.json']); rows = data['models']
                    self.assertEqual(len(rows), 30)
                    self.assertEqual([r for r in rows if r['model'] != build.CARBON_MODEL], old)
                    row = next(r for r in rows if r['model'] == build.CARBON_MODEL)
                    self.assertEqual(Fraction(**row['quality_rate']), (Fraction(20,43)+Fraction(22,44))/2)
                    self.assertEqual(Fraction(**row['goal_rate']), (Fraction(40,43)+1)/2)
                    self.assertEqual(row['observation_count'], 2)
                    self.assertNotIn('aggregation_method', row)
                    self.assertEqual(row['average_full_run_estimate'], dict(model=build.CARBON_MODEL,
                        pricing_basis='official_current_tariff_estimate', incomplete_usage=True,
                        mean_cost_low_usd='2.2', mean_cost_high_usd='3.4'))
                    self.assertEqual(rows, sorted(rows, key=lambda r: (-Fraction(**r['quality_rate']),
                        -Fraction(**r['goal_rate']), r['model'].lower(), r['model'])))
                    self.assertEqual(files[build.CARBON_FILE], raw)
                    self.assertEqual(data['carbon_provenance'], dict(packet=build.CARBON_FILE, sha256=pin,
                        **{k:v for k,v in fixture().items() if k != 'observations'}))
                    for name in baseline.keys()-{'index.html', 'MODEL_AVERAGES.json'}:
                        self.assertEqual(files[name], baseline[name])
                    html = files['index.html'].decode(); chart = html.split('<ol class="chart">')[1].split('</ol>')[0]
                    self.assertEqual(chart.count('<li class="chart-row">'), 30)
                    self.assertIn('30 models', html); self.assertIn('./'+build.CARBON_FILE, html)
                    self.assertIn('$3.40', chart)
                    self.assertNotRegex(chart.lower(), r'scored|assigned|coverage|badge|newcomer|experimental|\d+/\d+')
                    with patch('sys.argv', ['build.py']): build.main()
                    with patch('sys.argv', ['build.py', '--check']): build.main()
                    original = Path.read_bytes; reads = []
                    def drift(p):
                        if p == path:
                            reads.append(p)
                            return raw if len(reads) <= 2 else raw+b' '
                        return original(p)
                    with patch.object(Path, 'read_bytes', drift), self.assertRaisesRegex(ValueError, 'Carbon bytes drift'):
                        build.outputs()

    def test_exact_ties_and_cost_unit(self):
        packet = fixture(); row = build.november_average(packet)
        better = build.Average('last', row.quality+Fraction(1,10**30), Fraction())
        goal = build.Average('later', row.quality, Fraction(1))
        a = build.Average('Alpha', row.quality, row.goal)
        b = build.Average('alpha', row.quality, row.goal)
        self.assertEqual(sorted([b,row,goal,better,a], key=build.average_order), [better,goal,a,b,row])
        for obs in packet['observations']:
            obs.update(estimated_cost_low_usd='0', estimated_cost_high_usd='0')
        self.assertEqual(build.money(build.november_cost(packet)), '$0.00')
        packet['observations'][0]['estimated_cost_high_usd'] = '123456789012345678901234567890.1'
        self.assertEqual(build.november_cost(packet)['mean_cost_high_usd'], '61728394506172839450617283945.05')


class ApprovedCarbonTests(unittest.TestCase):
    def test_real_approved_packet_and_historical_parity(self):
        fixtures = build.ROOT/'tests/fixtures'
        baseline = json.loads((fixtures/'pre_carbon_models.json').read_bytes())
        files = build.outputs()  # Actual enabled packet, without intake mocks.
        data = json.loads(files['MODEL_AVERAGES.json'])
        rows = data['models']
        self.assertEqual(len(rows), 30)
        self.assertEqual([r for r in rows if r['model'] != 'gemini-4-carbon'], baseline['models'])
        for key in baseline.keys() - {'models', 'cost_assumptions'}:
            self.assertEqual(data[key], baseline[key], key)
        self.assertEqual(data['cost_assumptions'], build.CARBON_COST_SCOPE + baseline['cost_assumptions'])
        for name, digest in json.loads((fixtures/'pre_carbon_hashes.json').read_bytes()).items():
            if name in ('site/MODEL_AVERAGES.json', 'site/index.html'):
                continue  # Derived assets must change for the enabled 30-model intake.
            raw = (build.ROOT/name).read_bytes()
            self.assertEqual(sha256(raw).hexdigest(), digest, name)
            if name.startswith('site/'):
                self.assertEqual(files[name[5:]], raw, name)
        raw = (build.ROOT/'source/CARBON_20261111.json').read_bytes()
        pin = '09aae295f8c20f2015354a422e3c3d7545a2d330299633def52f20290d91b936'
        self.assertEqual(len(raw), 949)
        self.assertEqual(sha256(raw).hexdigest(), pin)
        self.assertEqual(build.CARBON_DIGEST, pin)
        self.assertEqual(files['CARBON_20261111.json'], raw)
        self.assertEqual((build.ROOT/'site/CARBON_20261111.json').read_bytes(), raw)
        packet = build.parse_carbon(raw, pin)
        self.assertEqual(packet['source_revision'], '19aaf4397e4e8752d62984617a2e41f19dcc2aa2')
        self.assertEqual([(o['assigned'],o['scored'],o['goal_completed'],o['reliable'],
            o['excluded'],o['aborted'],o['incomplete_usage']) for o in packet['observations']],
            [(44,44,44,42,0,0,False),(44,44,44,43,0,0,False)])
        row = next(r for r in rows if r['model'] == 'gemini-4-carbon')
        self.assertEqual(Fraction(**row['quality_rate']), Fraction(85,88))
        self.assertEqual(Fraction(**row['goal_rate']), Fraction(1))
        self.assertEqual(row['average_quality_percent'], '96.6%')
        self.assertEqual(row['average_goal_achieved_percent'], '100.0%')
        self.assertEqual(row['observation_count'], 2)
        self.assertNotIn('aggregation_method', row)
        self.assertEqual(row['average_full_run_estimate'], dict(model='gemini-4-carbon',
            pricing_basis='official_current_tariff_estimate', incomplete_usage=False,
            mean_cost_low_usd='95.343778', mean_cost_high_usd='95.343778'))
        self.assertEqual(data['carbon_provenance'], dict(packet='CARBON_20261111.json', sha256=pin,
            **{k:v for k,v in packet.items() if k != 'observations'}))
        ordered = sorted(rows, key=lambda r: (-Fraction(**r['quality_rate']),
            -Fraction(**r['goal_rate']), r['model'].lower(), r['model']))
        self.assertEqual(rows, ordered)
        rank = ordered.index(row) + 1
        html = files['index.html'].decode()
        chart = html.split('<ol class="chart">')[1].split('</ol>')[0]
        self.assertEqual(chart.count('<li class="chart-row">'), 30)
        carbon = next(part for part in chart.split('<li class="chart-row">') if 'gemini-4-carbon' in part)
        self.assertIn(f'>{rank:02d}</span>', carbon)
        for value in ('96.6%', '100.0%', '$95.34'):
            self.assertIn(value, carbon)
        self.assertNotRegex(chart.lower(), r'scored|assigned|coverage|badge|88/88|\d+/\d+')
        self.assertIn('30 models', html)
        self.assertIn('best-quality of two runs (one whole observation)', html)
        self.assertIn('Percentages follow the per-model methodology above.', html)
        self.assertIn('30 models · sorted by quality', html)
        self.assertIn('<span>Quality ↓</span>', html)
        self.assertIn('class="chart-stat quality-stat"', carbon)
        self.assertIn('./CARBON_20261111.json', html)
        for name, raw in files.items():
            for forbidden in (b'/root/', b'196eb', b'PUBLIC-PACKET-APPROVAL', b'FINANCE-AFTER', b'CREDENTIALS'):
                self.assertNotIn(forbidden, raw, name)

    def test_disabled_intake_matches_all_base_bytes(self):
        manifest = json.loads((build.ROOT/'tests/fixtures/pre_carbon_hashes.json').read_bytes())
        self.assertEqual(len(manifest), 22)
        with patch.object(build, 'load_carbon', return_value=None):
            files = build.outputs()
        self.assertEqual(len(json.loads(files['MODEL_AVERAGES.json'])['models']), 29)
        for name, digest in manifest.items():
            raw = files[name[5:]] if name.startswith('site/') else (build.ROOT/name).read_bytes()
            self.assertEqual(sha256(raw).hexdigest(), digest, name)
