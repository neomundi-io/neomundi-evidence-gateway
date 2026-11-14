# Evidence Protocol v1 — Candidate Specification

| | |
|---|---|
| **Status** | **Candidate Specification** — not a final standard |
| Version | `evidence-protocol/1`, candidate revision **1.0.0-rc.1** |
| Date | 11 November 2026 |
| Corpus of record | [`conformance/`](../conformance/README.md) version **1.3.0** |
| Licence | Apache-2.0 |

**Why "Candidate" and not "final":** **four** normative questions are still
open (§14), and on **all four** the two reference implementations are
measured as disagreeing on at least one case — the fourth
(`E-08`, a `.` path segment) was found on 11 November when the bench's
comparison instrument was corrected. A specification that called itself final while its
own implementations disagree on three inputs would be claiming a stability
it does not have. The open points are named, their current behaviour is frozen
and testable, and arbitration proposals exist — but **no proposal is
normative yet**.

This document is intended to be sufficient on its own. A reader
implementing Evidence Protocol v1 should not need to read `verify.py`,
`adapters/ingest.py`, `verifier-rs/` or `verifier-rs-crypto/`. Where this
document is silent, it says so, and silence is never to be read as
permission or prohibition (§2.3).

---

## 1. Scope

Evidence Protocol v1 defines how to **produce**, **transport** and
**verify** evidence of an execution: what was run, which bytes were
produced, who states what about them, and what remains unproven.

It defines:

- the structure of a **submission package** and of an **Evidence archive**;
- the integrity rules a verifier applies to them;
- a signature and trust profile for **attestations**;
- the conventions for **declared absences**;
- the comparison rules for **third-party receipts** (reconciliation);
- the vocabulary of **verdicts**, **control states** and **exit codes**.

It does **not** define:

- how an execution is performed, by what system, or with what model;
- how scores or measurements are computed;
- an identity or registration authority;
- a transport protocol, an API, or a storage service.

**The NeoMundi API is not a component of this protocol.** Nothing in this
document requires it, and a conforming implementation MUST be able to
verify evidence produced entirely by a third-party system. The reference
implementations in this repository are one implementation each of the
producer and verifier roles; they are not the protocol.

---

## 2. Normative language

### 2.1 Keywords

The keywords **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT** and **MAY**
are to be interpreted as in RFC 2119 and RFC 8174, and only when they
appear in capitals.

### 2.2 What each keyword binds

| Keyword | Meaning in this document |
|---|---|
| **MUST** / **MUST NOT** | An implementation that does otherwise is **not conforming**. A conformance case exists, or the obligation is marked as an uncovered gap in [`CONFORMANCE.md`](CONFORMANCE.md). |
| **SHOULD** / **SHOULD NOT** | Departing is permitted when the implementer has a reason and **states it**. A silent departure is a defect of documentation, not of conformance. |
| **MAY** | Genuinely optional. A verifier MUST NOT treat the absence of a MAY feature as a failure of the thing being verified. |

### 2.3 Three things this document distinguishes, and never mixes

| Term | Meaning |
|---|---|
| **Historical format** | A structure actually published and in use. It is described here as it is, including where it is inconsistent. It is **not** renamed, and no new obligation is applied to it retroactively. |
| **Normative rule** | An obligation stated here with MUST / MUST NOT. |
| **Profile** | A named set of conventions for one context (a signature profile, a canonicalisation profile, an ingestion profile). A profile is referenced by name **inside the data**, so a verifier never has to guess which one applies. |
| **Extension** | An optional, versioned capability. A verifier MAY implement it; its absence is never a conformance failure. |
| **Proposal** | A behaviour discussed for a future version. **Never applicable.** Proposals live in [`../DEVELOPPEMENT_EVIDENCE_PROTOCOL_V1/04_ARBITRAGES_PROTOCOLE.md`](../DEVELOPPEMENT_EVIDENCE_PROTOCOL_V1/04_ARBITRAGES_PROTOCOLE.md), not here. |

### 2.4 Silence

Where this document does not state a rule, an implementation MAY choose its
behaviour, and MUST be able to say which choice it made. Two conforming
implementations can disagree on a silent point; §14 lists every silence
known to produce a measured disagreement today.

A reader MUST NOT infer an obligation from the behaviour of a reference
implementation. Behaviour is evidence of what is possible, not of what is
required.

---

## 3. Architecture

### 3.1 The objects

| Object | What it is |
|---|---|
| **Producer** | Whoever assembles evidence. Any system. The protocol never requires it to identify itself to anyone. |
| **Artifact** | A file whose **bytes** are the evidence — a prompt, a response, a log, a dataset extract. |
| **Submission package** | A directory or ZIP containing a **submission manifest** (`submission.json`) and the artifacts it declares. |
| **Evidence archive** | A ZIP containing a **manifest**, a checksum list, and the members the manifest declares. Produced by an exporting system; larger and more structured than a submission package. |
| **Manifest** | The JSON document that declares what the package or archive contains: paths, sizes, SHA-256 digests, and declarations about the execution. |
| **Receipt** | A third party's own record of an execution, in that third party's format, imported without being reinterpreted. |
| **Attestation** | A **detached JWS** whose payload states digests of an Evidence archive, plus the identities and the time its signer declares. |
| **Trust store** | A JSON document listing public keys, the identities they are attributed to, and the **policy** for reading them. |
| **Verifier** | A program that reads one of the above and produces a **verification report**. |
| **Verification report** | The verifier's output: one line per control, each with a **state**, plus a **verdict** and an **exit code**. |

