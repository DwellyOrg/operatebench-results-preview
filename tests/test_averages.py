"""Average UI contracts using approved source rows and synthetic formatting fixtures."""
import dataclasses
import json
import re
import unittest
from decimal import Decimal
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from tools import build
from test_build import Document

ORDER = '''gpt-6-astra
gemini-4-argon
gpt-6.1-sol
claude-fable-5-1
claude-opus-5-5
gemini-3.8-flash
gpt-6-sol
muse-wonder-1.0
zai-org/GLM-5.3-Flash
nvidia/GLM-5.2-NVFP4-262K
muse-spark-1.3
Qwen/Qwen3.8-27B-FP8
deepseek-ai/DeepSeek-V4.1-Flash
deepseek-ai/DeepSeek-V4-Flash-0731
gpt-6-luna
Qwen/Qwen3.6-35B-A3B-FP8
nvidia/Kimi-K2.6-NVFP4
Qwen/Qwen3.5-397B-A17B-FP8
mistral-medium-3-5
nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4
Qwen/Qwen3.5-9B'''.splitlines()


def fixture():
    return dict(schema_version=1, currency='USD', assigned_cases_per_run=44,
        average_rule='arithmetic_mean_per_model', assumptions='Synthetic test-only scenarios.',
        models=[dict(model=model, mean_cost_low_usd='1.234', mean_cost_high_usd='2.345',
            incomplete_usage=True, pricing_basis='retained_tariff_estimate') for model in ORDER])


