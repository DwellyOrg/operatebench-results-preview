"""Mechanics only: synthetic packets never become checked-in result data."""
import copy
import json
import shutil
import tempfile
import unittest
from fractions import Fraction as F
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch
from tools import build
from test_averages import historical_ui_bytes

# Independently derived from original table counts and approved aggregate counts;
# no renderer/parser helpers used to calculate these exact rational goldens.
GOLDENS = {'gpt-6-astra': ['1827/1892', '1'],
 'claude-fable-5-1': ['3045/3784', '1'],
 'claude-opus-5-5': ['6/11', '87/88'],
 'gpt-6-sol': ['39/88', '79/88'],
 'nvidia/GLM-5.2-NVFP4-262K': ['3/22', '63/88'],
 'zai-org/GLM-5.3-Flash': ['13/88', '17/22'],
 'deepseek-ai/DeepSeek-V4-Flash-0731': ['1/44', '5/88'],
 'Qwen/Qwen3.8-27B-FP8': ['3/88', '3/88'],
 'gpt-6-luna': ['0', '189/880'],
 'deepseek-ai/DeepSeek-V4.1-Flash': ['1/43', '695/3784'],
 'Qwen/Qwen3.6-35B-A3B-FP8': ['0', '15/88'],
 'nvidia/Kimi-K2.6-NVFP4': ['0', '609/3784'],
 'Qwen/Qwen3.5-397B-A17B-FP8': ['0', '3/44'],
 'mistral-medium-3-5': ['0', '0'],
 'nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4': ['0', '0'],
 'Qwen/Qwen3.5-9B': ['0', '0'],
 'gpt-6.1-sol': ['21/22', '1'],
 'muse-wonder-1.0': ['91/344', '97/172'],
 'muse-spark-1.3': ['9/88', '37/88'],
 'gemini-4-argon': ['21/22', '1'],
 'gemini-3.8-flash': ['39/86', '1'],
 'gpt-6.1-terra': ['19/22', '1'],
 'claude-haiku-5-5': ['0', '0'],
 'mistral-large-4': ['0', '0'],
 'grok-4.7': ['1/3', '1'],
 'GLM-5.3': ['1/6', '8/9'],
 'moonshotai/Kimi-K3': ['0', '19/44'],
 'claude-sonnet-5-5': ['39/88', '81/88'],
 'claude-fable-5-2': ['31/44', '1'],
 'gemini-4-carbon': ['85/88', '1']}
SCRATCH = Path(tempfile.gettempdir())


def fixture(model):
    return dict(schema_version=1, model=model, provider='openai', endpoint='responses',
        reasoning='low', currency='USD', pricing_basis='official_current_tariff_estimate',
        case_set='same-44-cases', source_revision='a'*40, date='2026-11-17',
        cost_assumptions='Synthetic mechanics only; known token and cache tier usage includes recorded technical-recovery attempts.',
        observations=[dict(id='observation-1', assigned=44, scored=43, excluded=1,
            aborted=0, goal_completed=43, reliable=40, estimated_cost_low_usd='1.23',
            estimated_cost_high_usd='2.34', incomplete_usage=True)])


def encode(value):
    raw = json.dumps(value).encode()
    return raw, sha256(raw).hexdigest()


