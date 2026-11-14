<!-- English is the primary language of this directory: it is written for
     external developers. A French summary is in README.fr.md. -->

# Evidence Conformance Corpus

A frozen, hash-verifiable corpus for deciding whether an implementation
applies the rules that the NeoMundi Evidence contracts **explicitly define**.

**Version 1.3.0** · 50 cases · 7 families · 121 fixture files ·
172 digests in `SHA256SUMS`

You do not need any NeoMundi infrastructure, account, network access or
knowledge of NeoMundi's internals to use this. Everything runs offline.

---

## 1. The three questions this corpus answers

1. **Is a package conformant** to a given version of the protocol?
2. **Does a verifier apply the corresponding rules** correctly?
3. **Do two independent implementations agree** on the controls they both
   declare they implement?

And the three it does **not** answer — this matters more than the three
above:

| Not answered | Why |
|---|---|
| Is the attested event **true**? | Integrity is not truth. No case measures it, and none can. |
| Is the signer **who they claim to be**? | A trust store *declares* identities. No code verifies them. |
| Is the implementation **secure**? | A corpus produces counter-examples. It cannot prove their absence. |

---

## 2. Get it, and check it

```bash
git clone https://github.com/neomundi-io/neomundi-evidence-public
cd neomundi-evidence-public/conformance
```

### Verify the digests — do this first

```bash
sha256sum --check SHA256SUMS
```

Every file must match. The corpus is **frozen**: if a byte has moved, it no
longer measures what its case sheets claim, and the runner refuses to
proceed.

You can also confirm that the generator reproduces the corpus **byte for
byte**:

```bash
python3 runners/build_fixtures.py --check
# -> le generateur reproduit le corpus a l octet (121 fichiers, 50 fiches)
```

This is the strongest statement available about the corpus: not only are the
bytes unchanged, they are the bytes a declared program produces.

---

## 3. Build the verifiers

Three verifiers exist. You can run the corpus against any subset.

| Verifier | What it covers | Dependencies |
|---|---|---|
| `python` | submissions, archives, attestations | Python 3.11+ standard library, plus `cryptography` for attestations |
| `rust-core` | **submissions only** | **none** — `Cargo.lock` has exactly one entry |
| `rust-crypto` | **archives and attestations only** | `ed25519-dalek` (23 locked packages) |

```bash
# Python: nothing to build. For attestation cases only:
python3 -m pip install cryptography

# Rust, from the repository root:
cd verifier-rs        && cargo build --release && cd ..
cd verifier-rs-crypto && cargo build --release && cd ..
```

Both Rust crates build and test **offline** after the first dependency
fetch. `verifier-rs` needs no fetch at all.

---

## 4. Run it

```bash
# everything
python3 runners/run.py --verifier all

# one verifier
python3 runners/run.py --verifier python
python3 runners/run.py --verifier rust-core \
    --bin-rust-core ../verifier-rs/target/release/evidence-verify-rs

# strict mode: changes exit CODES, never verdicts
python3 runners/run.py --verifier all --strict

# machine-readable report
python3 runners/run.py --verifier all --json /tmp/report.json

# the coverage matrix
python3 runners/matrix.py --results /tmp/report.json --out /tmp/COVERAGE.md
```

If the binaries are elsewhere, pass `--bin-rust-core` and
`--bin-rust-crypto`, or set `CARGO_TARGET_DIR` / `CARGO_TARGET_DIR_CRYPTO`.

---

## 5. Read the results

### The eight states

| State | Meaning |
|---|---|
| `PASS` | the observed behaviour is what the case sheet expects |
| `FAIL` | it contradicts it — **a regression** |
| `KNOWN FAIL` | a **declared** defect, listed in `known_failures.json` |
| `NOT TESTED` | the control was not executed by this verifier |
| `NOT APPLICABLE` | the case does not address this verifier |
| `NOT RUNNABLE` | it **does** address it, but a **prerequisite of the machine** is missing |
| `AMBIGUOUS` | the contract does not allow a single result to be imposed |
| `ERROR` | a technical error prevents any conclusion |

### The rule that trips everyone up

> **An expected refusal is a PASS.**

A verifier that correctly **rejects** a malformed package **passes** the
corresponding conformance test. Families B through E are mostly expected
refusals. Counting them as failures would produce a "conformance rate" that
rewards permissiveness.

### `NOT APPLICABLE` is not a failure

`rust-core` covers submissions only; `rust-crypto` covers archives and
attestations only. Neither claims otherwise. Blaming a tool for not doing
what it does not announce would be a false measurement — and it would
inflate the other tool's denominator.

### `NOT RUNNABLE` is not `NOT APPLICABLE`

`NOT APPLICABLE` says the verifier **does not announce** this subject.
`NOT RUNNABLE` says the opposite: it does, and the **machine** lacks what it
needs. Today there is one such prerequisite — `cryptography`, for the nine
attestation cases on the `python` verifier. Without it the bench announces
the missing dependency **before any result**, marks those cases
`NOT RUNNABLE`, and exits **2**: nothing failed, and not everything was
tested. Conflating the two states would hide an installation defect inside a
denominator, and reading it as a `PASS` would be worse still.