class AverageTests(unittest.TestCase):
    def test_independent_means_and_order(self):
        rows = build.average_rows(); by_id = {r.model:r for r in rows}
        self.assertEqual([r.model for r in rows], ORDER)
        expected = {
            'claude-fable-5-1': (Fraction(3045,3784), Fraction(1)),
            'muse-wonder-1.0': (Fraction(91,344), Fraction(97,172)),
            'gpt-6-astra': (Fraction(1827,1892), Fraction(1)),
            'gemini-3.8-flash': (Fraction(39,86), Fraction(1)),
            'gpt-6-luna': (Fraction(0), Fraction(189,880)),
            'mistral-medium-3-5': (Fraction(0), Fraction(0)),
        }
        for model, (quality, goal) in expected.items():
            self.assertEqual((by_id[model].quality, by_id[model].goal), (quality, goal), model)
        self.assertNotEqual(by_id['muse-wonder-1.0'].quality, Fraction(22,83))
        self.assertEqual(rows, build.average_rows(reversed(build.latest_rows())))
        tied = [build.Average(m, Fraction(0), Fraction(1,2)) for m in ['beta','alpha','ALPHA','Alpha']]
        self.assertEqual([r.model for r in sorted(tied,key=build.average_order)], ['ALPHA','Alpha','alpha','beta'])
        base=build.latest_rows()
        for rows in ([],base[:-1],[base[0],*base[:-1]],build.all_rows()):
            with self.assertRaises(ValueError): build.average_rows(rows)

    @patch.object(build, 'load_selected_six', return_value=None)
    def test_unified_chart_census_values_and_clean_document(self, _selected_six):
        html=build.render(); doc=Document(); doc.feed(html)
        self.assertEqual(doc.models, ORDER)
        chart=re.findall(r'<li class="chart-row">(.*?)</li>',html)
        costs={c['model']:c for c in build.load_costs(ORDER)['models']}
        for item, row in zip(chart,build.average_rows()):
            self.assertIn('<code>'+row.model+'</code>',item)
            self.assertEqual(re.findall(r'<strong>(.*?)</strong>',item),
                             [build.percent(row.quality),build.percent(row.goal),build.money(costs[row.model])])
            for metric, fraction in [('quality',row.quality),('goal',row.goal)]:
                width=re.search(r'<rect class="'+metric+r'-fill" width="(.*?)"',item)[1]
                self.assertLess(abs(Decimal(width)-Decimal(fraction.numerator)*100/fraction.denominator),Decimal('0.000000001'))
            goal_width=re.search(r'<rect class="goal-fill" width="(.*?)"',item)[1]
            self.assertIn('x1="'+goal_width+'" x2="'+goal_width+'"',item)
        self.assertEqual(len(chart),21)
        self.assertNotIn('table',doc.tags)
        self.assertNotIn('results-table',html)
        self.assertNotIn('≥',html)
        self.assertIn('width="0.0000000000"',html)
        self.assertIn('width="100.0000000000"',html)
        self.assertIn('viewBox="0 0 100 16"',html)
        self.assertIn('0%</span><span>50%</span><span>100%',html)
        for word in ('unscored','excluded','aborted','scored','assigned','Observed','<details','2026-10-24','/44','REPEAT_20261024.json','GEMINI_AGGREGATES.json'):
            self.assertNotIn(word,html.split('<ol class="chart">',1)[1].split('</ol>',1)[0])
        for tag,attrs in doc.attributes:
            for target in attrs.get('aria-describedby','').split(): self.assertEqual(doc.ids.count(target),1)
        self.assertIn('sorted by quality',html)
        for url in doc.urls:
            if url.startswith('#'): self.assertEqual(doc.ids.count(url[1:]),1)
        self.assertNotIn('script',doc.tags)
        for text in ('CC BY 4.0','Prospire Technologies Ltd','Apache-2.0','3672fdeb6153e6677f5d36d6e6628f50f2efb1d5/docs/studies/2026-10-observations.md'):
            self.assertIn(text,html)
        css=(build.ROOT/'tools/style.css').read_text()
        self.assertIn('@media(max-width:600px)',css)
        self.assertIn('.chart-model{grid-column:1/3;grid-row:1}',css)

    @patch.object(build, 'load_selected_six', return_value=None)
    def test_escape_and_aggregate_only_download(self, _selected_six):
        row=build.Average('<script>"&',Fraction(0),Fraction(0))
        costs=fixture(); costs['models'][0]['model']=row.model
        html=build.render_chart([row],costs)
        self.assertIn('&lt;script&gt;&quot;&amp;',html); self.assertNotIn('<script>',html)
        data=json.loads(build.outputs()['MODEL_AVERAGES.json'])
        self.assertEqual(len(data['models']),21)
        for row in data['models']:
            self.assertEqual(set(row),{'model','average_quality_percent','average_goal_achieved_percent','quality_rate','goal_rate','average_full_run_estimate'})
        self.assertEqual(build.outputs(),build.outputs())

    def test_missing_costs_and_pin_fail_closed(self):
        with TemporaryDirectory() as directory, patch.object(build,'ROOT',Path(directory)):
            (Path(directory)/'source').mkdir()
            with self.assertRaisesRegex(ValueError,'Pinned cost source missing'): build.load_costs(ORDER)
            with patch.object(build,'COST_DIGEST','a'*64),self.assertRaises(ValueError): build.load_costs(ORDER)
            path=Path(directory)/'source/AVERAGE_COSTS.json'; raw=json.dumps(fixture()).encode();path.write_bytes(raw)
            with patch.object(build,'COST_DIGEST',None),self.assertRaises(ValueError): build.load_costs(ORDER)
            with patch.object(build,'COST_DIGEST',sha256(raw).hexdigest()):
                self.assertEqual(build.load_costs(ORDER),fixture())
                path.write_bytes(raw+b'\n')
                with self.assertRaises(ValueError):build.load_costs(ORDER)
        with self.assertRaises(ValueError): build.money(None)

    def test_render_source_drift_and_public_privacy(self):
        with self.assertRaises(ValueError):
            build.parse_gemini((build.ROOT/'source/GEMINI_AGGREGATES.json').read_bytes() + b'\n')
        original_read = Path.read_bytes
        def drift(path):
            data = original_read(path)
            return data + b'\n' if path.name == 'MODEL_RESULTS.md' else data
        with patch.object(Path, 'read_bytes', drift):
            with self.assertRaises(ValueError): build.render()
            with self.assertRaises(ValueError): build.outputs()
        for name, data in build.outputs().items():
            for forbidden in (b'/root/', b'/var/', b'credential', b'scorecard', b'ledger', b'raw_'):
                self.assertNotIn(forbidden, data, name)
        for path, digest in (
            ('source/MODEL_RESULTS.md','e0774775be2e2897f7cbaefc8a0acd24ecf4900e1114c2513ae2e66f04c2141f'),
            ('source/GEMINI_AGGREGATES.json','9f0e424c631886690902f9286b33390cd20832129ac3f92f0578edbeab2e2aae'),
            ('source/REPEAT_20261024.json','da3a70a54311b3ecba3b9361c9539322bea071d656c16672cd6026905363fc74')):
            self.assertEqual(sha256((build.ROOT/path).read_bytes()).hexdigest(),digest)

    @patch.object(build, 'load_selected_six', return_value=None)
    def test_approved_cost_integration(self, _selected_six):
        raw = (build.ROOT/'source/AVERAGE_COSTS.json').read_bytes()
        self.assertEqual(sha256(raw).hexdigest(), '90b263298ced3f9ef23ed073c3d63814902616c39806b6bf9c86c47b7a6cd1f9')
        costs = build.load_costs(ORDER)
        outputs = build.outputs()
        self.assertEqual(outputs['AVERAGE_COSTS.json'], raw)
        data = json.loads(outputs['MODEL_AVERAGES.json'])
        self.assertEqual({r['model']:r['average_full_run_estimate'] for r in data['models']},
                         {r['model']:r for r in costs['models']})
        html = outputs['index.html'].decode()
        notice = (build.ROOT/'NOTICE').read_text()
        for text in ('27 derived model means (21 two-observation means and six one-observation rates): site/MODEL_AVERAGES.json',
                     'source/AVERAGE_COSTS.json and its site/AVERAGE_COSTS.json copy.',
                     'These data and the site results content are CC BY 4.0, owned by',
                     'Prospire Technologies Ltd.',
                     'costs not reported\nin these unchanged historical snapshots.',
                     'Costs not reported in this unchanged repeat snapshot;',
                     'no official, independent human or provider attestation is claimed.'):
            self.assertIn(text, notice)
        footer = html.split('<footer>', 1)[1].split('</footer>', 1)[0]
        self.assertIn('owner-authorized Gemini, repeat and <a href="./AVERAGE_COSTS.json">cost aggregates</a>', footer)
        self.assertIn('owned by Prospire Technologies Ltd', footer)
        self.assertIn('https://creativecommons.org/licenses/by/4.0/', footer)
        for text in ('Not available', 'unavailable', 'await approved'):
            self.assertNotIn(text, html)
        for row in costs['models']:
            self.assertIn(build.money(row), html)
        self.assertEqual(sum(r['pricing_basis']=='river_owner_cache_scenarios' for r in costs['models']),10)
        original_read = Path.read_bytes
        def missing(path):
            if path.name == 'AVERAGE_COSTS.json':
                raise FileNotFoundError(path)
            return original_read(path)
        with patch.object(Path, 'read_bytes', missing):
            with self.assertRaises(FileNotFoundError): build.outputs()

    def test_cost_schema_negatives(self):
        value=fixture();raw=json.dumps(value)
        self.assertEqual(build.parse_costs(raw,ORDER,sha256(raw.encode()).hexdigest()),value)
        mutations=[lambda v:v.update(extra=1),lambda v:v.update(schema_version=True),
            lambda v:v.update(assigned_cases_per_run=44.0),lambda v:v.update(currency='EUR'),
            lambda v:v.update(average_rule='pooled'),lambda v:v.update(assumptions=''),
            lambda v:v['models'].pop(),lambda v:v['models'].append(v['models'][0]),
            lambda v:v['models'][0].update(model='unknown'),lambda v:v['models'][0].update(pricing_basis='invoice'),
            lambda v:v['models'][0].update(incomplete_usage=1),lambda v:v['models'][0].update(mean_cost_low_usd='3')]
        for bad in (0,None,True,'NaN','Infinity','-1','01','1e2','1.00','0.0'):
            mutations.append(lambda v,bad=bad:v['models'][0].update(mean_cost_low_usd=bad))
        for change in mutations:
            v=fixture();change(v)
            mutated=json.dumps(v).encode()
            with self.subTest(value=v),self.assertRaises(ValueError):
                build.parse_costs(mutated,ORDER,sha256(mutated).hexdigest())
        duplicate=raw.replace('"currency": "USD"','"currency": "USD", "currency": "USD"').encode()
        with self.assertRaises(ValueError):build.parse_costs(duplicate,ORDER,sha256(duplicate).hexdigest())
        with self.assertRaises(ValueError):build.parse_costs(raw,ORDER,'0'*64)

    def test_money_bounds_ranges_and_estimate_note(self):
        row=fixture()['models'][0]
        self.assertEqual(build.money(row),'$2.34')
        row.update(mean_cost_high_usd='1.234')
        self.assertEqual(build.money(row),'$1.23')
        row.update(incomplete_usage=False)
        self.assertEqual(build.money(row),'$1.23')
        row.update(mean_cost_low_usd='0.009',mean_cost_high_usd='0.009')
        self.assertEqual(build.money(row),'$0.01')
        row.update(incomplete_usage=True)
        self.assertEqual(build.money(row),'$0.00')
        row.update(mean_cost_low_usd='1.234',mean_cost_high_usd='2.345',incomplete_usage=False)
        self.assertEqual(build.money(row),'$2.35')
        row.update(mean_cost_low_usd='1.235',mean_cost_high_usd='1.235')
        self.assertEqual(build.money(row),'$1.24')
        row.update(mean_cost_low_usd='0.009',mean_cost_high_usd='0.011')
        self.assertEqual(build.money(row),'$0.02')
        row.update(incomplete_usage=True)
        self.assertEqual(build.money(row),'$0.01')
        html=build.render()
        for text in ('including known retries','not invoices','Some estimates have incomplete recorded usage','$2.52'):
            self.assertIn(text,html)

    def test_incomplete_river_source_ranges(self):
        expected={
            'deepseek-ai/DeepSeek-V4-Flash-0731':'$2.54',
            'Qwen/Qwen3.8-27B-FP8':'$2.52',
            'deepseek-ai/DeepSeek-V4.1-Flash':'$2.90',
            'nvidia/Kimi-K2.6-NVFP4':'$1.00',
        }
        rows=[r for r in build.load_costs(ORDER)['models']
              if r['incomplete_usage'] and r['pricing_basis']=='river_owner_cache_scenarios']
        self.assertEqual({r['model'] for r in rows},set(expected))
        for row in rows:
            with self.subTest(model=row['model']):
                self.assertEqual(build.money(row),expected[row['model']])

    def test_render_rejects_cost_override(self):
        bad=fixture()
        bad['models'][0].update(mean_cost_low_usd='-2',mean_cost_high_usd='-1')
        with self.assertRaises(TypeError):build.render(costs=bad)
        with self.assertRaises(TypeError):build.render(None,bad)

    def test_parse_costs_requires_valid_pin(self):
        raw=json.dumps(fixture()).encode()
        with self.assertRaises(TypeError):build.parse_costs(raw,ORDER)
        for pin in (None,'','0'*63,'g'*64,0,True):
            with self.subTest(pin=pin),self.assertRaises(ValueError):
                build.parse_costs(raw,ORDER,pin)
        with self.assertRaisesRegex(ValueError,'Approved cost bytes drift'):
            build.parse_costs(raw+b'\n',ORDER,sha256(raw).hexdigest())

if __name__=='__main__': unittest.main()
