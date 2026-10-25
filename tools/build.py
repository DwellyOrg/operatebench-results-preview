"""Offline, pinned-source static publisher. Python 3.11+, standard library only."""
import argparse
import json
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, ROUND_FLOOR, ROUND_CEILING
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
    raw = data.encode() if isinstance(data, str) else data
    if sha256(raw).hexdigest() != '9f0e424c631886690902f9286b33390cd20832129ac3f92f0578edbeab2e2aae':
        raise ValueError('Approved Gemini bytes drift')
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


@dataclass(frozen=True)
class Average:
    model: str
    quality: Fraction
    goal: Fraction


def average_order(row):
    return (-row.quality, -row.goal, row.model.casefold(), row.model)


def average_rows(rows=None):
    old = {r.model: r for r in all_rows()}
    rows = list(latest_rows() if rows is None else rows)
    if (len(rows) != 21 or {r.model for r in rows} != set(old)
            or any(r.cohort != 'repeat' for r in rows)):
        raise ValueError('Average view requires exact repeat model census')
    return sorted([Average(r.model, *[
        (metric_fraction(getattr(old[r.model], metric), old[r.model].scored)
         + metric_fraction(getattr(r, metric), r.scored)) / 2
        for metric in ('quality', 'goal')]) for r in rows], key=average_order)


COST_DIGEST = '77b64a66a2c7c823dd0053a51f011cdf32905cf1777a3daf439934b3297d4281'
COST_METHOD = 'arithmetic_mean_per_model'


def parse_costs(data, models, digest=None):
    value = json.loads(data, object_pairs_hook=unique_fields)
    if (type(value) is not dict or set(value) != {'schema_version', 'currency',
            'assigned_cases_per_run', 'average_rule', 'assumptions', 'models'}
            or type(value['schema_version']) is not int or value['schema_version'] != 1
            or value['currency'] != 'USD' or type(value['assigned_cases_per_run']) is not int
            or value['assigned_cases_per_run'] != 44 or value['average_rule'] != COST_METHOD
            or type(value['assumptions']) is not str or not value['assumptions'].strip()
            or type(value['models']) is not list):
        raise ValueError('Invalid average cost schema')
    seen = set()
    for row in value['models']:
        if (type(row) is not dict or set(row) != {'model', 'mean_cost_low_usd',
                'mean_cost_high_usd', 'incomplete_usage', 'pricing_basis'}
                or type(row['model']) is not str or row['model'] in seen
                or type(row['incomplete_usage']) is not bool
                or row['pricing_basis'] not in ('retained_tariff_estimate', 'river_owner_cache_scenarios')):
            raise ValueError('Invalid or duplicate average cost model')
        seen.add(row['model'])
        for key in ('mean_cost_low_usd', 'mean_cost_high_usd'):
            if type(row[key]) is not str or not re.fullmatch(r'(?:0|[1-9][0-9]*)(?:\.[0-9]*[1-9])?', row[key]):
                raise ValueError('Cost must be a canonical nonnegative decimal string')
        if Decimal(row['mean_cost_low_usd']) > Decimal(row['mean_cost_high_usd']):
            raise ValueError('Reversed cost range')
    if len(value['models']) != 21 or seen != set(models):
        raise ValueError('Average cost census drift')
    raw = data.encode() if isinstance(data, str) else data
    if digest is not None and sha256(raw).hexdigest() != digest:
        raise ValueError('Approved cost bytes drift')
    return value


def load_costs(models):
    path = ROOT / 'source/AVERAGE_COSTS.json'
    if not path.exists():
        raise ValueError('Pinned cost source missing')
    if COST_DIGEST is None:
        raise ValueError('Cost source has no approved byte pin')
    return parse_costs(path.read_bytes(), models, COST_DIGEST)


def money(row):
    if row is None:
        raise ValueError('Average cost required')
    low, high = [Decimal(row[k]) for k in ('mean_cost_low_usd', 'mean_cost_high_usd')]
    # Outward rounding preserves lower-bound semantics and scenario ranges.
    lo = low.quantize(Decimal('.01'), rounding=ROUND_FLOOR)
    hi = high.quantize(Decimal('.01'), rounding=ROUND_CEILING)
    if low == high:
        amount = f'${lo:.2f}' if row['incomplete_usage'] else f'${low.quantize(Decimal(".01"), rounding=ROUND_HALF_UP):.2f}'
    else:
        amount = f'${lo:.2f}–${hi:.2f}'
    return ('≥ ' if row['incomplete_usage'] else '') + amount


