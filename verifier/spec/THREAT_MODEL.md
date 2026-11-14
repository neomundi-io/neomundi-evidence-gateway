# Evidence Protocol v1 — Threat model and limits of the guarantees

Who can attack what, what the protocol stops, and — at greater length —
what it does **not** stop.

Companion to [`SPECIFICATION.md`](SPECIFICATION.md).

---

## 1. What is being protected, and from whom

The protocol protects **one** property: that a set of bytes is the set of
bytes a declaration commits to, and — where an attestation exists — that
someone holding a particular key committed to those digests.

Everything else that matters about evidence is **outside** it.

| Actor | Assumed capability |
|---|---|
| **Producer** | writes the manifest and the artifacts. **Fully trusted by the format, not at all by the verifier.** |
| **Transport** | can alter, truncate, reorder or substitute bytes in flight |
| **Holder** | can rewrite the package at leisure, including recomputing everything |
| **Signer** | holds a private key. May be the producer, or not. |
| **Verifier** | reads hostile input by default |
| **Reader of the report** | reads a verdict and an exit code, often from a script |

The last row is a threat surface in its own right, and the one most often
forgotten. A report that cannot be read correctly protects nothing — see
§3.6.

---

## 2. What the protocol stops

| Attack | Stopped by |
|---|---|
| a byte changed in an artifact | digest recomputation (`EP1-INT-002`) |
| a digest declared falsely | the same comparison, from the other side |
| a size declared falsely while the digest matches | `EP1-INT-003` |
| two artifacts' contents swapped, digests left in place | per-artifact pairing (`D-04`) |
| an artifact removed | `EP1-INT-020` → **INCOMPLETE**, not acceptance |
| a path escaping the package | `EP1-INT-010`, before any read |
| an absolute path, or a drive letter | `EP1-INT-011` |
| a duplicated ZIP member | `EP1-INT-013` |
| a corrupted or invalid compressed stream | `EP1-INT-031`, `EP1-INT-033` |
| a local header disagreeing with the central directory | `EP1-INT-032` |
| a signature byte flipped | Ed25519 verification (`EP1-SIG-002`) |
| a payload replaced after signing | verbatim signed bytes (`EP1-CAN-004`) |
| **algorithm confusion** — `alg: none`, `HS256`, `RS256` | the algorithm is **imposed**, not read (`EP1-SIG-010`) |
| a key supplied **inside** the token | keys resolve only from the store (`EP1-SIG-031`) — **stated, untested**, see `CONFORMANCE.md` §5.3 |
| a different public key under the same `kid` | store resolution + digest concordance (`D-08`) |
| an attestation that covers a different archive | digest concordance (`D-09`) |
| a member substituted inside an otherwise correct archive | **all** declared digests compared, not one (`EP1-SIG-022`) |
| a compromised key, used earlier | `on_compromised_key: untrusted_retroactively` (`EP1-TRU-012`) |
| a test key presented as production | `on_test_key` (`EP1-TRU-013`) |

---

## 3. What the protocol does **not** stop

### 3.1 A coherent rewrite — the central limit

A holder who replaces content **and recomputes every digest, count and
checksum** produces a package that is internally consistent. It passes an
integrity check.

**That is correct behaviour, not a defect.** Integrity is a statement about
internal consistency, never about history. Corpus `F-01` and `F-03` expect
**ACCEPTED**, and their expectation sheets say so in capitals, because the
temptation to "fix" them into failures is real and would corrupt the
measurement.

What distinguishes an original from a careful rewrite is an **external
anchor**:

| Anchor | What it gives |
|---|---|
| an attestation over the **original** digests, held elsewhere | `F-02`: the same rewritten archive, confronted with the original attestation, is **refused** |
| a third-party timestamp, **confirmed** | a date no holder controls |
| a digest published where the holder has no write access | a comparison the holder cannot influence |

Without one of those, a rewrite is undetectable **by construction**, and no
amount of control added inside the package changes that.

#### A measured correction to this repository's own published claim

