<sub>🇬🇧 <b>English</b> · 🇫🇷 <a href="LIMITS.fr.md">Français</a> · <a href="../README.md">← README</a></sub>

# Known limits of the arrangement

What this gateway, and the separation it belongs to, **cannot** establish.
This page is part of the product, not a disclaimer appended to it.

---

## Engine repository status

> **`neomundi-io/neomundi-evidence-public` is PUBLIC as this page is
> published. Its move to private is authorised and imminent.**
>
> This block is the **single place** in this repository where that status is
> recorded, and it is updated by its own commit the moment the move is made —
> so the repository's history carries the date, rather than a page asserting a
> state it cannot yet know.
>
> Whichever state applies: nothing is deleted and no history is rewritten. No
> branch, tag, pull request or commit is removed — the engine repository's
> entire content and history exist unchanged, and once it is private, access
> to them is **granted, not public**. Request access at
> [contact@neomundi.io](mailto:contact@neomundi.io).

## 🔴 The largest limit: nobody outside can re-run a verification

The Evidence verifiers — `verify.py`, `verify_attestation.py`, the two
independent Rust verifiers — live in the engine repository. The normative
specification (97 traced rules) and the public conformance corpus (50 frozen
cases, 121 fixture files) live there too.

So, once the move above is made:

| Who | Can re-run an independent verification? |
|---|---|
| anyone with engine access | yes |
| anyone without it | **no**, once the engine repository is private |

**This gateway does not close that gap, and is not meant to.** It verifies
nothing; it transports a verdict produced by an engine. A report obtained
through it is a verification performed by whoever runs the engine.

This is the cost of the separation, stated rather than discovered. The figures
on [`VERIFICATION_RESULTS.md`](VERIFICATION_RESULTS.md) remain **true and
anchored by digests** — but a third party can no longer reproduce them
unaided. If that capability is to be restored, it means publishing the
specification and the conformance corpus here; that is a decision, not an
oversight.

## 🔴 Independence

The gateway and the engine it invokes run **under the same operator** unless
that operator states otherwise. Every response says so in its `limits` array,
and the wording is deliberate:

> *independence: […] A report produced here is a verification performed by
> that operator, not an independent third-party verification.*

Related, and equally load-bearing:

- the reviewer observations in [`REVIEWS.md`](REVIEWS.md) were **reproduced**
  by NeoMundi. Reproduction by the author is not independent confirmation;
- the trust store's two channels ([`../trust/README.md`](../trust/README.md))
  are technically distinct but both under NeoMundi governance. They detect a
  substituted file; they do not make NeoMundi a third party to itself;
- `external-link/1` has **never** been exercised outside NeoMundi.

## What a verification, when it does happen, still does not establish

Copied into every gateway response from the engine's own report:

- **authenticity** — the archive verifier checks no signature;
- **content truth** — a perfectly valid signature over a fabricated archive
  is cryptographically valid. Signing establishes a commitment and custody,
  not a fact;
- **the signer's legal capacity** — no code establishes it. The published
  trust store declares `legal_capacity_to_attest: experimental` for its only
  signer, and states that **no verification of its powers has been made**;
- **independent timestamping** — `attested_at_declared` is declared by the
  signer. No trusted clock is involved;
- **third-party anchoring** — declared `planned`, and **no anchor
  verification is implemented**. An unverified anchor is no better than a
  text field;
- **ledger chaining** — out of scope: recomputing it would be a second
  implementation of the ledger;
- **the archive's origin** — no third-party signature, no anchor.

And one limit that no control can reach: an observation deleted
*consistently* — counts and sums recomputed — passes every internal check.
Only a digest kept elsewhere detects it.

## Limits of this gateway specifically

- **2 of the engine's 12 entry points are exposed**: `verify` and
  `attestation`. Binding, signing, timestamping, third-party package
  ingestion and reconciliation are **not** — named as future work in
  [`../docs/INTERFACE.md`](../docs/INTERFACE.md), not omitted silently;
- **`engine.revision_declared` is declared, never verified.** This gateway
  runs no `git` and checks no signature over the engine tree. It cannot
  establish that a directory corresponds to a commit;
- **the republished engine report is not byte-identical** to what the engine
  wrote: local paths are redacted. `engine_report_redacted` and
  `redactions_applied` say so in every response;
- **no envelope has been exercised by a third party.** Version `0.1.0`. That
  is the only thing separating it from a version;
- the demonstration's attestation uses a key whose status is **`test`**,
  which grants no attestation. Running it with `--allow-test-keys` shows a
  **declaration**, not an identity verification.

## Rights, as actually constituted

| | |
|---|---|
| this gateway | no reuse licence granted; rights reserved |
| the engine repository | no `LICENSE`, `NOTICE` or `CONTRIBUTING` file is present (measured on `3391c768`); its README states rights reserved |
| 🟡 **the two Rust verifier crates** | their `Cargo.toml` files declare **`license = "Apache-2.0"`** |

🟡 **That declaration is not withdrawn here, and could not be.** Those files
were published in a public repository carrying that package metadata. Anyone
who obtained them during that period may rely on the grant it expresses;
making the repository private does not reach back and revoke it. Neither
crate was ever published to a registry (`publish = false` on both).

The contradiction between that metadata and the rights-reserved statement is
**unresolved**, and is recorded here as unresolved rather than settled in one
direction by silence. It is a question for NeoMundi to answer explicitly.

## What is deliberately not published

Private keys, trust-store signing material, pilot secrets, the private
Q-1/Q-2 dossiers, pilot execution packets, and any material derived from a
pilot that identifies them. None of it is in this repository, and none of it
should ever be sent to it.
