<sub>🇬🇧 <b>English</b> · 🇫🇷 <a href="LIMITS.fr.md">Français</a> · <a href="../README.md">← README</a></sub>

# Known limits of the arrangement

What this gateway, and the separation it belongs to, **cannot** establish.
This page is part of the product, not a disclaimer appended to it.

---

## Engine repository status

> **`neomundi-io/neomundi-evidence-public` is PRIVATE since 2026-11-14.**
>
> Verified anonymously, with no token, at the moment of the move: the
> repository, its API record, its `raw` URLs and its pull-request pages all
> answer **404**.
>
> **Nothing was deleted and no history was rewritten.** `main` is still
> `3391c768f55b08590624aa1c24fe65fdb6420191`, all **7** branches are intact,
> the annotated tag `v1.0.0-rc1` is intact, and the repository had **0 forks**
> — so no public copy survives elsewhere. The entire content and history
> exist unchanged; access to them is **granted, not public**. Request access
> at [contact@neomundi.io](mailto:contact@neomundi.io).

## 🟢 Independent re-verification — restored, and bounded

Until 14 November 2026 this section said that nobody outside the engine could
re-run a verification. **That is no longer true, and it was the right thing to
fix rather than to live with.**

The verification surface is published in [`../verifier/`](../verifier):
the normative specification, the frozen conformance corpus (50 cases,
121 fixtures, 172 digest-covered entries), the Python verifiers and the two
independent Rust verifiers. 227 files, standard library only.

Measured in a clean room on 2026-11-14 — those files alone, no access to the
private repository:

| | |
|---|---|
| `sha256sum --check SHA256SUMS` | **172 / 172 OK** |
| corpus, all three verifiers | **80 PASS, 20 AMBIGUOUS, 50 not applicable**, **0 exit-code deviation on a concordant verdict** |
| valid artefact / tampered artefact | code **0** / code **1** |
| attestation without a trust store, then with `--strict` | code **0**, then code **2** |

**What remains bounded, and is not a formality:**

- these are **our** verifiers, on **our** specification, against **our**
  corpus. Running them confirms that our tools behave as we describe — not
  that the design is right. The Rust verifier exists so that two
  implementations can be *compared*; their declared divergences are
  published as `AMBIGUOUS` rather than reconciled;
- the corpus is **frozen**: evidence about the cases it contains, silent
  about every case it does not;
- `verifier-rs-crypto` needs network access to a crate registry on a first
  build (23 `Cargo.lock` entries). `verifier-rs` does not — it builds
  offline with nothing, and that asymmetry is deliberate;
- **what produces and signs stays private**: key generation and attestation,
  binding construction, timestamping, trust-store publication, the pilot
  reconciliation adapters. Nothing here can mint an attestation.

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
  [`../docs/INTERFACE.md`](../docs/INTERFACE.md), not omitted silently.
  Note that `verifier/adapters/ingest.py` **is** published, because the
  corpus needs it; the gateway simply does not expose an operation for it
  yet;
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

🟢 **Settled on 14 November 2026** by a decision of the rights holder,
Sébastien Favre: the **public verifier is licensed under Apache-2.0**. The
contradiction recorded here until then — Apache-2.0 metadata on two crates
against a blanket rights-reserved statement — is resolved by **scope**, not
by erasure.

| | |
|---|---|
| 🟢 the public verifier and this gateway | **Apache-2.0** — [`LICENSE`](../LICENSE), scope in [`NOTICE`](../NOTICE) |
| 🟢 the two Rust verifier crates | **Apache-2.0**, as their `Cargo.toml` already declared. **Confirmed, not replaced** |
| 🟡 `verifier/spec/`, `verifier/conformance/`, `verifier/examples/`, `trust/trust-store.json` | published for **verification and review**; rights reserved. Read them, run them, check our figures — no reuse licence |
| 🔴 the Evidence **engine** (private repository) | **proprietary.** Everything that *produces and signs*. Unchanged by this decision |

**Why the split holds together.** The engine's own `LICENSE` anticipated it,
at §6.4: *"Material republished elsewhere under a NeoMundi notice — notably
the public verification surface in `neomundi-io/neomundi-evidence-gateway` —
is governed by the notice published with it, not by this document."*
[`NOTICE`](../NOTICE) is that notice. **No file of the private engine was
modified to make this work.**

🟡 **One question left open, and named rather than quietly decided.** A
conformance corpus that may not be redistributed is awkward for a third party
implementing the protocol, who would reasonably want to ship the test
vectors. Extending Apache-2.0 to `spec/` and `conformance/` is a separate
decision, and has not been taken.

⚠ Apache-2.0 grants rights in the **software**. It grants nothing about what
a verification establishes — everything above in this page still applies —
and its §6 grants **no trademark rights**.

## What is deliberately not published

Private keys, trust-store signing material, pilot secrets, the private
Q-1/Q-2 dossiers, pilot execution packets, and any material derived from a
pilot that identifies them. None of it is in this repository, and none of it
should ever be sent to it.
