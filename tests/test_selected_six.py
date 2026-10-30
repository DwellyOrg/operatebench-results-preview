"""Adversarial synthetic intake tests and independent accepted-data goldens."""
import copy
import json
import re
from fractions import Fraction
from hashlib import sha256
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from tools import build


def fixture():
    models = []
    for i, (model, (provider, endpoint)) in enumerate(build.SELECTED_SIX_ROUTES.items()):
        scored = 7 if i == 5 else 44 - i
        models.append(dict(model=model, assigned=44, scored=scored, excluded=44-scored, aborted=0,
            goal_completed=i, reliable=max(0, i-1), observation_count=1, provider=provider,
            endpoint=endpoint or 'synthetic-native', wire_model=model, reasoning='synthetic', cost_usd=None))
    return dict(schema_version=1, series=build.SELECTED_SIX_SERIES, date='2026-10-29',
        conditions='Synthetic test only. Heterogeneous evaluator settings.',
        source_revision='a'*40, evaluator='synthetic-v1', models=models)


def encode(value):
    raw = json.dumps(value).encode()
    return raw, sha256(raw).hexdigest()


class ChartModelParser(HTMLParser):
    """Capture element parentage within each chart-model flex container."""
    def __init__(self):
        super().__init__()
        self.models = []
        self.stack = []

    def handle_starttag(self, tag, attrs):
        if tag == 'div' and dict(attrs).get('class') == 'chart-model':
            node = (tag, dict(attrs), [])
            self.models.append(node)
            self.stack = [node]
        elif self.stack:
            node = (tag, dict(attrs), [])
            self.stack[-1][2].append(node)
            if tag != 'br':
                self.stack.append(node)

    def handle_endtag(self, tag):
        if self.stack:
            assert self.stack[-1][0] == tag
            self.stack.pop()

    def handle_data(self, data):
        if self.stack:
            self.stack[-1][2].append(data)