@patch.object(build, 'load_five', new=lambda: [])
class OpenAI62Tests(unittest.TestCase):
    def test_closed_schema_and_pins(self):
        for model in build.OPENAI62_FILES:
            p = fixture(model)
            self.assertEqual(build.parse_openai62(*encode(p), model), p)
            mutations = [('schema_version',True), ('model','gpt-6.2-other'),
                ('provider','other'), ('endpoint',[]), ('endpoint','chat.completions'),
                ('reasoning',True), ('reasoning',''), ('reasoning','none'), ('reasoning','high'),
                ('currency','EUR'), ('case_set','combined-54'), ('source_revision','private'),
                ('date','2026-02-30'), ('pricing_basis','invoice'), ('extra',0),
                ('cost_assumptions',None), ('cost_assumptions','private/path'),
                ('observations',[])]
            for key,val in mutations:
                bad=copy.deepcopy(p); bad[key]=val
                with self.subTest(key=key), self.assertRaises(ValueError):
                    build.parse_openai62(*encode(bad),model)
            for key,val in [('id','other'), ('assigned',54), ('scored',True), ('scored',0),
                    ('excluded',0), ('aborted',-1), ('reliable',44), ('goal_completed',39),
                    ('incomplete_usage',1), ('extra',0), ('estimated_cost_low_usd','3'),
                    ('estimated_cost_high_usd',None), ('estimated_cost_high_usd','NaN'),
                    ('estimated_cost_high_usd','01'), ('estimated_cost_high_usd',0)]:
                bad=copy.deepcopy(p); bad['observations'][0][key]=val
                with self.subTest(key=key), self.assertRaises(ValueError):
                    build.parse_openai62(*encode(bad),model)
            bad=copy.deepcopy(p); bad['observations']*=2
            with self.assertRaises(ValueError): build.parse_openai62(*encode(bad),model)
            raw,pin=encode(p)
            for digest in (None,True,'0'*64,'g'*64):
                with self.assertRaises(ValueError): build.parse_openai62(raw,digest,model)
            with self.assertRaises(ValueError): build.parse_openai62(raw+b' ',pin,model)
            for key in (b'"schema_version": 1', b'"id": "observation-1"',
                        ('"model": "'+model+'"').encode()):
                bad=raw.replace(key,key+b', '+key)
                with self.assertRaises(ValueError): build.parse_openai62(bad,sha256(bad).hexdigest(),model)

    def test_current_goldens_and_disposable_activation(self):
        current=build.outputs()
        with patch.object(build, 'load_openai62', return_value=[]):
            baseline=build.outputs()
        rows=json.loads(baseline['MODEL_AVERAGES.json'])['models']
        expected={m:tuple(map(F,v)) for m,v in GOLDENS.items()}
        self.assertEqual({r['model']:(F(**r['quality_rate']),F(**r['goal_rate'])) for r in rows},expected)
        self.assertEqual([r['model'] for r in rows], sorted(expected,key=lambda m:(-expected[m][0],-expected[m][1],m.casefold(),m)))
        SCRATCH.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=SCRATCH,prefix='same44-mechanics-') as d:
            root=Path(d)
            for name in ('tools','source'): shutil.copytree(build.ROOT/name,root/name)
            shutil.copy(build.ROOT/'LICENSE-DATA',root/'LICENSE-DATA')
            for filename in build.OPENAI62_FILES.values():
                (root/'source'/filename).unlink(missing_ok=True)
            pins={m:None for m in build.OPENAI62_FILES}
            with patch.object(build,'ROOT',root),patch.object(build,'OPENAI62_DIGESTS',pins):
                self.assertEqual(build.outputs(),baseline)
                for model,filename in build.OPENAI62_FILES.items():
                    raw,pin=encode(fixture(model)); path=root/'source'/filename
                    pins[model]=pin
                    with self.assertRaises(ValueError): build.outputs()
                    pins[model]=None;path.write_bytes(raw)
                    with self.assertRaises(ValueError): build.outputs()
                    pins[model]='0'*64
                    with self.assertRaises(ValueError): build.outputs()
                    pins[model]=pin
                files=build.outputs(); new=json.loads(files['MODEL_AVERAGES.json'])['models']
                self.assertEqual([r for r in new if r['model'] not in pins],rows)
                expected.update({m:(F(40,43),F(1)) for m in pins})
                order=sorted(expected,key=lambda m:(-expected[m][0],-expected[m][1],m.casefold(),m))
                self.assertEqual([r['model'] for r in new],order)
                for r in new:
                    if r['model'] in pins:
                        self.assertEqual((F(**r['quality_rate']),F(**r['goal_rate'])),(F(40,43),F(1)))
                        self.assertEqual(r['observation_count'],1)
                        self.assertEqual(r['average_full_run_estimate']['mean_cost_high_usd'],'2.34')
                for name in baseline.keys()-{'index.html','MODEL_AVERAGES.json'}:
                    self.assertEqual(files[name],baseline[name])
                html=files['index.html'].decode();chart=html.split('<ol class="chart">')[1].split('</ol>')[0]
                self.assertEqual(chart.count('<li class="chart-row">'),32)
                self.assertIn('32 models',html)
                self.assertEqual(chart.count('$2.34'),2)
                self.assertNotRegex(chart.lower(),r'scored|badge|accordion|details|40/43')
                self.assertIn('Missing usage remains unknown',html)
                self.assertIn('declared technical-recovery inclusion',html)
                self.assertNotIn('Technical exclusion costs remain unknown',html)
                for model,filename in build.OPENAI62_FILES.items():
                    self.assertEqual(files[filename],(root/'source'/filename).read_bytes())
                    self.assertIn('./'+filename,html)
                with patch('sys.argv',['build.py']):build.main()
                with patch('sys.argv',['build.py','--check']):build.main()
                self.assertEqual(build.outputs(),files)
                # Re-read at export must pass byte approval again.
                model=next(iter(pins));path=root/'source'/build.OPENAI62_FILES[model]
                raw=path.read_bytes();original=Path.read_bytes;reads=[]
                def drift(p):
                    if p==path:
                        reads.append(p)
                        return raw if len(reads)<=2 else raw+b' '
                    return original(p)
                with patch.object(Path,'read_bytes',drift),self.assertRaises(ValueError):build.outputs()
        self.assertEqual(build.outputs(),current)

    def test_enabled_intake_preserves_all_current_objects(self):
        # Exercise actual configured pins/files without mocking the future loader.
        files = build.outputs()
        packets = build.load_openai62()  # Production validation is always applied.
        with patch.object(build, 'load_openai62', return_value=[]):
            legacy = build.outputs()
        baseline = json.loads(legacy['MODEL_AVERAGES.json'])
        data = json.loads(files['MODEL_AVERAGES.json'])
        rows = data['models']
        added = {p['model']: p for p in packets}
        self.assertEqual(len(baseline['models']), 30)
        self.assertEqual(len(rows), 30 + len(added))
        self.assertEqual([r for r in rows if r['model'] not in added], baseline['models'])
        expected = {m: tuple(map(F, v)) for m, v in GOLDENS.items()}
        for model, packet in added.items():
            # Numeric expectation comes directly from approved aggregate counts.
            obs = packet['observations'][0]
            expected[model] = (F(obs['reliable'], obs['scored']),
                               F(obs['goal_completed'], obs['scored']))
            row = next(r for r in rows if r['model'] == model)
            self.assertEqual(row['observation_count'], 1)
            self.assertEqual(row['average_full_run_estimate'], dict(model=model,
                pricing_basis='official_current_tariff_estimate',
                mean_cost_low_usd=obs['estimated_cost_low_usd'],
                mean_cost_high_usd=obs['estimated_cost_high_usd'],
                incomplete_usage=obs['incomplete_usage']))
            provenance = next(p for p in data['openai62_provenance'] if p['model'] == model)
            raw = (build.ROOT/'source'/build.OPENAI62_FILES[model]).read_bytes()
            self.assertEqual(files[build.OPENAI62_FILES[model]], raw)
            self.assertEqual(provenance['sha256'], sha256(raw).hexdigest())
            self.assertEqual(provenance['reasoning'], 'low')
            self.assertEqual(provenance['endpoint'], 'responses')
        self.assertEqual({r['model']: (F(**r['quality_rate']), F(**r['goal_rate']))
                          for r in rows}, expected)
        order = sorted(expected, key=lambda m: (-expected[m][0], -expected[m][1], m.casefold(), m))
        self.assertEqual([r['model'] for r in rows], order)
        from test_build import Document
        doc = Document(); doc.feed(files['index.html'].decode())
        self.assertEqual(doc.models, order)
        for name in legacy.keys() - {'index.html', 'MODEL_AVERAGES.json'}:
            self.assertEqual(files[name], legacy[name])
        for key in baseline.keys() - {'models', 'cost_assumptions', 'method'}:
            self.assertEqual(data[key], baseline[key])
        if packets:
            self.assertEqual(data['method'], baseline['method'] + ' Each OpenAI 6.2 model uses one observation.')
        else:
            self.assertEqual(files, legacy)

    def test_approved_actual_rows_and_legacy_byte_golden(self):
        files = build.outputs()
        data = json.loads(files['MODEL_AVERAGES.json'])
        rows = data['models']
        models = {'gpt-6.2-astra': (F(42,44), F(43,44), '95.5%', '97.7%',
                   '38.5159988', '$38.52', 'a520d96bcb0eb7cc1fd040b31277eba6b86fe4663ac55c1acdab12a6b25af0e8'),
                  'gpt-6.2-sol': (F(43,44), F(43,44), '97.7%', '97.7%',
                   '9.5845606', '$9.58', 'b8c1bbd42241d29b0e9dc57f493107b0cdcedd2a11e97a4d8fd3c1e9e195f630')}
        legacy = [r for r in rows if r['model'] not in models]
        self.assertEqual(len(legacy), 30)
        raw = json.dumps(legacy, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
        self.assertEqual(sha256(raw).hexdigest(), '01ae5ca77da7a90d2953c21905bb1483049c5b72857887f5215d7b632a4fd9ce')
        expected = {m: tuple(map(F, v)) for m,v in GOLDENS.items()}
        expected.update({m: v[:2] for m,v in models.items()})
        self.assertEqual(len(rows), 32)
        self.assertEqual({r['model']: (F(**r['quality_rate']), F(**r['goal_rate'])) for r in rows}, expected)
        order = sorted(expected, key=lambda m: (-expected[m][0], -expected[m][1], m.casefold(), m))
        self.assertEqual([r['model'] for r in rows], order)
        html = files['index.html'].decode()
        chart = html.split('<ol class="chart">',1)[1].split('</ol>',1)[0]
        self.assertEqual(chart.count('<li class="chart-row">'), 32)
        self.assertIn('both OpenAI 6.2 models have one observation each', html)
        self.assertIn('OpenAI 6.2 percentages use one observation', html)
        self.assertNotIn('OpenAI 6.32 models', html)
        self.assertIn('Each OpenAI 6.2 model uses one observation.', data['method'])
        self.assertIn('Fable 5.2 instead uses one whole best-quality observation of two', data['method'])
        for model, (quality, goal, qp, gp, cost, display, pin) in models.items():
            r = next(r for r in rows if r['model'] == model)
            self.assertEqual((r['average_quality_percent'],r['average_goal_achieved_percent']), (qp,gp))
            self.assertEqual(r['observation_count'], 1)
            self.assertEqual(r['average_full_run_estimate'], dict(model=model,
                pricing_basis='official_current_tariff_estimate', incomplete_usage=False,
                mean_cost_low_usd=cost, mean_cost_high_usd=cost))
            filename = build.OPENAI62_FILES[model]
            packet = files[filename]
            self.assertEqual(sha256(packet).hexdigest(), pin)
            self.assertEqual(packet, (build.ROOT/'source'/filename).read_bytes())
            packet_data = json.loads(packet)
            self.assertEqual(packet_data['source_revision'], '89bb9f6342c5f23c1fd031b84f56d805195dbe28')
            self.assertIn('1.7911276' if model.endswith('astra') else '0.4501136', packet_data['cost_assumptions'])
            obs = packet_data['observations'][0]
            self.assertEqual((obs['assigned'],obs['scored'],obs['excluded'],obs['aborted']), (44,44,0,0))
            self.assertEqual((F(obs['reliable'],44), F(obs['goal_completed'],44)), (quality,goal))
            part = next(x for x in chart.split('<li class="chart-row">') if '<code>'+model+'</code>' in x)
            self.assertEqual(__import__('re').findall(r'<strong>(.*?)</strong>',part), [qp,gp,display])
        self.assertNotRegex(chart.lower(), r'scored|assigned|badge|accordion|<details|\d+/\d+')

    def test_actual_openai_with_optional_legacy_intakes(self):
        fable, selected = build.load_fable(), build.load_selected_six()
        self.assertIsNotNone(fable)
        self.assertIsNotNone(selected)
        for has_fable in (False, True):
            for has_selected in (False, True):
                with self.subTest(fable=has_fable, selected_six=has_selected), \
                        patch.object(build, 'load_fable', return_value=fable if has_fable else None), \
                        patch.object(build, 'load_selected_six', return_value=selected if has_selected else None):
                    files = build.outputs()
                    html = build.render()
                    self.assertEqual(html.encode(), files['index.html'])
                    method = html.split('<details class="methodology"><summary>Methodology &amp; sources</summary><p>', 1)[1].split('</p>', 1)[0]
                    note = html.split('<p id="chart-note">', 1)[1].split('</p>', 1)[0]
                    data = json.loads(files['MODEL_AVERAGES.json'])
                    self.assertIn('OpenAI 6.2 models have one observation each', method)
                    self.assertIn('OpenAI 6.2 percentages use one observation', note)
                    self.assertNotIn('Both are average percentages across', note)
                    self.assertIn('Each OpenAI 6.2 model uses one observation.', data['method'])
                    self.assertNotIn('mean of two original per-observation rates', data['method'])
                    if has_fable:
                        self.assertIn('Fable 5.2 uses the best-quality of two runs', method)
                        if not has_selected:
                            self.assertIn('other models use one or two observations as applicable', method)
                        self.assertIn('Fable 5.2 instead uses one whole best-quality observation of two', data['method'])
                    else:
                        self.assertIn('one or two original per-observation rates', method)
                        self.assertNotIn('Fable 5.2 instead', data['method'])
                    self.assertEqual({p['model'] for p in data['openai62_provenance']}, set(build.OPENAI62_FILES))
                    self.assertEqual(sum(r['model'] in build.OPENAI62_FILES for r in data['models']), 2)
                    for model, filename in build.OPENAI62_FILES.items():
                        self.assertIn(f'<a href="./{filename}">{model} observation aggregates</a>', html)
                        self.assertEqual(files[filename], (build.ROOT/'source'/filename).read_bytes())

    def test_download_labels_identify_exact_model(self):
        import re
        html = build.render()
        for model, filename in build.OPENAI62_FILES.items():
            label = re.search(r'<a href="\./' + re.escape(filename) + r'">([^<]+)</a>', html)
            self.assertIsNotNone(label)
            self.assertEqual(label.group(1), model + ' observation aggregates')

    def test_legacy_intake_bytes_in_all_optional_configurations(self):
        expected = {
            (False, False): ('9106502bd808cbb36d7df10d0833abcec3b830478ec5ff292d7d1774802aaadf', '06fbfda6db4665ee8fbe1db47b948ac3a00e0ef9d1ecb9c9baa9cb7a7f13eac0'),
            (False, True): ('b787f96794aac86af1921c4d04310d8335fab2fac3c3df83eeb9c367da8e8a52', 'a8315e1fd51e1a9389d3b67b565b85f38b4f25a383760123cff77e57dd99b45c'),
            (True, False): ('ccc0058862a96269b223ea3230584ccaf5e9afc0a1e5a5080ac48e777c506b7d', '579345b160032bddc32d7c93161024489fa3131d6254bccee0434972d82b9b15'),
            (True, True): ('e367a2052e6a4cc135822bb703615eb900ef00e4c3183097e6bc4601edd2126e', '2aab131b3b602439c71f8b0ea9444d4a96ae0bdcb6c4899fa2de8e481238d9db'),
        }
        fable, selected = build.load_fable(), build.load_selected_six()
        for (has_fable, has_selected), hashes in expected.items():
            with self.subTest(fable=has_fable, selected_six=has_selected), \
                    patch.object(build, 'load_openai62', return_value=[]), \
                    patch.object(build, 'load_fable', return_value=fable if has_fable else None), \
                    patch.object(build, 'load_selected_six', return_value=selected if has_selected else None):
                files = build.outputs()
                self.assertEqual(tuple(sha256(historical_ui_bytes(n, files[n])).hexdigest() for n in ('index.html', 'MODEL_AVERAGES.json')), hashes)
