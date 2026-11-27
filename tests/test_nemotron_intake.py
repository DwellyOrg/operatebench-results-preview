"""Synthetic coverage; no evaluation results are asserted by this fixture."""

import json
import unittest
from hashlib import sha256
from unittest.mock import patch

from tools import build
from test_openai62 import encode, fixture

MODEL = 'nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-NVFP4'
PACKET = 'NVIDIA_NEMOTRON_3_5_SUPER_VL_120B_A12B_NVFP4.json'
VARIANT = 'provider-adapter-overlay-on-public-base'


class NemotronIntakeTests(unittest.TestCase):
    def packet(self):
        value = fixture(MODEL)
        value.update(provider='river', endpoint='chat-completions', reasoning='none-requested', source_variant=VARIANT)
        return value

    def parse(self, value, model=MODEL):
        raw, digest = encode(value)
        self.assertEqual(sha256(raw).hexdigest(), digest)
        return build.parse_five(raw, digest, model)

    def test_parse_requires_truthful_distinct_overlay_provenance(self):
        value = self.packet()
        self.assertEqual(build.FIVE_FILES[MODEL], PACKET)
        self.assertEqual(self.parse(value), value)
        for metadata in ({'source_variant': 'unchanged'}, {'provider': 'other'}, {'reasoning': 'other'}):
            with self.subTest(metadata=metadata), self.assertRaises(ValueError):
                self.parse(dict(value, **metadata))
        with self.assertRaises(ValueError):
            self.parse({k: v for k, v in value.items() if k != 'source_variant'})
        other = 'gemini-4-hydrogen'
        with self.assertRaises(ValueError):
            self.parse(dict(fixture(other), source_variant=VARIANT), other)

    def test_preview_labels_base_link_and_preserves_existing_row_objects(self):
        old = [packet for packet in build.load_five() if packet['model'] != MODEL]
        value = self.parse(self.packet())
        with patch.object(build, 'load_five', return_value=[*old, value]):
            page = build.render()
        self.assertIn('public base revision for ' + MODEL, page)
        self.assertIn('evaluated with a separate provider adapter overlay', page)
        self.assertNotIn('primary actual source revision for ' + MODEL, page)
        data = json.loads(build.aggregate_data([], {'models': [], 'assumptions': 'base'}, five=[*old, value]))
        row = next(r for r in data['five_provenance'] if r['model'] == MODEL)
        self.assertEqual(row['source_variant'], VARIANT)
        self.assertTrue(row['source_url'].endswith(value['source_revision']))
