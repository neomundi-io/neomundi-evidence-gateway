# Evidence Protocol v1 — Worked examples

Every example below points at **bytes that exist in this repository**. None
is written out inline and then left to drift from the artifact it describes:
there is **one** source of truth per example, and it is the file.

Where an example is a **frozen conformance fixture**, its digest is in
[`../conformance/SHA256SUMS`](../conformance/SHA256SUMS) and
`sha256sum --check` verifies it. Where it is not in the corpus, this
document says so.

Companion to [`SPECIFICATION.md`](SPECIFICATION.md). Corpus version
**1.3.0**.

---

## How to read an example

```bash
cd conformance
sha256sum --check SHA256SUMS                      # the bytes are the ones declared
cat expected/A-01-submission-v1-valid.json        # the expectation, before any run
python3 runners/run.py --verifier python          # the measurement
```

Each fixture has an **expectation sheet** in `conformance/expected/`,
written **before** the verifiers were run, carrying the rule, its source,
its status, and the expected verdict — or `null` where the contract is
silent.

---

## 1. A valid package

| | |
|---|---|
| `A-01-submission-v1-valid` | `submission/1`, two artifacts, exact digests and sizes |
| `A-02-submission-v2-valid` | `submission/2`, with a **declared absence** of model identity |
| `A-03-submission-v2-zip-valid` | the same `/2` package as a **ZIP** rather than a directory |

Fixtures: `conformance/fixtures/A-valid/<id>/`.
Expected: **ACCEPTED**, exit **0**.

`A-03` matters on its own: the same manifest and the same artifacts, in a
different container, must reach the same verdict. A container is transport,
not content.

## 2. A permitted incompleteness

| | |
|---|---|
| `B-06-optional-fields-absent` | `provenance_declared`, `limits_declared`, `notes_declared` all absent |
| `B-03-v2-null-model-with-reason` | `model_declared: null`, **with** reason and note |
| `A-04-empty-artifact-allowed` | an artifact of **zero bytes**, declared with the digest of the empty string |

Expected: **ACCEPTED**.

The absence of an optional property is **not an event**
(`EP1-COMPAT-004`). A declared absence, by contrast, is read and reported —
and the value stays unknown (`EP1-ABS-010`).

## 3. A refused incompleteness

| | |
|---|---|
| `B-02-required-field-absent` | `submission_id` absent — required by the schema → **REFUSED** |
| `B-04-v2-null-model-without-reason` | `null` model with **no** reason → **REFUSED**, even in `/2` |
| `B-05-v1-null-model-refused` | `null` model in `/1`, which does not allow it → **REFUSED** |
| `B-01-artifact-file-missing` | a declared artifact whose file is absent → **INCOMPLETE** |

`B-01` against `B-04` is the pair to study. A **missing file** makes the
package *incomplete*: nothing is wrong, something is absent. A **missing
reason** makes it *refused*: the declaration contradicts its own contract.
Collapsing the two into one verdict would answer a question nobody asked
(`EP1-VER-010`).

## 4. An invalid digest

| | |
|---|---|
| `D-01-artifact-tampered` | a byte **added** to an artifact, declared digest unchanged |
| `D-02-manifest-digest-wrong` | the **declared** digest is false, the bytes are intact |
| `D-03-size-wrong` | the declared **size** is false, the digest is right |
| `D-04-file-substituted` | the bytes of **two** artifacts swapped, each declared digest left in place |

All **REFUSED**, exit **1**.

`D-03` is the one implementers skip. The digest matches; only the size is
wrong. An implementation that checked digests alone would accept it — and
would be accepting a declaration that contradicts itself (`EP1-INT-003`).

`D-04` is the one that catches a lazy comparison: both digests are still
present and both files are still there. Only the pairing is wrong.

## 5. A missing artifact

| | |
|---|---|
| `B-01-artifact-file-missing` | declared, absent → **INCOMPLETE** |
| `D-05-artifact-removed` | declared, then **removed** → **INCOMPLETE** |

Neither is `REFUSED`: nothing disagrees, something is absent
(`EP1-INT-020`).

## 6. An unknown version

`C-04-unknown-version` — `schema` announces a contract identifier the
verifier does not know. **REFUSED**, and the refusal **names the identifier
found**.

