"""Approved November integration and synthetic adverse packets."""
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

# SHA-256 goldens for the public, disabled-November generated outputs.
PUBLIC_GOLDENS = {
    'index.html': '5cc9381a483c7f7b84bcc67a2eaf36c795aa74d8bd58b4847ae704cc9e0deb1c',
    'MODEL_AVERAGES.json': 'ce2ac6df016743b4b61410aadc8005a05145078450f5ab97e06fbb6c2f6e3d32',
}


def fixture():
    return dict(schema_version=1, model='claude-sonnet-5-5', provider='anthropic',
        endpoint='messages', reasoning='between_tools-low', currency='USD',
        pricing_basis='official_current_tariff_estimate', case_set='same-44-cases',
        source_revision='a'*40, date='2026-11-05', observations=[
            dict(id='test-only-1', assigned=44, scored=43, excluded=1, aborted=0,
                reliable=20, goal_completed=40, estimated_cost_low_usd='1.1',
                estimated_cost_high_usd='2.3', incomplete_usage=True),
            dict(id='test-only-2', assigned=44, scored=44, excluded=0, aborted=0,
                reliable=22, goal_completed=44, estimated_cost_low_usd='3.3',
                estimated_cost_high_usd='4.5', incomplete_usage=False)])


def encode(value):
    raw = json.dumps(value).encode()
    return raw, sha256(raw).hexdigest()