def render_row(row, cost=None):
    labels = ('Average quality (%)', 'Average goal achieved (%)', 'Average full-run estimate (USD)')
    values = (percent(row.quality), percent(row.goal), money(cost))
    return '<tr><th scope="row"><code>' + escape(row.model) + '</code></th>' + ''.join(
        f'<td data-label="{label}">{escape(value)}</td>' for label, value in zip(labels, values)) + '</tr>'


def render_chart(rows):
    # SVG geometry only: text remains ordinary responsive HTML at every viewport.
    bars = []
    for row in rows:
        width = Decimal(row.quality.numerator) * 100 / row.quality.denominator
        bars.append('<li class="chart-row"><code>' + escape(row.model) + '</code>'
            '<span class="bar"><svg viewBox="0 0 100 12" preserveAspectRatio="none" aria-hidden="true">'
            f'<rect width="{width:.10f}" height="12"/></svg></span>'
            '<strong>' + percent(row.quality) + '</strong></li>')
    return ('<figure aria-labelledby="chart-title"><figcaption id="chart-title">'
            'Average strict quality · all reported checks</figcaption>'
            '<div class="chart-axis" aria-hidden="true"><span>0%</span><span>50%</span><span>100%</span></div>'
            '<ol class="chart">' + ''.join(bars) + '</ol></figure>')


def render(rows=None, costs=None):
    rows = average_rows(rows)
    costs = load_costs(r.model for r in rows) if costs is None else costs
    by_model = {r['model']: r for r in costs['models']}
    table = ('<div class="results-table"><table aria-describedby="method cost-note"><caption>21 model averages · quality descending</caption>'
        '<thead><tr><th scope="col">Model</th><th scope="col" aria-sort="descending">Average quality (%) ↓</th>'
        '<th scope="col">Average goal achieved (%)</th><th scope="col">Average full-run estimate (USD)</th></tr></thead><tbody>'
        + ''.join(render_row(r, by_model[r.model]) for r in rows) + '</tbody></table></div>')
    note = ('Known 44-case campaign estimates including known retries, not invoices. ≥ means an incomplete estimate. '
            + costs['assumptions'])
    template = (ROOT / 'tools/template.html').read_text()
    for key, value in {'DOC': DOC, 'SHA': SHA, 'UPSTREAM': UPSTREAM,
                       'RESULTS': render_chart(rows) + table, 'COST_NOTE': escape(note)}.items():
        template = template.replace('{{' + key + '}}', value)
    return template


def aggregate_data(rows, costs):
    by_model = {r['model']: r for r in costs['models']}
    return (json.dumps({'schema_version': 1,
        'method': 'Unweighted mean of two original per-observation rates; exact rational arithmetic.',
        'cost_assumptions': costs['assumptions'],
        'models': [dict(model=r.model, average_quality_percent=percent(r.quality),
            average_goal_achieved_percent=percent(r.goal),
            quality_rate={'numerator': r.quality.numerator, 'denominator': r.quality.denominator},
            goal_rate={'numerator': r.goal.numerator, 'denominator': r.goal.denominator},
            average_full_run_estimate=by_model[r.model]) for r in rows]},
        indent=2, ensure_ascii=False) + '\n').encode()


def outputs():
    rows = average_rows()
    costs = load_costs(r.model for r in rows)
    return {'index.html': render().encode(),
            'MODEL_AVERAGES.json': aggregate_data(rows, costs),
            'REPEAT_20261024.json': (ROOT / 'source/REPEAT_20261024.json').read_bytes(),
            'GEMINI_AGGREGATES.json': (ROOT / 'source/GEMINI_AGGREGATES.json').read_bytes(),
            'favicon.svg': (ROOT / 'tools/favicon.svg').read_bytes(),
            'style.css': (ROOT / 'tools/style.css').read_bytes(),
            'MODEL_RESULTS.md': (ROOT / 'source/MODEL_RESULTS.md').read_bytes(),
            'LICENSE-DATA': (ROOT / 'LICENSE-DATA').read_bytes(),
            '.nojekyll': b'',
            'AVERAGE_COSTS.json': (ROOT / 'source/AVERAGE_COSTS.json').read_bytes()}


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
        print('OK: pinned historical sources, model averages and generated site match (21 models).')
    else:
        site.mkdir(exist_ok=True)
        for name, data in files.items():
            (site / name).write_bytes(data)
        print('Built site/ with 21 model averages.')

if __name__ == '__main__':
    main()
