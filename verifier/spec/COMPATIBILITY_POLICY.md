# Evidence Protocol v1 — Compatibility policy

| | |
|---|---|
| Applies to | `evidence-protocol/1`, candidate revision **1.0.0-rc.1** |
| Companion to | [`SPECIFICATION.md`](SPECIFICATION.md) |

**The rule that governs all the others:** the meaning of a **verdict** and
the definition of the **signed bytes** are never changed silently. Every
other compatibility question is negotiable; those two are not.

---

## 1. Five things are versioned separately

Conflating them is the usual way a protocol becomes unauditable.

| What | Identifier | Where it lives | Example |
|---|---|---|---|
| **the protocol** | `evidence-protocol/N` | this document set | `evidence-protocol/1` |
| **a contract** (document format) | `neomundi.evidence.<kind>/N` | the `schema` property, **inside the data** | `neomundi.evidence.submission/2` |
| **a profile** | a profile name, **inside the data** | `canonicalization`, `alg` | `neomundi-jcs-strings/1` |
| **an implementation** | its own release numbering | repository tags | `verifier-rs` |
| **the conformance corpus** | semantic version | `conformance/VERSION` | `1.1.0` |

**Why each identifier travels inside the data:** a verifier must never
have to guess which rules apply. Guessing is how a document written under
one contract gets judged by another.

Two consequences:

1. A new contract version is a **new identifier**, not a redefinition of an
   old one. `submission/1` means today exactly what it meant when it was
   published.
2. An implementation's version number says **nothing** about which
   contracts it supports. It must declare them (see
   [`CONFORMANCE.md`](CONFORMANCE.md)).

---

## 2. What is allowed to change within a contract version

### 2.1 Never

| | Why |
|---|---|
| the meaning of a **verdict** | a stored `ACCEPTE` would start meaning something else, retroactively, with no trace |
| the definition of the **signed bytes** | every existing signature would become invalid or — far worse — a different signature would become valid |
| the **canonicalisation** of a profile | same reason, one step removed |
| a **required** property becoming optional, or the reverse | a document that validated stops validating, or an invalid one starts |
| the **digest algorithm** | every declared digest in every published archive |
| a **control's title**, where published counts cite it | frozen documents cite line counts; a renamed title silently changes them |

### 2.2 Allowed, with care

| | Condition |
|---|---|
| **clarifying prose** | the obligation must be unchanged; if a reader's behaviour would change, it is not a clarification |
| **a new control** | its state must be reportable as `NOT TESTED`, and the count change must be published |
| **a tightened defensive limit** | it is a property of the verifier, must be declared, and must be reportable as such (`SPECIFICATION.md` EP1-INT-040) |
| **a new optional property** in a **new** contract version | see §3 |

### 2.3 The published-count trap, stated because it has bitten

Frozen documents cite exact control counts — "21 lines on GROUNDED-S1", "18
on MED", "17 PASS, 0 FAIL, 4 NOT TESTED" on the demonstration dossier.
Adding or renaming a control line shifts those counts, and a reader
comparing a new run against a frozen document sees a divergence that is
**entirely an artefact of the change**.

Adding a control is therefore not a free action. It requires publishing the
new counts alongside the old ones.

---

## 3. Forward and backward compatibility

### 3.1 Definitions used here

| | |
|---|---|
| **Backward compatible** (verifier) | a newer verifier still reads documents written under older contracts, and reaches the same verdicts |
| **Forward compatible** (document) | a document written under a newer contract is **refused with a named reason** by an older verifier, not misread |

**EP1-COMPAT-001.** A verifier **MUST** refuse a contract identifier it
does not know, and the refusal **MUST** name the identifier found. It
**MUST NOT** fall back to the closest version it knows.

A verifier that "best-effort" read an unknown version would be applying
rules the document never agreed to. Refusal is the compatible behaviour;
guessing is not.

### 3.2 Unknown properties

Both submission contracts declare `additionalProperties: false` at the root
and in every object. So, **by the letter of the contract**, an unknown
property is a refusal.

The reference ingestion implementation **names** the surplus property and
reports it `NOT TESTED` rather than refusing. This is a **declared
divergence**, with a stated reason — refusing would break packages the
previous contract accepted — and it is pinned by a test.

**EP1-COMPAT-002.** An implementation **MUST** state which of the two it
does. Both are defensible; **silence is not**, because the two produce
different verdicts on the same package.

**EP1-COMPAT-003.** An implementation that tolerates an unknown property
**MUST NOT** report it as checked. "Tolerated and named" and "verified" are
different states, and the first is `NOT TESTED`.

### 3.3 Optional properties

**EP1-COMPAT-004.** The absence of an optional property is **not an
event**. A verifier **MUST NOT** report it, and **MUST NOT** count it as a
`NOT TESTED` line — that would inflate the uncertainty of a complete
document.

---