The exit codes follow the same contract as the three tools — **1** something
failed, **2** nothing failed but a required guarantee is not demonstrated,
**0** the measurement is complete. See
[`../docs/INTEGRATION.md`](../docs/INTEGRATION.md).

### `AMBIGUOUS` is a state of this bench, not a protocol verdict

No verifier ever returns "ambiguous". It is **this report** refusing to
decide where the contract is silent. Ten of the fifty cases are ambiguous,
and each one names the gap.

**And a disagreement on an ambiguous case is now published.** The runner
compares the observed verdicts across applicable verifiers and reports them
under `ambiguous_divergences`, in a dedicated output section and in the
matrix's **Divergent ?** column. **6 of the 10** ambiguous cases diverge.

It is not a conformance failure — the contract does not decide — but it is
the dangerous thing a normative silence produces: **two honest verifiers,
one file, two verdicts.** Until 1.1.0 the runner measured each verdict and
never compared them, so `G-07`'s disagreement was in the data and invisible
everywhere. A divergence the sheets do not declare now turns CI red.

---

## 6. The seven families

| Family | Cases | What it probes |
|---|---|---|
| **A — valid** | 7 | submissions v1 and v2, a ZIP package, an empty artifact, a real archive, a real Ed25519/JWS attestation |
| **B — incomplete** | 6 | missing file, absent required field, `null` with and without a reason, absent optional fields |
| **C — malformed** | 9 | invalid JSON, invalid UTF-8, wrong type, unknown version, surplus field, not-a-ZIP, bad CRC, contradictory headers, invalid DEFLATE |
| **D — tampered** | 10 | altered artifact, wrong digest, wrong size, substituted files, removed artifact, invalid signature, tampered payload, substituted key, replaced attestation, altered archive member |
| **E — paths** | 8 | `../` traversal, absolute Unix and Windows paths, backslash, empty path, duplicate declaration, duplicate ZIP member, `.` segment |
| **F — coherent rewrite** | 3 | **packages rewritten and re-hashed consistently** |
| **G — ambiguous** | 7 | duplicate JSON keys, `NaN`, `Infinity`, lone surrogate, base64url padding and alphabet |

### Family F deserves its own warning

A package whose content was replaced **and whose digests were recomputed** is
internally consistent. **It passes an integrity check, and it should.**

Each F case sheet therefore carries:

> `PLAFOND DECLARE` — the expected result is an **acceptance**, and that is
> correct. Never convert this case into a `FAIL` to improve a detection rate.

What distinguishes an original from a competent rewrite is an **external
anchor** — a signature, a third-party timestamp, a digest kept somewhere
else. `F-02` shows exactly that: the same rewritten archive, confronted with
the *original* attestation, is refused.

---

## 7. Each case carries its own expectation

One sheet per case in `expected/<id>.json`:

```json
{
  "id": "D-01-artifact-tampered",
  "corpus_version": "1.3.0",
  "family": "D-tampered",
  "subject": "submission",
  "provenance": "SYNTHETIQUE, genere par conformance/runners/build_fixtures.py",
  "publication": { "licence": "Apache-2.0", "authorised": true,
                   "contains_private_data": false,
                   "contains_private_keys": false },
  "files": [ { "path": "fixtures/...", "sha256": "...", "bytes": 808 } ],
  "rule": {
    "statut": "NORMATIVE",
    "reference": "schemas/evidence-submission-v2.json#/.../sha256",
    "texte": "L empreinte declaree est RECALCULEE sur les octets du fichier..."
  },
  "expected": { "verdict": "REJETE", "exit_code": 1, "exit_code_strict": 1 },
  "limits": [ "L integrite ne demontre pas la verite des evenements.", "..." ]
}
```

Three properties of these sheets are deliberate:

1. **They were written before any verifier ran.** No expectation is derived
   from a Python (or Rust) output.
2. **Each cites a normative reference** — an RFC section, the ZIP APPNOTE, or
   an exact path inside a published schema. `COMPORTEMENT OBSERVE` marks the
   cases where the behaviour is implemented but *not* published.
3. **`rule.statut` is `NORMATIVE`, `AMBIGUOUS` or `EXTENSION`.** An ambiguous
   case never declares an implementation at fault.

### Exit codes are compared separately from verdicts

A code may legitimately differ between verifiers — `--strict` is a
contractual example. The **verdict** must agree; a code mismatch on an
agreeing verdict is reported as such, not as a conformance failure. A sheet
may also carry `expected_by_verifier` to override the common expectation
where the two tools genuinely have different output surfaces, and every
override states its reason.

---

## 8. Known failures, and why they are not hidden

`known_failures.json` lists **observed, declared** conformance failures. The
runner reports them as `KNOWN FAIL`: they stay visible on every run, and they
do not fail CI.

Without this mechanism, the only way to make CI green would be to **remove
the case from the corpus** — that is, to delete the measurement that is
inconvenient.

