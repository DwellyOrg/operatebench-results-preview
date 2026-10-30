# OperateBench model averages

A static, offline results preview for 27 exact model IDs. Each leaderboard row combines average strict quality, average tasks solved (goal achievement), and the average full-run cost estimate. A single horizontal bar overlays strict quality in mint and goal achievement in blue on a common 0–100% scale. Goal achievement includes strict-quality cases; the rates are not added. Exact percentages and one USD estimate appear alongside each bar, with no separate results table.

Each metric is the unweighted arithmetic mean of one or two original per-observation rates, calculated with exact rational arithmetic. It is not a pooled rate. Rows sort by exact mean quality descending, exact mean goal achievement descending, case-insensitive model ID ascending, then exact model ID ascending. Display percentages round to one decimal place. The original 21 models retain their two-rate means; the six additional models have one observation each. Heterogeneous runtime/evaluator versions and provider settings make these descriptive observations, not a controlled ranking.

The [pinned observation study](https://github.com/DwellyOrg/OperateBench/blob/3672fdeb6153e6677f5d36d6e6628f50f2efb1d5/docs/studies/2026-10-observations.md) explains the original grades and known correction. Original snapshots and reported grades remain unchanged. The new downloadable `MODEL_AVERAGES.json` contains model averages, observation counts, aggregate assumptions and selected-six provenance; legacy data endpoints remain available for compatibility.

The six additional estimates use official current API tariffs checked on 2026-10-30 and retained usage, including technical-correction attempts. Five are incomplete recorded-usage-only estimates; missing usage and reservation bounds are not charges. See `SELECTED_SIX_COSTS_20261030.json` for assumptions and official sources. Original 21 prices retain historical campaign tariffs and River owner scenarios; all costs are estimates, not invoices. Their rates are conditional on scored coverage, with technical exclusions and interrupted aborts excluded from quality denominators. Compliance 0.3.0 applies to the new observations; historical grades remain frozen. This is not an official release or independent human validation.

For the original 21 only, cost estimates cover full 44-case campaigns including known retries, not invoices. The chart displays a single upper estimate without range or lower-bound symbols; uncertainty and incomplete usage remain documented in the source JSON and cost note. Missing or changed pinned costs stop the build. Cache scenarios describe estimates, not actual bill bounds. Approved cost aggregates must pass a strict schema, exact model census, duplicate checks and a byte pin before use. Displayed upper estimates round up to cents for complete ranges, down for incomplete usage, and half-up for complete single amounts.

## Local validation

Python 3.11+ and the standard library are sufficient. No dependencies, JavaScript, external fonts or network calls are needed.

```sh
python -m unittest discover -s tests -v
PYTHONPATH=.:tests python tests/test_build.py
PYTHONPATH=.:tests python tests/test_repeat.py
PYTHONPATH=.:tests python tests/test_averages.py
PYTHONPATH=. python tests/test_workflow.py
python tools/build.py
python tools/build.py --check
```

The builder validates original denominators, dispositions, arithmetic, source pins and the full model census internally. Tests cover independently expected means, exact ordering, escaping, unified chart metrics and costs, source drift, cost semantics and the publication gate. `--check` rejects modified, missing or extra generated files. The existing workflow publishes only from main with explicit repository approval; this refresh does not change that gate.

## Attribution and licenses

Original OperateBench results are owned by Prospire Technologies Ltd. The pinned public table provides 19 historical rows; two Gemini rows are owner-authorized sanitized aggregates. Gemini audit evidence is owner-held/non-public. Approved repeat aggregates provide the second observation for the original 21 models. The exact approved `SELECTED_SIX_20261029.json` provides one observation for each of six additional models, for 27 models total. These results and site content are **CC BY 4.0**, with the actual license text in [LICENSE-DATA](LICENSE-DATA). Site code is **Apache-2.0**; see [LICENSE](LICENSE) and [NOTICE](NOTICE). No independent authorship of the source results is claimed.

[Public project](https://github.com/DwellyOrg/OperateBench/tree/963c6b265c71a632d9b333b01e0edcb21685d9e3)
