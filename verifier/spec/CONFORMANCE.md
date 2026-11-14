# Evidence Protocol v1 — Conformance

How to claim conformance, what a claim must declare, and what the published
tests do and do not establish.

Companion to [`SPECIFICATION.md`](SPECIFICATION.md). Machine-readable
mapping: [`traceability.json`](traceability.json). Corpus of record **1.3.0**.

---

## 1. The first rule

**Passing the conformance corpus is not conformance to this
specification.**

The corpus covers a **subset** of the obligations. The subset is published,
case by case and rule by rule, and the obligations it does **not** cover are
listed as **gaps** — never as satisfied.

**EP1-CONF-001.** An implementation **MUST NOT** state or imply that
passing the corpus establishes conformance to the specification. It **MAY**
state that it passes the corpus, **with the corpus version**.

A corpus result without a version is not a checkable statement: the corpus
moves, and `C-09` is the proof — the same case was a declared failure at
1.0.0 and a pass at 1.1.0, with the same bytes.

---

## 2. What a conformance claim MUST declare

A claim that omits any of these is not reviewable.

| # | Must declare | Example |
|---|---|---|
| 1 | **target version** of the protocol | `evidence-protocol/1`, candidate revision `1.0.0-rc.1` |
| 2 | **contracts** supported | `neomundi.evidence.submission/1`, `/2` |
| 3 | **profiles** supported | `neomundi-jcs-strings/1`; Ed25519/JWS |
| 4 | **functional perimeter** | submission only / archive only / attestation only / any combination |
| 5 | **normative rules** claimed | by identifier: `EP1-INT-002`, … |
| 6 | **corpus version** used | `1.3.0` |
| 7 | **cases executed** | by identifier, or "all applicable to the declared perimeter" |
| 8 | **cases excluded**, and why | e.g. the 15 attestation and archive cases, for a submission-only verifier |
| 9 | **known divergences** | including the rules deliberately not implemented |
| 10 | **how to reproduce** | the commands, and the platform they were run on |

**EP1-CONF-002.** A claim **MUST** name the **platform** it was measured
on. A result on one platform is not a result on another; this repository has
a measured case where the same code behaves differently on Linux and Windows
(§6).

**EP1-CONF-003.** Partial conformance is legitimate. An implementation
**MAY** claim conformance over a declared perimeter, provided the perimeter
is stated and the excluded cases are listed. A verifier that covers
submissions only is not a lesser implementation; it is a different one.

---

## 3. Perimeters, and why `NOT APPLICABLE` is not a failure

The three reference verifiers declare three different perimeters:

| Verifier | Perimeter | Applicable cases, of 50 |
|---|---|---|
| `python` (`verify.py`, `verify_attestation.py`, `adapters/ingest.py`) | submission, archive, attestation | **50** |
| `rust-core` (`evidence-verify-rs`) | **submission only** | **35** |
| `rust-crypto` (`evidence-verify-crypto`) | **archive and attestation only** | **15** |

**EP1-CONF-010.** A case outside an implementation's declared perimeter
**MUST** be reported `NOT APPLICABLE`, never `FAIL`. Reproaching a tool for
not doing what it does not claim is a false measurement — and it inflates
the denominator of whichever tool does claim it.

**EP1-CONF-011.** Any rate cited **MUST** publish its denominator: the
number of cases **applicable to the implementation concerned**, not the 50
cases of the corpus.

---

## 4. Measured state of the reference implementations

Corpus **1.3.0**, Linux x86-64, `rustc 1.99.1`, Python 3.12 (CI) /
3.14 (local):

| | `python` | `rust-core` | `rust-crypto` |
|---|---|---|---|
| applicable | 50 | 35 | 15 |
| `PASS` | **40** | **27** | **13** |
| `AMBIGUOUS` | 10 | 8 | 2 |
| `KNOWN FAIL` | **0** | 0 | 0 |
| **undeclared `FAIL`** | **0** | **0** | **0** |
| `NOT APPLICABLE` | 0 | 15 | 35 |

Together: `PASS = 80`, `AMBIGUOUS = 20`, `NOT APPLICABLE = 50`, and
**0 exit-code divergences on agreeing verdicts** — identical under
`--strict`.

**No conformance percentage is published.** 102 normative rules are stated
in this specification set; the corpus's 50 cases cite 38 distinct normative
references. A rate computed on that would read as a rate on the protocol.

---

## 5. Rule-level coverage

Generated from [`traceability.json`](traceability.json) and checked in CI by
`tests/test_specification.py`.

### 5.1 Is there a test?

| `coverage` | Rules | Meaning |
|---|---|---|
| `COVERED` | **81** | at least one corpus case or test exercises the rule |
| `PARTIAL` | **12** | exercised indirectly, or on one perimeter of several |
| `GAP` | **3** | **no test exercises it** — stated, not verified |
| `NOT TESTABLE` | **6** | a rule about how to *read* or *judge*, with no input that could falsify it |
| **total** | **102** | |

### 5.2 Do the reference implementations satisfy it?

A **different question**, deliberately recorded in a different field: a rule
can be well covered and violated, and that is exactly what must be
readable.

| `reference_implementations` | Rules |
|---|---|
| `CONFORMING` | **97** |
| `PARTIAL` | **2** |
| `GAP` | **0** |
| `UNKNOWN` | **3** |

### 5.3 The three rules with no test

Six at the previous revision. **Three were closed** by the 11 November
closure (`tests/test_obligations_sans_test.py`), and the three that remain
are **structurally** blocked, not forgotten.

