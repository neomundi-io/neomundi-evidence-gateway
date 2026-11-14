<sub>🇬🇧 <b>English</b> · 🇫🇷 <a href="README.fr.md">Français</a> · <a href="../README.md">← README</a></sub>

# The public verification surface

Everything a third party needs to verify a NeoMundi Evidence artefact
**without any access to the private engine repository** — and to check our
figures rather than take them.

```
227 files · 2.1 MB · Python standard library only (one optional Rust dependency)
```

---

## Why this exists

The Evidence engine is private. If verification had stayed inside it, every
number we publish would have been unfalsifiable by anyone outside NeoMundi.
These files are the part that must be public for "independent verification"
to mean anything.

**This is not the engine.** What stays private is everything that *produces*
and *signs*: key generation and attestation (`sign.py`), binding
construction, timestamping, trust-store publication, the pilot
reconciliation adapters, the private dossiers, and the dated internal
reports. What is here only ever *reads and judges*.

## What is here

| | |
|---|---|
| [`spec/`](spec) | the **normative specification** — Evidence Protocol v1, Candidate Specification. Written to be sufficient on its own: implementing it should not require reading `verify.py` |
| [`conformance/`](conformance) | the **frozen public corpus** — 50 cases, 7 families, 121 fixture files, 172 digest-covered entries, `VERSION` 1.3.0 |
| [`verify.py`](verify.py) | archive verifier — **standard library only**, no network |
| [`verify_attestation.py`](verify_attestation.py) | detached Ed25519/JWS attestation verifier (needs `cryptography`, and says `NOT TESTED` without it — never `PASS`) |
| [`canonical.py`](canonical.py) | the canonicalisation profile `verify_attestation.py` depends on |
| [`i18n.py`](i18n.py) | translations. **Optional**: delete it and the tools run, return the same verdicts and the same exit codes, in French |
| [`adapters/ingest.py`](adapters/ingest.py) | submission-package verifier. **35 of the 50 corpus cases need it** |
| [`verifier-rs/`](verifier-rs) | a **second, independent** verifier in Rust — `Cargo.lock` holds **one** entry, so the absence of dependencies is checkable *without compiling* |
| [`verifier-rs-crypto/`](verifier-rs-crypto) | the signature and archive verifier in Rust. Ed25519 is **not** reimplemented: it uses `ed25519-dalek` |

## Verify our figures — the four commands

```sh
# 1. the corpus is intact, byte for byte
cd conformance && sha256sum --check SHA256SUMS      # 172/172 OK expected

# 2. run it with the Python verifier
python3 runners/run.py --verifier python            # 40 PASS, 10 AMBIGUOUS expected

# 3. a valid artefact, and a tampered one
cd .. && python3 verify.py conformance/fixtures/A-valid/A-05-archive-valid/archive.zip
python3 verify.py conformance/fixtures/D-tampered/D-10-archive-member-tampered/archive.zip
echo $?                                             # 1 expected: one control FAILED

# 4. the trap strict mode exists for
F=conformance/fixtures/A-valid/A-07-attestation-store-not-confronted
python3 verify_attestation.py $F/attestation.jws --archive $F/archive.zip ; echo $?          # 0
python3 verify_attestation.py $F/attestation.jws --archive $F/archive.zip --strict ; echo $? # 2
```

The last pair is the point of the product: **four different situations return
`0`** by default, and only `--strict` separates "demonstrated" from "not
testable". The control lines are **byte-identical** with and without the flag
— strict mode changes the exit code, never a verdict.

### The two Rust verifiers

```sh
cd verifier-rs       && cargo build --release && cargo test --release
cd ../verifier-rs-crypto && cargo build --release
cd ../conformance && python3 runners/run.py --verifier all \
   --bin-rust-core   ../verifier-rs/target/release/evidence-verify-rs \
   --bin-rust-crypto ../verifier-rs-crypto/target/release/evidence-verify-crypto
```

