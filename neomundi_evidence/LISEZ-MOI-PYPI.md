# neomundi-evidence-verify

**Verify a NeoMundi Evidence archive, attestation or OpenTimestamps proof —
offline, with no API key, and without access to any private repository.**

```sh
pip install neomundi-evidence-verify
neomundi-evidence verify <archive.zip>
```

---

## What it does

This package distributes the **public** Evidence verifiers. It does not
reimplement them: the command-line front-end invokes the verifier as a
subprocess and passes its output and exit code through **verbatim**. The
verdict you read is, byte for byte, the one a direct call produces.

| Command | Verifies |
|---|---|
| `neomundi-evidence verify <archive.zip>` | archive structure, SHA-256 digests, named absences, internal consistency |
| `neomundi-evidence attest <a.jws> --archive <a.zip> --trust-store <s.json>` | a detached Ed25519/JWS attestation against a trust store |
| `neomundi-evidence timestamp <p.ots> --subject <file>` | an OpenTimestamps proof's **binding** to a subject, and its attestation state |
| `neomundi-evidence submission <package>` | a third-party submission package |
| `neomundi-evidence doctor` | what is installed, what is missing, and what the absence costs |

## Exit codes — read them

| Code | Meaning | Did a verification happen? |
|---|---|---|
| **0** | no control failed | yes |
| **1** | **at least one control FAILED** | yes |
| **2** | strict mode: a **required** guarantee is not demonstrated | yes |
| **3** | embedded verifier not found — broken install | **no** |
| **4** | bad usage — missing file or option | **no** |

`0`, `1` and `2` come from the verifier, untranslated. `3` and `4` exist so
that "nothing failed" and "nothing ran" never return the same code.

> ⚠ **`0` is not a certificate.** By default it means *no control failed* —
> which includes controls that **could not be performed**. `NOT TESTED` is
> not success. Use `--strict` to make an unmet required guarantee change the
> exit code to `2`. Strict mode changes **no verdict line**: only the code.

## Optional extras, and what each one buys

Nothing is required: all four operations run on the standard library alone.

```sh
pip install "neomundi-evidence-verify[attestations]"   # cryptography
pip install "neomundi-evidence-verify[timestamps]"     # opentimestamps
pip install "neomundi-evidence-verify[all]"
```

Without `cryptography`, `attest` reports `NOT TESTED` on the signature and on
trust — **never `PASS`**. Without `opentimestamps`, `timestamp` still reads
the **binding** (no dependency needed for that) but reports `NOT TESTED` on
the PENDING/BITCOIN state. An absence is never silent.

## OpenTimestamps — four states, never conflated

```sh
neomundi-evidence timestamp proof.ots --subject attestation.jws
```

| Observed | What is reported |
|---|---|
| a **Bitcoin** attestation is present | `PASS` — confirmed by the chain, with its block number(s) |
| only **PENDING** attestations | `NOT TESTED` — a calendar has undertaken to include the digest in a future transaction. **It attests no date** |
| the proof commits to a different digest | `FAIL` — the binding is refuted |
| `opentimestamps` not installed | `NOT TESTED` — state unknown; the binding is still checked |

> 🔴 **A `PENDING` proof is never presented as a confirmed timestamp**, and
> **no eIDAS qualified timestamp is claimed** — OpenTimestamps is not a
> qualified trust service provider under the regulation.
>
> Even a confirmed attestation is reported as `NOT TESTED` on *time verified
> by a third party*: validating a Bitcoin attestation requires a block
> header, i.e. a trust source this tool does not have. That check is
> delegated to the official client (`ots verify`). A tool claiming to verify
> time without a block header would be lying.

## What a verification does not establish

- **authenticity** — `verify` checks no signature;
- **content truth** — a valid signature over a fabricated archive is
  cryptographically valid. Signing establishes a commitment, not a fact;
- **the signer's legal capacity**, an **independent timestamp**, or
  **third-party anchoring**;
- and an observation deleted *consistently*, with counts and sums
  recomputed, passes every internal check. Only a digest kept elsewhere
  detects it.

Full list: [`references/LIMITS.md`](https://github.com/neomundi-io/neomundi-evidence-gateway/blob/main/references/LIMITS.md).

## Check the verifier itself

The **public conformance corpus** — 50 frozen cases, 121 fixtures, 172
digest-covered entries — is **not shipped in this wheel** (it is 1.2 MB of
test material, and a verifier package is not the place for it). Get it from
the repository and run it:

```sh
git clone https://github.com/neomundi-io/neomundi-evidence-gateway
cd neomundi-evidence-gateway/verifier/conformance
sha256sum --check SHA256SUMS            # 172/172 OK expected
python3 runners/run.py --verifier python # 40 PASS, 10 AMBIGUOUS expected
```

A refusal that was expected is a success: the `PASS` count includes packages
correctly **rejected**. The 10 `AMBIGUOUS` are cases the contract does not
decide — named rather than smoothed over.

## Independence — stated plainly

These are **our** verifiers, on **our** specification, against **our**
corpus. Running them confirms that our tools behave as we describe. It does
not make the verification independent of NeoMundi, and it does not establish
that the design is right.

## Licence

**Apache-2.0.** Copyright 2026 Sébastien Favre. See `LICENSE`, and `NOTICE`
for the exact scope.

The grant covers **this package** — the CLI and the six verifier files it
distributes. It does **not** cover the Evidence engine, which stays
proprietary, nor the normative specification and conformance corpus, which
are published for verification and review with rights reserved. The two Rust
verifiers of the project carry Apache-2.0 in their own `Cargo.toml` and are
not part of this Python package.

Apache-2.0 grants rights in the software. It grants nothing about what a
verification establishes, and §6 grants no trademark rights.
