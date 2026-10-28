import dataclasses
import json
import re
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
from hashlib import sha256
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
import unittest
from tools import build

# Independent transcription of every published row for regression assertions.
EXPECTED = '''gpt-6-astra|44|0|44|42|239
claude-fable-5-1|43|1|43|35|189
claude-opus-5-5|44|0|43|22|155
gpt-6-sol|44|0|39|19|72
nvidia/GLM-5.2-NVFP4-262K|44|0|34|6|123
zai-org/GLM-5.3-Flash|44|0|33|4|94
deepseek-ai/DeepSeek-V4-Flash-0731|44|0|2|1|213
Qwen/Qwen3.8-27B-FP8|44|0|1|1|207
gpt-6-luna|40|4|9|0|124
deepseek-ai/DeepSeek-V4.1-Flash|44|0|9|0|221
Qwen/Qwen3.6-35B-A3B-FP8|44|0|8|0|141
nvidia/Kimi-K2.6-NVFP4|43|1|7|0|75
Qwen/Qwen3.5-397B-A17B-FP8|44|0|3|0|110
mistral-medium-3-5|44|0|0|0|164
nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4|44|0|0|0|185
Qwen/Qwen3.5-9B|44|0|0|0|96
gpt-6.1-sol|44|0|44|42|53
muse-wonder-1.0|43|1|27|12|33
muse-spark-1.3|44|0|18|4|11'''


# Independent expected order, transcribed from the observed fractions and tie rules.
EXPECTED_MODEL_ORDER = """gemini-4-argon
gpt-6-astra
gpt-6.1-sol
claude-fable-5-1
claude-opus-5-5
gemini-3.8-flash
gpt-6-sol
muse-wonder-1.0
nvidia/GLM-5.2-NVFP4-262K
zai-org/GLM-5.3-Flash
muse-spark-1.3
deepseek-ai/DeepSeek-V4-Flash-0731
Qwen/Qwen3.8-27B-FP8
gpt-6-luna
deepseek-ai/DeepSeek-V4.1-Flash
Qwen/Qwen3.6-35B-A3B-FP8
nvidia/Kimi-K2.6-NVFP4
Qwen/Qwen3.5-397B-A17B-FP8
mistral-medium-3-5
nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4
Qwen/Qwen3.5-9B""".splitlines()

class Document(HTMLParser):
    def __init__(self):
        super().__init__()
        self.models = []
        self.in_model = False
        self.tags = []
        self.urls = []
        self.ids = []
        self.attributes = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.append(tag)
        self.attributes.append((tag, attrs))
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == 'code':
            self.in_model = True
        if tag == 'a':
            self.urls.append(attrs.get('href', ''))
    def handle_endtag(self, tag):
        if tag == 'code':
            self.in_model = False
    def handle_data(self, data):
        if self.in_model:
            self.models.append(data)