@patch.object(build, 'load_carbon', new=lambda: None)
class NovemberTests(unittest.TestCase):
    @patch.object(build, 'load_fable', new=lambda: None)
    def test_absent_parity(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('source', 'tools'):
                shutil.copytree(build.ROOT/name, root/name)
            shutil.copy(build.ROOT/'LICENSE-DATA', root/'LICENSE-DATA')
            (root/'source'/build.NOVEMBER_FILE).unlink()
            with patch.object(build, 'ROOT', root), patch.object(build, 'NOVEMBER_DIGEST', None):
                self.assertIsNone(build.load_november())
                files = build.outputs()
        for name, pin in PUBLIC_GOLDENS.items():
            self.assertEqual(sha256(files[name]).hexdigest(), pin)
        rows = json.loads(files['MODEL_AVERAGES.json'])['models']
        self.assertEqual(len(rows), 27)
        self.assertEqual(len({r['model'] for r in rows}), 27)
        self.assertNotIn(build.NOVEMBER_MODEL, {r['model'] for r in rows})
        chart = files['index.html'].decode().split('<ol class="chart">')[1].split('</ol>')[0]
        self.assertEqual(chart.count('<li class="chart-row">'), 27)

    def test_schema_adverse(self):
        self.assertEqual(build.parse_november(*encode(fixture())), fixture())
        mutations = [lambda v:v.update(extra=0), lambda v:v.update(schema_version=True),
            lambda v:v.update(model='other'), lambda v:v.update(provider='other'),
            lambda v:v.update(endpoint='Messages'), lambda v:v.update(reasoning='high'),
            lambda v:v.update(currency='EUR'), lambda v:v.update(pricing_basis='reservation'),
            lambda v:v.update(case_set='different'), lambda v:v.update(source_revision='A'*40),
            lambda v:v.update(date='2026-02-30'), lambda v:v.update(date='20261105'),
            lambda v:v['observations'].pop(), lambda v:v['observations'].append(v['observations'][0]),
            lambda v:v['observations'].__setitem__(1,v['observations'][0])]
        for key, bad in [('id','/private'), ('assigned',True), ('scored',0), ('scored',44.0),
                ('excluded',-1), ('aborted',2), ('goal_completed',45), ('reliable',41),
                ('incomplete_usage',1), ('extra',0), ('estimated_cost_low_usd','9')]:
            mutations.append(lambda v,k=key,b=bad:v['observations'][0].update({k:b}))
        for bad in (None, True, 1, '-1', 'NaN', 'Infinity', '1e2', '01', '1.00', '0.0', '.1'):
            mutations.append(lambda v,b=bad:v['observations'][0].update(estimated_cost_high_usd=b))
        mutations.append(lambda v:v['observations'][0].pop('reliable'))
        for mutate in mutations:
            value=fixture(); mutate(value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                build.parse_november(*encode(value))
        raw, pin=encode(fixture())
        for bad in (None, True, '', 'g'*64, 'a'*63, '0'*64):
            with self.assertRaises(ValueError): build.parse_november(raw,bad)
        for old in (b'"schema_version": 1', b'"id": "test-only-1"', b'"model": "claude-sonnet-5-5"'):
            duplicate=raw.replace(old,old+b', '+old)
            with self.assertRaises(ValueError): build.parse_november(duplicate,sha256(duplicate).hexdigest())
        with self.assertRaises(ValueError): build.parse_november(raw+b' ',pin)

    @patch.object(build, 'load_fable', new=lambda: None)
    def test_combined_and_gates(self):
        with patch.object(build, 'load_november', return_value=None):
            baseline=build.outputs()
        raw,pin=encode(fixture())
        with TemporaryDirectory() as directory:
            root=Path(directory)
            for name in ('source','tools'): shutil.copytree(build.ROOT/name,root/name)
            shutil.copy(build.ROOT/'LICENSE-DATA',root/'LICENSE-DATA')
            with patch.object(build,'ROOT',root):
                path=root/'source'/build.NOVEMBER_FILE
                path.unlink()
                with patch.object(build,'NOVEMBER_DIGEST',pin), self.assertRaises(ValueError): build.outputs()
                path.write_bytes(raw)
                with self.assertRaises(ValueError): build.outputs()
                with patch.object(build,'NOVEMBER_DIGEST',pin):
                    files=build.outputs(); data=json.loads(files['MODEL_AVERAGES.json'])
                    rows=data['models']; self.assertEqual(len(rows),28)
                    self.assertEqual(len({r['model'] for r in rows}),28)
                    old=json.loads(baseline['MODEL_AVERAGES.json'])['models']
                    self.assertEqual([r for r in rows if r['model']!=build.NOVEMBER_MODEL],old)
                    row=next(r for r in rows if r['model']==build.NOVEMBER_MODEL)
                    self.assertEqual(Fraction(**row['quality_rate']),(Fraction(20,43)+Fraction(22,44))/2)
                    self.assertNotEqual(Fraction(**row['quality_rate']),Fraction(42,87))
                    self.assertEqual(Fraction(**row['goal_rate']),(Fraction(40,43)+1)/2)
                    self.assertEqual(row['observation_count'],2)
                    self.assertEqual(row['average_full_run_estimate'],dict(model=build.NOVEMBER_MODEL,
                        mean_cost_low_usd='2.2',mean_cost_high_usd='3.4',incomplete_usage=True,
                        pricing_basis='official_current_tariff_estimate'))
                    self.assertEqual(files[build.NOVEMBER_FILE],raw)
                    self.assertEqual(data['november_provenance']['sha256'],pin)
                    html=files['index.html'].decode(); chart=html.split('<ol class="chart">')[1].split('</ol>')[0]
                    self.assertEqual(chart.count('<li class="chart-row">'),28)
                    self.assertIn('<strong>28</strong>',html)
                    self.assertIn('./'+build.NOVEMBER_FILE,html)
                    self.assertIn('$3.40',chart)
                    self.assertNotRegex(chart.lower(),r'scored|assigned|badge|newcomer|experimental|\d+/\d+')
                    self.assertEqual(re.findall(r'<code>([^<]+)</code>',chart),[r['model'] for r in rows])
                    for text in ('descriptive, not a controlled ranking','technical exclusions','not invoices','missing usage is excluded'):
                        self.assertIn(text,html)
                    for name in baseline.keys()-{'index.html','MODEL_AVERAGES.json'}:
                        self.assertEqual(files[name],baseline[name])
                    original=Path.read_bytes; reads=[]
                    def drift(p):
                        if p==path:
                            reads.append(p)
                            return raw if len(reads)<=2 else raw+b' '
                        return original(p)
                    with patch.object(Path,'read_bytes',drift), self.assertRaisesRegex(ValueError,'November bytes drift'):
                        build.outputs()
                    self.assertEqual(len(reads),3)
                    path.write_bytes(raw+b' ')
                    with self.assertRaises(ValueError): build.outputs()

    def test_exact_sort_ties_and_decimal_means(self):
        packet=fixture(); row=build.november_average(packet)
        tied=[build.Average(m,row.quality,row.goal) for m in ('Zulu','CLAUDE','claude')]+[row]
        self.assertEqual([r.model for r in sorted(tied,key=build.average_order)],
                         ['CLAUDE','claude',build.NOVEMBER_MODEL,'Zulu'])
        better_goal=build.Average('later',row.quality,Fraction(1))
        better_quality=build.Average('last',row.quality+Fraction(1,10**9),Fraction(0))
        self.assertEqual(sorted([row,better_goal,better_quality],key=build.average_order),[better_quality,better_goal,row])
        for o in packet['observations']:
            o.update(estimated_cost_low_usd='0', estimated_cost_high_usd='0', incomplete_usage=False)
        self.assertEqual(build.november_cost(packet)['mean_cost_high_usd'],'0')
        self.assertEqual(build.money(build.november_cost(packet)),'$0.00')
        packet['observations'][0]['estimated_cost_high_usd']='123456789012345678901234567890.1'
        self.assertEqual(build.november_cost(packet)['mean_cost_high_usd'],'61728394506172839450617283945.05')

    def test_approved_real_packet_and_publication(self):
        pin = 'a46e76a1a1bc12135bf38aa9bcc4b5a995c05bcc0fde2dd9462b9d5ded371af8'
        raw = (build.ROOT/'source'/build.NOVEMBER_FILE).read_bytes()
        self.assertEqual(build.NOVEMBER_DIGEST, pin)
        self.assertEqual(sha256(raw).hexdigest(), pin)
        packet = build.load_november()
        self.assertEqual(packet['source_revision'], '213d672ddaa8ec296c6b0bbe7b9c8e01785e020e')
        self.assertEqual([(o['assigned'], o['scored'], o['goal_completed'], o['reliable'],
                           o['excluded'], o['aborted'], o['incomplete_usage'],
                           o['estimated_cost_low_usd'], o['estimated_cost_high_usd'])
                          for o in packet['observations']],
                         [(44,44,41,19,0,0,False,'20.066624','20.066624'),
                          (44,44,40,20,0,0,False,'20.551442','20.551442')])
        files = build.outputs()
        self.assertEqual(len(files), 14)
        self.assertEqual(files[build.NOVEMBER_FILE], raw)
        data = json.loads(files['MODEL_AVERAGES.json'])
        rows = data['models']
        self.assertEqual(len(rows), 29)
        self.assertEqual(len({r['model'] for r in rows}), 29)
        self.assertEqual(sum(r['observation_count'] == 2 for r in rows), 22)
        self.assertEqual(sum(r['observation_count'] == 1 for r in rows), 7)
        row = next(r for r in rows if r['model'] == build.NOVEMBER_MODEL)
        self.assertEqual(Fraction(**row['quality_rate']), Fraction(39,88))
        self.assertEqual(Fraction(**row['goal_rate']), Fraction(81,88))
        self.assertEqual(row['average_quality_percent'], '44.3%')
        self.assertEqual(row['average_goal_achieved_percent'], '92.0%')
        self.assertEqual(row['average_full_run_estimate'], dict(model=build.NOVEMBER_MODEL,
            mean_cost_low_usd='20.309033', mean_cost_high_usd='20.309033',
            incomplete_usage=False, pricing_basis='official_current_tariff_estimate'))
        self.assertEqual(data['november_provenance']['sha256'], pin)
        chart = files['index.html'].decode().split('<ol class="chart">')[1].split('</ol>')[0]
        self.assertEqual(chart.count('<li class="chart-row">'), 29)
        self.assertEqual(re.findall(r'<code>([^<]+)</code>', chart), [r['model'] for r in rows])
        self.assertEqual(rows, sorted(rows, key=lambda r: (-Fraction(**r['quality_rate']),
            -Fraction(**r['goal_rate']), r['model'].lower(), r['model'])))
        sonnet = next(item for item in chart.split('<li class="chart-row">') if '<code>claude-sonnet-5-5</code>' in item)
        self.assertEqual(re.findall(r'<strong>(.*?)</strong>', sonnet), ['44.3%', '92.0%', '$20.31'])
        self.assertNotRegex(chart.lower(), r'scored|assigned|badge|newcomer|experimental|\d+/\d+')

    @patch.object(build, 'load_fable', new=lambda: None)
    def test_real_enabled_preserves_old_27_objects_and_download_bytes(self):
        with patch.object(build, 'load_november', return_value=None):
            old = build.outputs()
        current = build.outputs()
        old_rows = json.loads(old['MODEL_AVERAGES.json'])['models']
        self.assertEqual(len(old_rows), 27)
        self.assertEqual([r for r in json.loads(current['MODEL_AVERAGES.json'])['models']
                          if r['model'] != build.NOVEMBER_MODEL], old_rows)
        self.assertEqual(set(current), set(old) | {build.NOVEMBER_FILE})
        for name in old.keys() - {'index.html', 'MODEL_AVERAGES.json'}:
            self.assertEqual(current[name], old[name], name)
