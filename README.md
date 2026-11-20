# OperateBench model results

A static, offline results preview for 35 exact model IDs. Each leaderboard row combines strict quality, tasks solved (goal achievement), and a full-run cost estimate. Fable 5.2 selects one whole best-quality observation of two; eleven models, including both OpenAI 6.2 models, Hydrogen, Neon and Ember, each use one observation; the remaining models use two-observation means. A single horizontal bar overlays strict quality in mint and goal achievement in blue on a common 0–100% scale. Goal achievement includes strict-quality cases; the rates are not added. Exact percentages and one USD estimate appear alongside each bar, with no separate results table.

For models other than Fable 5.2, each metric is the unweighted arithmetic mean of one or two original per-observation rates, calculated with exact rational arithmetic. It is not a pooled rate. Rows sort by exact displayed quality rate descending, exact displayed goal achievement rate descending, case-insensitive model ID ascending, then exact model ID ascending. Display percentages round to one decimal place. The original 21 models retain their two-rate means; the six earlier additional models and both OpenAI 6.2 models have one observation each. Heterogeneous runtime/evaluator versions and provider settings make these descriptive observations, not a controlled ranking.

The [pinned observation study](https://github.com/DwellyOrg/OperateBench/blob/3672fdeb6153e6677f5d36d6e6628f50f2efb1d5/docs/studies/2026-10-observations.md) explains the original grades and known correction. Original snapshots and reported grades remain unchanged. The new downloadable `MODEL_AVERAGES.json` contains model summaries (including the disclosed Fable selection), observation counts, aggregate assumptions and selected-six provenance; legacy data endpoints remain available for compatibility.

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

Original OperateBench results are owned by Prospire Technologies Ltd. The pinned public table provides 19 historical rows; two Gemini rows are owner-authorized sanitized aggregates. Gemini audit evidence is owner-held/non-public. Approved repeat aggregates provide the second observation for the original 21 models. The exact approved `SELECTED_SIX_20261029.json` provides one observation for each of six additional models, and the approved `NOVEMBER_20261105.json` supplies two Sonnet observations; `ANTHROPIC_52_20261110.json` supplies two Fable observations, and `CARBON_20261111.json` supplies two Carbon observations, and approved `GPT_6_2_ASTRA.json` and `GPT_6_2_SOL.json` supply one observation each. Approved Hydrogen, Neon and Ember packets each supply one observation, for 35 models total. These results and site content are **CC BY 4.0**, with the actual license text in [LICENSE-DATA](LICENSE-DATA). Site code is **Apache-2.0**; see [LICENSE](LICENSE) and [NOTICE](NOTICE). No independent authorship of the source results is claimed.

[Public project](https://github.com/DwellyOrg/OperateBench/tree/963c6b265c71a632d9b333b01e0edcb21685d9e3)

The approved NOVEMBER_20261105.json preserves both claude-sonnet-5-5 observations
from public source revision 213d672ddaa8ec296c6b0bbe7b9c8e01785e020e
(https://github.com/DwellyOrg/OperateBench/tree/213d672ddaa8ec296c6b0bbe7b9c8e01785e020e).
The 35 models comprise 23 two-observation means, eleven single-observation rates and one best-of-two Fable selection.
Sonnet means are strict quality 39/88, goal achievement 81/88 and USD 20.309033
per 44-case observation, using complete reported usage at official current tariffs.
Stand-alone diagnostics are excluded from row costs and quality. These are
estimates, not invoices; no independent human validation is claimed.

The approved ANTHROPIC_52_20261110.json preserves two claude-fable-5-2 observations
from evaluated source revision 1c1cc3b005eaf7928400a0b50a1583826ea381c8.
Fable selects observation-1, the best strict-quality of two whole runs: 31/44
(70.5%), goal achievement 100.0% and USD 73.005296 ($73.01) for that same run, using complete reported usage at official current tariffs.
Separate protocol and SDK canaries are excluded. Costs are estimates, not invoices.

The approved CARBON_20261111.json preserves both gemini-4-carbon observations
from evaluated public source revision 19aaf4397e4e8752d62984617a2e41f19dcc2aa2.
Carbon uses their mean: strict quality 85/88 (96.6%), goal achievement 100.0%,
and estimated USD 95.343778 ($95.34) per 44-case observation. Complete reported
usage uses official current tariffs; separate protocol and canary costs are excluded.
Costs are estimates, not invoices. Carbon uses the ordinary mean methodology.

The approved [OpenAI 6.2 Astra aggregate](source/GPT_6_2_ASTRA.json) and
[OpenAI 6.2 Sol aggregate](source/GPT_6_2_SOL.json) each describe one observation
of the existing 44 cases, evaluated with the [actual source version](https://github.com/DwellyOrg/OperateBench/tree/89bb9f6342c5f23c1fd031b84f56d805195dbe28).
Astra achieved strict quality 42/44 (95.5%) and goal 43/44 (97.7%); Sol achieved
43/44 (97.7%) for both. The respective recorded-usage estimates are USD
38.5159988 ($38.52) and USD 9.5845606 ($9.58), including known technical
attempt overhead of USD 1.7911276 and USD 0.4501136. They use Standard and
cache-TTL pricing on complete reported token usage; additional fees are unknown.
These estimates are not invoices. The results have no independent human or
official benchmark validation.

The approved `GEMINI_4_HYDROGEN.json` and `GEMINI_4_NEON.json` each record
one observation of the same 44 cases using public evaluated source revision
https://github.com/DwellyOrg/OperateBench/tree/1fdb4a470231088cb05adf3daa4fb867e228d02a.
Hydrogen achieved strict quality 10/44 and Neon 39/44; both achieved 44/44
goals. Their respective pre-tax reported-usage API cost estimates are USD
56.285823 and USD 109.913439, including all attempts; additional fees are
unknown and these are not invoices. Low thinking was requested; the served
setting is not independently attested. These results are owned by Prospire
Technologies Ltd and licensed CC BY 4.0.

The approved `MUSE_EMBER_1_0.json` records one observation of the same 44
cases, with strict quality 9/44 and goal achievement 22/44. Its primary
[public source revision](https://github.com/DwellyOrg/OperateBench/tree/1fdb4a470231088cb05adf3daa4fb867e228d02a)
and [additional technical correction revision](https://github.com/DwellyOrg/OperateBench/tree/9e7464c1924432787c8ba8582cde42aa5d058d20)
share the Core, instructions, evaluator and cases. The conditional pre-tax
reported-usage estimate is USD 1.329589588 at published Standard tariffs,
including all 45 attempts and 52 responses from a retained unscored technical
attempt. The default service tier echo does not independently attest account
billing mode; additional fees and invoice totals are unknown. The result is
owned by Prospire Technologies Ltd and licensed CC BY 4.0.
