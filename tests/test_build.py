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
        if tag == 'th' and attrs.get('scope') == 'row':
            self.in_model = True
        if tag == 'a':
            self.urls.append(attrs.get('href', ''))
    def handle_endtag(self, tag):
        if tag == 'th':
            self.in_model = False
    def handle_data(self, data):
        if self.in_model:
            self.models.append(data)

class BuildTests(unittest.TestCase):
    def setUp(self):
        self.data = (build.ROOT / 'source/MODEL_RESULTS.md').read_bytes()
        self.public_rows = build.parse(self.data)
        self.rows = build.all_rows()

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

    def test_render_escape_defense_in_depth(self):
        row = dataclasses.replace(self.rows[0], model='<script>"&', cost='<img>')
        rendered = build.render_row(row)
        self.assertIn('&lt;script&gt;&quot;&amp;', rendered)
        self.assertIn('&lt;img&gt;', rendered)
        self.assertNotIn('<script>', rendered)

    def test_html_census_and_guardrails(self):
        html = build.render(self.rows)
        doc = Document()
        doc.feed(html)
        self.assertEqual(doc.models, EXPECTED_MODEL_ORDER)
        for text in ('not an official leaderboard or validated general-capability ranking', 'not independent semantic tasks', 'No independent human semantic validation yet', 'Estimates are not invoices', 'observed strict quality pass rate among scored cases', 'Prospire Technologies Ltd', 'CC BY 4.0', 'Apache-2.0'):
            self.assertIn(text, html)
        self.assertEqual(doc.tags.count('table'), 1)
        self.assertEqual(len(doc.models), 21)
        self.assertEqual(len(set(doc.models)), 21)
        self.assertNotIn('Three separate series', html)
        for tag in ('script', 'iframe', 'form'):
            self.assertNotIn(tag, doc.tags)
        for url in doc.urls:
            self.assertTrue(url.startswith(('#', './', build.UPSTREAM + '/', 'https://creativecommons.org/licenses/by/4.0/')), url)
        self.assertIn('href="./style.css"', html)
        self.assertIn('class="skip"', html)
        self.assertIn('lang="en"', html)

    def test_render_sorts_unordered_models_and_breaks_casefold_ties(self):
        doc = Document()
        doc.feed(build.render(reversed(self.rows)))
        self.assertEqual(doc.models, EXPECTED_MODEL_ORDER)
        models = ['beta', 'alpha', 'ALPHA', 'Beta', 'Alpha']
        rows = [dataclasses.replace(self.rows[0], model=model) for model in models]
        doc = Document()
        doc.feed(build.render(rows))
        self.assertEqual(doc.models, ['ALPHA', 'Alpha', 'alpha', 'Beta', 'beta'])

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

    def test_fraction_sort_ignores_numerator_and_rounded_display(self):
        base = self.rows[0]
        rows = [dataclasses.replace(base, model=model, scored=scored,
                                   goal=goal, quality=quality)
                for model, scored, goal, quality in (
                    ('a', '44/44', '44/44 (100.0%)', '0/44 (0.0%)'),
                    ('z', '43/44', '43/43 (100.0%)', '0/43 (0.0%)'),
                    ('b', '44/44', '44/44 (100.0%)', '20/44 (45.5%)'),
                    ('c', '43/44', '43/43 (100.0%)', '20/43 (46.5%)'),
                )]
        doc = Document()
        doc.feed(build.render(rows))
        self.assertEqual(doc.models, ['c', 'b', 'a', 'z'])

    def test_results_intro_markup(self):
        class ResultsIntro(HTMLParser):
            def __init__(self):
                super().__init__()
                self.stack = []
                self.errors = []
                self.direct_paragraphs = []
                self.count = 0

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if not self.stack:
                    if 'results-intro' not in attrs.get('class', '').split():
                        return
                    self.count += 1
                elif len(self.stack) == 1 and tag == 'p':
                    self.direct_paragraphs.append(attrs.get('id'))
                self.stack.append(tag)

            def handle_endtag(self, tag):
                if self.stack:
                    if self.stack[-1] != tag:
                        self.errors.append((self.stack[-1], tag))
                    else:
                        self.stack.pop()

        for name, html in (
            ('template', (build.ROOT / 'tools/template.html').read_text()),
            ('rendered', build.render(self.rows)),
            ('site', (build.ROOT / 'site/index.html').read_text()),
        ):
            with self.subTest(document=name):
                self.assertNotRegex(html, r'</p>\s*</p>')
                intro = ResultsIntro()
                intro.feed(html)
                self.assertEqual(intro.count, 1)
                self.assertEqual(intro.errors, [])
                self.assertEqual(intro.stack, [])
                self.assertEqual(intro.direct_paragraphs, ['comparison'])

    def test_order_copy_and_sort_indicator(self):
        html = build.render(self.rows)
        self.assertIn('<th scope="col" aria-sort="descending">All quality checks ↓</th>', html)
        caption = re.search(r'<caption>(.*?)</caption>', html).group(1)
        self.assertEqual(caption, '21 models · sorted by strict quality ↓')
        self.assertLessEqual(len(caption.split()), 12)
        comparison = re.search(r'<p id="comparison">(.*?)</p>', html).group(1)
        self.assertLessEqual(len(comparison.split()), 45)
        for claim in ('strict quality pass/scored fraction descending',
                      'goal completion fraction descending', 'compared exactly',
                      'Different runs/settings and historical behavior mappings',
                      'incomparable for a validated cross-series capability ranking'):
            self.assertIn(claim, comparison)
        self.assertNotIn('not an official', comparison + caption)
        hero = re.search(r'<p class="hero-copy">(.*?)</p>', html).group(1)
        self.assertIn('not an official leaderboard or validated general-capability ranking', hero)
        doc = Document()
        doc.feed(html)
        self.assertIn(('table', {'aria-describedby': 'comparison gemini-context'}), doc.attributes)
        readme = (build.ROOT / 'README.md').read_text()
        for claim in ('observed strict quality pass rate among scored cases',
                      'goal achieved fraction descending',
                      'case-insensitive exact model ID ascending, then exact model ID ascending',
                      'exact rational arithmetic',
                      'controlled cross-series capability ranking'):
            self.assertIn(claim, ' '.join(readme.split()))
        for text in (html, readme):
            for stale in ('alphabetical', 'not a ranking', 'not a quality ranking'):
                self.assertNotIn(stale, text.lower())

    def test_source_bytes_unchanged(self):
        self.assertEqual(sha256(self.data).hexdigest(),
                         'e0774775be2e2897f7cbaefc8a0acd24ecf4900e1114c2513ae2e66f04c2141f')
        gemini = (build.ROOT / 'source/GEMINI_AGGREGATES.json').read_bytes()
        self.assertEqual(sha256(gemini).hexdigest(), '9f0e424c631886690902f9286b33390cd20832129ac3f92f0578edbeab2e2aae')
        self.assertEqual(build.outputs()['GEMINI_AGGREGATES.json'], gemini)

    def test_about_project_scope_and_pinned_sources(self):
        html = build.render(self.rows)
        doc = Document()
        doc.feed(html)
        self.assertEqual(doc.ids.count('about'), 1)
        self.assertEqual(doc.ids.count('about-title'), 1)
        self.assertIn(('section', {'class': 'about', 'id': 'about',
                                  'aria-labelledby': 'about-title'}), doc.attributes)
        main_nav = html.split('<nav aria-label="Main">', 1)[1].split('</nav>', 1)[0]
        self.assertIn('<a href="#about">About</a>', main_nav)
        self.assertLess(html.index('id="about"'), html.index('id="results"'))
        about = html.split('id="about"', 1)[1].split('</section>', 1)[0]
        text = ' '.join(about.split())
        for claim in (
            'About OperateBench', 'The goal matters.<br>So does the trajectory.',
            'keep a persistent operation safe and progressing',
            'time, evidence, authority and external events change',
            'both the legitimate outcome and the trajectory',
            'official Lifecycle Track remains a technical preview',
            'one synthetic Maintenance Semantic Scenario with three variants',
            'not three independent semantic tasks',
            'Commerce and Property Compliance are SDK incubators, not additional admitted official tracks or official benchmark evidence',
            '44-case exploratory multi-flow model observations shown below are separate from official Lifecycle benchmark evidence',
            'neither production validity nor a general model ranking',
            'No official Lifecycle model results or leaderboard are published',
        ):
            with self.subTest(claim=claim):
                self.assertIn(claim, text)
        # Pin independently of the renderer's source revision and replacements.
        pinned = 'https://github.com/DwellyOrg/OperateBench/blob/963c6b265c71a632d9b333b01e0edcb21685d9e3/'
        for path in ('README.md', 'docs/METHODOLOGY.md'):
            self.assertIn(f'href="{pinned}{path}"', about)
        # Every page-local navigation target resolves uniquely.
        for url in doc.urls:
            if url.startswith('#'):
                self.assertEqual(doc.ids.count(url[1:]), 1, url)
        self.assertEqual(doc.models, EXPECTED_MODEL_ORDER)

    def test_canonical_data_license(self):
        # Independent pin of the canonical CC BY 4.0 text at the approved revision.
        data = (build.ROOT / 'LICENSE-DATA').read_bytes()
        self.assertEqual(len(data), 17023)
        self.assertEqual(sha256(data).hexdigest(), 'd557539df68e771cc1eedcc91d13f70fca930e508d11eedcafa4b15db49e3744')
        self.assertEqual(build.outputs()['LICENSE-DATA'], data)

    def test_local_favicon_and_row_source_labels(self):
        html = build.render(self.rows)
        self.assertIn('<link rel="icon" type="image/svg+xml" href="./favicon.svg">', html)
        svg = build.outputs()['favicon.svg']
        self.assertEqual(ET.fromstring(svg).tag, '{http://www.w3.org/2000/svg}svg')
        self.assertNotIn(b'href=', svg)
        self.assertIn(f'href="{build.DOC}"', html)
        for key in ('baseline', 'meta'):
            url = next(url for cohort, title, url in build.SERIES.values() if cohort == key)
            self.assertIn(f'href="{url}"', html)

    def test_sol_visible_missing_run_commit_disclosure(self):
        row = next(row for row in self.rows if row.model == 'gpt-6.1-sol')
        doc = Document()
        doc.feed(build.render_row(row))
        self.assertEqual(doc.urls, [build.DOC])
        self.assertIn(f'<a href="{build.DOC}">Table · no run commit</a>',
                      build.render_row(row))
        self.assertIn('“Table · no run commit”', (build.ROOT / 'README.md').read_text())

    def test_footer_dual_provenance_and_attribution(self):
        footer = build.render(self.rows).split('<footer>', 1)[1].split('</footer>', 1)[0]
        self.assertIn(f'<a href="{build.DOC}">pinned public OperateBench table (19 rows)</a>', footer)
        self.assertIn('<a href="./GEMINI_AGGREGATES.json">owner-authorized sanitized Gemini aggregates (2 rows)</a>', footer)
        self.assertIn('owned by Prospire Technologies Ltd', footer)
        self.assertIn('<a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>', footer)
        self.assertIn('<a href="./LICENSE-DATA">license text</a>', footer)
        self.assertIn('Site code: Apache-2.0', footer)
        self.assertNotIn('from the original', footer)

    def test_strict_quality_column_emphasis(self):
        css = (build.ROOT / 'tools/style.css').read_text()
        self.assertIn('td:nth-child(6){color:var(--accent);font-weight:650}', css)
        self.assertNotRegex(css, r'td:nth-child\(5\)\s*\{')
        doc = Document()
        doc.feed(build.render_row(self.rows[0]))
        cells = [(tag, attrs) for tag, attrs in doc.attributes
                 if tag in ('th', 'td')]
        self.assertEqual(cells[4][1]['data-label'], 'Goal achieved')
        self.assertEqual(cells[5][1]['data-label'], 'All quality checks')

    def test_seven_column_model_width_has_no_tablet_override(self):
        css = (build.ROOT / 'tools/style.css').read_text()
        # One deliberate width for desktop/tablet; mobile still uses auto!important.
        rules = re.findall(r'th:first-child\s*\{([^}]+)\}', css)
        widths = [match.group(1) for rule in rules
                  for match in re.finditer(r'(?:^|;)\s*width\s*:\s*([^;]+)', rule)]
        self.assertEqual(widths, ['27%'])
        tablet = css.split('@media(max-width:1000px){', 1)[1].split('@media(max-width:720px)', 1)[0]
        self.assertIn('th:first-child{padding-left:16px}', tablet)

    def test_unified_figures_and_sources(self):
        expected = EXPECTED + '\ngemini-4-argon|44|0|44|42|not reported\ngemini-3.8-flash|43|1|43|20|not reported'
        by_id = {r.model: r for r in self.rows}
        self.assertEqual(set(by_id), {line.split('|')[0] for line in expected.splitlines()})
        html = build.render(self.rows)
        for line in expected.splitlines():
            model, n, missing, goal, quality, cost = line.split('|')
            row = by_id[model]
            self.assertEqual(row.scored, n + '/44')
            self.assertEqual(row.unscored, '—' if missing == '0' else missing + (' aborted' if model == 'gpt-6-luna' else ' excluded'))
            for value, count in ((row.goal, goal), (row.quality, quality)):
                percent = (Decimal(count) * 100 / Decimal(n)).quantize(Decimal('.1'), rounding=ROUND_HALF_UP)
                self.assertEqual(value, f'{count}/{n} ({percent}%)')
            self.assertEqual(row.cost, cost if cost == 'not reported' else '$' + cost)
            self.assertIn(build.render_row(row), html)
        self.assertEqual([r.model for r in self.rows], EXPECTED_MODEL_ORDER)
        self.assertEqual({r.cohort for r in self.rows}, {'baseline', 'sol', 'meta', 'gemini'})
        for text in ('19 rows', '2 Gemini rows', 'owner-held/non-public', 'no public raw trajectories or evidence',
                     'no independent human review or provider attestation', 'does not mean success',
                     'historical v3, owner-run · 2026-10-16', 'Audit retained privately',
                     'v4 changed behavior mapping', 'historical results were not regraded',
                     'not reported</strong> (not zero)', 'not approved or reliably reconciled',
                     'docs/GEMINI_OFFLINE.md'):
            self.assertIn(text, html)
        for text in ('/root/', '/var/', 'ledger', 'scorecard', 'credential', 'campaign payload'):
            self.assertNotIn(text, html)
        self.assertEqual(build.outputs()['MODEL_RESULTS.md'], self.data)

    def test_meta_historical_tool_choice_disclosure(self):
        html = build.render(self.rows)
        note = re.search(r'<p id="meta-context">(.*?)</p>', html).group(1)
        doc = Document()
        doc.feed(note)
        pinned = ('https://github.com/DwellyOrg/OperateBench/blob/'
                  '963c6b265c71a632d9b333b01e0edcb21685d9e3/'
                  'docs/META_MUSE_SNAPSHOT.md#L104-L113')
        self.assertEqual(doc.urls, [pinned])
        for claim in ('Meta Standard uses <code>tool_choice:auto</code> instead of <code>required</code>',
                      'historical policy</a> excludes one <code>muse-wonder-1.0</code> text-only response with no tool call',
                      '43/44 scored'):
            self.assertIn(claim, note)
        visible_note = re.sub(r'<[^>]+>', '', note)
        self.assertLessEqual(len(visible_note), 210)
        for disclaimer in ('cost', 'invoice', 'failure'):
            self.assertNotIn(disclaimer, visible_note.lower())
        self.assertLess(html.index('id="results"'), html.index('id="meta-context"'))
        self.assertLess(html.index('id="meta-context"'), html.index('id="gemini-context"'))
        self.assertLess(html.index('id="gemini-context"'), html.index('<table'))

    def test_concise_gemini_caveat_and_no_replay_claim(self):
        html = build.render(self.rows)
        before, context = html.split('<aside class="aggregate-context"', 1)
        caveat, after = context.split('</aside>', 1)
        self.assertEqual(caveat.count('<p>'), 2)
        self.assertTrue(after.lstrip().startswith('<div class="results-table"'))
        pinned = 'https://github.com/DwellyOrg/OperateBench/blob/963c6b265c71a632d9b333b01e0edcb21685d9e3/docs/GEMINI_OFFLINE.md'
        self.assertIn(f'href="{pinned}"', caveat)
        for name, text in (('website', html), ('README.md', (build.ROOT / 'README.md').read_text())):
            for claim in ('87', '88 assigned', 'replay', 'zero provider calls'):
                self.assertNotIn(claim, text.lower(), name)

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

    def test_documentation_disclosure(self):
        for name in ('README.md', 'NOTICE'):
            text = (build.ROOT / name).read_text()
            for claim in ('19', 'Gemini rows', 'owner-held/non-public', 'CC BY 4.0', 'Prospire Technologies Ltd'):
                self.assertIn(claim, text, name)
        for name, data in build.outputs().items():
            if name.endswith(('.html', '.json', '.md')):
                for forbidden in (b'/root/', b'/var/www/', b'ledger', b'scorecard', b'credentials'):
                    self.assertNotIn(forbidden, data, name)

    def test_generated_output_matches(self):
        for name, data in build.outputs().items():
            self.assertEqual((build.ROOT / 'site' / name).read_bytes(), data, name)

if __name__ == '__main__':
    unittest.main()
