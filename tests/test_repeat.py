"""Independent current metrics and two-series presentation contracts."""
import dataclasses
import json
from hashlib import sha256
import unittest
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory
from tools import build
from test_build import Document

# model | scored | excluded | goal | strict, independently transcribed.
CURRENT = '''claude-fable-5-1|44|0|44|35
claude-opus-5-5|44|0|44|26
deepseek-ai/DeepSeek-V4-Flash-0731|44|0|3|1
deepseek-ai/DeepSeek-V4.1-Flash|43|1|7|2
gemini-3.8-flash|43|1|43|19
gemini-4-argon|44|0|44|42
gpt-6-astra|43|1|43|42
gpt-6-luna|44|0|9|0
gpt-6-sol|44|0|40|20
gpt-6.1-sol|44|0|44|42
mistral-medium-3-5|44|0|0|0
muse-spark-1.3|44|0|19|5
muse-wonder-1.0|40|4|20|10
nvidia/GLM-5.2-NVFP4-262K|44|0|29|6
nvidia/Kimi-K2.6-NVFP4|44|0|7|0
nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4|44|0|0|0
Qwen/Qwen3.5-397B-A17B-FP8|44|0|3|0
Qwen/Qwen3.5-9B|44|0|0|0
Qwen/Qwen3.6-35B-A3B-FP8|44|0|7|0
Qwen/Qwen3.8-27B-FP8|44|0|2|2
zai-org/GLM-5.3-Flash|44|0|35|9'''
ORDER = '''gpt-6-astra
gemini-4-argon
gpt-6.1-sol
claude-fable-5-1
claude-opus-5-5
gpt-6-sol
gemini-3.8-flash
muse-wonder-1.0
zai-org/GLM-5.3-Flash
nvidia/GLM-5.2-NVFP4-262K
muse-spark-1.3
deepseek-ai/DeepSeek-V4.1-Flash
Qwen/Qwen3.8-27B-FP8
deepseek-ai/DeepSeek-V4-Flash-0731
gpt-6-luna
nvidia/Kimi-K2.6-NVFP4
Qwen/Qwen3.6-35B-A3B-FP8
Qwen/Qwen3.5-397B-A17B-FP8
mistral-medium-3-5
nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4
Qwen/Qwen3.5-9B'''.splitlines()

class RepeatTests(unittest.TestCase):
    def setUp(self):
        self.data = (build.ROOT / 'source/REPEAT_20261024.json').read_bytes()
        self.rows = build.latest_rows()

    def test_every_current_metric_and_sort(self):
        by_id = {r.model: r for r in self.rows}
        self.assertEqual(len(by_id), 21)
        self.assertEqual([r.model for r in self.rows], ORDER)
        scored = excluded = 0
        for line in CURRENT.splitlines():
            model, n, missing, goal, quality = line.split('|')
            row = by_id[model]
            self.assertEqual(row.scored, n + '/44')
            self.assertEqual(row.goal.split()[0], goal + '/' + n)
            self.assertEqual(row.quality.split()[0], quality + '/' + n)
            self.assertEqual(row.unscored, missing + ' excluded' if int(missing) else '—')
            self.assertEqual(row.cost, 'not reported')
            scored += int(n)
            excluded += int(missing)
        self.assertEqual((scored, excluded), (917, 7))


    def test_determinism_and_generation_drift(self):
        expected = build.outputs()
        self.assertEqual(expected, build.outputs())
        with TemporaryDirectory() as directory:
            root = Path(directory)
            site = root / 'site'; site.mkdir()
            for name, data in expected.items():
                (site / name).write_bytes(data)
            with patch.object(build, 'ROOT', root), patch.object(build, 'outputs', return_value=expected), patch('sys.argv', ['build.py', '--check']):
                build.main()
                (site / 'extra.txt').write_text('unexpected')
                with self.assertRaises(SystemExit):
                    build.main()
                (site / 'extra.txt').unlink()
                (site / 'index.html').write_bytes(b'drift')
                with self.assertRaises(SystemExit):
                    build.main()
                (site / 'index.html').unlink()
                with self.assertRaises(SystemExit):
                    build.main()
        doc = Document(); doc.feed(expected['index.html'].decode())
        for url in doc.urls:
            if url.startswith('./') and url != './':
                self.assertIn(url[2:], expected)


    def test_fail_closed_manifest(self):
        self.assertEqual(sha256(self.data).hexdigest(), 'da3a70a54311b3ecba3b9361c9539322bea071d656c16672cd6026905363fc74')
        mutations = [lambda x: x.update(extra=1), lambda x: x.update(schema_version=True),
                     lambda x: x.update(date='2026-10-25'), lambda x: x.update(conditions='same'),
                     lambda x: x['models'].append(x['models'][0]),
                     lambda x: x['models'][1].update(model=x['models'][0]['model'])]
        for key, value in [('scored', True), ('assigned', 44.0), ('excluded', False), ('reliable', True),
                           ('goal_completed', 45), ('reliable', 45), ('excluded', -1), ('aborted', 1),
                           ('cost_usd', 0), ('cost_usd', 1.25), ('quality_rate', .5), ('reliable', '35/44')]:
            mutations.append(lambda x, k=key, v=value: x['models'][0].update({k:v}))
        for mutate in mutations:
            value = json.loads(self.data); mutate(value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                build.parse_repeat(json.dumps(value))
        with self.assertRaises(ValueError):
            build.parse_repeat(self.data.replace(b'"assigned": 44', b'"assigned": 44, "assigned": 44', 1))
        for malformed in ('null', '[]', '1', '{"models": []}'):
            with self.assertRaises(ValueError):
                build.parse_repeat(malformed)
        with self.assertRaises(ValueError):
            build.parse_repeat(self.data + b'\n')


if __name__ == '__main__':
    unittest.main()