### 3.2 How they relate

```
      artifacts (bytes)
            │  declared by path + sha256 + bytes
            ▼
   submission manifest ──────────────► VERIFIER ──► verification report
   (submission/1 or /2)                  ▲                 │
                                         │                 ├─ verdict
      Evidence archive ──────────────────┤                 ├─ control states
      (ZIP + manifest + checksums)       │                 └─ exit code
            │                            │
            │ digests of the archive     │
            ▼                            │
      attestation (detached JWS) ────────┤
            │                            │
            │ key_id                     │
            ▼                            │
        trust store ────────────────── policy
            │
            └─ (optional) timestamp descriptor + proof ──► external anchor

      third-party receipt ──┐
                            ├── reconciliation map ──► per-field status
      our own record    ────┘
```

Three properties of this picture are normative:

1. **An artifact is identified by its bytes**, never by its name alone
   (§6).
2. **An attestation commits to digests, not to files.** It can be verified
   against an archive that has been moved, renamed, or copied — and it
   fails against an archive whose bytes differ (§7).
3. **A trust store is read through its policy.** The same key, the same
   signature and two different policies legitimately give two different
   results (§8).

---

## 4. Contracts and versions

### 4.1 Status of each published contract

| Contract identifier | Kind | Status | Schema |
|---|---|---|---|
| `neomundi.evidence.submission/1` | submission manifest | historical format, **supported** | `schemas/evidence-submission-v1.json` |
| `neomundi.evidence.submission/2` | submission manifest | historical format, **supported** — adds declared absence of model identity | `schemas/evidence-submission-v2.json` |
| `neomundi.evidence.manifest/1` | Evidence manifest | historical format | `schemas/evidence-manifest-v1.json` |
| `neomundi.evidence.attestation/1` | attestation payload | historical format | `schemas/evidence-attestation-v1.json` |
| `neomundi.evidence.trust-store/1` | trust store | historical format | `schemas/evidence-trust-store-v1.json` |
| `neomundi.evidence.external-receipt/1` | imported receipt | historical format | `schemas/evidence-external-receipt-v1.json` |
| `neomundi.evidence.reconciliation-map/1` | reconciliation map | historical format | `schemas/evidence-reconciliation-map-v1.json` |
| `neomundi.evidence.timestamp/1` | timestamp descriptor | historical format | `schemas/evidence-timestamp-v1.json` |
| `neomundi.evidence.external-link/1` | external-link declaration | **candidate** — never yet exercised by a third party | `schemas/evidence-external-link-v1.json` |
| `neomundi.evidence.external-link-report/1` | external-link verifier output | **candidate** | `schemas/evidence-external-link-report-v1.json` |
| `station.export.campagne/2`, `/3` | Evidence archive manifest | **external** to this repository — produced by an exporting system; recognised, not defined here | — |
| `neomundi-jcs-strings/1` | canonicalisation profile | **profile** | `canonical.py` (§5) |
| `json-sorted-compact/1` | canonicalisation profile | **external** profile — emitted by a measuring system, recognised and recomputable here, **not** an Evidence profile (§4.6) | — |
| `neomundi.evidence.verification-report/1` | verifier output | historical format | — (described in §10) |

**EP1-VER-040.** The two `external-link` contracts are **candidate**, not
historical. A candidate contract **MAY** change between revisions, and an
implementation **MUST NOT** treat it as frozen. The distinction is recorded
because the eight contracts above it have been exercised and these two have
not: `external-link/1` has so far been exercised only by documents **we**
wrote.

**EP1-VER-001.** Every document defined by this protocol **MUST** carry a
`schema` property whose value is the exact contract identifier above.

**EP1-VER-002.** A verifier **MUST NOT** apply the rules of one contract
version to a document that declares another. A document declaring an
unknown identifier **MUST** be refused, and the refusal **MUST** name the
identifier found.

### 4.2 Two inconsistencies in the published set, described as they are

These are stated because a third party reading the schemas will hit them.
Neither is corrected here: correcting a published `$id` is a contract
change, and contract changes are out of scope for this revision.

1. **`$id` is not uniform.** The six non-submission schemas use absolute
   URLs (`https://neomundi.io/schemas/...`). The two submission schemas use
   the bare contract identifier (`neomundi.evidence.submission/1`), which
   is a valid relative URI-reference but resolves differently. An
   implementation **SHOULD** identify a contract by its `schema` property
   value, **not** by resolving `$id`.

2. **`neomundi.evidence.manifest/1` and `station.export.campagne/*` are both
   "the manifest".** The first is this repository's own manifest format for
   a signed bundle; the second is the manifest of an Evidence archive
   produced by an exporting system. They are different documents with
   different required properties. The `schema` property disambiguates them;
   nothing else does.

### 4.3 Difference between `/1` and `/2`

`/2` differs from `/1` in exactly one place: `execution.model_declared` MAY
be `null`, and a `null` then obliges two companion properties (§9.2). Every
other property is identical, including `additionalProperties: false` at the
root and in every object.

**EP1-VER-003.** A `/1` manifest **MUST NOT** carry a `null`
`model_declared`. A `/1` manifest whose `model_declared` is `null`
**MUST** be refused.

### 4.4 Three rules the schemas state, restated here