A failure that is **not** declared turns CI red. So does a **stale** entry: a
declared defect that no longer occurs means either it was fixed (remove the
entry) or the case no longer probes it (fix the case). Both need a decision.

At version **1.1.0 there are none**. The single declared failure of 1.0.0 —
`verify.py` raising an uncaught `zlib.error` on an invalid DEFLATE stream and
exiting 1 with no verdict at all — **was found by this corpus and has been
fixed**. `C-09-archive-deflate-invalid` now passes on all three verifiers.

Its entry was **not deleted**. It moved to the `resolved` section of
`known_failures.json`, which keeps the original observation, the exact cause,
the fix and the regression test. Two reasons:

- a reader must be able to reconstruct what the corpus measured at a given
  version — the only way to re-read an old conclusion without deforming it;
- a resolved case is **no longer declared**, so if the defect returns, its
  failure arrives as an **undeclared** one and turns CI red. The regression
  signals itself, with no extra mechanism.

**No expectation changed.** `C-09` expected `REJETE` at 1.0.0 and still does.
The corpus was right; the implementation was not. See
[`CHANGELOG.md`](CHANGELOG.md).

---

## 9. Add your own verifier

1. Decide its **perimeter** — which of `submission`, `archive`,
   `attestation` it covers — and add it to `PERIMETRES` in `runners/run.py`.
2. Add a branch to `construire_commande` that builds its command line.
3. If it writes a JSON report with a `verdict` field, `run.py` reads it.
   Otherwise it falls back to the human-readable output, and says so in
   `lu_depuis`.
4. Run it. Cases outside its perimeter will be `NOT APPLICABLE`.

You do **not** need to touch the fixtures or the expectations. That is the
point of keeping them separate from the implementations.

If your verifier disagrees with a `NORMATIVE` case, one of three things is
true, and it is worth finding out which: your verifier is wrong, the case is
wrong, or the rule is not as normative as the sheet claims.

---

## 10. Report an error in the corpus

Open an issue with:

- the case id;
- the verifier and its version;
- the observed output and exit code;
- **why you believe the expectation is wrong** — ideally the contract text or
  RFC section that contradicts it.

A corpus error is a real possibility. Five instrument errors were found and
fixed while building this one, and each is documented where it bit. If a
sheet contradicts its own normative reference, the sheet is wrong.

---

## 11. Provenance, licence, privacy

| | |
|---|---|
| **Licence** | Apache-2.0, the repository's |
| **Provenance** | everything is **synthetic**, generated by `runners/build_fixtures.py`, except three files reused from `examples/dossier-v1/` — already public in this repository and declared "no real data" |
| **Private pilot data** | **none**. No pilot folder is reused |
| **Private keys** | **none**, anywhere in the corpus |

The cryptographic counter-examples are **byte alterations** — a flipped
signature byte, a rewritten header, a re-encoded segment — never signatures
forged with another key. Forging would require shipping a private key in a
public corpus, which is excluded. The "wrong key" and "key substitution"
cases are obtained by altering the **trust store**, which holds only public
material.

The demonstration key carries `status: test` and grants nothing without
`--allow-test-keys`.

---

## 12. Limits — read these before quoting any number

1. **Integrity does not demonstrate truth.**
2. **A valid signature does not certify the event**, only that a key
   committed to some bytes.
3. **Python/Rust agreement does not rule out a common defect.** Two
   implementations that agree share the same residual error perimeter; if the
   contract is wrong, they will both be wrong, together.
4. **The corpus is not exhaustive.** 50 cases cite 38 normative references.
   The Evidence contracts contain more. What the matrix does not list in §5 is
   **not covered**.
5. **Fuzzing does not prove the absence of vulnerabilities.** The
   repository's fuzzing benches produce counter-examples; silence is not
   proof.
6. **A coherent forgery can be accepted** — family F, by design.
7. **Normative ambiguities are not hidden.** Ten cases record them rather
   than picking a side.
8. **Signatures must be read through their trust policy.** A mathematically
   valid signature from an untrusted key is not an attestation.
9. **Offline verification proves nothing about an external timestamp.**
10. **No result here establishes regulatory conformance.**

### And the one about numbers

Every count in the generated matrix carries its **denominator**: the number
of cases **applicable to the verifier concerned**, never the corpus total.
The matrix publishes **no conformance percentage at all**, because a rate
computed over a partial corpus reads as a rate over the protocol.

---

## 13. What is where

```
conformance/
  README.md              this file
  README.fr.md           French summary
  VERSION                1.3.0
  manifest.json          index of every case, with counts
  SHA256SUMS             172 digests -- check these first
  known_failures.json    declared failures (none open) + `resolved` history
  CHANGELOG.md           what moved per version, and what did NOT
  fixtures/              the frozen bytes, by family
  expected/              one sheet per case
  runners/
    build_fixtures.py    the generator -- runs once, output is versioned
    run.py               the conformance bench
    matrix.py            the coverage matrix
  reports/
    latest.json          last run
    COVERAGE.md          generated matrix
```