A verifier must not fall back to the nearest version it knows
(`EP1-COMPAT-001`): that would apply rules the document never agreed to.

## 7. A valid signature

| | |
|---|---|
| `A-06-attestation-valid` | archive + detached JWS + trust store, **with** the store digest confronted |
| `A-07-attestation-store-not-confronted` | the **same** attestation, **without** `--store-digest` |

`A-06` is expected to reach the level `cryptographically_attested`.

`A-07` is the instructive one: the two reference verifiers **legitimately
disagree**. `verify_attestation.py` reports its level; `evidence-verify-crypto`
reports `INCOMPLET`, because for it an untested pillar is a missing pillar.
Neither contradicts a contract, so the expectation sheet carries the
divergence explicitly in `expected_by_verifier` — the corpus's only such
derogation.

Keys: **demonstration keys only**, `store_kind: "test"`. No private key
exists anywhere in the corpus.

## 8. An incorrect signature

| | |
|---|---|
| `D-06-attestation-signature-invalid` | one **byte of the signature** flipped |
| `D-07-attestation-payload-tampered` | the **payload** replaced after signing |
| `D-08-attestation-wrong-key` | the store carries a **different** public key under the same `kid` |
| `D-09-attestation-replaced-by-other` | the attestation covers **another** archive |

All **REFUSED**.

`D-07` is the one that proves `EP1-CAN-004`: the signed bytes are those the
token carries **verbatim**. A verifier that re-serialised the parsed payload
before verifying would pass or fail here for the wrong reason.

**No signature in this corpus is forged.** Forging one would require a
private key in a public repository. These cases alter **bytes**, or the
**store** — which holds only public material. For the purpose of proving
that a verifier refuses, an altered signature and a forged one are
indistinguishable to `verify_strict`.

## 9. A declared absence

`A-02-submission-v2-valid` and `B-03-v2-null-model-with-reason`:
`model_declared: null`, plus `model_absence_reason_declared` ∈
{`not_applicable`, `unavailable`}, plus a non-empty note.

The two reasons are **not** interchangeable (`EP1-ABS-011`):

| Reason | Meaning |
|---|---|
| `not_applicable` | **no** AI model took part at all — a deterministic run, rules in code, a fixed table. There is nothing to name. |
| `unavailable` | a model **did** take part, and its identity cannot be stated. |

A verifier never fills either in on the submitter's behalf.

## 10. Reconciliation — agreement and divergence

**Not in the conformance corpus.** The corpus 1.3.0 covers submission,
archive and attestation; it carries **no** reconciliation case. These
examples live in the repository and are exercised by
`tests/test_reconciliation.py` (27 cases), not by the corpus.

| File | What it shows |
|---|---|
| `examples/reconciliation/receipt-synthetic.html` | a third-party receipt, in the third party's own format |
| `examples/reconciliation/map-comparable.json` | a map declaring the receipt's context as **identical** to ours — what a legitimate comparison looks like |
| `examples/reconciliation/map-no-context.json` | the same receipt with **no declared context** — every measured value becomes `NOT COMPARABLE` |
| `examples/reconciliation/reconciliation-synthetic.md` | the resulting per-field report |
| `examples/dossier-v1/receipt-imported.json` | the same receipt after import, with its own digest preserved |

The pair of maps is the example to read. **The same receipt and the same
record, with and without a declared context, produce different statuses** —
and that is correct. Two values are a divergence of computation only if
they measure the same thing (`EP1-REC-010`).

Note `map-comparable.json`'s own words: a comparability boundary bites on
**measured values**, never on a digest or an identifier. A digest is equal
or it is not.

## 11. A coherent falsification — the declared ceiling

| | |
|---|---|
| `F-01-coherent-rewrite-accepted` | an artifact's content **replaced** and its digest **recomputed** → **ACCEPTED** |
| `F-02-coherent-rewrite-breaks-attestation` | the **same** rewritten archive against the **original** attestation → **REFUSED** |
| `F-03-archive-amputated-no-contract` | an observation removed **everywhere**, counts and sums redone → **ACCEPTED** |

**`F-01` and `F-03` expect ACCEPTANCE, and that is correct.** A package
that is internally consistent passes an integrity check. Integrity is a
statement about internal consistency, not about history.

Each of these sheets carries `PLAFOND DECLARE`:

