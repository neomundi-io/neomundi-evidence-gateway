<div align="center">

<sub><b>English</b> · <a href="README.fr.md">Français</a></sub>

# NeoMundi Evidence Gateway

### A stable interface to the Evidence engine — which may be private.

**Submit an artifact. Receive a versioned report. Read what it does not establish.**

**Measurement → Station → Evidence → Gateway**

[![Measurement](https://img.shields.io/badge/Measurement-Measure-2563eb?style=flat-square)](https://github.com/neomundi-io/neomundi-runtime-measurement)
[![Station](https://img.shields.io/badge/Station-Observe-0f766e?style=flat-square)](https://github.com/neomundi-io/neomundi-station-public)
[![Evidence](https://img.shields.io/badge/Evidence-Verify-D4A545?style=flat-square)](https://github.com/neomundi-io/neomundi-evidence-public)
[![Gateway](https://img.shields.io/badge/Gateway-Integrate-475569?style=flat-square)](https://github.com/neomundi-io/neomundi-evidence-gateway)

[![Status](https://img.shields.io/badge/Status-experimental-a16207?style=flat-square)](#maturity-read-this-before-quoting-anything) [![Stdlib only](https://img.shields.io/badge/Dependencies-Python_stdlib-0f766e?style=flat-square)](#requirements) [![License](https://img.shields.io/badge/License-all_rights_reserved-6b7280?style=flat-square)](#rights)

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
what the [Evidence specification](https://github.com/neomundi-io/neomundi-evidence-public/blob/main/spec/SPECIFICATION.md)
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
engine's [`docs/INTEGRATION.md`](https://github.com/neomundi-io/neomundi-evidence-public/blob/main/docs/INTEGRATION.md).

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
engine's [limitations](https://github.com/neomundi-io/neomundi-evidence-public/blob/main/docs/EVIDENCE_LIMITATIONS.md).

## Requirements

Python 3.11, 3.12 or 3.13 — the versions the suites are run on, and the
engine's own — **standard library only**. Earlier versions are not claimed
because they are not exercised: the Ubuntu 26.04 runners no longer offer 3.9
or 3.10. `jsonschema` is optional and
used by the suites to validate the envelopes against the published contracts;
without it that control reports `NOT TESTED`, never `PASS`.

The engine is **not** vendored, copied or redistributed here. It is located at
run time, by configuration. That is what lets it be private.

## Rights

No reuse licence is granted by this repository; rights are reserved. This is a
decision, not an omission. Report security issues privately to
[contact@neomundi.io](mailto:contact@neomundi.io) — never send private keys,
trust-store signing material or pilot secrets.

Independent review and qualification work on the Evidence engine is credited
in the engine repository, not here.

**[Explore NeoMundi](https://neomundi.io)** · **[Discuss a pilot](mailto:contact@neomundi.io)**
