<sub>🇬🇧 <b>English</b> · 🇫🇷 <a href="ENGINE_ACCESS.fr.md">Français</a> · <a href="../README.md">← README</a></sub>

# Configuring access to the engine — including a private one

The engine is not shipped here. It is located at run time. That is the whole
point: this gateway can be public while the engine it invokes is private.

---

## The three variables

| Variable | What it does | Required |
|---|---|---|
| `EVIDENCE_ENGINE_HOME` | directory holding the Evidence engine (`verify.py` at its root) | **yes** |
| `EVIDENCE_PYTHON` | interpreter used to run the engine; defaults to the one running the gateway | no |
| `EVIDENCE_ENGINE_REVISION` | revision the operator **declares** the engine to be at. Republished with that reserve, never verified | no |

`--engine-home` on the command line takes precedence over
`EVIDENCE_ENGINE_HOME`.

There is **no default path**. Guessing one would turn an absent
configuration into something that looks like a broken engine. With nothing
declared, the gateway answers `engine_not_declared` and exit code `3`.

```sh
export EVIDENCE_ENGINE_HOME=/srv/evidence            # a private checkout is fine
export EVIDENCE_ENGINE_REVISION=3391c768             # declared, not verified
python gateway.py engine                             # what is reachable, and what it declares
```

## What the gateway needs from the engine

Exactly this, and nothing more:

| Need | Why |
|---|---|
| `verify.py` at the engine root | the `verify` operation |
| `verify_attestation.py` at the engine root | the `attestation` operation |
| both accept `--json <file>`, `--lang`, `--strict` | the gateway reads the **machine report**, never the text output |
| a working Python for the engine | the engine's own requirement, not the gateway's |

Read-only is enough. The gateway writes the engine's report into its own
temporary directory, never into the engine tree.

Optional, and only read if present:

- `conformance/VERSION` → republished as `engine.conformance_corpus_declared`;
- `schemas/*.json` → listed by `gateway.py contracts`.

## What it does not need, and must never be given

- **no copy of the engine.** Vendoring it here would make this repository a
  redistribution of the engine, and a second thing to keep in step.
- **no network access to the engine.** The engine has no HTTP interface; the
  gateway invokes it as a local process. An integration that needs a network
  boundary puts *this gateway* behind one — the gateway stays next to the
  engine.
- **no signing key, no trust-store signing material, no pilot secret.** The
  gateway verifies nothing and signs nothing; it has no use for any of them.

## When the engine becomes private

Nothing in this gateway changes. What changes is on the engine side, and it
is worth stating plainly:

| What breaks | Consequence |
|---|---|
| `https://raw.githubusercontent.com/.../neomundi-evidence-public/main/trust/trust-store.json` | the public trust store stops resolving. An integrator who fetched it from that URL must be given another channel **before** the engine is made private, not after |
| the engine's public links, CI badges and conformance corpus | unreachable to anyone without access |
| `git clone` of the engine by an integrator | needs a grant |

The gateway's own configuration is unaffected: a private checkout at
`EVIDENCE_ENGINE_HOME` works exactly like a public one.

## Half the contract can be tested without the engine

The two states that say *no verification took place* — `rejected` and
`engine_unavailable` — need no engine at all:

```sh
python tests/test_gateway.py      # cases 4 and 5 run with no engine
sh demo/demo.sh --no-engine
```

That is deliberate. An integrator who has not been granted the engine can
still qualify the envelope, the refusal reasons and the exit codes.
