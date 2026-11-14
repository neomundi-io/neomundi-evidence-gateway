<div align="center">

<sub><b>English</b> · <a href="README.fr.md">Français</a></sub>

# NeoMundi Evidence Gateway

### A stable interface to the Evidence engine — which may be private.

**Submit an artifact. Receive a versioned report. Read what it does not establish.**

**Measurement → Station → Evidence → Gateway**

[![Measurement](https://img.shields.io/badge/Measurement-Measure-2563eb?style=flat-square)](https://github.com/neomundi-io/neomundi-runtime-measurement)
[![Station](https://img.shields.io/badge/Station-Observe-0f766e?style=flat-square)](https://github.com/neomundi-io/neomundi-station-public)
[![Evidence](https://img.shields.io/badge/Evidence-Verify-D4A545?style=flat-square)](verifier/README.md)
[![Gateway](https://img.shields.io/badge/Gateway-Integrate-475569?style=flat-square)](https://github.com/neomundi-io/neomundi-evidence-gateway)

[![PyPI](https://img.shields.io/pypi/v/neomundi-evidence-verify?label=PyPI&style=flat-square)](https://pypi.org/project/neomundi-evidence-verify/)
[![Status](https://img.shields.io/badge/Status-experimental-a16207?style=flat-square)](#maturity-read-this-before-quoting-anything) [![Stdlib only](https://img.shields.io/badge/Dependencies-Python_stdlib-0f766e?style=flat-square)](#requirements) [![License](https://img.shields.io/badge/License-Apache_2.0-0f766e?style=flat-square)](LICENSE)

</div>

---

## What this is

NeoMundi Evidence verifies archives, bindings and detached attestations. Its
tools are command-line programs that read local files. This gateway is the
**input/output boundary** around them: one versioned request envelope in, one
versioned response envelope out.

It exists for one reason: an integrator should be able to use Evidence
**without the engine being public**, and without anyone re-implementing
verification on the outside.

## What it deliberately does not do

> **It verifies nothing.**

It reads no archive, computes no digest, compares no manifest, derives no
verdict. Every control line, every count and the verdict itself come from the
engine and are republished unchanged. The response says so in each payload:

```json
"verdict": { "source": "evidence-engine", "computed_by_gateway": false }
```

This abstention is the product, not a shortcut. A gateway that reimplemented
verification would be a second verifier with its own divergences — exactly
what the [Evidence specification](verifier/spec/SPECIFICATION.md)
is written to avoid. [`tests/test_no_verification_logic.py`](tests/test_no_verification_logic.py)
fails if a verification primitive ever appears in the product sources, and
compares the republished verdict, field by field, against a **direct** engine
call on the same artifact.

## Five situations, five exit codes

The engine answers `0`, `1` and `2`. Two situations it cannot express, because
they are about reaching the engine at all, and a consumer must never read them
as success:

| Code | Meaning | Did a verification happen? |
|---|---|---|
| **0** | the engine ran, no control failed | yes |
| **1** | the engine ran, **at least one control failed** | yes |
| **2** | the engine ran, strict mode, a **required** guarantee is not demonstrated | yes |
| **3** | **engine unavailable** — not declared, absent, missing entry point, timed out, unreadable report | **no** |
| **4** | **request refused** — unknown contract, unknown operation, missing or ill-typed field, path outside the artifact root | **no** |

`0`, `1` and `2` are the engine's own codes, passed through untranslated. See
[`docs/INTERFACE.md`](docs/INTERFACE.md).

## Use it

```sh
export EVIDENCE_ENGINE_HOME=/path/to/the/evidence/engine

# the stable interface: a request envelope in, a response envelope out
python gateway.py submit examples/02-verify-corpus-strict.json \
       --artifact-root "$EVIDENCE_ENGINE_HOME" --out response.json

# shortcuts, which build the same envelope
python gateway.py verify <archive.zip> --corpus <dir> --strict
python gateway.py attest <attestation.jws> --artifact <archive.zip> --trust-store <store.json>

# is the engine reachable at all, and what does it declare?
python gateway.py engine
python gateway.py contracts
```

[Configuring access to a private engine](docs/ENGINE_ACCESS.md) · [Interface and envelopes](docs/INTERFACE.md)

## Run the five scenarios yourself

```sh
EVIDENCE_ENGINE_HOME=/path/to/engine sh demo/demo.sh   # the five scenarios
sh demo/demo.sh --no-engine                            # scenarios 4 and 5, no engine needed
python tests/test_gateway.py
python tests/test_no_verification_logic.py
```

The demonstration compares each **observed** exit code with the **expected**
one and fails if a single code differs. It uses the engine's own synthetic
demonstration dossier; it touches no confidential data, and scenarios 4 and 5
touch no artifact at all.

## Contracts

| | |
|---|---|
| [`contracts/gateway-request-v1.json`](contracts/gateway-request-v1.json) | `neomundi.evidence.gateway.request/1` — what a caller submits |
| [`contracts/gateway-response-v1.json`](contracts/gateway-response-v1.json) | `neomundi.evidence.gateway.response/1` — what the gateway returns |

Both are JSON Schema draft 2020-12 and both are **closed**
(`additionalProperties: false`): a field the contract does not allow is
refused, never ignored. That is the discipline of the Evidence contracts, and
this gateway does not relax it.

The engine's report contracts — `neomundi.evidence.verification-report/1` and
`neomundi.evidence.attestation-report/1` — are **not redefined here**. Their
payload is carried verbatim under `engine_report`. They are documented in the
engine's `docs/INTEGRATION.md`, which is **not public**. What is public: each report names its own contract in its `schema` field, and the fields are readable in [`verifier/verify.py`](verifier/verify.py) and [`verifier/spec/SPECIFICATION.md`](verifier/spec/SPECIFICATION.md).

## Quick start — verify a proof in four commands

```sh
# 1. install. No API key, no account, no network call at verification time.
pip install neomundi-evidence-verify            # once published; see PUBLISHING.md
#   or, today, from a clone:
git clone https://github.com/neomundi-io/neomundi-evidence-gateway
cd neomundi-evidence-gateway && pip install .

# 2. verify an example archive from the public conformance corpus
neomundi-evidence verify verifier/conformance/fixtures/A-valid/A-05-archive-valid/archive.zip
echo $?        # 0 - no control failed

# 3. the same command on a tampered archive
neomundi-evidence verify verifier/conformance/fixtures/D-tampered/D-10-archive-member-tampered/archive.zip
echo $?        # 1 - one control FAILED, and the line says which member

# 4. an OpenTimestamps proof (needs the optional extra)
pip install "neomundi-evidence-verify[timestamps]"
cd verifier/examples/timestamp
neomundi-evidence timestamp NEOMUNDI_EVIDENCE_DEMO_V0.1.zip.jws.confirmed.ots \
                  --subject NEOMUNDI_EVIDENCE_DEMO_V0.1.zip.jws
```

### Reading the verdict

Read the **exit code**, not the absence of red text.

| Code | Meaning | Did a verification happen? |
|---|---|---|
| **0** | no control failed | yes |
| **1** | **at least one control FAILED** | yes |
| **2** | strict mode: a **required** guarantee is not demonstrated | yes |
| **3** | embedded verifier not found - broken install | **no** |
| **4** | bad usage - missing file or option | **no** |

> ⚠ **`0` is not a certificate.** It means *no control failed* — and that
> includes controls that **could not be performed**. `NOT TESTED` is not
> success. Add `--strict` to make an unmet *required* guarantee return `2`
> instead. Strict mode changes **no verdict line**: only the code.

`neomundi-evidence doctor` prints what is installed, what is missing, and what
each absence costs.

### OpenTimestamps — four states, never conflated

| Observed | Reported | `--strict` |
|---|---|---|
| a **Bitcoin** attestation is present | `PASS` — confirmed by the chain, with block number(s) | `0` |
| only **PENDING** attestations | `NOT TESTED` — a calendar undertook to include the digest in a future transaction; **it attests no date** | **`2`** |
| the proof commits to another digest | **`FAIL`** — the binding is refuted | `1` |
| `opentimestamps` not installed | `NOT TESTED` — state unknown; the **binding** is still checked | `2` |

Measured on the two proofs shipped in `verifier/examples/timestamp/`: the
confirmed one reports *2 Bitcoin attestations, blocks 974714 and 974715*; the
pending one reports *4 PENDING and NO Bitcoin*.

> 🔴 A `PENDING` proof is **never** presented as a confirmed timestamp, and
> **no eIDAS qualified timestamp is claimed** — OpenTimestamps is not a
> qualified trust service provider under the regulation.
>
> Even on a confirmed proof, *time verified by a third party* stays
> `NOT TESTED`: validating a Bitcoin attestation needs a block header, i.e. a
> trust source this tool does not have. That check is delegated to the
> official client (`ots verify`). A tool claiming to verify time without a
> block header would be lying.

### What the result lets you assert — and what it does not

A `0` says: this archive's structure, digests and declared absences are
internally consistent, as checked by the controls that ran.

It does **not** establish authenticity (`verify` checks no signature),
content truth (a valid signature over a fabricated archive is still
cryptographically valid), the signer's legal capacity, an independent
timestamp, or third-party anchoring. And an observation deleted
*consistently* — counts and sums recomputed — passes every internal check;
only a digest kept elsewhere detects it.

Full list: [`references/LIMITS.md`](references/LIMITS.md). Independence, in
one line: these are **our** verifiers on **our** corpus — running them
confirms our tools behave as described, not that the design is right.

## The public record

The engine is a private repository. What a third party needs in order to
**verify**, trace, cite or confront the work is published **here**, and does
not depend on access to it:

| | |
|---|---|
| [`trust/trust-store.json`](trust/trust-store.json) | the **public trust store**, byte for byte, `sha256 dac94e8a…` — the artifact, not only its digest. [Notice](trust/README.md) |
| [`references/REVIEWS.md`](references/REVIEWS.md) | the three **independent reviews**: what each reviewer did, each review's limits, and the exact engine PR, merge commit and date |
| [`references/VERIFICATION_RESULTS.md`](references/VERIFICATION_RESULTS.md) | what was **measured**, against which revision, with which digest — and which digests have no reachable artifact |
| [`verifier/`](verifier) | 🟢 the **public verification surface** — specification, frozen conformance corpus, Python verifiers and two independent Rust verifiers. 227 files, standard library only. [Notice](verifier/README.md) |
| [`references/LIMITS.md`](references/LIMITS.md) | the **known limits** — what a verification still does not establish, and what independence does and does not mean here |

## Maturity — read this before quoting anything

**Experimental, version 0.1.0.** This gateway has never been exercised by a
third party. Its envelopes are versioned so they can be changed by adding a
new version, not by moving an existing one — but nothing about them has been
qualified by anyone outside NeoMundi.

Two limits are republished in **every** response, and neither is a formality:

- **gateway scope** — the gateway performs no verification of its own;
- **independence** — the gateway and the engine it invokes run under the same
  operator unless the operator states otherwise. A report produced here is a
  verification performed by *that operator*. It is **not** an independent
  third-party verification, and must never be presented as one.

Everything the engine itself does not establish — content truth, legal
capacity of a signer, independent timestamping, third-party anchoring — is
copied into the response's `limits` array, prefixed `engine:`. See the
engine's own limitations document, which is not public — its `does_not_establish` lines are copied into [`references/LIMITS.md`](references/LIMITS.md).

## Requirements

Python 3.11, 3.12 or 3.13 — the versions the suites are run on, and the
engine's own — **standard library only**. Earlier versions are not claimed
because they are not exercised: the Ubuntu 26.04 runners no longer offer 3.9
or 3.10. `jsonschema` is optional and
used by the suites to validate the envelopes against the published contracts;
without it that control reports `NOT TESTED`, never `PASS`.

The engine that **produces and signs** is not vendored here: it is located at
run time, by configuration, and that is what lets it stay private. The engine
that **verifies** is published, in [`verifier/`](verifier) — so point the
gateway at it and nothing else is needed:

```sh
EVIDENCE_ENGINE_HOME="$PWD/verifier" python gateway.py   verify verifier/conformance/fixtures/A-valid/A-05-archive-valid/archive.zip   --artifact-root "$PWD/verifier"
```

## Rights

The **public verifier is licensed under Apache-2.0** — see
[`LICENSE`](LICENSE). The grant covers the verifier and this gateway, and
**nothing else**: the Evidence engine stays proprietary, and
[`NOTICE`](NOTICE) lists line by line what is covered and what is not. Read
`NOTICE` before reusing anything: this repository is deliberately
mixed-licence.

Apache-2.0 grants rights in the *software*. It grants nothing about what a
verification establishes, and §6 grants no trademark rights.

Report security issues privately to
[contact@neomundi.io](mailto:contact@neomundi.io) — never send private keys,
trust-store signing material or pilot secrets.

Independent review and qualification work on the Evidence engine is credited
in the engine repository, not here.

**[Explore NeoMundi](https://neomundi.io)** · **[Discuss a pilot](mailto:contact@neomundi.io)**
