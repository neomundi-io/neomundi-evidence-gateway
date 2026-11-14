# Evidence Protocol v1 — Glossary

Terms as this protocol uses them. Where a word is used elsewhere with a
wider meaning, the narrower meaning here is the one that applies.

Companion to [`SPECIFICATION.md`](SPECIFICATION.md).

---

## The objects

**Artifact** — A file whose **bytes** are the evidence. An artifact is
identified by its digest, not by its name. Renaming an artifact does not
change it; changing one byte does.

**Submission package** — A directory or ZIP holding a submission manifest
(`submission.json`) and the artifacts it declares. The small, portable
form: what a third party sends.

**Evidence archive** — A ZIP holding a manifest, a checksum list, and the
members the manifest declares. The larger, structured form: what an
exporting system produces. **Not** the same thing as a submission package,
and not interchangeable with it — the archive has its own manifest contract
and its own controls.

**Manifest** — The JSON document that declares what a package or archive
contains, and what its producer states about the execution.

**Receipt** — A third party's own record of an execution, in that third
party's format. Imported as-is; never reinterpreted.

**Attestation** — A detached JWS whose payload declares digests of an
Evidence archive, plus identities and a declared time. It commits to
**digests**, not to files.

**Trust store** — A JSON document listing public keys, the identities they
are **attributed** to, and the policy for reading them. It declares
identities; it does not verify them.

**Timestamp descriptor** — A document declaring the digest of a subject,
the digest of an OpenTimestamps proof, and whether that proof is `pending`
or `confirmed`.

**Verifier** — A program that reads one of the above and produces a
verification report. The protocol defines what a verifier must conclude,
not how it is written or invoked.

**Verification report** — A verifier's output: one line per control, each
with a **state**; plus a **verdict**; plus, for a command-line tool, an
**exit code**.

---

## The states and verdicts

**`PASS`** — A control ran, and the property holds.

**`FAIL`** — A control ran, and the property does not hold.

**`NOT TESTED`** — A control did **not** run. The report says what would
make it runnable. Never counted as success, and never counted silently into
a coverage figure.

**`ACCEPTED`** (`ACCEPTE`) — Every applicable control ran and passed.

**`REFUSED`** (`REJETE`) — At least one control failed.

**`INCOMPLETE`** (`INCOMPLET`) — Nothing failed, but something needed to
conclude was absent. The verdict that says *the question has not been
answered*.

> `PASS`, `FAIL` and `NOT TESTED` are **terms of the contract**, not prose.
> They are never translated and never localised. Only the surrounding
> sentences change language.

---

## The reconciliation statuses

**`MATCHED`** — Both sides present, comparable, equal.

**`MISMATCHED`** — Both sides present, comparable, **different**.

**`MISSING`** — One side absent.

**`NOT VERIFIABLE`** — Present, but we cannot recompute it. Neither an
agreement nor a divergence: an impossibility to check.

**`NOT COMPARABLE`** — Both present, and a **comparability boundary** is
crossed. The status most often forgotten, and the one that prevents a
reasoning error from being published as a discovery.

**Comparability boundary** — A difference that makes two values measure
different things: a different definition, a different measurement version,
a different coverage. Evaluated **before** value equality, never after.

---

## Classification of rules

**Historical format** — A structure actually published and in use,
described as it is, including where it is inconsistent. Never renamed, and
never retroactively subjected to a new obligation.

**Normative rule** — An obligation stated with MUST / MUST NOT. Carries an
identifier (`EP1-INT-002`) so a test can cite it.

**Profile** — A named set of conventions for one context, **named inside
the data** so a verifier never has to guess which one applies.

**Extension** — An optional, versioned capability. Its absence is never a
conformance failure.

**Proposal** — A behaviour discussed for a future version. **Never
applicable.** A proposal that is treated as an obligation is a retroactive
contract change.

**Declared divergence** — A knowing departure from a clear rule, with a
stated reason and a pinned test. Different from an ambiguity (where the
contract is silent) and from a defect (where nobody decided anything).

---

## The guarantees, and what separates them

**Integrity** — The bytes are the ones declared. Says nothing about where
they came from.

**Cryptographic validity** — A signature verifies over exactly the bytes it
covers. Says nothing about whether the key should be believed.

**Key trust** — A resolved key, read **through the policy** of the store
that carries it. Says nothing about who holds the key.

**Signer identity** — Who the signer actually is. **Established by nothing
in this protocol.** A trust store declares it.

**Truth of the event** — Whether what is attested actually happened as
described. **Outside the protocol entirely.** A valid signature over a
false statement is a valid signature.

---

## Terms about what can go wrong

**Coherent rewrite** — A package whose content was replaced **and whose
digests were recomputed**. It is internally consistent, so it passes an
integrity check — **and that is correct behaviour**. Integrity is a
statement about internal consistency, not about history.

**External anchor** — Something outside the package that commits to its
original digests: a signature held elsewhere, a third-party timestamp, a
digest published where the rewriter has no control. The only thing that
distinguishes an original from a careful rewrite.

**Declared ceiling** — A limit the protocol states about itself, published
rather than hidden. Family **F** of the conformance corpus freezes one:
the coherent rewrite is **accepted**, and the test asserting that is a
**success**, not a defect to be fixed.

**Defensive limit** — A bound a verifier imposes to stay safe on hostile
input (size caps, node caps, refusing ZIP64). A property of the
**verifier**, not of the evidence; never presented as a statement about the
evidence, and never required of another implementation.

**Undeclared failure** — A conformance failure nobody wrote down. The thing
CI must turn red for.

**Declared failure** — A conformance failure that is written down, with its
cause and a proposed fix. Visible on every run; does not turn CI red.
Without this category, the only way to get a green CI would be to delete
the inconvenient measurement.

---

## Terms about canonicalisation

**Canonicalisation** — Rewriting a document into a single agreed byte form
so that two producers of the same content produce the same bytes.

**`neomundi-jcs-strings/1`** — The restricted profile of this protocol:
UTF-8 without BOM, sorted keys, `,`/`:` separators, keys matching
`^[a-z0-9_]+$`, and **numbers and booleans forbidden**. Equivalent to RFC
8785 **on that domain only**, which is why the domain is restricted rather
than the implementation extended.

**Verbatim signed bytes** — The two base64url parts of a JWS exactly as
they appear in the token. What a signature is verified over. A verifier
that re-serialises the parsed payload instead will eventually invalidate a
good signature, and the failure will look like tampering.

---

## Three distinctions worth keeping

| Not the same as | |
|---|---|
| **absent** vs. **wrong** | an absent artifact makes a package *incomplete*; a wrong one makes it *refused* |
| **unknown** vs. **false** | an unresolved key is `NOT TESTED`, never `FAIL` |
| **not comparable** vs. **divergent** | two values that do not measure the same thing are not in disagreement |