These were implicit in "validate against the schema". They are written out
because a third party implementing from this document alone would otherwise
have to infer them — and because the conformance matrix found them missing
(`../DEVELOPPEMENT_EVIDENCE_PROTOCOL_V1/05_MATRICE_NORMATIVE.md` §4).

**EP1-VER-004.** A manifest missing any **required** property **MUST** be
refused, and the refusal **MUST** name the property. The required sets are
those the schemas declare; both submission contracts require `schema`,
`submission_id`, `submitted_at_declared`, `pilot`, `execution` and
`artifacts`.

**EP1-VER-005.** A manifest **MUST** be a readable UTF-8 JSON **object**.
Bytes that are not valid UTF-8, text that is not valid JSON, and a JSON
value that is not an object **MUST** each be refused with a reason that says
**which** of the three happened. Collapsing them into one message makes a
producer debug the wrong layer.

**EP1-VER-006.** When every applicable control passes, the verdict **MUST**
be `ACCEPTED`. A verifier **MUST NOT** refuse a package for a reason it
cannot name as a failed control — a gratuitous refusal is as much a false
report as a gratuitous acceptance, and it is the half that is rarely
tested.

---

### 4.6 Two canonicalisation profiles, and why they are not interchangeable

`neomundi-jcs-strings/1` and `json-sorted-compact/1` both sort keys and emit
compact JSON. They are **not** the same profile, and this specification
names both so that the difference cannot be read as an inconsistency.

| | `neomundi-jcs-strings/1` | `json-sorted-compact/1` |
|---|---|---|
| Defined by | this repository (§5, `canonical.py`) | an external measuring system |
| Numbers | **FORBIDDEN** — every value is a string | **permitted** (`0.3863`, `1.0`) |
| Booleans | **FORBIDDEN** | permitted |
| Used by | Evidence attestations | audit-trail exports recognised by `external-link/1` |

**EP1-VER-041.** A verifier **MUST NOT** recompute a digest declared under
one profile using the other. The forbidden-number rule is what makes
`neomundi-jcs-strings/1` equivalent to RFC 8785 **on its domain**; applying
that domain to a record carrying numbers would either fail or silently
canonicalise something else.

**EP1-VER-042.** `adapters/external_link.py` recomputes `json-sorted-compact/1`
and **refuses** any other canonicalisation with `NON VERIFIABLE`. It does
**not** recompute `neomundi-jcs-strings/1`: that profile belongs to the
attestation path, which `verify_attestation.py` already covers, and
duplicating a cryptographic engine is how two implementations begin to
disagree. The boundary is deliberate, and §11 records what it leaves open.

**EP1-VER-043.** A digest declared with `byte_length_declared` **MUST** have
that length confronted with the bytes actually hashed whenever the material
is available, and a mismatch **MUST** be reported. For a coverage of kind
`canonical_record` the length is that of the **canonical projection**, never
that of the file: an audit-trail export of 752 bytes legitimately carries a
digest over a 451-byte projection, and measuring the file would manufacture
a false mismatch.

**EP1-VER-044.** A declared issuer **MUST NOT** be reported as
authenticated. `external-link/1` carries no attestation, and a verifier
**MUST NOT** resolve an issuer-supplied verification URL to decide:
a verdict that depends on reaching the issuer's own service is not a
verdict a third party can reproduce.


## 5. Canonicalisation

### 5.1 Where canonicalisation applies — and where it does not

This is the most common source of error when implementing a protocol of
this kind, so it is stated before the profile itself:

| Object | Canonicalisation |
|---|---|
| submission manifest | **none** — hashed and read as the bytes on disk |
| artifact | **none** — an artifact is its bytes |
| Evidence archive member | **none** — hashed as stored |
| attestation payload, **when produced** | profile `neomundi-jcs-strings/1` |
| attestation payload, **when verified** | **none** — see EP1-CAN-004 |

**EP1-CAN-001.** An implementation **MUST NOT** canonicalise a document
before computing a digest that the protocol compares to a declared digest.
Declared digests are over stored bytes.

**EP1-CAN-004.** Signature verification **MUST** use the bytes carried
verbatim by the JWS, never a re-serialisation of the parsed payload. The
canonicalisation profile takes **no part** in signature verification.

This separation is deliberate and load-bearing. If a verifier re-serialised
the payload before verifying, then any disagreement between its serialiser
and the signer's would invalidate a perfectly good signature — and the
failure would look like tampering.

### 5.2 Profile `neomundi-jcs-strings/1`

A restricted profile, equivalent to RFC 8785 (JCS) **on its domain only**:

1. UTF-8, **no** byte-order mark.
2. Serialisation equivalent to
   `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`.
3. Permitted value types: **string**, `null`, object, array of permitted
   values. **Numbers and booleans are forbidden.**
4. Every object key matches `^[a-z0-9_]+$`.

**EP1-CAN-002.** A document that declares `canonicalization:
"neomundi-jcs-strings/1"` **MUST** satisfy all four rules. A verifier
**SHOULD** check them and report the result as a control **distinct** from
signature verification.

**EP1-CAN-003.** A profile check failure **MUST NOT** be reported as a
signature failure, and a signature failure **MUST NOT** be reported as a
profile failure. They are different facts with different consequences.

### 5.3 Why the restriction, and what it costs

RFC 8785 is hard in three places. This profile removes two of them and
inherits the third:

