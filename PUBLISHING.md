# Publishing `neomundi-evidence-verify` to PyPI

The package is **built, tested and licensed. It is NOT published.**

Everything on GitHub is ready. What remains is outside this repository: the
Trusted Publisher must be created on PyPI, and the `publish` workflow must be
run deliberately. Neither has been done, and neither should be done without
an explicit decision.

---

## 🟢 The licence point is settled

Publishing to PyPI is a **redistribution**, and until 14 November 2026 that
was incompatible with this repository's blanket rights-reserved statement.
**That blocker is lifted.**

Decision of the rights holder, **Sébastien Favre, 14 November 2026**: the
**public verifier is licensed under Apache-2.0**. See [`LICENSE`](LICENSE),
and [`NOTICE`](NOTICE) for the exact scope.

| | |
|---|---|
| 🟢 covered | `neomundi_evidence/` and the **six** verifier files the wheel distributes; the gateway; the two Rust crates (**confirmed**, they already declared Apache-2.0) |
| 🟡 not covered | `verifier/spec/`, `verifier/conformance/`, `verifier/examples/`, `trust/trust-store.json` — published for verification and review, rights reserved |
| 🔴 not covered | the Evidence **engine**, private and proprietary. **No file of it was modified** |

The split is coherent without touching the private repository because the
engine's own `LICENSE` §6.4 already provides for it: *"Material republished
elsewhere under a NeoMundi notice […] is governed by the notice published
with it, not by this document."* `NOTICE` is that notice.

🟡 **One question remains open**, and is named in `NOTICE` rather than
quietly decided: whether `spec/` and `conformance/` should also become
Apache-2.0, so that a third-party implementer may ship the test vectors.

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

## How publication happens: the workflow, not a laptop

Publication is performed by **GitHub Actions** with **PyPI Trusted
Publishing** (OIDC). There is **no PyPI token anywhere** — not in the
repository, not in repository secrets, not on anyone's machine. Nothing to
leak, nothing to rotate.

**Workflow name: `publish`** — `.github/workflows/publish.yml`.

It cannot fire by accident. Four independent guards:

| Guard | What it stops |
|---|---|
| `workflow_dispatch` only | no push, no tag, no merge ever triggers it |
| a typed confirmation input | the operator must type `PUBLIER` exactly; anything else aborts before the build |
| a GitHub **Environment** per index (`testpypi`, `pypi`) | lets you require a manual reviewer, and PyPI's publisher config is bound to the environment name |
| build-then-verify, in separate jobs | the publishing job needs the verifying job to have passed; the artefact is built once and reused |

What the verifying job checks before anything is uploaded:

- `python -m twine check` on both distributions;
- the **licence metadata** is `Apache-2.0` and `LICENSE` + `NOTICE` are in
  the wheel;
- the wheel contains the nine expected files and **no private file** — no
  `gateway.py`, no corpus, no Rust crate, no trust store, no `references/`;
- the six verifier files are **byte-identical** to their source;
- the wheel installs in a clean environment **offline**, with **zero**
  dependency pulled, and the CLI returns **0 / 1 / 2 / 4** on the four
  reference cases;
- `tests/test_paquet_pip.py` passes (11 PASS).

### Running it, when the GO comes

```
Actions → publish → Run workflow
  index        : testpypi      (then pypi, in a second run)
  confirmation : PUBLIER
```

Publish to **TestPyPI first**, install from it in a clean venv, and only then
run it again against `pypi`. The workflow prints the exact install command to
use for that check.

### What must be created on PyPI first — one time, by the owner

A Trusted Publisher is configured **on PyPI**, not here. Settings to enter,
for each index:

| Field | Value |
|---|---|
| PyPI Project Name | `neomundi-evidence-verify` |
| Owner | `neomundi-io` |
| Repository name | `neomundi-evidence-gateway` |
| Workflow name | `publish.yml` |
| Environment name | `pypi` — and `testpypi` for the TestPyPI publisher |

Create it at *Your projects → Publishing* (or, for a name never yet
published, *Publishing → Add a pending publisher*). TestPyPI needs its own
publisher, configured identically at `test.pypi.org`.

⚠ **The environment name must match exactly**, or OIDC will be refused.

### Before the first run

- confirm the name one last time — a released PyPI name is **permanent**,
  even after deletion:
  `curl -s -o /dev/null -w '%{http_code}\n' https://pypi.org/pypi/neomundi-evidence-verify/json`
  (**404** expected);
- create the two GitHub Environments (`testpypi`, `pypi`), and add a required
  reviewer to `pypi` if you want a second pair of eyes on the real index.

## After publication

- tag the repository with the published version;
- state the version in `verifier/README.md` next to the four commands;
- `neomundi-evidence` is a stable entry point: changing a flag's meaning or
  an exit code is a **breaking change** and takes a major version. The five
  exit codes are part of the contract, not an implementation detail.
