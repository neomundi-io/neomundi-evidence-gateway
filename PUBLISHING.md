# Publishing `neomundi-evidence-verify` to PyPI

The package is **built and tested. It is NOT published**, and must not be
until the point below is settled.

---

## 🔴 The blocking point: publishing to PyPI is redistribution

`pip install` copies the files onto the user's machine, and PyPI distributes
them to anyone. That is **redistribution** in the ordinary sense, and it is
exactly what the current rights position forbids:

| Where | What it says |
|---|---|
| engine `LICENSE` §3 | *"Without the prior written authorisation of the Rights Holder, no person may copy, reproduce, publish, distribute […] the Work […] in whole or in part, in source or in compiled form"* |
| this repository's README | *"No reuse licence is granted by this repository; rights are reserved"* |
| `verifier/README.md` | *"published for verification and review"* |

**You cannot offer `pip install` while reserving all rights.** The two
statements contradict each other, and a user who runs the install command is
entitled to assume the first one.

So this is a **decision for the rights holder (Sébastien Favre)**, not a
packaging detail. Three coherent ways out:

| Option | What it means | Consequence |
|---|---|---|
| **A — grant a licence to the verifier package** | e.g. Apache-2.0, as the two Rust verifiers and the `neomundi` measurement SDK already carry | `pip install` becomes coherent. Consistent with the gateway's own argument: an independent verifier nobody may reuse is a weaker artefact |
| **B — grant a narrow licence** | "use and redistribute unmodified, for verification purposes" | allows PyPI while reserving derivative works. Non-standard, so OSI tooling and corporate reviewers will flag it |
| **C — do not publish** | distribute from the git clone only (`pip install .`) | the Quick Start still works. But `pip install neomundi-evidence-verify` stays impossible, and the reservation still sits awkwardly with inviting people to run the tools |

⚠ Whatever is chosen, it applies **forward only**. The Apache-2.0 declaration
already carried by the two Rust crates is untouched — see engine `LICENSE`
§6, and §6.3 on why correcting the rights holder changed nothing there.

**No other blocking point was found.** The name is free, the dependencies are
permissive and optional, and the tests pass from a clean environment.

## The name — free, and to be confirmed

Measured on PyPI on 2026-11-14:

| Name | Status |
|---|---|
| **`neomundi-evidence-verify`** | **404 — free** ← proposed, used by this package |
| `neomundi-evidence` | 404 — free (worth reserving to avoid confusion) |
| `neomundi-evidence-verifier` | 404 — free |
| `evidence-verify` | **200 — TAKEN by a third party.** Never use the bare name |
| `neomundi` | **200 — ours**, the measurement SDK, 2.0.0, Apache-2.0. **Not to be touched** |

The import package is `neomundi_evidence`, which does **not** collide with
the `neomundi` SDK: it is a separate top-level name, not a submodule. The
console script is `neomundi-evidence`; the installed SDK declares no console
script, so there is no collision there either (measured).

> Both names are **proposals**. Confirm them before the first upload: a PyPI
> name cannot be reused once released, even after deletion.

## Licences and dependencies — measured

| | |
|---|---|
| mandatory dependencies | **none**. All four operations run on the standard library alone |
| `attestations` extra | `cryptography>=42` — Apache-2.0 OR BSD-3-Clause |
| `timestamps` extra | `opentimestamps>=0.4` — LGPL-3.0; pulls `python-bitcoinlib` (LGPL-3.0) and `pycryptodomex` (BSD-2-Clause / public domain) |
| redistributed by this package | **nothing third-party.** Extras are fetched from PyPI by pip, not vendored |

⚠ **`opentimestamps` is LGPL-3.0.** It is an *optional, separately installed*
dependency, never bundled, so no copyleft obligation attaches to this
package. Keep it that way: **never vendor it**.

## What is in the artefacts — verified

```
wheel : 15 entries, 318 KB uncompressed, 101 KB on disk
        neomundi_evidence/{__init__,cli}.py
        neomundi_evidence/_verifier/{verify,verify_attestation,canonical,i18n,timestamp}.py
        neomundi_evidence/_verifier/adapters/ingest.py
        + dist-info (METADATA, licence, entry point)
sdist : the same, plus verifier/*.py at their original path, so that a wheel
        built from the sdist materialises identically
```

