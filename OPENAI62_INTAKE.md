# Approved same44 intake

The approved one-observation packets are active at `source/GPT_6_2_ASTRA.json`
and `source/GPT_6_2_SOL.json`, with exact SHA256 pins in
[tools/build.py](tools/build.py). The builder validates each packet on load and
again before exporting its unchanged bytes. Both files are required by the
production pins. A controlled configuration may omit an individual file only
when its corresponding pin is `None`; a missing pinned file or an unpinned
present file is rejected. The two models each scored the
existing 44 cases. The actual [evaluated source version](https://github.com/DwellyOrg/OperateBench/tree/89bb9f6342c5f23c1fd031b84f56d805195dbe28)
is linked from the preview and machine provenance. The added data are owned by
Prospire Technologies Ltd and licensed CC BY 4.0; no independent human or
official benchmark validation is claimed.

The closed schema reuses `_parse_observations` through `parse_openai62`:

- Exactly these top-level keys: `schema_version` (integer 1), `model` (exact ID
  for its file), `provider` (`openai`), `endpoint` (`responses`), `reasoning` (`low`), `currency` (`USD`), `pricing_basis`
  (`official_current_tariff_estimate`), `case_set` (`same-44-cases`),
  `source_revision` (40 lowercase hexadecimal characters identifying the actual
  [OperateBench source](https://github.com/DwellyOrg/OperateBench)), `date`
  (valid ISO calendar date), `cost_assumptions` (1–2000 characters of sanitized
  prose; no slash, backslash, angle brackets or line breaks), `observations`.
- `observations` is exactly one object. Exactly these keys: `id`
  (`observation-1`), `assigned` (44), `scored` (1–44), `excluded`, `aborted`,
  `goal_completed`, `reliable` (all counts are integers, never booleans),
  `estimated_cost_low_usd`, `estimated_cost_high_usd`, `incomplete_usage`
  (boolean). Excluded and aborted are nonnegative; scored plus excluded plus
  aborted equals 44; 0 ≤ reliable ≤ goal_completed ≤ scored.
- Both cost bounds are canonical nonnegative decimal strings, low ≤ high;
  no exponent, redundant trailing fractional zeros, NaN or numeric JSON types.
  Duplicate JSON keys, extra keys, wrong types, wrong IDs and byte drift fail.

Parent approved the sanitized aggregates and their exact bytes. Astra quality
is 42/44 and goal 43/44; Sol is 43/44 for both. Each row is one observation,
not a two-observation mean. Historical means and the Fable best-of-two selection
remain unchanged.

Reported-token-usage estimates are USD 38.5159988 and USD 9.5845606,
respectively, at Standard and explicit cache-TTL rates. They include known
technical-attempt overhead of USD 1.7911276 and USD 0.4501136, respectively.
Additional fees are unknown; these are estimates, not invoices. The packets
record the cost assumptions and no raw traces, private paths or account data.
No estimate is scaled by 44/scored.

For local validation, run (set `TMPDIR` to the owner's permitted scratch area):

```sh
PYTHONPATH=.:tests python -m unittest discover -s tests
PYTHONPATH=.:tests python -m pytest -q
PYTHONPATH=. python tools/build.py
PYTHONPATH=. python tools/build.py --check
```

Update actual-data goldens and descriptive census/NOTICE only from approved
results. Legacy tests explicitly isolate the historical intake and retain their
original goldens. The enabled-intake test checks configured approved packets,
exact full-list ordering and unchanged historical objects in either state.
Qualify activation in a disposable full site copy: place temporary synthetic
packets there, set that copy's pins, generate its preview, then run its entire
unittest suite and build/check in subprocesses with PYTHONPATH pointing to the
copy. These are mechanics tests only; never publish synthetic output. Keep
historical objects, costs, Fable best-of and averaging untouched.
Review the existing preview and exact exported packet bytes, then obtain parent
publication approval through the existing workflow. This lane performs no
benchmark execution, commit, push, merge, deployment or publication.
