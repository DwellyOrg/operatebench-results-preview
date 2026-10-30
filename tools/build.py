"""Offline, pinned-source static publisher. Python 3.11+, standard library only."""
import argparse
from datetime import date
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


SELECTED_SIX_DIGEST = 'a5032145578776f88e32d6235849dfb2243afefc4992827c4344bcc34817e432'
SELECTED_SIX_FILE = 'SELECTED_SIX_20261029.json'
SELECTED_SIX_SERIES = '2026-10-29 owner-run selected six'
# Routes qualified for the accepted actual observations.
SELECTED_SIX_ROUTES = {
    'gpt-6.1-terra': ('openai', 'responses'),
    'claude-haiku-5-5': ('anthropic', 'messages'),
    'mistral-large-4': ('mistral', 'native-chat'),
    'grok-4.7': ('xai', 'responses'),
    'GLM-5.3': ('river', 'http'),
    'moonshotai/Kimi-K3': ('river', 'http'),
}


ORIGINAL_SOURCE = 'f3bd45fb0d219929c9415b734dfeb9ef0cb6a5b8'
CORRECTION_SOURCE = '989c22d9c8342df26eb78eb77f798c9b245abf6e'


def validate_recovery_provenance(packet):
    """Closed aggregate-only contract; counts refer to distinct original cells."""
    p = packet['provenance']
    def fields(value, keys):
        if type(value) is not dict or set(value) != set(keys.split()):
            raise ValueError('Invalid recovery provenance fields')
    def counts(value, keys):
        if any(type(value[k]) is not int or value[k] < 0 for k in keys.split()):
            raise ValueError('Invalid recovery counts')
    fields(p, 'original_source_revision correction_source_revision models')
    if (p['original_source_revision'] != ORIGINAL_SOURCE
            or p['correction_source_revision'] != CORRECTION_SOURCE
            or packet['source_revision'] != CORRECTION_SOURCE
            or type(p['models']) is not list or len(p['models']) != 6):
        raise ValueError('Invalid recovery sources or census')
    effective = {m['model']: m for m in packet['models']}
    seen = set()
    original_counts = {
        'gpt-6.1-terra': (44, 0, 0), 'claude-haiku-5-5': (13, 31, 0),
        'mistral-large-4': (24, 20, 0), 'grok-4.7': (15, 29, 0),
        'GLM-5.3': (28, 12, 4), 'moonshotai/Kimi-K3': (38, 6, 0)}
    original_grades = {'gpt-6.1-terra': (44,38), 'claude-haiku-5-5': (0,0),
        'mistral-large-4': (0,0), 'grok-4.7': (15,5),
        'GLM-5.3': (25,5), 'moonshotai/Kimi-K3': (16,0)}
    selected = 0
    for m in p['models']:
        fields(m, 'model original_scored original_excluded original_aborted technical_selected distinct_attempted total_attempts terminal_attempts effective_original effective_corrected effective_unresolved attempt_groups')
        name = m['model']
        if type(name) is not str or name not in effective or name in seen:
            raise ValueError('Invalid recovery model census')
        seen.add(name)
        counts(m, 'original_scored original_excluded original_aborted technical_selected distinct_attempted total_attempts terminal_attempts effective_original effective_corrected effective_unresolved')
        if tuple(m[k] for k in ('original_scored', 'original_excluded', 'original_aborted')) != original_counts[name]:
            raise ValueError('Immutable original counts drift')
        technical = m['original_excluded'] + m['original_aborted']
        if (m['original_scored'] + technical != 44
                or m['technical_selected'] != technical
                or m['distinct_attempted'] != technical
                or not 0 <= m['effective_corrected'] <= m['distinct_attempted']
                or m['total_attempts'] != m['terminal_attempts']
                or m['terminal_attempts'] < m['distinct_attempted']
                or m['effective_original'] != m['original_scored']
                or m['effective_unresolved'] != technical - m['effective_corrected']
                or effective[name]['scored'] != m['effective_original'] + m['effective_corrected']
                or effective[name]['excluded'] + effective[name]['aborted'] != m['effective_unresolved']):
            raise ValueError('Recovery reconciliation failed')
        goal, reliable = original_grades[name]
        if not (goal <= effective[name]['goal_completed'] <= goal + m['effective_corrected']
                and reliable <= effective[name]['reliable'] <= reliable + m['effective_corrected']
                and effective[name]['reliable'] - reliable <= effective[name]['goal_completed'] - goal):
            raise ValueError('Immutable original grades drift')
        selected += technical
        if type(m['attempt_groups']) is not list:
            raise ValueError('Invalid attempt-contract groups')
        groups = set()
        totals = {'original': 0, 'correction': 0}
        for g in m['attempt_groups']:
            fields(g, 'phase source_revision basis registry_mapping_sha256 count')
            phase = g['phase']
            if (type(phase) is not str or phase not in totals
                    or g['source_revision'] not in ((ORIGINAL_SOURCE,) if phase == 'original' else (ORIGINAL_SOURCE, CORRECTION_SOURCE))
                    or g['basis'] != 'admitted-attempt-contract'
                    or type(g['registry_mapping_sha256']) is not str
                    or not re.fullmatch(r'[0-9a-f]{64}', g['registry_mapping_sha256'])
                    or type(g['count']) is not int or g['count'] <= 0):
                raise ValueError('Invalid attempt-contract group')
            key = (phase, g['source_revision'], g['registry_mapping_sha256'])
            if key in groups:
                raise ValueError('Duplicate attempt-contract group')
            groups.add(key)
            totals[phase] += g['count']
        if totals != {'original': 44, 'correction': m['terminal_attempts']}:
            raise ValueError('Attempt-contract counts do not reconcile')
    if selected != 102 or sum(m['original_scored'] for m in p['models']) != 162:
        raise ValueError('Recovery scope must cover all 102 technical originals')


