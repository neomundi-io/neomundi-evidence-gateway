<sub>🇬🇧 <b>English</b> · 🇫🇷 <a href="README.fr.md">Français</a> · <a href="../README.md">← README</a></sub>

# The public trust store

[`trust-store.json`](trust-store.json) is what a verifier needs in order to
decide whether an Ed25519/JWS attestation was signed by a key NeoMundi
publishes — and under what declared identity.

```
sha256  dac94e8ad4baf0a48fe94b8006a238d970d242cdc52b8d9dd51294777751598d
bytes   3038
schema  neomundi.evidence.trust-store/1
```

---

## Why it lives here

Until 14 November 2026 this file was served from the Evidence engine
repository, at a `raw.githubusercontent.com` URL. Access to that repository
is **granted, not assumed** — see
[`../references/LIMITS.md`](../references/LIMITS.md). So the file is published
here instead, **byte for byte**, not rewritten, and this gateway is now its
public home.

The copy was verified against **four** sources on the day of the move, all
agreeing on `dac94e8a…`: the engine working tree, this copy, the
`raw.githubusercontent.com` URL while it still answered, and the second
channel below.

> A digest is not a substitute for an accessible artifact. The second channel
> publishes only a digest — on purpose, and it says so itself. An artifact had
> to remain reachable, and this is it.

## The two channels, and what each is for

| Channel | Serves | Purpose |
|---|---|---|
| **this file** | the **content** | what you actually verify against |
| [`mcp.neomundi.org/trust/trust-store-digest.json`](https://mcp.neomundi.org/trust/trust-store-digest.json) | the **digest**, plus declared signer and key metadata | detect a **substituted** store |

Confront them. If this file's `sha256` does not equal the second channel's
`sha256`, **stop** — one of the two has been altered, and neither tells you
which.

```sh
curl -sO https://raw.githubusercontent.com/neomundi-io/neomundi-evidence-gateway/main/trust/trust-store.json
sha256sum trust-store.json
curl -s https://mcp.neomundi.org/trust/trust-store-digest.json
```

⚠ **The two channels are technically distinct but both remain under NeoMundi
governance.** They defend against a substituted file in transit. They do not
make NeoMundi an independent third party to itself.

## What this file contains — and what it cannot contain

One active key: `kid = nm-ev-recherche-202611-1`, `kty: OKP`, `crv: Ed25519`,
`alg: EdDSA`, with its **public point `x` only**. There is no private scalar,
no `d` member, no `PRIVATE KEY` block — checked before publication. A trust
store that carried key material would not be a trust store.

Three declared identities, including the signer **NeoMundi Recherche**
(association, FR, `RNA W563015824`), whose own entry states in full that
**no verification of its powers has been made** and that its
`legal_capacity_to_attest` is `experimental`.

## What possessing it does not give you

- **it does not verify anything by itself.** Confronting an attestation to
  this store requires a verifier. This gateway is not one, and the Evidence
  engine is private — see [`../references/LIMITS.md`](../references/LIMITS.md);
- a valid signature binds **specific bytes to a key**. It does not establish
  legal identity, legal capacity, a date, or the truth of any content;
- the store's `store_kind` is `production`, but a key whose `status` is
  `test` grants **no** attestation — that is the store's own policy
  (`on_test_key: untrusted_unless_allowed`), not a convention of this page.

## Rotation and revocation

`verification_policy` publishes what a verifier must do with an unknown,
rotated, expired, compromised or test key. Any future change to this store
will be published **here**, with a new digest, and the second channel updated
to match. The `changes` array inside the file is its own history.