⚠ `verifier-rs-crypto` pulls `ed25519-dalek` and its transitive closure —
**23 entries in its `Cargo.lock`**. A first build therefore needs network
access to a crate registry. `verifier-rs` does not: it builds offline with
nothing.

⚠ The two crates **must stay siblings**. `verifier-rs-crypto` reaches six
shared modules by `#[path = "../../verifier-rs/src/…"]` — they are *the same
files*, not a copy to keep in step. Moving either directory breaks the build.

## What the corpus will tell you, including about us

Measured in a clean room on 2026-11-14, from these files alone, with no
access to the private repository:

| Verifier | Result |
|---|---|
| Python | **40 PASS, 10 AMBIGUOUS** |
| `evidence-verify-rs` | 27 PASS, 8 AMBIGUOUS, 15 not applicable |
| `evidence-verify-crypto` | 13 PASS, 2 AMBIGUOUS, 35 not applicable |
| all three | **80 PASS, 20 AMBIGUOUS, 50 not applicable — 0 exit-code deviation on a concordant verdict** |

Three things to read correctly:

- **a refusal that was expected is a success.** The PASS count includes
  packages correctly *rejected*;
- **the 10 AMBIGUOUS are neither.** They are cases the contract does not
  decide, and on some of them the two reference implementations are
  **measured as disagreeing**. The corpus names them instead of smoothing
  them over;
- **"not applicable" is not a failure and not a pass.** The denominator of
  any rate is the number of cases applicable to that verifier — not 50.

## The traceability file is the honest part

[`spec/traceability.json`](spec/traceability.json) records every normative
rule and what tests it. Measured on this revision (`1.0.0-rc.1`, corpus
1.3.0): **102 rules**.

| `coverage` — is there a test? | | `reference_implementations` — do we obey it? | |
|---|---|---|---|
| COVERED | **81** | CONFORMING | **97** |
| PARTIAL | 12 | PARTIAL | 2 |
| GAP | **3** | UNKNOWN | **3** |
| NOT TESTABLE | 6 | | |

The two columns are **deliberately separate**: a rule can be well covered and
still violated, and that is precisely what has to be readable. The 3 `GAP`
and the 3 `UNKNOWN` are declared, not hidden.

> ⚠ Our own README once said "97 normative rules". That was the count at an
> earlier revision; rules were added by the consolidations of 13 November.
> **102** is the measured figure here. Prefer the file to any prose,
> including ours.

## What this does not give you

- **it does not make the verification independent of us.** These are *our*
  verifiers, on *our* specification, against *our* corpus. A third party
  running them confirms that our tools behave as we say — not that the
  design is right. Independence would mean a verifier written by someone
  else; the Rust one exists precisely so that two implementations can be
  *compared*, and their declared divergences are published;
- it establishes nothing about content truth, a signer's legal capacity, an
  independent timestamp or third-party anchoring — see
  [`../references/LIMITS.md`](../references/LIMITS.md);
- the corpus is **frozen**. It is evidence about the cases it contains, and
  silent about every case it does not.

## One consequence of republishing unmodified

These 227 files are a **byte-for-byte** republication of what the engine
holds — that property is asserted in this repository's commit history and
checked by `tests/test_corpus_public.py`. So some of them still carry links
and clone instructions pointing at `neomundi-io/neomundi-evidence-public`,
which is private: `conformance/README.md` is the clearest case.

Those links are left as they are, deliberately. Editing a republished frozen
artefact to tidy a link would cost the one property that makes this corpus
worth publishing. **Read such a link as naming where the file came from, not
as somewhere you can go.** To clone the corpus, clone this repository
instead.

## Rights

These files are published for **verification and review**. No reuse licence
is granted by this repository; rights are reserved. The two Rust crates carry
`license = "Apache-2.0"` in their own `Cargo.toml`, as they did when first
published — that declaration stands and is not withdrawn here. See
[`../references/LIMITS.md`](../references/LIMITS.md), *Rights*.