def parse_selected_six(data, digest):
    if type(digest) is not str or not re.fullmatch(r'[0-9a-f]{64}', digest):
        raise ValueError('Selected six requires an approved byte pin')
    raw = data.encode() if isinstance(data, str) else data
    if sha256(raw).hexdigest() != digest:
        raise ValueError('Selected six bytes drift')
    value = json.loads(data, object_pairs_hook=unique_fields)
    def token(v):
        return type(v) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,79}', v)
    if (type(value) is not dict or set(value) != ({'schema_version', 'series', 'date',
            'conditions', 'source_revision', 'evaluator', 'models'} |
            ({'provenance'} if value.get('schema_version') == 2 else set()))
            or type(value['schema_version']) is not int or value['schema_version'] not in (1, 2)
            or value['series'] != SELECTED_SIX_SERIES
            or type(value['date']) is not str or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value['date'])
            or type(value['conditions']) is not str
            or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 ,;().-]{0,299}', value['conditions'])
            or type(value['source_revision']) is not str
            or not re.fullmatch(r'[0-9a-f]{40}', value['source_revision'])
            or not token(value['evaluator']) or type(value['models']) is not list):
        raise ValueError('Invalid selected six metadata')
    date.fromisoformat(value['date'])
    seen = set()
    for m in value['models']:
        if (type(m) is not dict or set(m) != {'model', 'assigned', 'scored', 'excluded',
                'aborted', 'goal_completed', 'reliable', 'observation_count', 'provider',
                'endpoint', 'wire_model', 'reasoning', 'cost_usd'}
                or type(m['model']) is not str or m['model'] not in SELECTED_SIX_ROUTES
                or m['model'] in seen):
            raise ValueError('Invalid selected six model fields or census')
        seen.add(m['model'])
        provider, endpoint = SELECTED_SIX_ROUTES[m['model']]
        if (any(type(m[k]) is not int for k in ('assigned', 'scored', 'excluded', 'aborted',
                'goal_completed', 'reliable', 'observation_count'))
                or m['assigned'] != 44 or m['observation_count'] != 1
                or not 0 <= m['reliable'] <= m['goal_completed'] <= m['scored'] <= 44
                or m['scored'] == 0 or min(m['excluded'], m['aborted']) < 0
                or m['scored'] + m['excluded'] + m['aborted'] != 44
                or m['cost_usd'] is not None or m['wire_model'] != m['model']
                or m['provider'] != provider or not token(m['endpoint'])
                or m['endpoint'] != endpoint
                or not token(m['reasoning'])):
            raise ValueError('Invalid selected six counts, route or cost')
    if seen != set(SELECTED_SIX_ROUTES) or len(value['models']) != 6:
        raise ValueError('Selected six census drift')
    if value['schema_version'] == 2:
        validate_recovery_provenance(value)
    return value


