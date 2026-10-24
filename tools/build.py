"""Offline, pinned-source static publisher. Python 3.11+, standard library only."""
import argparse
import json
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
from hashlib import sha256
from html import escape
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SHA = '963c6b265c71a632d9b333b01e0edcb21685d9e3'
DIGEST = 'e0774775be2e2897f7cbaefc8a0acd24ecf4900e1114c2513ae2e66f04c2141f'
UPSTREAM = 'https://github.com/DwellyOrg/OperateBench'
DOC = f'{UPSTREAM}/blob/{SHA}/docs/MODEL_RESULTS.md'
SERIES = {
    f'[Baseline original campaign]({UPSTREAM}/commit/58b36826894c4306aa3ab)': ('baseline', 'Baseline original campaign', f'{UPSTREAM}/commit/58b36826894c4306aa3ab'),
    'Additive Sol6.1 run': ('sol', 'Additive Sol6.1 run', DOC),
    f'[Additive Meta Standard]({UPSTREAM}/commit/c6fb49bf2a3714c094c4)': ('meta', 'Additive Meta Standard', f'{UPSTREAM}/commit/c6fb49bf2a3714c094c4'),
}
TITLE = '# Model results — descriptive observations: 44 related synthetic cases per model, one trial per case; separate sources/settings; no independent human review yet; not a general-capability ranking'
HEADER = '| Model | Series (distinct runs/settings) | Scored / assigned | Unscored (excluded / aborted) | Goal achieved | All quality checks | Estimated cost (USD, not invoice) |'
SEPARATOR = '| --- | --- | --- | --- | --- | --- | --- |'

@dataclass(frozen=True)
class Row:
    model: str
    cohort: str
    scored: str
    unscored: str
    goal: str
    quality: str
    cost: str


def parse(data: bytes):
    lines = data.decode('utf-8').splitlines()
    if len(lines) != 23 or lines[:4] != [TITLE, '', HEADER, SEPARATOR]:
        raise ValueError('Unexpected source structure or headings')
    rows = []
    for line in lines[4:]:
        cells = line.split('|')
        if len(cells) != 9 or cells[0] or cells[-1]:
            raise ValueError('Unexpected columns')
        model, series, scored, unscored, goal, quality, cost = [c.strip() for c in cells[1:-1]]
        if not re.fullmatch(r'`[A-Za-z0-9][A-Za-z0-9./-]*`', model):
            raise ValueError('Unsafe model ID')
        if series not in SERIES:
            raise ValueError('Unknown series or source URL')
        match = re.fullmatch(r'(\d+)/44', scored)
        if not match or not 0 < int(match[1]) <= 44:
            raise ValueError('Invalid scored denominator')
        n = int(match[1])
        missing = 0
        if unscored != '—':
            match = re.fullmatch(r'([1-9]\d*) (excluded|aborted)', unscored)
            if not match:
                raise ValueError('Invalid unscored disposition')
            missing = int(match[1])
        if n + missing != 44:
            raise ValueError('Unscored cases must be separate from scored cases')
        counts = []
        for value in (goal, quality):
            match = re.fullmatch(r'(\d+)/(\d+) \((\d+\.\d)%\)', value)
            if not match:
                raise ValueError('Invalid metric')
            num, den = int(match[1]), int(match[2])
            if den != n or not 0 <= num <= den:
                raise ValueError('Invalid metric denominator')
            percent = (Decimal(num) * 100 / den).quantize(Decimal('.1'), rounding=ROUND_HALF_UP)
            if percent != Decimal(match[3]):
                raise ValueError('Invalid percentage arithmetic')
            counts.append(num)
        if counts[1] > counts[0] or not re.fullmatch(r'\$[1-9]\d*', cost):
            raise ValueError('Invalid quality subset or estimated cost')
        rows.append(Row(model[1:-1], SERIES[series][0], scored, unscored, goal, quality, cost))
    if len({r.model for r in rows}) != 19 or Counter(r.cohort for r in rows) != {'baseline': 16, 'sol': 1, 'meta': 2}:
        raise ValueError('Unexpected model census')
    # Pin all figures, IDs, row order, costs and source bytes, beyond structural checks.
    if sha256(data).hexdigest() != DIGEST:
        raise ValueError('Pinned source SHA snapshot drift')
    return rows