class BuildTests(unittest.TestCase):
    def setUp(self):
        self.data = (build.ROOT / 'source/MODEL_RESULTS.md').read_bytes()
        self.public_rows = build.parse(self.data)
        self.rows = build.all_rows()
        self.latest = build.latest_rows()

    def test_all_published_rows(self):
        expected = [line.split('|') for line in EXPECTED.splitlines()]
        self.assertEqual(len(self.public_rows), 19)
        for i, (row, values) in enumerate(zip(self.public_rows, expected)):
            model, n, missing, goal, quality, cost = values
            self.assertEqual(row.model, model)
            self.assertEqual(row.scored, n + '/44')
            self.assertEqual(row.unscored, '—' if missing == '0' else missing + (' aborted' if model == 'gpt-6-luna' else ' excluded'))
            self.assertEqual(row.goal.split()[0], goal + '/' + n)
            self.assertEqual(row.quality.split()[0], quality + '/' + n)
            self.assertEqual(row.cost, '$' + cost)
            self.assertEqual(row.cohort, 'baseline' if i < 16 else 'sol' if i == 16 else 'meta')
        self.assertEqual(self.public_rows[1].quality, '35/43 (81.4%)')
        self.assertEqual(self.public_rows[8].goal, '9/40 (22.5%)')
        self.assertEqual(self.public_rows[17].goal, '27/43 (62.8%)')

    def test_unknown_and_malformed_inputs_rejected(self):
        changes = [
            ('# Model results', '# New results'),
            ('Scored / assigned', 'Scored'),
            ('Additive Sol6.1 run', 'Unknown series'),
            ('github.com/DwellyOrg', 'evil.example/DwellyOrg'),
            ('`gpt-6-astra`', '`<img src=x onerror=alert(1)>`'),
            ('`gpt-6-sol`', '`gpt-6-astra`'),
            ('44/44 (100.0%)', '44/43 (100.0%)'),
            ('42/44 (95.5%)', '42/44 (95.4%)'),
            ('1 excluded', '2 excluded'),
            ('$239', '$240'),  # syntactically valid drift must also fail
            ('$239', '$NaN'),
        ]
        for old, new in changes:
            with self.subTest(new=new), self.assertRaises(ValueError):
                build.parse(self.data.replace(old.encode(), new.encode(), 1))
        for data in (self.data + self.data.splitlines(True)[4], self.data[:-10], self.data.replace(b'| 44/44 |', b'| 44/44 | extra |', 1)):
            with self.assertRaises(ValueError):
                build.parse(data)


    def test_exact_fraction_inputs(self):
        for value, scored, expected in (
            ('42/44 (95.5%)', '44/44', Fraction(21, 22)),
            ('44/44 (100.0%)', '44/44', Fraction(1)),
            ('1/44 (2.3%)', '44/44', Fraction(1, 44)),
            ('0/40 (0.0%)', '40/44', Fraction(0)),
            ('20/43 (46.5%)', '43/44', Fraction(20, 43)),
            ('35/43 (81.4%)', '43/44', Fraction(35, 43)),
        ):
            with self.subTest(value=value):
                result = build.metric_fraction(value, scored)
                self.assertIsInstance(result, Fraction)
                self.assertEqual(result, expected)
        for value, scored in (
            ('1/0 (0.0%)', '0/44'), ('45/44 (102.3%)', '44/44'),
            ('-1/44 (0.0%)', '44/44'), ('20/43 (46.5%)', '44/44'),
            ('20/43 (46.6%)', '43/44'), ('1/44', '44/44'),
            ('1.0/44 (2.3%)', '44/44'), ('0/45 (0.0%)', '45/44'),
            ('1/44 (2.3%) extra', '44/44'), ('1/44 (2.3%)', '44/45'),
        ):
            with self.subTest(value=value, scored=scored), self.assertRaises(ValueError):
                build.metric_fraction(value, scored)


    def test_source_bytes_unchanged(self):
        self.assertEqual(sha256(self.data).hexdigest(),
                         'e0774775be2e2897f7cbaefc8a0acd24ecf4900e1114c2513ae2e66f04c2141f')
        gemini = (build.ROOT / 'source/GEMINI_AGGREGATES.json').read_bytes()
        self.assertEqual(sha256(gemini).hexdigest(), '9f0e424c631886690902f9286b33390cd20832129ac3f92f0578edbeab2e2aae')
        self.assertEqual(build.outputs()['GEMINI_AGGREGATES.json'], gemini)


    def test_canonical_data_license(self):
        # Independent pin of the canonical CC BY 4.0 text at the approved revision.
        data = (build.ROOT / 'LICENSE-DATA').read_bytes()
        self.assertEqual(len(data), 17023)
        self.assertEqual(sha256(data).hexdigest(), 'd557539df68e771cc1eedcc91d13f70fca930e508d11eedcafa4b15db49e3744')
        self.assertEqual(build.outputs()['LICENSE-DATA'], data)


    def test_gemini_fail_closed(self):
        data = (build.ROOT / 'source/GEMINI_AGGREGATES.json').read_bytes()
        self.assertEqual(len(build.parse_gemini(data)), 2)
        for mutate in (
            lambda x: x.update(extra='unapproved'),
            lambda x: x.update(mapping='v4'),
            lambda x: x.update(date='2026-10-17'),
            lambda x: x['models'][0].update(scored=43),
            lambda x: x['models'][0].update(assigned=43),
            lambda x: x['models'][0].update(assigned=44.0),
            lambda x: x['models'][0].update(cost_usd=0),
            lambda x: x['models'][0].update(quality='42/44 (95.4%)'),
            lambda x: x['models'][0].update(model='gemini-3.8-flash'),
            lambda x: x['models'].append(x['models'][0]),
            lambda x: x['models'][0].update(excluded=1),
            lambda x: x['models'][0].update(aborted=1),
        ):
            value = json.loads(data)
            mutate(value)
            with self.assertRaises(ValueError):
                build.parse_gemini(json.dumps(value))
        with self.assertRaises(ValueError):
            build.parse_gemini(data.decode().replace('"assigned": 44', '"assigned": 44, "assigned": 44', 1))


    def test_generated_output_matches(self):
        for name, data in build.outputs().items():
            self.assertEqual((build.ROOT / 'site' / name).read_bytes(), data, name)


if __name__ == '__main__':
    unittest.main()