def load_selected_six():
    path = ROOT / 'source' / SELECTED_SIX_FILE
    if not path.exists() and SELECTED_SIX_DIGEST is None:
        return None
    if not path.exists():
        raise ValueError('Approved selected six packet missing')
    return parse_selected_six(path.read_bytes(), SELECTED_SIX_DIGEST)


def selected_averages(packet):
    return [Average(m['model'], Fraction(m['reliable'], m['scored']),
                    Fraction(m['goal_completed'], m['scored'])) for m in packet['models']]


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


COST_DIGEST = '90b263298ced3f9ef23ed073c3d63814902616c39806b6bf9c86c47b7a6cd1f9'
COST_METHOD = 'arithmetic_mean_per_model'


SELECTED_COST_FILE = 'SELECTED_SIX_COSTS_20261030.json'
SELECTED_COST_DIGEST = '3a04d7ff6caf0edec3c6c71f37119b6f6bb9b1dd07b3a4ed029de47cc15683f9'


def parse_costs(data, models, digest, *, selected=False):
    if type(digest) is not str or not re.fullmatch(r'[0-9a-f]{64}', digest):
        raise ValueError('Cost source has no valid approved byte pin')
    raw = data.encode() if isinstance(data, str) else data
    if sha256(raw).hexdigest() != digest:
        raise ValueError('Approved cost bytes drift')
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
                or row['pricing_basis'] not in (('official_current_tariff_estimate',) if selected else
                    ('retained_tariff_estimate', 'river_owner_cache_scenarios'))):
            raise ValueError('Invalid or duplicate average cost model')
        seen.add(row['model'])
        for key in ('mean_cost_low_usd', 'mean_cost_high_usd'):
            if type(row[key]) is not str or not re.fullmatch(r'(?:0|[1-9][0-9]*)(?:\.[0-9]*[1-9])?', row[key]):
                raise ValueError('Cost must be a canonical nonnegative decimal string')
        if Decimal(row['mean_cost_low_usd']) > Decimal(row['mean_cost_high_usd']):
            raise ValueError('Reversed cost range')
    if (len(value['models']) != (6 if selected else 21) or seen != set(models)
            or (selected and seen != set(SELECTED_SIX_ROUTES))):
        raise ValueError('Average cost census drift')
    return value


def load_costs(models):
    path = ROOT / 'source/AVERAGE_COSTS.json'
    if not path.exists():
        raise ValueError('Pinned cost source missing')
    return parse_costs(path.read_bytes(), models, COST_DIGEST)


def load_selected_costs():
    path = ROOT / 'source' / SELECTED_COST_FILE
    if not path.exists():
        raise ValueError('Pinned selected cost source missing')
    return parse_costs(path.read_bytes(), SELECTED_SIX_ROUTES, SELECTED_COST_DIGEST, selected=True)


def combined_costs(costs):
    added = load_selected_costs()
    return dict(costs, models=costs['models'] + added['models'])


def money(row):
    """Show a single upper estimate; source JSON retains complete ranges."""
    if row is None:
        raise ValueError('Average cost required')
    high = Decimal(row['mean_cost_high_usd'])
    low = Decimal(row['mean_cost_low_usd'])
    if low == high and not row['incomplete_usage']:
        value = high.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    else:
        value = high.quantize(Decimal('.01'), rounding=ROUND_FLOOR if row['incomplete_usage'] else ROUND_CEILING)
    return f'${value:.2f}'


