"""Adversarial synthetic intake tests and independent accepted-data goldens."""
import copy
import json
import re
from fractions import Fraction
from hashlib import sha256
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
                        self.assertIsNone(row['average_full_run_estimate'])
                        for metric,key in [('quality_rate','reliable'),('goal_rate','goal_completed')]:
                            self.assertEqual(Fraction(**row[metric]),Fraction(m[key],m['scored']))
                    expected=sorted(old+build.selected_averages(fixture()),key=build.average_order)
                    self.assertEqual([r['model'] for r in rows],[r.model for r in expected])
                    html=files['index.html'].decode()
                    self.assertEqual(html.count('<li class="chart-row">'),27)
                    self.assertEqual(html.count('<strong>Unknown</strong>'),6)
                    cost_note = html.split('<p id="cost-note">')[1].split('</p>')[0]
                    self.assertTrue(cost_note.startswith(
                        'Known estimates and the historical River scenario below apply only to the original 21. '
                        'Costs for the six additional models remain Unknown; no provider charges or invoices are inferred. '))
                    self.assertIn('>additional model aggregates</a>',html)
                    self.assertNotIn('approved selected six aggregates',html)
                    self.assertNotIn('21 models',html)
                    self.assertIn('<strong>27</strong>',html)
                    self.assertIn('one or two original per-observation',html)
                    self.assertIn('heterogeneous runtime/evaluator versions and provider settings',html)
                    chart=html.split('<ol class="chart">')[1].split('</ol>')[0]
                    self.assertEqual(html.count('<ol class="chart">'),1)
                    labels = re.findall(r'<code>([^<]+)</code><br><small>Scored (\d+)/(\d+)</small>',chart)
                    self.assertEqual(len(labels),27)
                    visible = {model:(int(scored),int(assigned)) for model,scored,assigned in labels}
                    self.assertEqual(len(visible),27)
                    structure = ChartModelParser()
                    structure.feed(chart)
                    self.assertEqual(len(structure.models),27)
                    for rank, (container, row) in enumerate(zip(structure.models, expected), 1):
                        scored, assigned = visible[row.model]
                        self.assertEqual(container, ('div', {'class':'chart-model'}, [
                            ('span', {'class':'chart-rank', 'aria-hidden':'true'}, [f'{rank:02d}']),
                            ('span', {}, [
                                ('code', {}, [row.model]),
                                ('br', {}, []),
                                ('small', {}, [f'Scored {scored}/{assigned}'])])]))
                    originals = {r.model:r for r in build.all_rows()}
                    unequal_rates = 0
                    for repeat in build.latest_rows():
                        original = originals[repeat.model]
                        n1,d1 = map(int,original.scored.split('/'))
                        n2,d2 = map(int,repeat.scored.split('/'))
                        self.assertEqual(visible[repeat.model],(n1+n2,d1+d2))
                        for metric,key in [('quality','quality_rate'),('goal','goal_rate')]:
                            a = build.metric_fraction(getattr(original,metric),original.scored)
                            b = build.metric_fraction(getattr(repeat,metric),repeat.scored)
                            mean = (a+b)/2
                            pooled = (a*n1+b*n2)/(n1+n2)
                            self.assertEqual(Fraction(**by_id[repeat.model][key]),mean)
                            unequal_rates += mean != pooled
                    self.assertGreater(unequal_rates,0)
                    for model in fixture()['models']:
                        self.assertEqual(visible[model['model']],(model['scored'],model['assigned']))
                    self.assertEqual(visible[fixture()['models'][-1]['model']],(7,44))
                    self.assertIn('<strong>0.0%</strong>',chart)
                    self.assertIn('Coverage is total scored/assigned across available observations; '
                                  'percentages remain means of original scored-case rates.',html)
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
            '271070a082cbf3b868d61e0501203295d7cbaa364e0ac15f8fc98a268e97ca5e')
        self.assertEqual(packet['source_revision'], 'f3bd45fb0d219929c9415b734dfeb9ef0cb6a5b8')
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
            'claude-haiku-5-5': (13,0,0,31,0,'adaptive-low'),
            'mistral-large-4': (24,0,0,20,0,'none'),
            'grok-4.7': (15,15,5,29,0,'low'),
            'GLM-5.3': (28,25,5,12,4,'low'),
            'moonshotai/Kimi-K3': (38,16,0,6,0,'none'),
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
            self.assertIsNone(row['average_full_run_estimate'])
            self.assertEqual(Fraction(**row['quality_rate']),Fraction(m['reliable'],m['scored']))
            self.assertEqual(Fraction(**row['goal_rate']),Fraction(m['goal_completed'],m['scored']))
        self.assertEqual(sum(m['scored'] for m in packet['models']),162)
        self.assertEqual(sum(m['excluded'] for m in packet['models']),98)
        self.assertEqual(sum(m['aborted'] for m in packet['models']),4)
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
            import subprocess
            for name,raw in files.items():
                original=subprocess.check_output(['git','show',f'4b29d28:site/{name}'],cwd=build.ROOT)
                self.assertEqual(raw,original,name)