The completeness control (`registre.enregistrements_exportes` against the
members' counts) was long presented as catching an amputation. It is **not**
a defence against forgery: a forger that also rebuilds that field is
detected **nowhere** — measured, 20 PASS, 0 FAIL. It catches a *careless*
forger, not a careful one. Its declared purpose is different — telling
whether an export is **partial** — and it fulfils that.

Full record:
[`../DEVELOPPEMENT_CORPUS_CONFORMITE/06_DIVERGENCE_FALSIFICATION_SCENARIO_D.md`](../DEVELOPPEMENT_CORPUS_CONFORMITE/06_DIVERGENCE_FALSIFICATION_SCENARIO_D.md).

### 3.2 A malicious producer telling the truth about false bytes

A producer who runs nothing, writes plausible artifacts, declares their
digests correctly and signs the result produces **valid evidence of a
fabrication**. Every control passes. The verdict is `ACCEPTED`, and it is
right: the question the protocol answers is not the question "did this
happen".

**EP1-LIM-001** exists for this case. A valid signature over a false
statement is a valid signature.

### 3.3 Signer identity

A trust store **declares** identities — legal name, kind, jurisdiction,
registration reference. **No code in this protocol verifies any of them.**

| Established | Not established |
|---|---|
| a signature verifies under the key registered as `kid` | that the entity named next to `kid` holds it |
| the store's policy accepts that key | that the store itself is authentic |
| the store's digest matches what the caller expected | that the caller's expectation was right |

An attacker who controls the store controls the identity attribution
entirely. The store's digest is the only lever a caller has, and it only
helps if the caller obtained that digest independently.

**A verifier MUST NOT report "identity verified"** (`EP1-TRU-020`).

### 3.4 Where the key actually is

The protocol says nothing about custody. A signature proves that **something
holding the private key** signed. It does not prove a person, a device, an
intent, or that the holder was authorised.

Key compromise is handled as a **trust** question, never a **validity** one:
the signature stays mathematically valid, and what changes is whether it
should be believed (`EP1-COMPAT-022`).

### 3.5 Time

**Every date in the evidence is a declaration** until an external anchor
confirms it. An offline verification establishes **no** time guarantee
(`EP1-TS-003`).

A `pending` OpenTimestamps proof records a **submission**, not a
confirmation (`EP1-TS-002`). Nothing in this project currently carries a
confirmed anchor over its own attestations.

A producer can therefore backdate freely, and the protocol will not notice.

### 3.6 A report nobody can read correctly

Three failure modes of the **reporting** layer, all three of which have
actually occurred in this repository:

| Failure | Consequence | Status |
|---|---|---|
| exit non-zero with **no verdict** | indistinguishable from a legitimate refusal; a script reader concludes "refused" and is right by accident | `C-09`, **fixed** in this revision; six remaining in `adapters/ingest.py`, declared |
| a `PASS` that means different things on different platforms | a reader cannot know what was established | `EP1-INT-012` on archives, **measured and declared**, `CONFORMANCE.md` §5.4 |
| a `NOT TESTED` counted as a success | a coverage figure that overstates what ran | forbidden by `EP1-ABS-001`, `EP1-ABS-002`; tested |

This is why `EP1-VER-020` and `EP1-VER-021` are MUSTs about a verifier's
**output**, not about its parsing.

### 3.7 Attacks on the input formats themselves

A verifier reads hostile input. Known classes, and how they are addressed:

| Class | Addressed by |
|---|---|
| decompression bomb | declared size bounds, checked before reading (`EP1-INT-035`) — `rust-core` only; `verify.py` relies on `zipfile` |
| deeply nested JSON | a node cap in `rust-core`; **not declared** in Python |
| a hidden member (reducing a declared count to make a file invisible) | an exactness invariant in `rust-core`; found and fixed during an earlier revision |
| ZIP64 ambiguity | refused by `rust-core` |
| a `zlib` error escaping | `EP1-INT-033`, `EP1-VER-021` |

All of these are **defensive limits** — properties of a verifier, not of the
evidence (`EP1-INT-040`). They are declared, and an implementation is not
required to adopt the same ones (`EP1-INT-041`).

Bounded fuzzing was run in an earlier revision and found defects. **It does
not establish the absence of vulnerabilities**, and no claim here depends on
it.

### 3.8 A defect common to every implementation

Two independent implementations agreeing is evidence against *independent*
mistakes. It is **no** evidence against a **shared** misreading of the
contract — and the two were written from the same contracts, by the same
process, in the same week.

The corpus measures agreement. Agreement is not correctness.

### 3.9 The ambiguities, as an attack surface

Four normative silences (`SPECIFICATION.md` §14). **Three** produce
measured disagreement between the reference implementations — the third
(base64url) was found during this revision, and the corpus does not yet
record it.

`G-02` is the one with real teeth: an artifact carrying **two** `sha256`
properties. One implementation reads the last, another refuses, and a third
written tomorrow might read the first. A producer who knows which verifier
a reader uses can write **one file that says two things**.

This is published rather than quietly patched, because patching it in the
historical contracts would make yesterday's valid packages invalid with no
version to point at (`COMPATIBILITY_POLICY.md` §5).

---

## 4. What a result NEVER establishes

**EP1-LIM-001.** No result of this protocol establishes:

1. the **truth** of the attested event;
2. the **scientific validity** of any measurement inside the evidence;
3. the **authenticity** of the execution — that it ran, on what, when;
4. the **legal identity** of the signer;
5. an **EU AI Act** certification, or any other certification;
6. **regulatory compliance** of any kind;
7. an **external timestamp**, while the proof is `pending`;
8. that a **coherently rewritten** package is original.

**EP1-LIM-002.** An implementation, a report, a user interface or a
marketing document **MUST NOT** present any result of this protocol as
establishing anything in that list.

---

## 5. What a reader should do with all this

| If you need | Then |
|---|---|
| to know bytes were not altered in transit | this protocol is sufficient |
| to know **who** committed to them | you need the trust store **and** an independent reason to believe it |
| to know **when** | you need a confirmed external anchor; `pending` is not one |
| to know the event **happened** | you need something outside this protocol entirely — an independent witness, a contemporaneous third-party record, a replay |
| to resist a **determined holder** | you need an anchor they do not control, and you need it to exist **before** they would want to rewrite |

The last row is the honest summary of this threat model: against a holder
who can rewrite everything and anchor nothing, the protocol establishes
internal consistency and no more. Its value is that it says so.
