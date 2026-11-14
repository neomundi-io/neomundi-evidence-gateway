# Evidence conformance corpus — changelog

The corpus is **frozen**. A change here is an event: it requires a new
version, never a silent regeneration. Every release states what moved and —
just as important — **what did not**.

Digests of fixture files are the corpus's contract with its readers. A
release that leaves them untouched says so explicitly, and the claim is
measurable.

---

## 1.3.0 — 13 November 2026

### What changed

Expectation **metadata** again. **No fixture byte changed.**

Three sheets correct their `exit_code_strict`, which was **0** and is **2**:

| Case | Subject | `exit_code_strict` | Why 2 is the contractual value |
|---|---|---|---|
| `A-05-archive-valid` | archive | 0 → **2** | `verify.py`'s one required guarantee is the **replayed-input digests**, demonstrated only by `--corpus`. The bench supplies none, and no archive fixture carries one |
| `F-03-archive-amputated-no-contract` | archive | 0 → **2** | derived from `A-05`; same required guarantee, same cause |
| `A-07-attestation-store-not-confronted` | attestation | 0 → **2** | the line *"trust store digest confronted"* is marked **REQUIRED** by `verify_attestation.py` itself — and it is the very subject of this case |

`A-05` and `F-03` gain a declared `rust-crypto` override at **0**:
`evidence-verify-crypto` models no replayed-input guarantee on an archive,
so it has none left undemonstrated. A difference of **surface**, declared
with its reason — not a divergence of rule.

`F-01-coherent-rewrite-accepted` carries the same expectation pair and
**stays at 0**: it is a *submission* case, and that path already received
`--strict`.

### Why this release exists

**The corpus declared a strict-mode value that no run had ever measured.**

`conformance/runners/run.py` appended `--strict` to five of its seven command
paths. The two it omitted were `verify.py` on an archive and
`verify_attestation.py` on an attestation. On those, `run.py --strict`
compared the sheet's `exit_code_strict` against a tool launched in **non-strict
mode** — so the three wrong values could not surface, and CI stayed green on a
claim it was not testing.

Propagating the flag made them visible immediately: three code mismatches,
on exactly the three sheets corrected here.

The `A-07` sheet also **mis-attributed** its own divergence. Its
`rust-crypto` override explained the strict code 2 by that tool modelling a
*verdict* in addition to a level. That explanation was wrong: Python reaches 2
by the **required-guarantee rule**, which it implements too, on the very line
this case is built around. Both tools return 2; only the **verdict surface**
differs — `ACCEPTE` against `INCOMPLET` — and that divergence is preserved.
The reason text is corrected.

### Found by

Reported by **Olusanya Timothy**, external reviewer, on 13 November 2026, in
an independent verification of the public repository. Two observations:
`verify_attestation.py` exiting **0** on a tampered signature when no trust
store is supplied, and five additional corpus failures in an environment
without `cryptography`. Both were **reproduced to the line**.

The first turned out to be **intentional and already documented** — but
`docs/ATTESTATION.md` still presented strict mode as a *future need*, which is
very likely what prompted the recommendation to build it. The second was
**real at the bench level**: a missing dependency was reported as
*"undeclared failures — regression"*, naming the dependency nowhere.

Neither observation was about `exit_code_strict`. Investigating them is what
uncovered the flag that was not propagated, and the three values it hid.

### What did NOT change

| | |
|---|---|
| fixture files | **121**, and **0** modified — same bytes, same digests |
| cases, families, rule counts | unchanged: 50, 7, 40 normative + 10 ambiguous |
| expected **verdicts** | **none changed** — `ACCEPTE` and `REJETE` are untouched everywhere |
| default (non-strict) exit codes | **none changed** |
| declared failures | **0**, as in 1.1.0 and 1.2.0 |
| measured ambiguous divergences | **6**, the same six |

The third row is the one that sets the release level. An `exit_code_strict`
is expectation **metadata** about a **non-default flag**: no verdict moves, so
this is a **MINOR** release under the rules at the bottom of this file. A
changed *verdict* would have been MAJOR.

### The diff

`corpus_version` moves in the 50 sheets and the manifest, three sheets change
an `exit_code_strict` and two gain an override: **51 lines of `SHA256SUMS`**
change, and **not one of the 121 fixture lines**.

### Measured, before and after

```
                                   before        after
python, non-strict            40 PASS / 10 AMB   unchanged
python, --strict              40 PASS / 10 AMB   unchanged
  of which code mismatches       0 (unmeasured)    0 (measured)
three verifiers, non-strict   80 PASS / 20 AMB / 50 N-A   unchanged
three verifiers, --strict     80 PASS / 20 AMB / 50 N-A   unchanged
python, without cryptography  5 FAIL, exit 1     9 NOT RUNNABLE, exit 2
```

---

## 1.2.0 — 11 November 2026

### What changed

Expectation **metadata** again. No fixture byte changed.

Three ambiguous cases now **freeze their behaviour per verifier**, as
`G-01`–`G-05` already did:

| Case | `python` | Rust |
|---|---|---|
| `E-08-path-dot-segment` | ACCEPTE (0) | `rust-core` REJETE (1) |
| `G-06-base64url-padding` | REJETE (1) | `rust-crypto` REJETE (1) |
| `G-07-base64url-standard-alphabet` | ACCEPTE (0) | `rust-crypto` REJETE (1) |

