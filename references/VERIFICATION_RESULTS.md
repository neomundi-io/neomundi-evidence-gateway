<sub>🇬🇧 <b>English</b> · 🇫🇷 <a href="VERIFICATION_RESULTS.fr.md">Français</a> · <a href="../README.md">← README</a></sub>

# Verification results and traceability digests

What was measured, when, against which revision, and with which digest.
Everything on this page is a **recorded measurement**, not a claim about
quality. Read [`LIMITS.md`](LIMITS.md) before quoting any of it.

**Reference date: 2026-11-14.**

---

## The revisions these figures belong to

| Component | Revision | Note |
|---|---|---|
| Evidence engine | **`3391c768f55b08590624aa1c24fe65fdb6420191`** | `main` at the time of measurement; merge commit of engine PR #39 |
| engine tree | `75fd66b4df098b60b4a08f1e52a8b92aefacc1df` | — |
| engine freeze tag | **`v1.0.0-rc1`** → `ee36e9470ee17117b6794ad886021c33355b1ca0` | the only tag; **no GitHub release exists** |
| conformance corpus | **1.3.0** | 50 cases, 7 families, 121 fixture files |
| this gateway | **`2573760b2f153a48ce74e7250dd3598908aabf50`** | tree `1aa54e9ba3dbdb8efedcb524ab514c8c0634c091` |

A revision identifier is a declaration until it is checked against bytes. The
digests below are what makes these rows checkable.

## Digests — the traceability anchors

| Artifact | sha256 | Accessible here? |
|---|---|---|
| **trust store** (3038 bytes) | `dac94e8ad4baf0a48fe94b8006a238d970d242cdc52b8d9dd51294777751598d` | 🟢 **yes** — [`../trust/trust-store.json`](../trust/trust-store.json) |
| conformance corpus `SHA256SUMS` (21 202 bytes, 172 lines) | `e3edeb26c54363ace46737563f4824f79a0adab2baebcb8351bb15d632a6a297` | 🟢 **yes** — [`../verifier/conformance/SHA256SUMS`](../verifier/conformance/SHA256SUMS) |
| conformance corpus `manifest.json` | `2720995161e6b98ee707c72ba3000a5029d8e49a07f1e80de3cf6da82fdd5ec2` | 🟢 **yes** — and the 172 entries it covers |
| V1 demonstration archive (the one `demo/demo.sh` uses) | `e31e12bb7e32c7a33db1ecacc8c38cd18225fa10618c7e1aa5d6f9540f2ad7d6` | 🔴 no — it lives in the private engine. Use a corpus fixture instead: see [`../verifier/README.md`](../verifier/README.md) |

🟢 **Three of the four artifacts above are now reachable here.** On
14 November the trust store was the only one; publishing the verification
surface brought the corpus with it. A digest with no reachable artifact is an
anchor, not a proof — so the table keeps saying, row by row, which is which.

The one remaining `🔴` is the demonstration dossier used by `demo/demo.sh`.
Its digest is recorded; the archive itself stays private. A third party
reproducing the five scenarios should point `--artifact-root` at a corpus
fixture.

## Engine measurements, as recorded on `3391c768`

| Measurement | Result |
|---|---|
| engine CI on `main` | **11 check-runs, 11 success** |
| suites declared in CI | **29** `test_*.py` files, **28 invoked** — the only one not invoked is `test_timestamp_network.py`, excluded on purpose (network). Measured against the workflow, comment lines discounted |
| conformance corpus, Python verifier | **40 PASS, 10 AMBIGUOUS, 0 FAIL**, and **0 exit-code deviation on a concordant verdict** |
| `sha256sum --check SHA256SUMS` on the corpus | **OK** |
| named falsification suite | **10/10 detected**, 1 declared limit |
| attestation suite | 24/24, including a forged `alg` (`none` / `HS256` / `RS256`) → **3/3 refused** |
| archive falsification | 10/10 · external link | 18 controls |
| published schemas | **10** files in `schemas/`, **10** valid draft-2020-12, **10** closed (`additionalProperties: false`) — measured |

⚠ **The 10 AMBIGUOUS are not failures and not successes.** They are cases
where the contract does not decide, and on three of them the two reference
implementations are **measured as disagreeing**. The corpus names them rather
than papering over them. A count of PASS is not probative on its own.

## Gateway measurements, as recorded on `2573760b`