> the expected result is an **acceptance**. Never convert this case into a
> `FAIL` to improve a detection rate.

`F-02` shows what does detect it: an **external anchor**. The same bytes,
confronted with a signature made over the *original* digests, are refused.

`F-03` has a measured history worth reading: the forger that produces it
was long believed to be detected by a completeness control. It is not — a
forger that **also** rebuilds the declared export count is detected
**nowhere**. See
[`../DEVELOPPEMENT_CORPUS_CONFORMITE/06_DIVERGENCE_FALSIFICATION_SCENARIO_D.md`](../DEVELOPPEMENT_CORPUS_CONFORMITE/06_DIVERGENCE_FALSIFICATION_SCENARIO_D.md).

## 12. The ambiguous cases

Ten cases where **no verdict is imposed**, because the contract does not
decide. Their sheets carry `expected.verdict: null` and freeze the
**observed** behaviour of each verifier instead.

| Case | The silence |
|---|---|
| `G-01-duplicate-json-keys` | `submission_id` declared **twice**. RFC 8259 §4: undefined. Python accepts (last wins); Rust refuses. |
| `G-02-duplicate-key-on-digest` | **two** `sha256` for one artifact — which one is checked? |
| `G-03-nan-outside-rfc` | `NaN`, outside RFC 8259 §6 |
| `G-04-infinity-outside-rfc` | `Infinity`, likewise |
| `G-05-lone-surrogate` | a lone UTF-16 surrogate half — **both** refuse, for two different reasons |
| `G-06-base64url-padding` | a JWS segment with `=` padding, which RFC 7515 §2 forbids — but decoder tolerance is unspecified |
| `G-07-base64url-standard-alphabet` | the signature segment rewritten in **standard** base64 (`+`, `/`) |
| `C-05-field-not-allowed-by-schema` | a surplus property in `pilot`, which `additionalProperties: false` forbids — see below |
| `E-06-path-declared-twice` | the same path twice in `artifacts`, with two different digests; no `uniqueItems` in the schema |
| `E-08-path-dot-segment` | `artefacts/./prompt.txt` — a `.` segment is not an upward traversal. **A measured disagreement**: `python` accepts, `rust-core` refuses |

`G-02` is the one with teeth. The duplicated key is a **digest**. One
implementation reads the last occurrence, another would read the first — so
one file, two honest verifiers, two verdicts, and the author chose both.

**`C-05` is listed here but is not really an ambiguity.** The schema is
explicit: `additionalProperties: false` requires a refusal. The reference
implementation **names** the surplus property and reports it `NOT TESTED`
instead — a **declared divergence** with a stated reason, pinned by a test.
Classing it as "ambiguous" understates it. See
[`../DEVELOPPEMENT_EVIDENCE_PROTOCOL_V1/04_ARBITRAGES_PROTOCOLE.md`](../DEVELOPPEMENT_EVIDENCE_PROTOCOL_V1/04_ARBITRAGES_PROTOCOLE.md)
§5.

## 13. An archive, and how it breaks

| | |
|---|---|
| `A-05-archive-valid` | the repository's demonstration Evidence archive, taken as it is |
| `C-06-not-a-zip` | a `.zip` that is not an archive |
| `C-07-archive-crc-invalid` | a member whose CRC-32 contradicts its data |
| `C-08-archive-local-header-mismatch` | the **local** header names a different member than the central directory |
| `C-09-archive-deflate-invalid` | a member announces DEFLATE and carries an **invalid stream** |
| `D-10-archive-member-tampered` | one byte added to `rapport.md` |

`C-09` is the case with the history. At corpus 1.0.0 the Python reference
let a `zlib.error` escape — **exit 1, no verdict, no report** — while the
Rust verifier refused it with a reasoned report. The defect was fixed and
the corpus moved to 1.1.0 **without changing a single expectation**: the
expectation had been right all along.

---

## What these examples do not contain

| Absent | Why |
|---|---|
| a **real** pilot dossier | none is published, and none was opened |
| a **private key** | nowhere, in any form |
| a **forged** signature | it would require a private key (§8) |
| a **confirmed** timestamp over this project | `examples/timestamp/` carries a confirmed proof for an earlier demonstration subject; nothing in this project has a confirmed anchor |
| a **reconciliation** fixture in the corpus | §10 — tests cover it, the corpus does not |