class SelectedSixTests(unittest.TestCase):
    def test_public_chart_omits_scored_counts_preserves_metrics_and_order(self):
        html = build.render()
        chart = re.findall(r'<li class="chart-row">(.*?)</li>', html)
        rows = sorted(build.average_rows() + build.selected_averages(build.load_selected_six()),
                      key=build.average_order)
        self.assertEqual(len(chart), 27)
        self.assertEqual(len(rows), 27)
        for item, row in zip(chart, rows):
            with self.subTest(model=row.model):
                self.assertIn('<code>' + row.model + '</code>', item)
                self.assertEqual(re.findall(r'<strong>(.*?)</strong>', item)[:2],
                                 [build.percent(row.quality), build.percent(row.goal)])
                self.assertNotRegex(item.lower(), r'scored|assigned|coverage|\d+/\d+|<small|<details|title=')
        self.assertNotIn('Coverage is total scored/assigned', html)

    def test_current_generated_bytes_and_census(self):
        packet = build.load_selected_six()
        files = build.outputs()
        rows = json.loads(files['MODEL_AVERAGES.json'])['models']
        expected = {row.model for row in build.average_rows()}
        self.assertEqual(len(expected), 21)
        if build.SELECTED_SIX_DIGEST is None:
            self.assertIsNone(packet)
        else:
            self.assertIsNotNone(packet)
            selected = {row['model'] for row in packet['models']}
            self.assertEqual(len(selected), 6)
            self.assertTrue(expected.isdisjoint(selected))
            expected |= selected
        self.assertEqual(len(rows), len(expected))
        self.assertEqual({row['model'] for row in rows}, expected)
        for name, raw in files.items():
            self.assertEqual(raw, (build.ROOT/'site'/name).read_bytes(), name)

    def test_schema_independent_of_pin(self):
        raw, pin = encode(fixture())
        self.assertEqual(build.parse_selected_six(raw, pin), fixture())
        changes = [lambda v:v.update(extra=1), lambda v:v.update(schema_version=True),
            lambda v:v.update(date='2026-02-30'), lambda v:v.update(conditions='/root/private'),
            lambda v:v.update(evaluator='https://secret'), lambda v:v.update(source_revision='A'*40),
            lambda v:v['models'].pop(), lambda v:v['models'].append(v['models'][0])]
        for key, value in [('extra', 1), ('assigned',True), ('scored',0), ('excluded',5),
            ('cost_usd',0), ('observation_count',True), ('model','zai-org/GLM-5.3-Flash'),
            ('wire_model','Flash'), ('provider','other'), ('endpoint','/private/path'),
            ('reasoning','secret=value'), ('reliable',45), ('goal_completed',-1)]:
            changes.append(lambda v,k=key,x=value:v['models'][0].update({k:x}))
        for change in changes:
            value=fixture(); change(value); raw,pin=encode(value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                build.parse_selected_six(raw,pin)
        raw,pin=encode(fixture())
        duplicate=raw.replace(b'"schema_version": 1',b'"schema_version": 1, "schema_version": 1')
        with self.assertRaises(ValueError): build.parse_selected_six(duplicate,sha256(duplicate).hexdigest())
        for bad in (None,True,'g'*64,'a'*63):
            with self.assertRaises(ValueError): build.parse_selected_six(raw,bad)
        with self.assertRaises(ValueError): build.parse_selected_six(raw+b' ',pin)

    def test_final_export_bytes_drift(self):
        raw, pin = encode(fixture())
        original_read_bytes = Path.read_bytes
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('source', 'tools'):
                shutil.copytree(build.ROOT/name, root/name)
            shutil.copy(build.ROOT/'LICENSE-DATA', root/'LICENSE-DATA')
            packet_path = root/'source'/build.SELECTED_SIX_FILE
            packet_path.write_bytes(raw)
            packet_reads = []

            def drifting_read_bytes(path):
                if path == packet_path:
                    packet_reads.append(path)
                    return raw if len(packet_reads) <= 2 else raw + b' '
                return original_read_bytes(path)

            with patch.object(build, 'ROOT', root), patch.object(build, 'SELECTED_SIX_DIGEST', pin), \
                    patch.object(Path, 'read_bytes', drifting_read_bytes):
                with self.assertRaisesRegex(ValueError, 'Selected six bytes drift'):
                    build.outputs()
            self.assertEqual(len(packet_reads), 3)

    def test_active_and_gates(self):
        with patch.object(build, 'load_selected_six', return_value=None):
            baseline=build.outputs()
        self.assertEqual(json.loads(baseline['MODEL_AVERAGES.json'])['cost_assumptions'],
                         build.load_costs(r.model for r in build.average_rows())['assumptions'])
        old=build.average_rows()
        with TemporaryDirectory() as directory:
            root=Path(directory)
            for name in ('source','tools'):
                shutil.copytree(build.ROOT/name,root/name)
            shutil.copy(build.ROOT/'LICENSE-DATA',root/'LICENSE-DATA')
            with patch.object(build,'ROOT',root):
                path=root/'source'/build.SELECTED_SIX_FILE
                path.unlink(missing_ok=True)
                raw,pin=encode(fixture())
                with patch.object(build,'SELECTED_SIX_DIGEST',pin), self.assertRaises(ValueError):
                    build.outputs()
                path.write_bytes(raw)
                with patch.object(build,'SELECTED_SIX_DIGEST',None), self.assertRaises(ValueError):
                    build.outputs()
                with patch.object(build,'SELECTED_SIX_DIGEST',pin):
                    files=build.outputs(); data=json.loads(files['MODEL_AVERAGES.json'])
                    self.assertEqual(data['cost_assumptions'], build.SELECTED_COST_SCOPE + json.loads(baseline['MODEL_AVERAGES.json'])['cost_assumptions'])
                    rows=data['models']; self.assertEqual(len(rows),27)
                    self.assertEqual(len({r['model'] for r in rows}),27)
                    by_id={r['model']:r for r in rows}
                    for previous in json.loads(baseline['MODEL_AVERAGES.json'])['models']:
                        current=copy.deepcopy(by_id[previous['model']])
                        self.assertEqual(current.pop('observation_count'),2)
                        self.assertEqual(current,previous)
                    for m in fixture()['models']:
                        row=by_id[m['model']]
                        self.assertEqual(row['observation_count'],1)
                        self.assertIsNotNone(row['average_full_run_estimate'])
                        for metric,key in [('quality_rate','reliable'),('goal_rate','goal_completed')]:
                            self.assertEqual(Fraction(**row[metric]),Fraction(m[key],m['scored']))
                    expected=sorted(old+build.selected_averages(fixture()),key=build.average_order)
                    self.assertEqual([r['model'] for r in rows],[r.model for r in expected])
                    html=files['index.html'].decode()
                    self.assertEqual(html.count('<li class="chart-row">'),27)
                    self.assertEqual(html.count('<strong>Unknown</strong>'),0)
                    cost_note = html.split('<p id="cost-note">')[1].split('</p>')[0]
                    self.assertTrue(cost_note.startswith(
                        build.SELECTED_COST_SCOPE))
                    self.assertIn('>additional model aggregates</a>',html)
                    self.assertNotIn('approved selected six aggregates',html)
                    self.assertNotIn('21 models',html)
                    self.assertIn('<strong>27</strong>',html)
                    self.assertIn('one or two original per-observation',html)
                    self.assertIn('heterogeneous runtime/evaluator versions and provider settings',html)
                    chart=html.split('<ol class="chart">')[1].split('</ol>')[0]
                    self.assertEqual(html.count('<ol class="chart">'),1)
                    labels = re.findall(r'<code>([^<]+)</code>',chart)
                    self.assertEqual(labels, [row.model for row in expected])
                    self.assertNotRegex(chart.lower(), r'scored|assigned|coverage|\d+/\d+')
                    structure = ChartModelParser()
                    structure.feed(chart)
                    self.assertEqual(len(structure.models),27)
                    for rank, (container, row) in enumerate(zip(structure.models, expected), 1):
                        self.assertEqual(container, ('div', {'class':'chart-model'}, [
                            ('span', {'class':'chart-rank', 'aria-hidden':'true'}, [f'{rank:02d}']),
                            ('span', {}, [
                                ('code', {}, [row.model])])]))
                    originals = {r.model:r for r in build.all_rows()}
                    unequal_rates = 0
                    for repeat in build.latest_rows():
                        original = originals[repeat.model]
                        n1,d1 = map(int,original.scored.split('/'))
                        n2,d2 = map(int,repeat.scored.split('/'))
                        for metric,key in [('quality','quality_rate'),('goal','goal_rate')]:
                            a = build.metric_fraction(getattr(original,metric),original.scored)
                            b = build.metric_fraction(getattr(repeat,metric),repeat.scored)
                            mean = (a+b)/2
                            pooled = (a*n1+b*n2)/(n1+n2)
                            self.assertEqual(Fraction(**by_id[repeat.model][key]),mean)
                            unequal_rates += mean != pooled
                    self.assertGreater(unequal_rates,0)
                    self.assertIn('<strong>0.0%</strong>',chart)
                    self.assertIn('Both are average percentages across one or two observations.',html)
                    for forbidden in ('badge','observation','synthetic-native'):
                        self.assertNotIn(forbidden,chart)
                    self.assertEqual(data['selected_six_provenance']['sha256'],pin)
                    self.assertEqual(files[build.SELECTED_SIX_FILE],raw)
                    for name in baseline.keys()-{'index.html','MODEL_AVERAGES.json'}:
                        self.assertEqual(files[name],baseline[name])
                    path.write_bytes(raw+b' ')
                    with self.assertRaises(ValueError): build.outputs()


class ActualSelectedSixTests(unittest.TestCase):
    def test_accepted_actual_goldens(self):
        packet = build.load_selected_six()
        self.assertIsNotNone(packet)
        self.assertEqual(build.SELECTED_SIX_DIGEST,
            'a5032145578776f88e32d6235849dfb2243afefc4992827c4344bcc34817e432')
        self.assertEqual(packet['source_revision'], build.CORRECTION_SOURCE)
        self.assertEqual(packet['evaluator'], 'Compliance-0.3.0')
        self.assertEqual(packet['date'], '2026-10-29')
        self.assertEqual(packet['conditions'],
            'Heterogeneous runtime and evaluator versions and provider settings; historical grades unchanged. '
            'Technical and protocol exclusions are not quality failures. River recovery used serial pending cases. '
            'Descriptive comparison, not a controlled ranking.')
        routes = {
            'gpt-6.1-terra': ('openai','responses'),
            'claude-haiku-5-5': ('anthropic','messages'),
            'mistral-large-4': ('mistral','native-chat'),
            'grok-4.7': ('xai','responses'),
            'GLM-5.3': ('river','http'),
            'moonshotai/Kimi-K3': ('river','http'),
        }
        expected = {
            'gpt-6.1-terra': (44,44,38,0,0,'none'),
            'claude-haiku-5-5': (44,0,0,0,0,'adaptive-low'),
            'mistral-large-4': (24,0,0,20,0,'none'),
            'grok-4.7': (15,15,5,29,0,'low'),
            'GLM-5.3': (36,32,6,8,0,'low'),
            'moonshotai/Kimi-K3': (44,19,0,0,0,'none'),
        }
        rows = json.loads(build.outputs()['MODEL_AVERAGES.json'])['models']
        by_id = {r['model']:r for r in rows}
        for m in packet['models']:
            self.assertEqual(tuple(m[k] for k in
                ('scored','goal_completed','reliable','excluded','aborted','reasoning')),
                expected[m['model']])
            self.assertEqual((m['provider'],m['endpoint']),routes[m['model']])
            self.assertEqual(m['wire_model'],m['model'])
            self.assertEqual(m['assigned'],44)
            self.assertEqual(m['observation_count'],1)
            self.assertIsNone(m['cost_usd'])
            row = by_id[m['model']]
            self.assertEqual(row['observation_count'],1)
            self.assertIsNotNone(row['average_full_run_estimate'])
            self.assertEqual(Fraction(**row['quality_rate']),Fraction(m['reliable'],m['scored']))
            self.assertEqual(Fraction(**row['goal_rate']),Fraction(m['goal_completed'],m['scored']))
        self.assertEqual(sum(m['scored'] for m in packet['models']),207)
        self.assertEqual(sum(m['excluded'] for m in packet['models']),57)
        self.assertEqual(sum(m['aborted'] for m in packet['models']),0)
        for endpoint in ('chat','native-chat','unqualified'):
            value = copy.deepcopy(packet)
            next(m for m in value['models'] if m['model']=='grok-4.7')['endpoint']=endpoint
            raw,pin=encode(value)
            with self.assertRaises(ValueError): build.parse_selected_six(raw,pin)

    def test_disabled_copy_reproduces_original_public_bytes(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            shutil.copytree(build.ROOT/'source',root/'source')
            shutil.copytree(build.ROOT/'tools',root/'tools')
            shutil.copy(build.ROOT/'LICENSE-DATA',root/'LICENSE-DATA')
            (root/'source'/build.SELECTED_SIX_FILE).unlink()
            with patch.object(build,'ROOT',root), patch.object(build,'SELECTED_SIX_DIGEST',None):
                files=build.outputs()
            # Original 21 public bytes from accepted baseline commit
            # 4b29d28a891173e10293530b24f881e8a2680af8 (site/ tree).
            # Freeze the entire census and SHA256s so shallow CI needs no history.
            expected = {
                '.nojekyll': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
                'AVERAGE_COSTS.json': '90b263298ced3f9ef23ed073c3d63814902616c39806b6bf9c86c47b7a6cd1f9',
                'GEMINI_AGGREGATES.json': '9f0e424c631886690902f9286b33390cd20832129ac3f92f0578edbeab2e2aae',
                'LICENSE-DATA': 'd557539df68e771cc1eedcc91d13f70fca930e508d11eedcafa4b15db49e3744',
                'MODEL_AVERAGES.json': 'b98e74361f8923e709093a4de94a9c46f2d95c978dddc800a801e7a72dd0284c',
                'MODEL_RESULTS.md': 'e0774775be2e2897f7cbaefc8a0acd24ecf4900e1114c2513ae2e66f04c2141f',
                'REPEAT_20261024.json': 'da3a70a54311b3ecba3b9361c9539322bea071d656c16672cd6026905363fc74',
                'favicon.svg': '0a4b7f85f216f0b41105999cace9315e8f64d48a455290d81c2f0de855944620',
                'index.html': '7f4e7953c74783c0767f7bb8b36280a85155b1ebb9afc4843cebe1029bc8cd45',
                'style.css': '35344b7bf79357009c94cc2639002423b22705072314bbd20a7cd4bc0a546ddc',
            }
            self.assertEqual(set(files), set(expected))
            for name, raw in files.items():
                self.assertEqual(sha256(raw).hexdigest(), expected[name], name)


class SelectedCostTests(unittest.TestCase):
    def test_combined_cost_note_scopes_legacy_and_names_incomplete_models(self):
        files = build.outputs()
        note = unescape(files['index.html'].decode().split('<p id="cost-note">')[1].split('</p>')[0])
        assumptions = build.load_costs(r.model for r in build.average_rows())['assumptions']
        self.assertEqual(note, json.loads(files['MODEL_AVERAGES.json'])['cost_assumptions'])
        self.assertTrue(note.endswith('For the original 21 only: ' + assumptions))
        self.assertNotIn('Known 44-case campaign', note)
        self.assertEqual(note.count('not invoices'), 1)
        self.assertIn('gpt-6.1-terra covers complete recorded usage.', note)
        self.assertIn('claude-haiku-5-5, mistral-large-4, grok-4.7, GLM-5.3, '
                      'moonshotai/Kimi-K3 cover retained recorded usage only; missing usage is excluded.', note)

    def test_current_cost_intake(self):
        files = build.outputs()
        data = json.loads(files['MODEL_AVERAGES.json'])
        expected = ['$6.11', '$3.88', '$10.37', '$77.66', '$7.82', '$28.98']
        by_id = {r['model']: r for r in data['models']}
        for name, price in zip(build.SELECTED_SIX_ROUTES, expected):
            cost = by_id[name]['average_full_run_estimate']
            self.assertIsNotNone(cost)
            self.assertEqual(build.money(cost), price)
        self.assertEqual(data['selected_six_cost_provenance']['sha256'],
            '3a04d7ff6caf0edec3c6c71f37119b6f6bb9b1dd07b3a4ed029de47cc15683f9')
        self.assertEqual(files[build.SELECTED_COST_FILE],
                         (build.ROOT/'source'/build.SELECTED_COST_FILE).read_bytes())

    def test_selected_cost_schema_and_legacy_isolation(self):
        value = build.load_selected_costs()
        def parse(v):
            raw, pin = encode(v)
            return build.parse_costs(raw, build.SELECTED_SIX_ROUTES, pin, selected=True)
        changes = [lambda v: v.update(extra=1), lambda v: v.update(schema_version=True),
            lambda v: v['models'].pop(), lambda v: v['models'].append(v['models'][0]),
            lambda v: v['models'][0].update(model='unexpected'),
            lambda v: v['models'][0].pop('incomplete_usage'),
            lambda v: v['models'][0].update(incomplete_usage=1),
            lambda v: v['models'][0].update(pricing_basis='retained_tariff_estimate'),
            lambda v: v['models'][0].update(mean_cost_high_usd=None),
            lambda v: v['models'][0].update(mean_cost_high_usd='0'),
            lambda v: v['models'][0].update(mean_cost_low_usd='01'),
            lambda v: v['models'][0].update(mean_cost_low_usd='1.0')]
        for change in changes:
            mutated=copy.deepcopy(value); change(mutated)
            with self.subTest(change=change), self.assertRaises(ValueError): parse(mutated)
        raw,pin=encode(value)
        duplicate=raw.replace(b'"currency": "USD"', b'"currency": "USD", "currency": "USD"')
        with self.assertRaises(ValueError):
            build.parse_costs(duplicate,build.SELECTED_SIX_ROUTES,sha256(duplicate).hexdigest(),selected=True)
        for digest in (None, True, 'a'*64):
            with self.assertRaises(ValueError):
                build.parse_costs(raw,build.SELECTED_SIX_ROUTES,digest,selected=True)
        with self.assertRaises(ValueError):
            build.parse_costs(raw,build.SELECTED_SIX_ROUTES,pin)
        zero=copy.deepcopy(value)
        zero['models'][0].update(mean_cost_low_usd='0',mean_cost_high_usd='0')
        self.assertEqual(build.money(parse(zero)['models'][0]),'$0.00')
        self.assertEqual([m['incomplete_usage'] for m in value['models']], [False]+[True]*5)

    def test_selected_cost_file_gates(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            shutil.copytree(build.ROOT/'source',root/'source')
            shutil.copytree(build.ROOT/'tools',root/'tools')
            shutil.copy(build.ROOT/'LICENSE-DATA',root/'LICENSE-DATA')
            path=root/'source'/build.SELECTED_COST_FILE
            raw=path.read_bytes()
            with patch.object(build,'ROOT',root):
                path.unlink()
                with self.assertRaises(ValueError): build.outputs()
                path.write_bytes(raw+b' ')
                with self.assertRaises(ValueError): build.outputs()
                path.write_bytes(raw)
                with patch.object(build,'SELECTED_COST_DIGEST',None), self.assertRaises(ValueError):
                    build.outputs()
                # Disabling the outcome packet ignores even a malformed successor cost file.
                path.write_bytes(b'bad')
                with patch.object(build,'load_selected_six',return_value=None):
                    self.assertNotIn(build.SELECTED_COST_FILE,build.outputs())