## 4. When a new contract version is required

A new version is required when a change would make an existing, valid
document invalid, or an existing invalid document valid. Concretely:

| Change | New version? |
|---|---|
| adding a value to a closed enumeration (e.g. a third absence reason) | **yes** — an older verifier would refuse it, correctly |
| adding a **required** property | **yes** |
| adding an **optional** property | **yes**, under `additionalProperties: false` — the letter of the contract refuses it |
| removing a property | **yes** |
| forbidding something previously accepted (duplicate JSON keys, `NaN`) | **yes** — see §5 |
| relaxing something previously refused | **yes** |
| fixing an implementation to match the contract it already published | **no** — the contract did not change |

The last row is this revision's own case: the `C-09` fix brought the Python
implementation into line with a rule the corpus already declared normative.
**No contract changed, and no expectation changed** — the corpus went from
1.0.0 to 1.1.0 on expectation *metadata* alone.

---

## 5. The three open questions, and how they may be settled

[`SPECIFICATION.md`](SPECIFICATION.md) §14 lists them: duplicate JSON keys,
`NaN`/`Infinity`, base64url strictness. All three are **silences** in the
contracts, and the two reference implementations behave differently on the
first two.

Each candidate rule is a **tightening**: it would refuse an input that one
implementation accepts today. By §4, tightening requires a new version.

**EP1-COMPAT-010.** None of the three proposals **MUST** be applied to
`submission/1` or `submission/2`. Doing so would make a package that
validated yesterday invalid today, with no version to point at.

Two routes are available, and the choice is not a technical one:

| Route | What it is | Cost |
|---|---|---|
| **successor version** — `submission/3` | the strict rules become part of a new contract; `/1` and `/2` keep their behaviour forever | producers must migrate deliberately; verifiers support three contracts |
| **negotiated strict profile** — e.g. `neomundi-strict-json/1` | the rules become a **profile**, declared inside the document; a document opts in | no new contract; a verifier must honour the profile when it is declared, and MUST NOT apply it when it is not |

The second route is cheaper and keeps `/1` and `/2` untouched, at the cost
of two reading modes for one contract. The first is cleaner and costs a
migration.

**Neither is adopted here.** The arbitration, with measured compatibility
figures, is in
[`../DEVELOPPEMENT_EVIDENCE_PROTOCOL_V1/04_ARBITRAGES_PROTOCOLE.md`](../DEVELOPPEMENT_EVIDENCE_PROTOCOL_V1/04_ARBITRAGES_PROTOCOLE.md).

---

## 6. Deprecation

**EP1-COMPAT-020.** A contract version **MUST NOT** be withdrawn while
evidence that cites it exists. Published archives, published digests and
published attestations do not get to be re-read later under a different
rulebook.

**EP1-COMPAT-021.** Deprecating a version means: announcing that producers
**SHOULD** stop using it, publishing the successor and a migration path,
and continuing to **verify** it. Verification support is not deprecated at
the same time as production support, and in practice is not deprecated at
all.

**EP1-COMPAT-022.** A key marked `compromised` with
`on_compromised_key: untrusted_retroactively` **is** a retroactive change —
the only one this protocol permits — and it is a change of **trust**, never
of **validity**. The signature stays mathematically valid; what changes is
whether it should be believed. A report **MUST** keep the two separate.

---

## 7. The conformance corpus's own versioning

`conformance/VERSION`, semantic, with rules in
[`../conformance/CHANGELOG.md`](../conformance/CHANGELOG.md):

| Change | Release |
|---|---|
| a fixture's **bytes** change | **MAJOR** — the corpus no longer measures what earlier conclusions cited |
| an expected **verdict** changes | **MAJOR** |
| a case is added or removed | **MINOR** |
| expectation **metadata** changes (a declared failure resolved) | **MINOR** |
| documentation only, no digest moves | **PATCH** |

**EP1-COMPAT-030.** A fixture whose input has not changed **MUST** keep its
digest. Regenerating it to "refresh" the corpus breaks every published
claim that cites it, in exchange for nothing.

**EP1-COMPAT-031.** A conformance result **MUST** cite the corpus version
it was obtained against. "Passes the corpus" without a version is not a
checkable statement.

---

## 8. Compatibility claims this document does not make

| Not claimed | Why |
|---|---|
| conformance to **DSSE**, **in-toto**, **Sigstore** | no test establishes it; the comparison in `03_ETUDE_STANDARDS.md` is a comparison, not a claim |
| conformance to **RFC 8785** | the profile is a strict, differently-named subset |
| that any **third-party receipt format** is supported in general | reconciliation works where a map declares a correspondence, and nowhere else |
| that verification behaves identically on **Windows** or **macOS** | CI runs one platform; one measured platform-dependence is documented in `../DEVELOPPEMENT_EVIDENCE_PROTOCOL_V1/08_LIMITES.md` §3 |