| JCS difficulty | In this profile |
|---|---|
| **number formatting** (ECMAScript rules: `1.0` → `1`, `1e-07` → `1e-7`) | **removed** — numbers are forbidden. A count travels as `"30"`, not `30`. |
| **key ordering** (JCS sorts on UTF-16 code units; most languages sort on code points — the orders differ outside the BMP) | **removed** — keys restricted to `[a-z0-9_]`, where both orders coincide |
| **string escaping** | inherited — JSON serialisers in common use already agree with JCS here |

**Outside this domain the equivalence does not hold.** That is why the
domain is restricted rather than the implementation extended: a signed
object has no need of numbers, and doing without one costs a pair of
quotation marks.

**EP1-CAN-005.** An implementation **MUST NOT** claim RFC 8785 conformance
on the basis of implementing this profile. The profile is a strict subset
with a different name, declared in the data.

---

## 6. Integrity

### 6.1 Digests and sizes

**EP1-INT-001.** Declared digests **MUST** be SHA-256, lowercase
hexadecimal, 64 characters.

**EP1-INT-002.** A verifier **MUST** recompute the digest of every artifact
it can read, and **MUST** refuse the package when a recomputed digest
differs from the declared one.

**EP1-INT-003.** When a size is declared, a verifier **MUST** compare it to
the actual byte count and **MUST** refuse on divergence — even if the
digest matches. A digest that matches a wrong size means the declaration is
internally inconsistent, and an inconsistent declaration is not evidence.

**EP1-INT-004.** An artifact of **zero bytes** is valid. Its digest is the
SHA-256 of the empty string. A verifier **MUST NOT** refuse a package for
this reason alone.

### 6.2 Paths

**EP1-INT-010.** A declared path **MUST** be relative, **MUST NOT** be
empty, and **MUST NOT** escape the package root. A verifier **MUST** refuse
a package carrying such a path, and **MUST** do so **before** reading the
file.

**EP1-INT-011.** A declared path **MUST NOT** be absolute, in any
convention: POSIX (`/etc/passwd`), Windows drive (`C:\...`) and UNC
(`\\host\share`) are all refused.

