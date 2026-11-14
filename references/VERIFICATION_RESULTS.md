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
| conformance corpus `SHA256SUMS` (21 202 bytes, 172 lines) | `e3edeb26c54363ace46737563f4824f79a0adab2baebcb8351bb15d632a6a297` | 🔴 no — digest recorded, artifact in the engine repository |
| conformance corpus `manifest.json` | `2720995161e6b98ee707c72ba3000a5029d8e49a07f1e80de3cf6da82fdd5ec2` | 🔴 no — same |
| V1 demonstration archive (the one the five scenarios use) | `e31e12bb7e32c7a33db1ecacc8c38cd18225fa10618c7e1aa5d6f9540f2ad7d6` | 🔴 no — in the engine repository |

🔴 **A digest with no reachable artifact is an anchor, not a proof.** Three of
the four rows above are exactly that, and the table says so rather than
implying otherwise. The trust store was moved here precisely so that it would
not be one of them.

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

The `NOT TESTED` lines are the cases that need the engine. They are reported
as not tested, never as passed.

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
