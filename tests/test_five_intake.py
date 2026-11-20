"""Synthetic, inert tests of the five-model intake; these are not benchmark results."""
import copy
import json
import itertools
import html
import re
import shutil
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from tools import build
from test_openai62 import fixture, encode


class FiveIntakeTests(unittest.TestCase):
    def test_approved_hydrogen_and_neon(self):
        expected = {
            'gemini-4-hydrogen': (10, '56.285823', '6cc8dcbac6f9cfb993c8c9b25cacaf17fc80ec852618f00e029b2c0ce4d5ee73'),
            'gemini-4-neon': (39, '109.913439', 'd44eee5ef1a5b6d8aae10c3daae2c8409bfcb2c7621f816a246c9e0d25427435'),
        }
        files = build.outputs()
        data = json.loads(files['MODEL_AVERAGES.json'])
        self.assertEqual(len(data['models']), 34)
        self.assertEqual({p['model'] for p in build.load_five()}, set(expected))
        self.assertEqual(len(files), 19)
        self.assertIn('.nojekyll', files)
        for model, (reliable, cost, pin) in expected.items():
            raw = (build.ROOT / 'source' / build.FIVE_FILES[model]).read_bytes()
            self.assertEqual(sha256(raw).hexdigest(), pin)
            self.assertEqual(files[build.FIVE_FILES[model]], raw)
            packet = build.parse_five(raw, pin, model)
            self.assertEqual(packet['source_revision'], '1fdb4a470231088cb05adf3daa4fb867e228d02a')
            obs = packet['observations'][0]
            self.assertEqual((obs['assigned'], obs['scored'], obs['goal_completed'], obs['reliable']), (44, 44, 44, reliable))
            row = next(row for row in data['models'] if row['model'] == model)
            self.assertEqual(row['observation_count'], 1)
            self.assertEqual(row['average_full_run_estimate']['mean_cost_high_usd'], cost)
            self.assertIn(model + ' observation aggregates (JSON)', files['index.html'].decode())
        self.assertIn('served setting is not independently attested', data['cost_assumptions'])

    def test_counts_and_cost_scope_for_optional_models(self):
        real = build.load_five()
        other = [fixture(model) for model in list(build.FIVE_FILES)[2:]]
        for packet in other:
            packet['cost_assumptions'] = 'Synthetic scope for ' + packet['model'] + ' & test.'
        scenarios = ([], real[:1], real[1:], real, real + other, other[:1])
        for packets in scenarios:
            with self.subTest(models=[p['model'] for p in packets]):
                with patch.object(build, 'load_five', return_value=packets):
                    page = build.render()
                count = 32 + len(packets)
                self.assertIn('both OpenAI 6.2 models have one observation each', page)
                self.assertNotRegex(page, r'OpenAI 6\.(?:32|33|34|37) models')
                self.assertIn(f'{count} models · sorted by quality', page)
                self.assertIn(f'<strong>{count}</strong><span>models observed</span>', page)
                scope = build.five_cost_scope(packets)
                note = html.unescape(re.search(r'<p id="cost-note">(.*?)</p>', page).group(1))
                data = json.loads(build.aggregate_data([], {'models': [], 'assumptions': 'BASE'}, five=packets))
                self.assertTrue(note.startswith(scope))
                self.assertEqual(data['cost_assumptions'], scope + 'BASE')
                for assumption in {p['cost_assumptions'] for p in packets}:
                    self.assertEqual(note.count(assumption), 1)
                    self.assertEqual(data['cost_assumptions'].count(assumption), 1)
                for model in ('gemini-4-hydrogen', 'gemini-4-neon'):
                    prefix = scope.split('the served setting is not independently attested. ')[0] if 'the served setting is not independently attested. ' in scope else ''
                    self.assertEqual(model in prefix, any(p['model'] == model for p in packets))
                if not packets:
                    self.assertEqual(scope, '')
                if len(packets) == 5:
                    self.assertIn('&amp; test.', page)

    def test_decoder_and_rejections(self):
        for model in build.FIVE_FILES:
            packet = fixture(model)
            packet.update(provider='provider', endpoint='endpoint', reasoning='setting')
            raw, pin = encode(packet)
            self.assertEqual(build.parse_five(raw, pin, model), packet)
            for change in ('extra', 'route', 'coverage', 'cost', 'revision'):
                bad = copy.deepcopy(packet)
                if change == 'extra': bad['extra'] = 1
                if change == 'route': bad['endpoint'] = '../private'
                if change == 'coverage': bad['observations'][0]['scored'] = 44
                if change == 'cost': bad['observations'][0]['estimated_cost_low_usd'] = '1.0'
                if change == 'revision': bad['source_revision'] = 'not-a-public-revision'
                with self.subTest(model=model, change=change), self.assertRaises(ValueError):
                    build.parse_five(*encode(bad), model)
            with self.assertRaises(ValueError): build.parse_five(raw + b' ', pin, model)
            with self.assertRaises(ValueError): build.parse_five(raw, None, model)
            duplicate = raw.replace(b'"model":', b'"model": "duplicate", "model":', 1)
            with self.assertRaises(ValueError): build.parse_five(duplicate, sha256(duplicate).hexdigest(), model)

    def test_additional_sources_are_closed_and_opt_in(self):
        model = next(iter(build.FIVE_FILES))
        packet = fixture(model)
        packet['additional_source_revisions'] = ['b' * 40, 'c' * 40]
        self.assertEqual(build.parse_five(*encode(packet), model), packet)
        for invalid in ([], None, 'b' * 40, True, [True], [1], ['b' * 40, 'b' * 40],
                        ['a' * 40], ['B' * 40], ['b' * 39], ['g' * 40]):
            bad = copy.deepcopy(packet)
            bad['additional_source_revisions'] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                build.parse_five(*encode(bad), model)
        raw, _ = encode(packet)
        duplicate = raw.replace(b'"additional_source_revisions":',
                                b'"additional_source_revisions": [], "additional_source_revisions":', 1)
        with self.assertRaises(ValueError):
            build.parse_five(duplicate, sha256(duplicate).hexdigest(), model)
        legacy = fixture(next(iter(build.OPENAI62_FILES)))
        legacy['additional_source_revisions'] = ['b' * 40]
        with self.assertRaises(ValueError):
            build.parse_openai62(*encode(legacy), legacy['model'])

    def test_additional_sources_export_and_provenance(self):
        with patch.object(build, 'load_five', return_value=[]):
            baseline = build.outputs()
        model = next(iter(build.FIVE_FILES))
        packet = fixture(model)
        packet['additional_source_revisions'] = ['b' * 40, 'c' * 40]
        raw, pin = encode(packet)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(build.ROOT / 'source', root / 'source')
            shutil.copytree(build.ROOT / 'tools', root / 'tools')
            shutil.copy(build.ROOT / 'LICENSE-DATA', root / 'LICENSE-DATA')
            for filename in build.FIVE_FILES.values():
                (root / 'source' / filename).unlink(missing_ok=True)
            (root / 'source' / build.FIVE_FILES[model]).write_bytes(raw)
            pins = {m: pin if m == model else None for m in build.FIVE_FILES}
            with patch.object(build, 'ROOT', root), patch.object(build, 'FIVE_DIGESTS', pins):
                files = build.outputs()
                self.assertEqual(files[build.FIVE_FILES[model]], raw)
                data = json.loads(files['MODEL_AVERAGES.json'])
                old = json.loads(baseline['MODEL_AVERAGES.json'])['models']
                rows = {row['model']: row for row in data['models']}
                self.assertEqual([rows[row['model']] for row in old], old)
                provenance = data['five_provenance'][0]
                revisions = [packet['source_revision']] + packet['additional_source_revisions']
                urls = [build.UPSTREAM + '/tree/' + revision for revision in revisions]
                self.assertEqual(provenance['source_urls'], urls)
                self.assertEqual(provenance['additional_source_revisions'], revisions[1:])
                for url in urls:
                    self.assertIn('href="' + url + '"', files['index.html'].decode())
                self.assertEqual(files, build.outputs())

    def test_missing_pins_activation_and_historical_parity(self):
        with patch.object(build, 'load_five', return_value=[]):
            baseline = build.outputs()
        baseline_rows = {r['model']: r for r in json.loads(baseline['MODEL_AVERAGES.json'])['models']}
        self.assertEqual(len(baseline_rows), 32)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(build.ROOT / 'source', root / 'source')
            shutil.copytree(build.ROOT / 'tools', root / 'tools')
            shutil.copy(build.ROOT / 'LICENSE-DATA', root / 'LICENSE-DATA')
            for filename in build.FIVE_FILES.values():
                (root / 'source' / filename).unlink(missing_ok=True)
            pins = {m: None for m in build.FIVE_FILES}
            with patch.object(build, 'ROOT', root), patch.object(build, 'FIVE_DIGESTS', pins):
                self.assertEqual(build.outputs(), baseline)
                for model, filename in build.FIVE_FILES.items():
                    raw, pin = encode(fixture(model))
                    path = root / 'source' / filename
                    path.write_bytes(raw)
                    with self.assertRaises(ValueError): build.load_five()
                    pins[model] = pin
                active = build.outputs()
                data = json.loads(active['MODEL_AVERAGES.json'])
                rows = {r['model']: r for r in data['models']}
                self.assertEqual(len(rows), 37)
                self.assertEqual({m: rows[m] for m in baseline_rows}, baseline_rows)
                html = active['index.html'].decode()
                for model, filename in build.FIVE_FILES.items():
                    self.assertEqual(active[filename], (root / 'source' / filename).read_bytes())
                    self.assertEqual(rows[model]['observation_count'], 1)
                    self.assertIn(model + ' observation aggregates (JSON)', html)
                self.assertEqual(active, build.outputs())
                (root / 'source' / next(iter(build.FIVE_FILES.values()))).unlink()
                with self.assertRaises(ValueError): build.load_five()

    def test_method_and_caption_with_optional_combinations(self):
        packet = fixture(next(iter(build.FIVE_FILES)))
        packet['additional_source_revisions'] = ['b' * 40]
        loaders = ('load_selected_six', 'load_november', 'load_fable', 'load_carbon', 'load_openai62')
        real = [getattr(build, name)() for name in loaders]
        for flags in itertools.product((False, True), repeat=len(loaders)):
            patches = [patch.object(build, name, return_value=value if enabled else ([] if name == 'load_openai62' else None))
                       for name, value, enabled in zip(loaders, real, flags)]
            with self.subTest(flags=flags):
                with patch.object(build, 'load_five', return_value=[packet]):
                    for item in patches: item.start()
                    try:
                        html = build.render()
                        self.assertIn('additional intake models use one observation each', html)
                        self.assertIn('Additional intake models use one observation each.', html)
                        self.assertIn(build.UPSTREAM + '/tree/' + 'b' * 40, html)
                        self.assertNotIn('Both are average percentages across two observations.', html)
                    finally:
                        for item in reversed(patches): item.stop()

    def test_optional_intake_without_earlier_features(self):
        model = next(iter(build.FIVE_FILES))
        packet = fixture(model)
        with patch.object(build, 'load_five', return_value=[packet]), \
             patch.object(build, 'load_selected_six', return_value=None), \
             patch.object(build, 'load_openai62', return_value=[]), \
             patch.object(build, 'load_fable', return_value=None), \
             patch.object(build, 'load_carbon', return_value=None), \
             patch.object(build, 'load_november', return_value=None):
            html = build.render()
            self.assertIn('one or two original per-observation rates', html)
            self.assertIn('additional intake models use one observation each', html)
            self.assertNotIn('Both are average percentages across two observations.', html)
            rows = build.average_rows() + [build.november_average(packet)]
            costs = build.load_costs(r.model for r in rows if r.model != model)
            costs['models'].append(build.november_cost(packet))
            data = json.loads(build.aggregate_data(rows, costs, five=[packet]))
            self.assertIn('mean of one or two', data['method'])
            self.assertIn('Each additional intake model uses one observation.', data['method'])
