# Getting Started

## 1. Choose the Reproduction Level

| Level | Purpose | Does it rerun the full study? |
| --- | --- | --- |
| Integrity | Verify public file hashes, published scientific lineage and checkpoint boundaries | No |
| Regression | Execute current unit/integration tests, including bounded native checks | No |
| Saved-channel audit | Recheck 18 compiled channels and 108 saved schedules | No |
| Fresh experiments | Generate new primary, native/application, overlay or transport results | Yes, for the selected family |

Do not confuse a successful integrity check with a new scientific replication.
Wall-clock runtime is host-dependent and is not simulated task latency.

## 2. Install

Use Python 3.12 in a new virtual environment. Run commands from the repository root.

```bash
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# PowerShell alternative:
# .venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
git clone --branch v1.3.0 https://github.com/sequence-toolbox/SeQUeNCe.git SeQUeNCe
git -C SeQUeNCe checkout --detach 88f92cca8aaa6dbf82bccc6a759465120afbdd34
python -m pip check
```

The original environment lock is `requirements-lock-windows-py312.txt`.
It records an observed Windows resolution, not a guarantee of cross-platform
installation. The project metadata pins the scientific quantum packages; the
remaining declared ranges support a fresh installation. Record your actual
dependency versions when reporting a replication.

If upstream SeQUeNCe is outside this repository, set `DEQUINT_SEQUENCE_ROOT` to its
absolute checkout path. Native reference checks verify the pinned ancestor and
the inspected upstream/installed module contents; they do not trust the directory
name alone. Never substitute an unrelated SeQUeNCe release without documenting it.

## 3. Verify the Supplied Snapshot

```bash
python tools/verify_public_release.py
python -B -m pytest tests -p no:cacheprovider
python tools/verify_public_release.py --scientific
python -B -m pytest tests_public -p no:cacheprovider
```

The snapshot command verifies published hashes and source/data lineage, including
explicit mappings for privacy-redacted environment paths. It does not silently
replace original freeze hashes. The historical freeze's original byte-identity
check is not the public-copy verifier when one of its metadata files was redacted.
Read `PUBLICATION_PROVENANCE.json` for the exact original/public identities.

The full pre-publication canonical regression receipt records 292 passing tests
in `results/revision_full_tests.xml`. A current clone's execution is a separate
check; compare the reported counts, not only the old XML file.

## 4. Run a Small, Fresh Primary Study

Keep every supplied result folder immutable. Choose a new output directory.

```bash
python -m dequint.experiments --output scratch/primary_smoke --seeds 1 --requests 4
python -m dequint.analyze scratch/primary_smoke
```

The smoke study exercises the pipeline; it is not the ten-seed paper study and
must not be substituted into a reported table. See the CLI `--help` and the
[primary protocol](EXPERIMENT_PROTOCOL.md) for the complete design.

Exact primitive and native references can also use fresh output directories:

```bash
python -c "from dequint.quantum_validation import run_validation; run_validation('scratch/quantum_checks')"
python -c "from dequint.native_reference import run_native_reference; run_native_reference('scratch/native_reference')"
```

## 5. Reproduce a Full Evidence Family

| Family | Runner | Protocol |
| --- | --- | --- |
| Primary | `python -m dequint.experiments --output scratch/primary_full --seeds 10 --requests 48` | `docs/EXPERIMENT_PROTOCOL.md` |
| Native/application | `python -m dequint.followup --output scratch/followup` | `docs/FOLLOWUP_PROTOCOL.md` |
| Quantum overlay | `python tools/run_shortcut_investigation.py` in a separate reproduction directory | `docs/SHORTCUT_EXTENSION_PROTOCOL.md` |
| Compiled depth | `python tools/run_compiled_depth.py --run-name fresh_replication` | `docs/COMPILED_DEPTH_PROTOCOL.md` |
| Matched transport | `freeze`, `run`, `analyze`, `verify` subcommands of `tools/run_review_supplement.py` in a separate reproduction directory | `docs/REVIEW_SUPPLEMENT_PROTOCOL.md` |

The overlay runner deliberately refuses an existing `results/shortcut_v1`.
The transport runner likewise refuses an existing freeze. For either, copy
`src`, `tests`, `tools`, `docs`, `pyproject.toml` and the dependency lock to a new
empty reproduction directory; install the addon there, retain the upstream
checkout path via `DEQUINT_SEQUENCE_ROOT`, and execute its frozen protocol.
Do not delete supplied results to make a runner proceed.

For the overlay runner, also create an empty `manuscript_existing_patch`
directory in that reproduction workspace (`mkdir manuscript_existing_patch`).
Its final reporting step writes `shortcut_results.tex` there; no private paper
or Wiley template is needed. The saved original audit scripts remain unchanged
historical tools. Use the public `--scientific` verifier for their redacted saved
evidence; it performs no writes to frozen records.

Fresh transport commands in that empty reproduction directory:

```bash
python tools/run_review_supplement.py freeze
python tools/run_review_supplement.py run
python tools/run_review_supplement.py analyze
python tools/run_review_supplement.py verify
```

## Troubleshooting

- **Cannot locate SeQUeNCe checkout:** clone the pinned source or set
  `DEQUINT_SEQUENCE_ROOT`; installing the wheel alone is not enough for provenance checks.
- **Frozen source/protocol drift:** do not rewrite the manifest to conceal it.
  Restore the matching inputs or record a new experiment/version in a new directory.
- **Output already exists:** choose a new directory or reproduction workspace.
- **Old manuscript/report builder needs absent files:** paper/reviewer/private-archive
  tooling is retained for historical traceability where safe, not as the public
  experiment entry point. Confidential inputs are intentionally absent.
- **Different package or OS:** report the difference. An old passing XML receipt
  does not certify your current environment.
