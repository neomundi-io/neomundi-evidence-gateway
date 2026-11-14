<sub>🇬🇧 <b>English</b> · 🇫🇷 <a href="REVIEWS.fr.md">Français</a> · <a href="../README.md">← README</a></sub>

# Independent reviews — attributions and technical references

Three external reviewers examined NeoMundi Evidence in November 2026. Each
review changed the product. This page records **what each person actually
did**, and keeps the technical trace reachable whatever the visibility of the
engine repository.

> **Why this page exists.** Each technical reference below points into the
> Evidence **engine** repository, `neomundi-io/neomundi-evidence-public`.
> Access to that repository is **granted, not assumed** — see
> [`LIMITS.md`](LIMITS.md) for its current status. Nothing has been deleted
> and no history has been rewritten: the pull requests, their diffs and their
> merge commits exist unchanged. But an attribution must not depend on who
> can open a link, so every identifier, date, merge commit and measured
> figure is recorded here in full.

---

## Mark Mocnaj — Project Petunia × Judicator (OGS)

**Scope reviewed.** Interoperability and ingestion: the OGS B-3 v2 submission
was used to test Evidence ingestion, schema compatibility, artifact integrity
and deterministic replay.

**What the review found.** Four ingestion discrepancies, each a real defect in
the adapter rather than in the submission:

| | Discrepancy | Cause in the adapter |
|---|---|---|
| A | execution-kind representation | an **emptiness** test instead of a membership test — any non-empty string passed, while the message itself said "absent" |
| B | declared-timestamp format | **no control at all**, not even a type check: seven JSON shapes were accepted |
| C | missing artifact role | an optional read that returned `None` without objecting |
| D | list-valued pilot metadata | a guard that did not protect against a **non-empty list** → crash, and **no report at all** |

**What changed.** The adapter was corrected and regression-tested; the four
rules now reject with exit code 1, and case D rejects **with** a report. The
structural cause was addressed too: the adapter had been re-implementing the
schema rules by hand, giving two sources of truth. **No file in `schemas/` was
modified — the `/2` contract was not touched**, and the 25 existing profiles
kept their verdicts.

The unchanged candidate then passed the documented technical ingestion
checks, including **19 artifact hashes and byte counts** and **five
deterministic replay cases**.

**Limit.** This establishes bounded ingestion compatibility — not upstream
claim certification, not general production readiness, not complete
scientific validation.

**Technical reference.** Engine pull request **#24**, *"fix(ingestion) : le
code applique les regles que le contrat /2 publie"* — merged
**2026-11-11T11:21:23Z**, merge commit **`330ecb03`**, head `4be3fca9`,
7 commits, 13 files, +3457/−35. **Archived in the engine repository.**

