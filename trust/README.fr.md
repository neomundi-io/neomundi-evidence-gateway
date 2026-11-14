<sub>🇬🇧 <a href="README.md">English</a> · 🇫🇷 <b>Français</b> · <a href="../README.fr.md">← README</a></sub>

# Le magasin de confiance public

[`trust-store.json`](trust-store.json) est ce qu'un vérificateur doit détenir
pour décider si une attestation Ed25519/JWS a été signée par une clé que
NeoMundi publie — et sous quelle identité déclarée.

```
sha256  dac94e8ad4baf0a48fe94b8006a238d970d242cdc52b8d9dd51294777751598d
octets  3038
schéma  neomundi.evidence.trust-store/1
```

---

## Pourquoi il vit ici

Jusqu'au 14 novembre 2026, ce fichier était servi depuis le dépôt du moteur
Evidence. Ce dépôt est privé, donc le fichier est publié ici — **à l'octet**,
non réécrit.

La copie a été confrontée à **quatre** sources le jour du déplacement, toutes
concordantes sur `dac94e8a…` : l'arbre de travail du moteur, cette copie,
l'URL `raw.githubusercontent.com` tant qu'elle répondait encore, et le second
canal ci-dessous.

> Une empreinte ne remplace pas une preuve accessible. Le second canal ne
> publie qu'une empreinte — délibérément, et il le dit lui-même. Il fallait
> qu'un artefact reste atteignable : c'est celui-ci.

## Les deux canaux, et à quoi sert chacun

| Canal | Sert | Rôle |
|---|---|---|
| **ce fichier** | le **contenu** | ce contre quoi on vérifie réellement |
| [`mcp.neomundi.org/trust/trust-store-digest.json`](https://mcp.neomundi.org/trust/trust-store-digest.json) | l'**empreinte**, plus le signataire et les métadonnées de clé déclarés | détecter un magasin **substitué** |

Les confronter. Si le `sha256` de ce fichier diffère de celui du second
canal, **s'arrêter** : l'un des deux a été altéré, et aucun des deux ne dit
lequel.

```sh
curl -sO https://raw.githubusercontent.com/neomundi-io/neomundi-evidence-gateway/main/trust/trust-store.json
sha256sum trust-store.json
curl -s https://mcp.neomundi.org/trust/trust-store-digest.json
```

⚠ **Les deux canaux sont techniquement distincts mais restent tous deux sous
la gouvernance de NeoMundi.** Ils protègent d'un fichier substitué en
transit. Ils ne font pas de NeoMundi un tiers indépendant de lui-même.

## Ce que ce fichier contient — et ce qu'il ne peut pas contenir

Une clé active : `kid = nm-ev-recherche-202611-1`, `kty: OKP`,
`crv: Ed25519`, `alg: EdDSA`, avec son **point public `x` seulement**. Aucun
scalaire privé, aucun membre `d`, aucun bloc `PRIVATE KEY` — vérifié avant
publication. Un magasin qui porterait du matériel de clé ne serait pas un
magasin de confiance.

Trois identités déclarées, dont le signataire **NeoMundi Recherche**
(association, FR, `RNA W563015824`), dont la fiche énonce elle-même en clair
qu'**aucune vérification de ses pouvoirs n'a été faite** et que sa
`legal_capacity_to_attest` vaut `experimental`.

## Ce que le détenir ne donne pas

- **il ne vérifie rien par lui-même.** Confronter une attestation à ce
  magasin exige un vérificateur. Ce gateway n'en est pas un, et le moteur
  Evidence est privé — voir
  [`../references/LIMITS.fr.md`](../references/LIMITS.fr.md) ;
- une signature valide lie des **octets précis à une clé**. Elle n'établit ni
  identité juridique, ni capacité juridique, ni date, ni vérité d'un
  contenu ;
- le `store_kind` du magasin vaut `production`, mais une clé de `status`
  `test` n'accorde **aucune** attestation — c'est la politique du magasin
  lui-même (`on_test_key: untrusted_unless_allowed`), pas une convention de
  cette page.

## Rotation et révocation

`verification_policy` publie ce qu'un vérificateur doit faire d'une clé
inconnue, tournée, expirée, compromise ou de test. Tout changement futur de
ce magasin sera publié **ici**, avec une nouvelle empreinte, et le second
canal mis à jour en conséquence. Le tableau `changes` du fichier est sa propre
histoire.
