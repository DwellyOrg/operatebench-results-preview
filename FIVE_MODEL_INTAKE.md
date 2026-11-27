# Five-model intake

Hydrogen, Neon, Ember, Ripple and Kimi K3.1 Pro are active with approved packet bytes and pins. The five
independent file and pin entries in `tools/build.py` are:

| Exact model ID | File under `source/` |
| --- | --- |
| `gemini-4-hydrogen` | `GEMINI_4_HYDROGEN.json` |
| `gemini-4-neon` | `GEMINI_4_NEON.json` |
| `muse-ember-1.0` | `MUSE_EMBER_1_0.json` |
| `ricursiveAI/Ripple-65B-Preview-NVFP4` | `RICURSIVEAI_RIPPLE_65B_PREVIEW_NVFP4.json` |
| `moonshotai/Kimi-K3.1-Pro` | `MOONSHOTAI_KIMI_K3_1_PRO.json` |

Each packet uses the same closed one-observation schema as
[the OpenAI 6.2 intake](OPENAI62_INTAKE.md). The exact keys, types, coverage,
cost, revision and date rules described there apply, with these differences:
`model` must equal its exact ID above; `provider`, `endpoint`, and `reasoning`
are the actual run's nonempty route/setting identifiers, each 1–80 ASCII
letters, digits, periods, underscores or hyphens, starting with a letter or
digit. The decoder does not establish their truth. `cost_assumptions` must
accurately describe the approved usage estimate and its limitations for that
model; it must meet the existing sanitized prose restrictions. The source
revision is the actual evaluated **public** OperateBench code identity, not a
private campaign identifier. One `observation-1` covers the same 44 cases.
An optional `additional_source_revisions` root field records other public
OperateBench commits used for actual technical attempts, including failed
integration attempts when applicable. If present it is a nonempty list of
unique 40-character lowercase hexadecimal commit IDs, each different from
`source_revision`. The primary revision identifies the primary actual evaluated
code; additional revisions identify technical attempts, not a claim that every
case ran on the latest code. Omit the field for a single-source observation.
The parent establishes the actual revisions, shared core, instructions,
evaluator and cases, and approves the public provenance. The cost assumptions
must cover all known technical attempts and disclose usage limitations.
The visible provenance links every source, and JSON `source_urls` lists the
primary followed by the additional fixed public repository links.
The decoder does not establish the accuracy of results, provenance, approval,
or public suitability of prose: parent review must establish these.

When parent has sanitized replay and usage-approved packets and exact SHA256
byte hashes, place each approved byte-for-byte JSON file in `source/` and set
its `FIVE_DIGESTS` entry to the supplied 64-character lowercase hash. Update
the corresponding entry in the explicit mapping for individual pins.
Each missing file with a `None` pin is omitted; a present unpinned file or a
missing pinned file fails the build. A subset can be admitted independently;
all five accepted alongside the original 32 give 37. The builder checks
bytes and schema on load and again before copying packet bytes to the site.
Do not use synthetic tests as result data. Update any census and descriptive
materials only after actual data and publication are approved.

For a local check, from the site root, use the project's existing Python with
`PYTHONPATH=.:tests` for `python -m unittest discover -s tests` and
`PYTHONPATH=.` for `python tools/build.py` followed by
`python tools/build.py --check`. Review the exact generated files, accessible
per-model packet links, provenance, cost assumptions and historical row parity.
Parent owns any further publication, CI, merge and live verification.

## Nemotron addition

The separate Nemotron packet uses `source_variant: provider-adapter-overlay-on-public-base`. Its `source_revision` identifies the public base, not the exact executing adapter tree. Route is River Chat Completions with reasoning requested off. The same coverage and pinned-byte checks apply.

The [Nemotron packet](source/NVIDIA_NEMOTRON_3_5_SUPER_VL_120B_A12B_NVFP4.json) records 44/44 scored cases, strict quality 0/44 and goal achievement 5/44. The estimate is USD 1.26171867 (complete recorded token usage), not an invoice. This run used a separate HTTP provider adapter overlay on the linked public base; the link is not the exact executing tree.