**Attribution status.** 🟢 **Approved.** Published with this contributor's
approval in [`neomundi-use-cases`](https://github.com/neomundi-io/neomundi-use-cases)
on 2026-11-14.

---

## Dennis Christie — ASIN-HHC / CP8

**Scope reviewed.** Reproducibility and execution evidence. The reviewer
examined NeoMundi measurement receipts and evidence-verification boundaries
using an existing controlled CP8 execution packet and reconciliation
materials.

**What the review found.**

- a reported **AI measurement** is a different object from the underlying
  **external tool execution**, and the two were not being distinguished
  clearly enough;
- a raw aggregate (**0.3863**) against an older normalised dashboard display
  (**0.594**) — **two NeoMundi representations of the same thing, not
  conflicting measurements from two parties**.

**What changed.** Stronger digest-coverage handling, a clearer separation
between declared and independently verified relationships, additional
regression checks, and documentation corrections. The consolidation also
found, while acting on the review, that **three declared contract fields were
dead** — `byte_length_declared`, `declared_by`, `issuer_declared`: their
schema prose stated the correct rule while no code enforced it. Falsified on
real material: a declared length of `999999` bytes on a 1416-byte file
returned **VERIFIED**. It now returns **CONTRADICTORY**.

**Limits.** External execution is **not yet** cryptographically or
operationally bound to the separate AI measurement. A SHA-256 digest is not a
signature and does not authenticate an issuer. Issuer authentication and
excerpt retention remain open. This is a bounded methodological review — not
independent end-to-end validation, not performance certification, not an
endorsement of the platform.

**Technical reference.** Engine pull request **#38**, *"Consolidation après
audit externe : trois champs déclarés cessent d'être des champs morts"* —
merged **2026-11-13T16:03:04Z**, merge commit **`439d1549`**, head
`ef66edca`, 6 commits, 17 files, +2010/−43. **Archived in the engine repository.**

**Attribution status.** 🟢 **Approved.** Published with this contributor's
approval in [`neomundi-use-cases`](https://github.com/neomundi-io/neomundi-use-cases)
on 2026-11-14.

---

## An external reviewer — conformance corpus and strict mode

🟡 **This reviewer is deliberately not named on this page.** A named
acknowledgment of their work was drafted in engine pull request **#40**,
which carries an explicit publication gate — *"DO NOT MERGE without the
reviewer's approval of their name and exact wording"* — and which **remains
open and unmerged**. Presenting an attribution that is pending as though it
were approved would be the one thing this page must not do. The slot is
reserved; the name will be added when, and only when, that approval exists.

**Scope reviewed.** An independent verification of the then-public engine
repository, carried out on **13 November 2026**.

**What the reviewer actually reported — two observations, both reproduced to
the line.**

1. `verify_attestation.py` exiting **0** on a tampered signature when **no
   trust store** is supplied;
2. **five additional corpus failures** in an environment without the optional
   `cryptography` dependency.

**What the two observations turned out to be.**

- the first was **intentional and already documented**: exit code 0 means "no
  control failed", and a missing trust store yields `NOT TESTED`, not a
  failure. But `docs/ATTESTATION.md` still presented strict mode as a *future
  need*, which is very likely what prompted the recommendation to build it.
  The documentation was wrong, not the behaviour;
- the second was **real at the bench level**: a missing dependency was
  reported as *"undeclared failures — regression"*, naming the dependency
  nowhere.

**What must not be attributed to this reviewer.** Neither observation was
about `exit_code_strict`. **Investigating them** is what uncovered a separate
defect — the conformance harness appended `--strict` to only **five of its
seven** command paths, so three wrong expected values could not surface and
CI stayed green on a claim it was not testing. That finding, and the three
corrected sheets, are **not** this reviewer's claims. They are what the
review caused to be looked for.

**What did not change** in corpus 1.3.0: **121 fixture files, 0 modified** —
same bytes, same digests; and 50 cases, 7 families, 40 normative + 10
ambiguous, all unchanged.

**Technical reference.** Engine pull request **#39**, *"Audit externe : le
banc ne transmettait pas --strict, et une dependance absente passait pour une
regression"* — merged **2026-11-13T22:07:50Z**, merge commit **`3391c768`**,
head `1c248d02`, 69 files, +1334/−348. Pull request **#40** (named
acknowledgment) **open, unmerged**, head `cc5f3223`. Both **archived in the engine repository**.

**Attribution status.** 🟡 **Pending the reviewer's approval.** Not approved,
and not presented as approved.

---

## What this page is not

- it is **not** a certification, an endorsement, or a partnership claim by or
  of any reviewer;
- no reviewer is presented as NeoMundi's certification body, and none
  inherits any authority from NeoMundi;
- a review establishes what it examined, inside the scope it examined. The
  per-review *Limits* above are part of the attribution, not a disclaimer
  appended to it;
- corrective code authorship is **NeoMundi's**, and is distinct from the
  reviewer contributions recorded here.

See also [`VERIFICATION_RESULTS.md`](VERIFICATION_RESULTS.md) for what was
measured, and [`LIMITS.md`](LIMITS.md) for what the engine going private
costs.