def render_chart(rows, costs, packet=None):
    # Goal achievement includes strict-quality cases: overlay, never add the rates.
    by_model = {r['model']: r for r in costs['models']}
    bars = []
    for rank, row in enumerate(rows, 1):
        quality = Decimal(row.quality.numerator) * 100 / row.quality.denominator
        goal = Decimal(row.goal.numerator) * 100 / row.goal.denominator
        label = '<code>' + escape(row.model) + '</code>'
        if packet:
            label = '<span>' + label + '</span>'
        bars.append('<li class="chart-row"><div class="chart-model">'
            f'<span class="chart-rank" aria-hidden="true">{rank:02d}</span>'
            + label + '</div>'
            '<span class="bar" aria-hidden="true"><svg viewBox="0 0 100 16" preserveAspectRatio="none">'
            f'<rect class="goal-fill" width="{goal:.10f}" height="16"/>'
            f'<rect class="quality-fill" width="{quality:.10f}" height="16"/>'
            f'<line class="goal-marker" x1="{goal:.10f}" x2="{goal:.10f}" y1="0" y2="16" '
            'vector-effect="non-scaling-stroke"/></svg></span>'
            '<span class="chart-stat quality-stat"><span class="metric-label">Strict quality</span>'
            '<strong>' + percent(row.quality) + '</strong></span>'
            '<span class="chart-stat goal-stat"><span class="metric-label">Tasks solved</span>'
            '<strong>' + percent(row.goal) + '</strong></span>'
            '<span class="chart-stat chart-cost"><span class="metric-label">Est. run cost</span>'
            '<strong>' + escape(money(by_model[row.model])) + '</strong></span></li>')
    chart = ('<figure class="leaderboard" aria-labelledby="chart-title" aria-describedby="chart-note method cost-note">'
            '<figcaption id="chart-title">Quality, tasks solved &amp; cost</figcaption>'
            '<div class="chart-key"><span><i class="quality-key" aria-hidden="true"></i>Strict quality</span>'
            '<span><i class="goal-key" aria-hidden="true"></i>Tasks solved</span>'
            f'<span class="chart-sort">{len(rows)} models · sorted by quality</span></div>'
            '<p id="chart-note">Mint shows cases passing all quality checks. The blue endpoint shows tasks solved '
            '(goal achieved), including those passing all checks. Both are average percentages across two observations.</p>'
            '<div class="chart-header" aria-hidden="true"><span>Model</span>'
            '<span class="chart-axis"><span>0%</span><span>50%</span><span>100%</span></span>'
            '<span>Quality ↓</span><span>Tasks solved</span><span>Est. run cost</span></div>'
            '<ol class="chart">' + ''.join(bars) + '</ol></figure>')

    if packet:
        chart = chart.replace('Both are average percentages across two observations.',
            'Both are average percentages across one or two observations.')
    return chart


SELECTED_COST_SCOPE = ('The original 21 retain historical campaign tariffs and River owner scenarios, '
                       'including known retries. Some estimates have incomplete recorded usage. '
                       'The six additional estimates use official current API rates as of 2026-10-30; '
                       'gpt-6.1-terra covers complete recorded usage. '
                       'claude-haiku-5-5, mistral-large-4, grok-4.7, GLM-5.3, '
                       'moonshotai/Kimi-K3 cover retained recorded usage only; missing usage is excluded. '
                       'All costs are estimates, not invoices. For the original 21 only: ')


def render(rows=None):
    rows = average_rows(rows)
    costs = load_costs(r.model for r in rows)
    packet = load_selected_six()
    if packet:
        costs = combined_costs(costs)
        rows = sorted(rows + selected_averages(packet), key=average_order)
    note = ('Known 44-case campaign estimates including known retries, not invoices. Some estimates have incomplete recorded usage. '
            + costs['assumptions'])
    template = (ROOT / 'tools/template.html').read_text()
    if packet:
        note = SELECTED_COST_SCOPE + costs['assumptions']
        template = template.replace('21 models', f'{len(rows)} models').replace('<strong>21</strong>', f'<strong>{len(rows)}</strong>')
        template = template.replace('two original per-observation rates', 'one or two original per-observation rates')
        template = template.replace('with heterogeneous settings:', 'with heterogeneous runtime/evaluator versions and provider settings:')
        template = template.replace('descriptive, not a controlled ranking.',
            'descriptive, not a controlled ranking. For the original 21, two-rate means are retained; '
            'the six additional models have one observation each. Rates are conditional on scored coverage; '
            'technical exclusions and interrupted aborts are not quality failures. '
            'Compliance 0.3.0 applies to the additional observations; historical grades remain frozen.')
        if packet['schema_version'] == 2:
            template = template.replace('Compliance 0.3.0 applies',
                'Corrected technical attempts replace only excluded or aborted original cells within the same observation; source revisions and admission registry mappings differ across original and correction attempts. Compliance 0.3.0 applies')
        template = template.replace('cost aggregates</a>,', 'cost aggregates</a> and <a href="./' + SELECTED_SIX_FILE + '">additional model aggregates</a>,')
    if packet:
        template = template.replace('additional model aggregates</a>,', 'additional model aggregates</a> and <a href="./' + SELECTED_COST_FILE + '">current cost aggregates and assumptions</a>,')
    for key, value in {'DOC': DOC, 'SHA': SHA, 'UPSTREAM': UPSTREAM,
                       'STYLE_VERSION': sha256((ROOT / 'tools/style.css').read_bytes()).hexdigest()[:12],
                       'RESULTS': render_chart(rows, costs, packet), 'COST_NOTE': escape(note)}.items():
        template = template.replace('{{' + key + '}}', value)
    return template