| Measurement | With the engine | Without the engine |
|---|---|---|
| `tests/test_gateway.py` | **26 PASS, 0 FAIL, 0 NOT TESTED** | 17 PASS, 0 FAIL, **1 NOT TESTED** |
| `tests/test_no_verification_logic.py` | **7 PASS, 0 FAIL, 0 NOT TESTED** | 6 PASS, 0 FAIL, **1 NOT TESTED** |
| `demo/demo.sh` | 5 scenarios, **5 observed exit codes = 5 expected** | 2 scenarios, 2 = 2 |
| gateway CI on `main` | **4 check-runs, 4 success** | — |

The `NOT TESTED` lines are the cases that need an engine. They are reported
as not tested, never as passed.

### Clean room — 2026-11-14, no access to the private repository

The published verification surface was copied into an empty directory, with
no `.git`, no remote and no credential, and exercised there:

| Test | Observed |
|---|---|
| public tools install and answer `--help` | `verify.py`, `verify_attestation.py`, `adapters/ingest.py` — **3/3 OK** |
| `sha256sum --check SHA256SUMS` | **172 / 172 OK** |
| corpus, Python verifier | **40 PASS, 10 AMBIGUOUS, 0 FAIL** |
| corpus, `evidence-verify-rs` (built there, offline, **65 unit tests pass**) | 27 PASS, 8 AMBIGUOUS, 15 n/a |
| corpus, `evidence-verify-crypto` (built there) | 13 PASS, 2 AMBIGUOUS, 35 n/a |
| **all three together** | **80 PASS, 20 AMBIGUOUS, 50 n/a — 0 exit-code deviation on a concordant verdict** |
| valid artefact (`A-05`) | 17 PASS, 0 FAIL, 4 NOT TESTED — code **0** |
| tampered artefact (`D-10`) | 16 PASS, **1 FAIL**, 4 NOT TESTED — code **1** |
| unverifiable (`A-07`, no trust store) | code **0**; with `--strict`, code **2**, two required guarantees named |
| control lines with and without `--strict` | **byte-identical** |
| the gateway driven against the **public verifier** instead of the engine | five scenarios, codes **0 / 1 / 2 / 4 / 3** |

Rust toolchain used: `rustc 1.99.1`, `cargo 1.99.1` — the versions the engine
CI uses. Binaries built in the clean room:
`evidence-verify-rs` `6b0e56df…`, `evidence-verify-crypto` `eb1d22de…`.
⚠ Those two digests are **not** a reproducibility claim: a release binary
depends on the toolchain and the host, and nothing here pins either.

### The five scenarios, and the code each returns

| # | Scenario | Status | Exit | Engine verdict |
|---|---|---|---|---|
| 1 | valid artifact, corpus supplied, strict | `completed` | **0** | `no_failure` — 19 PASS / 0 FAIL / 3 NOT TESTED |
| 2 | tampered artifact (one member rewritten) | `completed` | **1** | `fail` — 16 PASS / **1 FAIL** / 4 NOT TESTED |
| 3 | unverifiable artifact (no corpus, strict) | `completed` | **2** | required guarantee named: replayed-input digests |
| 4 | input or schema error | `rejected` | **4** | none — **no verification took place** |
| 5 | engine unavailable | `engine_unavailable` | **3** | none — **no verification took place** |

### The measurement that matters most

`tests/test_no_verification_logic.py`, test **C**: the verdict the gateway
republishes is confronted, field by field, with a **direct** engine call on
the same artifact.

> **22 control lines identical** (states and labels, same order), `counts`
> identical, `required_not_demonstrated` identical, **same exit code**.

That is what substantiates "the gateway duplicates no verification logic".
Not the README saying so.

### Reproducibility, measured — and its limit

Two consecutive runs of the demonstration: **verdicts and exit codes
identical**, and **4 of the 5 responses byte-identical**.

⚠ The fifth is not. Scenario 2 rebuilds the tampered archive on every run; a
ZIP carries its members' timestamps, so its `sha256` changes (`f16a0844…`
then `0df147d7…`). **Verdict and counts are identical** (`fail`, 16/1/4).
Compare verdicts, never the digest of a rebuilt archive.

## What is *not* on this page

- no result produced by a third party on their own infrastructure. Every
  figure above was measured by NeoMundi, on NeoMundi machines or in NeoMundi
  CI. The reviewer observations recorded in [`REVIEWS.md`](REVIEWS.md) were
  **reproduced** by NeoMundi — reproduction is not independence;
- no claim that `external-link/1` has ever been exercised outside NeoMundi.
  It has not;
- no figure from the private Q-1 / Q-2 dossiers, which are not published.