**EP1-INT-012.** A verifier **MUST NOT** treat `\` as a path separator when
reading a declared path. A path containing `\` is refused rather than
reinterpreted: reinterpreting it would make the same manifest mean two
different things on two systems.

**EP1-INT-013.** A ZIP container **MUST NOT** declare the same member name
twice. A verifier **MUST** refuse such a container; which of the two
members a reader would get is not determined by the format.

Two path questions are **open** and produce no obligation here: a path
declared twice in `artifacts`, and a path containing a `.` segment
(§14.4).

### 6.3 Missing and surplus files

**EP1-INT-020.** A declared artifact whose file is absent **MUST NOT** be
reported as verified. The verifier **MUST** distinguish *absent* from
*wrong*: an absent file makes the package **incomplete**, a file with the
wrong bytes makes it **refused** (§10.1).

**EP1-INT-021.** A file present in the package but **not** declared in the
manifest **MUST NOT** silently pass. A verifier **MUST** report it. Whether
it refuses or merely reports is a policy the verifier **MUST** state.

> **The reference ingestion implementation states its policy** in
> [`docs/SUBMISSION.md`](../docs/SUBMISSION.md) §2: it **reports and does not
> refuse** — `NOT TESTED`, paths named, not marked required, so the verdict
> stays `ACCEPTE` and the exit code `0`, **`--strict` included**. Until
> 12 November 2026 that policy existed only as a source comment, which left
> the `MUST state` half of this rule unmet while the `MUST report` half was
> already satisfied.

### 6.4 ZIP containers

**EP1-INT-030.** A verifier **MUST** refuse a container that is not a valid
ZIP, and the refusal **MUST** be a verdict — see EP1-VER-020.

**EP1-INT-031.** A verifier **MUST** verify the CRC-32 of each member it
reads, and **MUST** refuse a container carrying a member whose CRC-32 does
not match.

**EP1-INT-032.** A verifier **MUST** refuse a container in which a local
file header disagrees with the central directory about a member's name.

**EP1-INT-033.** A member whose compressed stream is **invalid** — an
unparseable DEFLATE stream, a reserved block type (RFC 1951 §3.2.3), a
truncated stream — **MUST** produce a refusal **with a verdict**, never an
unhandled error. See EP1-VER-021, and §13 for the measured history of this
rule.

**EP1-INT-034.** A verifier **MUST NOT** decode "as much as possible" of a
damaged stream and verify the part that decoded. Partial decoding of
evidence is not evidence of a part.

**EP1-INT-035.** A verifier **MUST** bound what it reads from a container
before reading it: declared member counts, declared sizes and declared
offsets **MUST** be checked for internal consistency first. An
implementation **SHOULD** publish the bounds it enforces; the bounds
themselves are a **defensive limit**, not a protocol rule (§6.5).

### 6.5 Contractual guarantees vs. defensive limits

| | |
|---|---|
| **Contractual** | Rules EP1-INT-001 … 034. A conforming verifier applies them. They are properties of the evidence. |
| **Defensive** | Size caps, node caps, nesting caps, refusal of ZIP64, time limits. They are properties of the **verifier**, chosen to make it safe to run on hostile input. |

**EP1-INT-040.** A verifier **MAY** impose defensive limits, **MUST**
report a refusal caused by one as such — distinguishable from a refusal
caused by a contractual rule — and **MUST NOT** present a defensive refusal
as a statement about the evidence.

**EP1-INT-041.** An implementation **MUST NOT** require another
implementation to enforce the same defensive limits in order to call it
conforming.

---

## 7. Attestations: signature profile

### 7.1 Form

**EP1-SIG-001.** An attestation **MUST** be a JWS in **compact
serialisation** (RFC 7515 §3.1), with exactly three parts separated by two
`.` characters: `header.payload.signature`.

**EP1-SIG-002.** The signed bytes **MUST** be
`ASCII(BASE64URL(header)) ‖ "." ‖ ASCII(BASE64URL(payload))`
— the two encoded parts exactly as they appear in the token, taken
**verbatim** (RFC 7515 §5.2 step 8).

**EP1-SIG-003.** A verifier **MUST NOT** re-encode either part before
verifying. See EP1-CAN-004.

### 7.2 The algorithm is imposed, not read

**EP1-SIG-010.** A verifier of this profile **MUST** use Ed25519 (RFC 8032)
regardless of what the JWS header `alg` claims. It **MUST** compare the
header's `alg` to `"EdDSA"` and refuse on mismatch — but it **MUST NOT**
select its algorithm from that field.

This is the parade against algorithm confusion. A verifier that chose its
algorithm from the token lets the token's author choose how it is checked,
including choosing `"none"`.

**EP1-SIG-011.** A verifier **MUST** refuse `alg: "none"`, and **MUST NOT**
implement an unsigned mode.

**EP1-SIG-012.** Ed25519 verification **MUST** be strict in the sense of
RFC 8032 §5.1.7: non-canonical encodings of `R` or `S`, and small-order
public keys, **MUST** be refused rather than accepted by a permissive
equation.

### 7.3 Payload

**EP1-SIG-020.** The payload **MUST** be a JSON object declaring
`schema: "neomundi.evidence.attestation/1"` and
`canonicalization: "neomundi-jcs-strings/1"`.

**EP1-SIG-021.** The payload **MUST** declare the digests of its subject:
`subject.bundle_sha256`, and — when the subject is an Evidence archive —
`subject.manifest_sha256` and `subject.checksums_sha256`.

**EP1-SIG-022.** A verifier **MUST** compare **every** digest the payload
declares against the subject it was given, and **MUST** refuse on any
divergence. Checking one of three declared digests and reporting
"concordance" is a false report: the other two are what detect a member
substituted inside an otherwise correct archive.

**EP1-SIG-023.** `attestation_kind` **MUST** be `contemporaneous` or
`retrospective`. A `retrospective` attestation states that the signature
was made **after** the fact; a verifier **MUST NOT** present it as
contemporaneous evidence, and **MUST** carry the distinction into its
report.

**EP1-SIG-024.** `attested_at_declared` is a **declaration by the signer**.
A verifier **MUST NOT** present it as a verified time. Only an external
anchor can do that (§11).

### 7.4 Key identification

**EP1-SIG-030.** The payload **MUST** carry `key_id`, matching
`^[a-z0-9][a-z0-9-]{2,63}$`, and the verifier **MUST** resolve the key by
that identifier in the trust store.

**EP1-SIG-031.** A verifier **MUST NOT** take a public key from the
attestation itself, nor from a JWS header (`jwk`, `jku`, `x5u`, `x5c`). A
key that travels with the signature it verifies proves only that the
signer holds a key.

**EP1-SIG-032.** When `key_id` resolves to **no** key in the supplied trust
store, the trust pillar **MUST** be reported as **not tested** — not as a
failure. An unknown key is not a false key (§8.2).

---

## 8. Trust

### 8.1 The five pillars, and what they add up to

A verifier of attestations **MUST** report these five facts separately:

| # | Pillar | Question |
|---|---|---|
| 1 | **profile** | Does the payload declare, and satisfy, the canonicalisation profile? |
| 2 | **header** | Is the JWS header well-formed, and is its `alg` the expected one? |
| 3 | **signature** | Does the Ed25519 signature verify over the verbatim signed bytes? |
| 4 | **trust** | Does the key resolve in the supplied store, and does the policy accept it? |
| 5 | **concordance** | Do **all** declared digests match the subject supplied? |

**EP1-TRU-001.** The level `cryptographically_attested` **MUST NOT** be
derived unless the pillars the implementation declares as required are all
`PASS`. An implementation **MUST** publish which pillars it requires.

**EP1-TRU-002.** A verifier **MUST NOT** report a single aggregate result
in place of the five pillars. One number cannot say *which* of five
different things failed, and each failure has a different meaning.

### 8.2 Policy

A trust store **MUST** carry a `verification_policy`. The policy decides
what a resolved key means — not whether the mathematics worked.

| Policy field | Question it answers |
|---|---|
| `accepted_algorithms`, `accepted_curves` | which signature profiles this store authorises at all |
| `on_unknown_key` | a `key_id` absent from the store |
| `on_expired_key` | the attestation is dated after `valid_until_declared` |
| `on_rotated_key_within_window` / `..._after_window` | the key was superseded; the attestation predates or postdates the handover |
| `on_compromised_key` | the key is marked compromised |
| `on_test_key` | the store, or the key, is marked `test` |

**EP1-TRU-010.** A verifier **MUST** read the policy from the store it was
given, and **MUST NOT** substitute a default of its own when the store
states one.

**EP1-TRU-011.** An unknown key **MUST** map to **not tested**, never to
failure, unless the policy says otherwise. "Unknown" and "false" are
different facts; reporting the first as the second is how a verifier
manufactures a conclusion it has not reached.

**EP1-TRU-012.** `on_compromised_key: untrusted_retroactively` **MUST**
withdraw trust from attestations that **predate** the compromise report.
An implementation that only distrusted later attestations would be reading
the field as `untrusted_from_now`, which is a different policy with a
different name.

**EP1-TRU-013.** A key or store marked `test` **MUST NOT** yield a trusted
result unless the caller explicitly allows test keys, and the report
**MUST** say that it did.

### 8.3 The four guarantees, which MUST stay separate

| # | Guarantee | Established by |
|---|---|---|
| 1 | **the bytes are the ones declared** | digest comparison (§6) |
| 2 | **the signature is cryptographically valid** | Ed25519 verification over the verbatim bytes (§7) |
| 3 | **the key is trusted** | the store **and its policy** (§8.2) |
| 4 | **the signer is who it claims to be** | **nothing in this protocol** |

**EP1-TRU-020.** An implementation **MUST NOT** report "identity verified",
or any equivalent, on the strength of guarantees 1–3. A trust store
**declares** identities; no code in this protocol verifies them.

**EP1-TRU-021.** None of the four guarantees, alone or together,
establishes that **the attested event occurred as described**. A valid
signature over a false statement is a valid signature.

---

## 9. Declared absences

### 9.1 Four different absences

The protocol distinguishes four situations that a careless implementation
collapses into one:

| Situation | Representation | What a verifier reports |
|---|---|---|
| an **optional property** is not stated | the property is absent | nothing — absence of an optional property is not an event |
| a value is **deliberately not stated**, and why is given | `null` + a reason + a note | the declaration is **read and reported**; the value stays unknown |
| a **control could not be run** | — | `NOT TESTED`, naming what was missing |
| the thing to be verified is **absent from the package** | — | the package is **incomplete** (EP1-INT-020) |

**EP1-ABS-001.** A verifier **MUST NOT** report `PASS` for a control it did
not run. An unrun control **MUST** be `NOT TESTED`, and the report **MUST**
say what would make it runnable.

**EP1-ABS-002.** A verifier **MUST NOT** count `NOT TESTED` towards a
coverage or success figure without publishing it as a separate number.

### 9.2 The declared-absence convention of `submission/2`

In `/2`, `execution.model_declared` MAY be `null`, meaning *the submitter
declares that no model identity is being stated*.

**EP1-ABS-010.** A `null` `model_declared` **MUST** be accompanied by
`model_absence_reason_declared` ∈ {`not_applicable`, `unavailable`} **and**
a non-empty `model_absence_note_declared`. Without both, the absence is
indistinguishable from an oversight, and the manifest **MUST** be refused.

**EP1-ABS-011.** The two reasons are not interchangeable:
`not_applicable` means **no model took part at all**; `unavailable` means a
model took part and its identity cannot be stated. A verifier **MUST NOT**
rewrite one as the other, and **MUST NOT** fill either in on the
submitter's behalf.

**EP1-ABS-012.** A **named** model **MUST NOT** also carry an absence
reason. Declaring both contradicts itself, and the manifest **MUST** be
refused.

**EP1-ABS-013.** An implementation **MUST NOT** require a reason vocabulary
larger than the one the contract publishes. Adding reasons is a contract
change (see [`COMPATIBILITY_POLICY.md`](COMPATIBILITY_POLICY.md) §4).

---

## 10. Verdicts, reports and exit codes

### 10.1 Verdicts

| Verdict | Meaning |
|---|---|
| **ACCEPTED** (`ACCEPTE`) | every applicable control ran and passed |
| **REFUSED** (`REJETE`) | at least one control failed |
| **INCOMPLETE** (`INCOMPLET`) | nothing failed, but something required to conclude was absent |

**EP1-VER-010.** `INCOMPLETE` **MUST NOT** be reported as `ACCEPTED`, and
**MUST NOT** be reported as `REFUSED`. It is the verdict that says *the
question has not been answered*, and collapsing it into either one answers
a question that was not asked.

**EP1-VER-011.** A verdict **MUST** be derivable from the control states in
the same report. A report whose verdict does not follow from its own lines
is self-contradictory and **MUST NOT** be produced.

### 10.2 Control states

| State | Meaning |
|---|---|
| `PASS` | the control ran and the property holds |
| `FAIL` | the control ran and the property does not hold |
| `NOT TESTED` | the control did not run; the report says why |

**EP1-VER-012.** These three states are **terms of the contract**, not
prose. An implementation **MUST NOT** translate or localise them, and
**MUST NOT** add a fourth state to this set without declaring it as an
extension.

**EP1-VER-013.** A verifier **MUST** report one line per control it
attempted, each carrying its state and, when the state is not `PASS`, a
reason naming what was found.

### 10.3 Exit codes

| Code | Meaning |
|---|---|
| **0** | no control failed |
| **1** | at least one control failed |
| **2** | a **required** guarantee was not demonstrated, in strict mode |
| **3** | the verifier could not run (reserved; used by the Rust implementations) |

**EP1-VER-020.** A verifier **MUST NOT** exit with a non-zero code without
also producing a report. A bare non-zero exit is indistinguishable from a
legitimate refusal, and a reader of a script cannot tell them apart.

**EP1-VER-021.** A verifier **MUST NOT** let an error escape as an
unhandled exception, a stack trace, or a crash, on **any** input. Malformed
input is the normal case for a verifier, and a crash on malformed input is
a refusal the reader cannot distinguish from a verdict.

**EP1-VER-022.** A **strict mode** MAY change exit codes. It **MUST NOT**
change any verdict or any control state. The same evidence does not become
more or less valid because the caller passed a flag.

**EP1-VER-023.** Exit codes are a property of a **tool**, not of the
protocol's semantics. An implementation offering a different interface — a
library, an HTTP service — **MUST** carry the verdict and the control
states, and MAY have no exit code at all.

### 10.4 Machine-readable report

**EP1-VER-030.** A machine-readable report **SHOULD** be offered. When it
is, it **MUST** carry the three state counts as **three distinct fields**.
A consumer reading only `pass` and `fail` would otherwise believe coverage
was complete.

**EP1-VER-031.** A machine-readable report **SHOULD** carry an explicit
statement of what it does **not** establish. The reference reports carry
authenticity, origin and "that the execution took place".

---

## 11. Timestamping

**EP1-TS-001.** A timestamp descriptor **MUST** declare the digest of its
subject, the digest of the proof file, the calendars submitted to, and
`state_at_stamping` ∈ {`pending`, `confirmed`}.

**EP1-TS-002.** A `pending` proof **MUST NOT** be presented as an attested
date. It records a submission, not a confirmation.

**EP1-TS-003.** A verifier **MUST NOT** derive any time guarantee from an
offline verification. Without an external anchor, every date in the
evidence is a **declaration**.

---

## 12. Reconciliation with a third-party receipt

### 12.1 What reconciliation is, and is not

A receipt is a third party's record, in the third party's format. Importing
it **MUST NOT** reinterpret it.

**EP1-REC-001.** An importer **MUST** record the receipt's own bytes and
their digest, and **MUST** preserve the values it extracts **verbatim**.

**EP1-REC-002.** The protocol **MUST NOT** presume that a model was used,
that an execution came from any particular system, or that the receipt's
fields mean the same things as ours. A correspondence between a receipt
field and one of ours exists only where a **reconciliation map** declares
it.

**EP1-REC-003.** Without an entry in the map, a field **MUST** be
`NOT COMPARABLE`. Guessing a correspondence by name similarity **MUST NOT**
be done.

### 12.2 The five statuses

| Status | Meaning |
|---|---|
| `MATCHED` | both sides present, comparable, equal |
| `MISMATCHED` | both sides present, comparable, **different** |
| `MISSING` | one side absent |
| `NOT VERIFIABLE` | present, but we cannot recompute it |
| `NOT COMPARABLE` | both present, and a comparability boundary is crossed |

**EP1-REC-010.** Comparability **MUST** be evaluated **before** value
equality. Two different values are a divergence of computation only if they
measure the same thing: same definition, same measurement version, same
coverage.

**EP1-REC-011.** A field that is not comparable **MUST NOT** be reported
`MISMATCHED`. Reporting it so would state a discovery where there is a
reasoning error.

**EP1-REC-012.** A reconciliation **MUST NOT** average, arbitrate, or
otherwise resolve a divergence the data does not resolve. Both values
**MUST** be preserved as they are.

**EP1-REC-013.** A reconciliation **MUST NOT** raise an assurance level on
the strength of a declaration, and **MUST NOT** describe as "signed"
anything whose signature it has not verified.

**EP1-REC-014.** An ambiguous label — a receipt carrying the same label on
several fields — **MUST NOT** be resolved by choosing the first. The map
**MUST** disambiguate it, or the field stays `NOT COMPARABLE`.

---

## 13. One rule with a measured history

EP1-INT-033 and EP1-VER-021 are written as they are because of a measured
failure, not from principle.

Case `C-09-archive-deflate-invalid` of the conformance corpus presents an
archive whose member announces DEFLATE and carries an invalid stream. At
corpus version 1.0.0, the Python reference implementation let a
`zlib.error` escape: **exit code 1, no verdict, no report**. The Rust
implementation refused the same input with a reasoned report.

Exit 1 with no verdict is indistinguable from a legitimate refusal. A
reader of a script sees `1`, concludes "refused", and is right by accident.

The defect was fixed in this revision; the corpus moved to 1.1.0 **without
changing a single expectation**, because the expectation had been right all
along. The full record is in
[`../conformance/CHANGELOG.md`](../conformance/CHANGELOG.md) and the
`resolved` section of `known_failures.json`.

The rule is in this specification so that a third-party implementation does
not have to rediscover it.

---

## 14. Open normative questions

Four. Each is **measured**, and **none is arbitrated here**. Three of the
four produce a measured disagreement between the reference implementations. Full analysis and proposals:
[`../DEVELOPPEMENT_EVIDENCE_PROTOCOL_V1/04_ARBITRAGES_PROTOCOLE.md`](../DEVELOPPEMENT_EVIDENCE_PROTOCOL_V1/04_ARBITRAGES_PROTOCOLE.md).

### 14.1 Duplicate JSON object keys

RFC 8259 §4 says the behaviour is **undefined**. The two reference
implementations disagree: one accepts and keeps the **last** occurrence,
the other refuses. Corpus: `G-01`, and `G-02` where the duplicated key is a
**digest**.

**No obligation is stated.** An implementation **MUST** be able to say
which it does.

### 14.2 `NaN` and `Infinity`

Outside RFC 8259 §6. One reference implementation accepts them through its
JSON library; the other refuses. Corpus: `G-03`, `G-04`.

### 14.3 base64url strictness

RFC 7515 §2 requires base64url **without** padding. Whether a decoder
**tolerates** padding, or the standard alphabet (`+`, `/`), is not
specified. Corpus: `G-06`, `G-07`.

**Measured, and it is a disagreement.** On `G-07` — the signature segment
rewritten in the standard alphabet — the Python implementation **accepts**
(exit 0, signature pillar `PASS`) and the Rust implementation **refuses**
(exit 1, naming the alphabet). So an attestation whose signature segment is
not valid base64url is reported as cryptographically valid by one of the two.

On `G-06` the two **agree**, and until 11 November they agreed with
**different diagnoses**: Rust named the padding; Python reported that *the
key did not sign these bytes* — true of the mangled bytes, and blaming the
wrong component. Python now names the encoding and says the key is not at
fault. **No verdict changed**: whether a verifier must *refuse* these
deviations is this very open question, and settling it here would apply a
new rule to a historical contract.

Both behaviours are now **frozen per verifier** in the corpus sheets
(version **1.2.0**), as `G-01`–`G-05` already were. Until 1.1.0 they were
not, and the bench — which measured both verdicts — never compared them: the
`G-07` disagreement was in the data and invisible everywhere.

### 14.4 Paths: duplicate declaration, and `.` segments

`artifacts` carries no `uniqueItems`, so a path declared twice is neither
permitted nor forbidden. And the prose "a relative path, with no upward
traversal" does not say whether `./a.txt` is acceptable. Corpus: `E-06`,
`E-08`.

**`E-08` is a measured disagreement**, found on 11 November when the bench's
comparison was fixed: `python` **accepts** `artefacts/./prompt.txt` (exit 0),
`rust-core` **refuses** it (exit 1). And Python's own report then flags
`artefacts/prompt.txt` as an **undeclared file** — the two spellings of one
path do not recognise each other inside the same tool. Frozen per verifier in
corpus 1.2.0.

`E-06` shows no measured disagreement: both refuse.

### 14.5 A fifth point, which is **not** an ambiguity

`additionalProperties: false` appears at the root and in every object of
both submission contracts. The schema therefore **requires a refusal** for
a surplus property. The reference ingestion implementation **names** the
surplus property and reports it as `NOT TESTED` instead of refusing — a
**declared divergence**, with a stated reason (refusing would break
packages the previous contract accepted) and a pinned test.

This document records it as what it is: a knowing departure from a clear
rule, not a silence in the contract. Corpus case `C-05` currently classes
it as ambiguous, which understates it. See
[`04_ARBITRAGES_PROTOCOLE.md`](../DEVELOPPEMENT_EVIDENCE_PROTOCOL_V1/04_ARBITRAGES_PROTOCOLE.md)
§5.

---

## 15. What this protocol does not establish

**EP1-LIM-001.** An implementation **MUST NOT** present any result of this
protocol as establishing:

1. the **truth** of the attested event;
2. the **scientific validity** of any measurement in the evidence;
3. the **legal identity** of a signer;
4. a **certification** under the EU AI Act or any other regime;
5. **regulatory compliance** of any kind;
6. an **external timestamp**, while the proof is `pending`;
7. the **authenticity** of a package that was **coherently rewritten**.

The last one is the one to understand before using this protocol. A package
whose content was replaced **and whose digests were recomputed** is
internally consistent. It passes an integrity check, and that is **correct
behaviour** — integrity is a statement about internal consistency, not
about history.

What distinguishes an original from a careful rewrite is an **external
anchor**: a signature over the original digests held elsewhere, a
third-party timestamp, a digest published somewhere the rewriter does not
control. Corpus family **F** freezes both halves of this: the rewrite is
accepted, and the same rewrite confronted with the **original** attestation
is refused.

Full analysis: [`THREAT_MODEL.md`](THREAT_MODEL.md).

---

## 16. Conformance

How to claim conformance, what must be declared, and which obligations are
currently covered by tests: [`CONFORMANCE.md`](CONFORMANCE.md).

Passing the corpus is **not** exhaustive conformance to this
specification. The corpus covers a subset, the subset is published, and the
uncovered obligations are listed as **gaps**, never as satisfied.

---

## 17. References

| | |
|---|---|
| RFC 2119, RFC 8174 | normative keywords |
| RFC 8259 | JSON |
| RFC 8785 | JCS — the basis of the restricted profile in §5 |
| RFC 7515 | JWS |
| RFC 7517, RFC 8037 | JWK, and `OKP`/Ed25519 key representation |
| RFC 8032 | Ed25519, including §5.1.7 strict verification |
| RFC 1951 | DEFLATE |
| PKWARE APPNOTE | ZIP format |
| JSON Schema 2020-12 | the published schemas' dialect |
| in-toto, DSSE, Sigstore, OpenTimestamps | compared in [`../DEVELOPPEMENT_EVIDENCE_PROTOCOL_V1/03_ETUDE_STANDARDS.md`](../DEVELOPPEMENT_EVIDENCE_PROTOCOL_V1/03_ETUDE_STANDARDS.md) — **no conformance to any of them is claimed** |