**No duplication in the repository.** The verifiers live once, in
`verifier/`. `setup.py` materialises them into the wheel at build time, and
`neomundi_evidence/_verifier/` is git-ignored. `tests/test_paquet_pip.py`
epreuve A fails if a copy is ever committed.

**No private file.** Epreuve E refuses a wheel containing `gateway.py`,
`engine.py`, the conformance corpus, the Rust verifiers, `spec/`, the trust
store or `references/`.

## Test results — 2026-11-14

Clean `venv`, Python 3.12.10, wheel installed **offline** with no extras:

| Test | Observed |
|---|---|
| `pip install` of the wheel, no network | OK, 0 dependency pulled |
| `neomundi-evidence --version` | `0.1.0 (protocole 1.0.0-rc.1, corpus 1.3.0)` |
| `doctor` with no extras | 4/4 tools present, both absences named with their cost |
| valid archive | code **0** |
| tampered archive | code **1**, the failing member named |
| strict without replayed inputs | code **2** |
| missing file | code **4**, *"AUCUNE verification n a eu lieu"* |
| attestation without `cryptography` | `NOT TESTED` on signature and trust — never `PASS` |
| `tests/test_paquet_pip.py` | **11 PASS, 0 FAIL, 0 NOT TESTED** |
| CLI output vs a **direct** call | **22 control lines identical, same exit code** |
| Quick Start reproduced from `pip install .` | the four steps return 0 / 0 / 1 / 0 as documented |

## OpenTimestamps — status

A **real confirmed proof** was exercised:
`verifier/examples/timestamp/…confirmed.ots` carries **2 Bitcoin
attestations, blocks 974714 and 974715**, alongside 4 PENDING ones.

| State | Reported | code | `--strict` |
|---|---|---|---|
| confirmed (Bitcoin present) | `PASS` with block numbers | 0 | **0** |
| pending only | `NOT TESTED` — *attests no date* | 0 | **2** |
| binding refuted | **`FAIL`** | **1** | 1 |
| `opentimestamps` absent | `NOT TESTED`, state unknown; binding still checked | 0 | 2 |
| subject file missing | bad usage | **4** | 4 |

🔴 `PENDING` is never reported as confirmed, and **no eIDAS qualification is
claimed** anywhere. Even on a confirmed proof, *time verified by a third
party* stays `NOT TESTED`: that needs a block header, and is delegated to
`ots verify`.

⚠ The CLI exposes **only** the `verify` subcommand of the timestamping tool.
`stamp` and `upgrade`, which submit a digest to public calendars, are **not
exposed**: this package verifies, it does not produce.

## The procedure, once the licence is settled

Do **not** run these before an explicit GO.

```sh
# 0. the licence decision is recorded, and LICENSE-PACKAGE.txt reflects it
# 1. confirm the name one last time (a released name is permanent)
curl -s -o /dev/null -w '%{http_code}\n' https://pypi.org/pypi/neomundi-evidence-verify/json   # 404 expected

# 2. bump the version if needed, then build clean
rm -rf build dist neomundi_evidence/_verifier *.egg-info
python -m build

# 3. check the artefacts before uploading
python -m pip install --quiet twine
python -m twine check dist/*
python tests/test_paquet_pip.py          # 11 PASS expected

# 4. TestPyPI first, and install from it in a clean venv
python -m twine upload --repository testpypi dist/*
python -m venv /tmp/t && /tmp/t/bin/pip install \
  --index-url https://test.pypi.org/simple/ neomundi-evidence-verify
/tmp/t/bin/neomundi-evidence doctor

# 5. only then, the real index
python -m twine upload dist/*
```

Use a **project-scoped API token**, never an account-wide one, and prefer
PyPI Trusted Publishing from a dedicated workflow over a long-lived token.

## After publication

- tag the repository with the published version;
- state the version in `verifier/README.md` next to the four commands;
- `neomundi-evidence` is a stable entry point: changing a flag's meaning or
  an exit code is a **breaking change** and takes a major version. The five
  exit codes are part of the contract, not an implementation detail.