| Rule | What is not verified | Why it remains |
|---|---|---|
| `EP1-CAN-003` | that a **profile** failure is not reported as a **signature** failure | would need a payload with an invalid profile **and** a valid signature — the profile lives in the payload, so any variant must be **re-signed**. No private key exists in this repository, and none will. |
| `EP1-SIG-023` | `attestation_kind: retrospective` | same reason: the kind lives in the signed payload |
| `EP1-INT-040` | that a **defensive** refusal is distinguishable from a **contractual** one | would need to trigger a declared defensive bound in Python; its bounds are not declared — which is what `EP1-INT-035` records as `PARTIAL` |

### The three that were closed, and the one that mattered

| Rule | How it is now verified |
|---|---|
| **`EP1-SIG-031`** | a JWS header is **enriched** with `jwk`, `jku`, `x5u` and `x5c`, and three measurements lock the behaviour: with no store the signature stays `NOT TESTED`; with a store whose `kid` is absent, `NOT TESTED` again; with the right store it is the **store's** key that is used — the report names it — and never the one the token carried |
| `EP1-VER-013` | 13 non-`PASS` lines swept across 6 failure regimes, every one carrying a non-empty reason |
| `EP1-VER-031` | `does_not_establish` present and non-empty, and the three counts remain three distinct fields |

`EP1-SIG-031` is the one that mattered. It is the classic way a signature
check becomes **decorative**: a token that carries its own public key proves
only that its author holds a key. The reference implementations resolved keys
from the store alone — that was **read in the code**, and nothing falsified
it. A test that does not build the counter-example demonstrates nothing.

**EP1-CONF-020.** A new obligation **MUST** appear as a coverage gap until a
test exercises it. An untested obligation **MUST NOT** be counted as
satisfied.

### 5.4 The implementation `GAP` — **corrected**

`EP1-INT-012` — a declared path **MUST NOT** be reinterpreted when it
contains `\`.

At the previous revision this was conforming for **submissions** and **not**
for **archives**: `verify.py` tested an archive member with
`".." in Path(n).parts`, and `pathlib` is platform-dependent.

| member name | Windows | Linux (before) | Linux (now) |
|---|---|---|---|
| `..\secret.txt` | refused | **accepted** | **refused** |
| `a\..\..\etc\passwd` | refused | **accepted** | **refused** |
| `../ok.txt` | refused | refused | refused |
| `/abs.txt` | refused | refused | refused |

**Corrected on 11 November.** The check now goes through `membre_abusif()`,
which refuses the backslash and splits on `/` — exactly as
`adapters/ingest.py` and `verifier-rs/src/chemins.rs` already did. Both Rust
verifiers were already conforming and platform-independent; only this path
was not.

Compatibility measured **before** applying: 18 tracked archives,
128 members, **0** affected. No contract was touched, and the correction
aligns Linux with what Windows already refused.

`tests/test_chemins_archive.py` locks it, and its case 2 measures the
**syntax tree**: no `pathlib`, no `os.path` in the predicate — because no
*input* could distinguish the two implementations from a single machine.

### 5.5 The two `PARTIAL`

| Rule | Where it holds, where it does not |
|---|---|
| `EP1-INT-035` (bound metadata before reading) | enforced and tested in `rust-core`; `verify.py` relies on `zipfile`, whose bounds are not declared |
| `EP1-VER-021` (no unhandled error on any input) | `verify.py` conforms since the `C-09` fix; `adapters/ingest.py` still has **six** inputs where it exits 1 with no report — measured again in this revision, unchanged, declared in `COMPLETUDE_RUST_EVIDENCE/08` §3 |

---

## 6. What is not qualified

| | Status |
|---|---|
| **Windows**, **macOS** | **not qualified** — CI runs `ubuntu-latest` only, and §5.4 is a measured reason to expect differences |
| Python versions other than 3.11–3.13 | not qualified |
| Rust toolchains other than `stable` at the date of the run | not qualified |
| **reconciliation**, in the corpus | no case exists; `tests/test_reconciliation.py` covers it |
| **timestamping**, in the corpus | no case exists; `tests/test_timestamp.py` covers it |
| absence of a defect **common** to all three verifiers | out of reach of an agreement bench |
| **security** | a corpus produces counter-examples; it does not prove an absence |

---

## 7. How to run the corpus against your own implementation

1. Decide your **perimeter** — which of `submission`, `archive`,
   `attestation` — and add it to `PERIMETRES` in
   `conformance/runners/run.py`.
2. Add a branch to `construire_commande` building your command line.
3. If your tool writes a JSON report with a `verdict` field, the runner
   reads it; otherwise it falls back to the human-readable output and says
   so in `lu_depuis`.
4. Run it:

```bash
cd conformance
sha256sum --check SHA256SUMS
python3 runners/build_fixtures.py --check
python3 runners/run.py --verifier <yours>
```

Full instructions, in English:
[`../conformance/README.md`](../conformance/README.md) §9.

**EP1-CONF-030.** If a corpus case appears **wrong** to you, that is a
report to make, not an obstacle to work around. The corpus can be wrong:
see `conformance/README.md` §10. Silently excluding a case and then claiming
conformance is the one thing this document exists to make impossible.

---

## 8. Claims this document does not make

| Not claimed | Why |
|---|---|
| conformance to **DSSE**, **in-toto**, **Sigstore** | no test establishes it. The comparison in `../DEVELOPPEMENT_EVIDENCE_PROTOCOL_V1/03_ETUDE_STANDARDS.md` is a comparison. |
| conformance to **RFC 8785** | the canonicalisation profile is a strict, differently-named subset |
| that this specification is **stable** | it is a **Candidate Specification**: four normative questions are open |
| **regulatory** conformance of any kind | nothing here establishes it; see [`THREAT_MODEL.md`](THREAT_MODEL.md) |