def aggregate_data(rows, costs, packet=None):
    by_model = {r['model']: r for r in costs['models']}
    value = {'schema_version': 1,
        'method': 'Unweighted mean of two original per-observation rates; exact rational arithmetic.',
        'cost_assumptions': costs['assumptions'],
        'models': [dict(model=r.model, average_quality_percent=percent(r.quality),
            average_goal_achieved_percent=percent(r.goal),
            quality_rate={'numerator': r.quality.numerator, 'denominator': r.quality.denominator},
            goal_rate={'numerator': r.goal.numerator, 'denominator': r.goal.denominator},
            average_full_run_estimate=by_model[r.model]) for r in rows]}
    if packet:
        value['cost_assumptions'] = SELECTED_COST_SCOPE + costs['assumptions']
        value['method'] = 'Unweighted mean of one or two original per-observation rates; exact rational arithmetic.'
        if packet['schema_version'] == 2:
            value['method'] = ('Unweighted mean of one or two per-observation rates; '
                'technical corrections replace original technical cells; exact rational arithmetic.')
        value['selected_six_cost_provenance'] = dict(packet=SELECTED_COST_FILE, sha256=SELECTED_COST_DIGEST)
        value['selected_six_provenance'] = dict(packet=SELECTED_SIX_FILE, sha256=SELECTED_SIX_DIGEST,
            **{k: v for k, v in packet.items() if k != 'models'})
        for row in value['models']:
            row['observation_count'] = 1 if row['model'] in SELECTED_SIX_ROUTES else 2
    return (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode()


def outputs():
    rows = average_rows()
    costs = load_costs(r.model for r in rows)
    packet = load_selected_six()
    if packet:
        costs = combined_costs(costs)
        rows = sorted(rows + selected_averages(packet), key=average_order)
    files = {'index.html': render().encode(),
            'MODEL_AVERAGES.json': aggregate_data(rows, costs, packet),
            'REPEAT_20261024.json': (ROOT / 'source/REPEAT_20261024.json').read_bytes(),
            'GEMINI_AGGREGATES.json': (ROOT / 'source/GEMINI_AGGREGATES.json').read_bytes(),
            'favicon.svg': (ROOT / 'tools/favicon.svg').read_bytes(),
            'style.css': (ROOT / 'tools/style.css').read_bytes(),
            'MODEL_RESULTS.md': (ROOT / 'source/MODEL_RESULTS.md').read_bytes(),
            'LICENSE-DATA': (ROOT / 'LICENSE-DATA').read_bytes(),
            '.nojekyll': b'',
            'AVERAGE_COSTS.json': (ROOT / 'source/AVERAGE_COSTS.json').read_bytes()}

    if packet:
        raw = (ROOT / 'source' / SELECTED_SIX_FILE).read_bytes()
        parse_selected_six(raw, SELECTED_SIX_DIGEST)
        files[SELECTED_SIX_FILE] = raw
        cost_raw = (ROOT / 'source' / SELECTED_COST_FILE).read_bytes()
        parse_costs(cost_raw, SELECTED_SIX_ROUTES, SELECTED_COST_DIGEST, selected=True)
        files[SELECTED_COST_FILE] = cost_raw
    return files


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
        print(f'OK: pinned sources, model averages and generated site match ({len(json.loads(files["MODEL_AVERAGES.json"])["models"])} models).')
    else:
        site.mkdir(exist_ok=True)
        for name, data in files.items():
            (site / name).write_bytes(data)
        print(f'Built site/ with {len(json.loads(files["MODEL_AVERAGES.json"])["models"])} model averages.')

if __name__ == '__main__':
    main()