GEMINI = {
    "series": "Gemini v3 owner-run campaign",
    "mapping": "historical v3; original-source replay only",
    "date": "2026-10-16",
    "models": [
        {"model": "gemini-4-argon", "assigned": 44, "scored": 44, "excluded": 0, "aborted": 0,
         "goal": "44/44 (100.0%)", "quality": "42/44 (95.5%)", "cost_usd": None},
        {"model": "gemini-3.8-flash", "assigned": 44, "scored": 43, "excluded": 1, "aborted": 0,
         "goal": "43/43 (100.0%)", "quality": "20/43 (46.5%)", "cost_usd": None},
    ],
}


def parse_gemini(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    value = json.loads(data, object_pairs_hook=unique)
    # Exact approved schema, types and values: reject extra fields or any drift.
    if json.dumps(value, sort_keys=True) != json.dumps(GEMINI, sort_keys=True):
        raise ValueError('Approved Gemini aggregate schema or figures drift')
    return [Row(m['model'], 'gemini', f"{m['scored']}/44",
                '—' if not m['excluded'] else f"{m['excluded']} excluded",
                m['goal'], m['quality'], 'not reported') for m in value['models']]


REPEAT_DIGEST = 'da3a70a54311b3ecba3b9361c9539322bea071d656c16672cd6026905363fc74'
REPEAT_CONDITIONS = 'Core includes the public payment-history and approval-checkpoint corrections. Provider compatibility adapters differ from earlier series. Historical grades were not regraded.'


def unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def percent(value):
    return str((Decimal(value.numerator) * 100 / value.denominator).quantize(Decimal('.1'), rounding=ROUND_HALF_UP)) + '%'


def parse_repeat(data):
    value = json.loads(data, object_pairs_hook=unique_fields)
    if (type(value) is not dict or set(value) != {'schema_version', 'series', 'date', 'conditions', 'models'}
            or type(value['schema_version']) is not int or value['schema_version'] != 1
            or value['series'] != '2026-10-24 owner-run repeat'
            or value['date'] != '2026-10-24' or value['conditions'] != REPEAT_CONDITIONS
            or type(value['models']) is not list):
        raise ValueError('Unapproved repeat schema or conditions')
    rows = []
    for m in value['models']:
        if type(m) is not dict or set(m) != {'model', 'assigned', 'scored', 'excluded', 'aborted', 'goal_completed', 'reliable', 'cost_usd'}:
            raise ValueError('Unapproved repeat fields')
        if type(m['model']) is not str:
            raise ValueError('Invalid repeat model ID')
        if any(type(m[k]) is not int for k in ('assigned', 'scored', 'excluded', 'aborted', 'goal_completed', 'reliable')):
            raise ValueError('Repeat counts must be integers')
        if (m['assigned'] != 44 or not 0 <= m['reliable'] <= m['goal_completed'] <= m['scored'] <= 44
                or m['scored'] == 0 or min(m['excluded'], m['aborted']) < 0
                or m['assigned'] != m['scored'] + m['excluded'] + m['aborted'] or m['cost_usd'] is not None):
            raise ValueError('Invalid repeat counts or cost')
        metrics = [f"{m[k]}/{m['scored']} ({percent(Fraction(m[k], m['scored']))})" for k in ('goal_completed', 'reliable')]
        unscored = ', '.join(f"{m[k]} {k}" for k in ('excluded', 'aborted') if m[k]) or '—'
        rows.append(Row(m['model'], 'repeat', f"{m['scored']}/44", unscored, *metrics, 'not reported'))
    if len(rows) != 21 or {r.model for r in rows} != {r.model for r in all_rows()}:
        raise ValueError('Repeat model census drift')
    raw = data.encode() if isinstance(data, str) else data
    if sha256(raw).hexdigest() != REPEAT_DIGEST:
        raise ValueError('Approved repeat bytes drift')
    return sorted(rows, key=quality_order)


def latest_rows():
    return parse_repeat((ROOT / 'source/REPEAT_20261024.json').read_bytes())


def observed_range(rows, metric):
    values = [metric_fraction(getattr(r, metric), r.scored) for r in rows]
    low, high = min(values), max(values)
    return percent(low) if low == high else percent(low)[:-1] + '–' + percent(high)


def observation(row):
    labels = {key: (title, url) for key, title, url in SERIES.values()}
    labels['gemini'] = ('Historical Gemini v3 · 2026-10-16 · owner-held audit', './GEMINI_AGGREGATES.json')
    labels['repeat'] = ('2026-10-24 · owner-held audit/no public run commit', './REPEAT_20261024.json')
    title, url = labels[row.cohort]
    if row.cohort == 'sol':
        title = 'Table · no run commit'
    prefix = '' if row.cohort in ('repeat', 'gemini') else 'Historical · '
    return (f'<li><a href="{escape(url)}">{escape(prefix + title)}</a>; '
            f'scored / assigned {escape(row.scored)}; unscored {escape(row.unscored)}; '
            f'goal {escape(row.goal)}; all quality checks {escape(row.quality)}; '
            f'estimated USD {escape(row.cost)}.</li>')


def render_latest_row(row, old):
    series = [old, row]
    history = '<details><summary>2 series · observation history</summary><ul>' + ''.join(observation(r) for r in series) + '</ul></details>'
    values = [history, escape(row.scored), escape(row.unscored),
              escape(row.goal) + '<small>Observed ' + observed_range(series, 'goal') + '</small>',
              escape(row.quality) + '<small>Observed ' + observed_range(series, 'quality') + '</small>', 'not reported']
    labels = ['Source / run', 'Scored / assigned', 'Unscored', 'Goal achieved', 'All quality checks', 'Est. USD']
    return '<tr><th scope="row"><code>' + escape(row.model) + '</code></th>' + ''.join(f'<td data-label="{label}">{value}</td>' for label, value in zip(labels, values)) + '</tr>'


def metric_fraction(value, scored):
    """Read the exact scored-case fraction; display percentages never sort rows."""
    scored_match = re.fullmatch(r'(\d+)/44', scored)
    match = re.fullmatch(r'(\d+)/(\d+) \((\d+\.\d)%\)', value)
    if not scored_match or not match:
        raise ValueError('Invalid scored fraction or metric')
    num, den = int(match[1]), int(match[2])
    if not 0 < den <= 44 or den != int(scored_match[1]) or not 0 <= num <= den:
        raise ValueError('Invalid metric denominator or numerator')
    percent = (Decimal(num) * 100 / den).quantize(Decimal('.1'), rounding=ROUND_HALF_UP)
    if percent != Decimal(match[3]):
        raise ValueError('Invalid percentage arithmetic')
    return Fraction(num, den)


def quality_order(row):
    return (-metric_fraction(row.quality, row.scored),
            -metric_fraction(row.goal, row.scored), row.model.casefold(), row.model)


def all_rows():
    rows = parse((ROOT / 'source/MODEL_RESULTS.md').read_bytes()) + parse_gemini(
        (ROOT / 'source/GEMINI_AGGREGATES.json').read_bytes())
    if len(rows) != 21 or len({r.model for r in rows}) != 21:
        raise ValueError('Duplicate or missing model')
    return sorted(rows, key=quality_order)


def render_row(row):
    short_labels = {'baseline': 'Baseline', 'sol': 'Table · no run commit', 'meta': 'Meta'}
    labels_by_run = {key: (short_labels[key], url) for key, title, url in SERIES.values()}
    labels_by_run['gemini'] = ('Gemini v3 · 2026-10-16 · owner-held audit', '#gemini-context')
    title, url = labels_by_run[row.cohort]
    values = (row.scored, row.unscored, row.goal, row.quality, row.cost)
    labels = ('Scored / assigned', 'Unscored', 'Goal achieved', 'All quality checks', 'Est. USD')
    return '<tr><th scope="row"><code>' + escape(row.model) + '</code></th>' + f'<td data-label="Source / run"><a href="{escape(url)}">{escape(title)}</a></td>' + ''.join(
        f'<td data-label="{label}">{escape(value)}</td>' for label, value in zip(labels, values)) + '</tr>'


def render_table_rows(rows, renderer=render_row):
    """Sort and escape table bodies without attaching latest-series context."""
    return ''.join(renderer(row) for row in sorted(rows, key=quality_order))


def disposition_count(row, disposition):
    return sum(int(count) for count, label in re.findall(r'(\d+) (excluded|aborted)', row.unscored)
               if label == disposition)


def render(rows):
    rows = list(rows)
    if not rows or any(row.cohort != 'repeat' for row in rows):
        raise ValueError('Latest page requires repeat rows only')
    historical = {row.model: row for row in all_rows()}
    if len(rows) != len(historical) or {row.model for row in rows} != set(historical):
        raise ValueError('Latest page requires the exact model census')
    wonder = next(row for row in rows if row.model == 'muse-wonder-1.0')
    total_scored = sum(int(row.scored.split('/')[0]) for row in rows)
    total_excluded = sum(disposition_count(row, 'excluded') for row in rows)
    total_aborted = sum(disposition_count(row, 'aborted') for row in rows)
    totals = f'{total_scored} scored + {total_excluded} excluded'
    if total_aborted:
        totals += f' + {total_aborted} aborted'

    table = '<div class="results-table"><table aria-describedby="comparison spread-context repeat-context meta-context gemini-context"><caption>21 models · latest 2026-10-24 · strict quality ↓</caption><thead><tr><th scope="col">Exact model ID</th><th scope="col">Source / run</th><th scope="col">Scored / assigned</th><th scope="col">Unscored</th><th scope="col">Goal achieved</th><th scope="col" aria-sort="descending">All quality checks ↓</th><th scope="col">Est. USD</th></tr></thead><tbody>' + render_table_rows(rows, lambda row: render_latest_row(row, historical[row.model])) + '</tbody></table></div>'
    template = (ROOT / 'tools/template.html').read_text()
    return template.replace('{{DOC}}', DOC).replace('{{SHA}}', SHA).replace('{{UPSTREAM}}', UPSTREAM).replace('{{RESULTS}}', table).replace('{{TOTALS}}', totals).replace('{{WONDER_SCORED}}', escape(wonder.scored)).replace('{{WONDER_EXCLUDED}}', str(disposition_count(wonder, 'excluded')))


def outputs():
    rows = latest_rows()
    return {'index.html': render(rows).encode(),
            'REPEAT_20261024.json': (ROOT / 'source/REPEAT_20261024.json').read_bytes(),
            'GEMINI_AGGREGATES.json': (ROOT / 'source/GEMINI_AGGREGATES.json').read_bytes(),
            'favicon.svg': (ROOT / 'tools/favicon.svg').read_bytes(),
            'style.css': (ROOT / 'tools/style.css').read_bytes(),
            'MODEL_RESULTS.md': (ROOT / 'source/MODEL_RESULTS.md').read_bytes(),
            'LICENSE-DATA': (ROOT / 'LICENSE-DATA').read_bytes(),
            '.nojekyll': b''}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    files = outputs()
    site = ROOT / 'site'
    if args.check:
        actual = {str(p.relative_to(site)) for p in site.rglob('*') if p.is_file()}
        if actual != set(files) or any(not (site / name).exists() or (site / name).read_bytes() != data for name, data in files.items()):
            raise SystemExit('Generated site differs; run python3 tools/build.py')
        print('OK: pinned historical sources, approved repeat aggregates and generated site match (21 models).')
    else:
        site.mkdir(exist_ok=True)
        for name, data in files.items():
            (site / name).write_bytes(data)
        print('Built site/ with 21 latest models and two original series per model.')

if __name__ == '__main__':
    main()