### Why this release exists

**The corpus was measuring disagreements it never published.**

The runner recorded each verifier's observed verdict — it has been in
`observed` of the JSON report since 1.0.0 — and **never compared one
verifier to another** on an ambiguous case. The `G-07` disagreement was in
the data and invisible in everything a reader looks at: no summary line, no
ambiguous section, no matrix column.

Fixing the comparison instrument surfaced **six** disagreements, including
one nobody had named: **`E-08`**. And the 1.1.0 sheet for `E-08` asserted
the opposite — *"the reference implementations admit the `.` segment"* —
which is **false**: `python` admits it, `rust-core` refuses it. That note is
corrected here.

A measured aside, visible in Python's own report on `E-08`: having accepted
the declaration `artefacts/./prompt.txt`, it then flags
`artefacts/prompt.txt` as an **undeclared file**. The two spellings of one
path do not recognise each other inside the same tool.

### What the runner does now

- computes, per ambiguous case, the distinct observed verdicts across
  applicable verifiers;
- publishes them as `ambiguous_divergences` in the JSON report and as a
  dedicated section of the human-readable output;
- marks a divergence the sheets do **not** declare — and CI fails on one,
  because a corpus that measures a disagreement without declaring it is a
  corpus that hides what it knows;
- the coverage matrix gains a **Divergent ?** column: **6 of the 10**
  ambiguous cases diverge.

A divergence on an ambiguous case is **not** a conformance failure: the
contract does not decide. It must be **visible**, because that is exactly
what a normative silence produces that is dangerous — two honest verifiers,
one file, two verdicts.

### What did NOT change

| | |
|---|---|
| fixture files | **121**, and **0** modified |
| cases, families, rule counts | unchanged: 50, 7, 40 normative + 10 ambiguous |
| expected verdicts | **none changed** — ambiguous cases impose none, and none was imposed |
| declared failures | **0**, as in 1.1.0 |

**No ambiguity is settled.** Freezing an observed behaviour is the opposite
of arbitrating it: it records what each tool does so that a change becomes
visible, and leaves the normative question open.

### The diff

`corpus_version` moves in the 50 sheets and the manifest, and three sheets
gain their per-verifier declarations: **51 lines of `SHA256SUMS`** change,
and **not one of the 121 fixture lines**.

---

## 1.1.0 — 11 November 2026

### What changed

One **expectation metadata** release. No fixture byte changed.

`C-09-archive-deflate-invalid` was a **declared failure** in 1.0.0: on an
archive whose member announces DEFLATE and carries an invalid stream,
`verify.py` let a `zlib.error` escape and exited 1 **with no verdict and no
report**. The defect is fixed; the case now passes.

| | 1.0.0 | 1.1.0 |
|---|---|---|
| `C-09` / `python` | **KNOWN FAIL** | **PASS** |
| declared failures | 1 | **0** |
| `python` PASS | 39 | **40** |

The 1.0.0 entry was **not deleted**. It moved to the `resolved` section of
`known_failures.json`, which carries its original observation, its exact
cause, the fix, and the regression test. A reader can still reconstruct what
the corpus measured at 1.0.0 — the only way to re-read an old conclusion
without deforming it.

### What did NOT change

| | |
|---|---|
| fixture files | **121**, and **0** modified — same bytes, same digests |
| cases | 50 |
| families | 7 (A–G) |
| normative rules | 40 · ambiguous 10 |
| expected verdicts | **none changed**, `C-09` included: it expected `REJETE` in 1.0.0 and still does |

The last row is the one to read carefully. **The corpus was right in 1.0.0**;
Python did not do what the corpus expected. Fixing Python did not require
changing a single expectation — which is the strongest thing a conformance
corpus can demonstrate about itself.

### What the diff looks like

`corpus_version` moves from `1.0.0` to `1.1.0` in the 50 case sheets and in
`manifest.json`, so their digests move too: **51 lines of `SHA256SUMS`**
change, and **not one of the 121 fixture lines**.

### One defect in the generator, fixed in passing

The first regeneration produced `VERSION` and `SHA256SUMS` with **CRLF**
endings: `pathlib.write_text` translates `"\n"` on Windows. All 172 digest
lines then differed from the repository's while **no digest had changed**.

Both files are now written with `write_bytes`. The corpus must come out at
the same bytes on every machine — that is its one non-negotiable property,
and the tool that produces it had been quietly able to break it.

---

## 1.0.0 — 11 November 2026

First public release. 50 cases, 7 families, 121 fixture files, 172 digests,
40 normative and 10 ambiguous rules, 38 distinct normative references.

One declared failure: `C-09-archive-deflate-invalid` / `python` — see 1.1.0
above, and the `resolved` section of `known_failures.json`.

---

## Versioning rules

| Change | Release |
|---|---|
| a fixture's **bytes** change | **MAJOR** — the corpus no longer measures what earlier conclusions cited |
| an expected **verdict** changes | **MAJOR** — any conclusion drawn from the old one must be re-read |
| a case is **added** or **removed** | **MINOR** |
| expectation **metadata** changes (declared failure resolved, reference clarified) | **MINOR** |
| documentation only, no digest moves | **PATCH** |

A fixture whose input has not changed **keeps its digest**. Regenerating it
to "refresh" the corpus would break every published claim that cites it, in
exchange for nothing.
