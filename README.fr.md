<div align="center">

<sub><a href="README.md">English</a> · <b>Français</b></sub>

# NeoMundi Evidence Gateway

### Une interface stable vers le moteur Evidence — qui peut être privé.

**Soumettre un artefact. Recevoir un rapport versionné. Lire ce qu'il n'établit pas.**

**Mesure → Station → Evidence → Gateway**

[![Mesure](https://img.shields.io/badge/Mesure-Mesurer-2563eb?style=flat-square)](https://github.com/neomundi-io/neomundi-runtime-measurement)
[![Station](https://img.shields.io/badge/Station-Observer-0f766e?style=flat-square)](https://github.com/neomundi-io/neomundi-station-public)
[![Evidence](https://img.shields.io/badge/Evidence-Vérifier-D4A545?style=flat-square)](verifier/README.fr.md)
[![Gateway](https://img.shields.io/badge/Gateway-Intégrer-475569?style=flat-square)](https://github.com/neomundi-io/neomundi-evidence-gateway)

[![Statut](https://img.shields.io/badge/Statut-expérimental-a16207?style=flat-square)](#maturité--à-lire-avant-de-citer-quoi-que-ce-soit) [![Bibliothèque standard](https://img.shields.io/badge/Dépendances-stdlib_Python-0f766e?style=flat-square)](#prérequis) [![Licence](https://img.shields.io/badge/Licence-tous_droits_réservés-6b7280?style=flat-square)](#droits)

</div>

---

## Ce que c'est

NeoMundi Evidence vérifie des archives, des liaisons et des attestations
détachées. Ses outils sont des programmes en ligne de commande qui lisent des
fichiers locaux. Ce gateway est la **frontière d'entrée/sortie** posée autour
d'eux : une enveloppe de requête versionnée en entrée, une enveloppe de
réponse versionnée en sortie.

Il existe pour une raison : un intégrateur doit pouvoir employer Evidence
**sans que le moteur soit public**, et sans que personne ne réimplémente la
vérification à l'extérieur.

## Ce qu'il ne fait délibérément pas

> **Il ne vérifie rien.**

Il ne lit aucune archive, ne calcule aucune empreinte, ne compare aucun
manifeste, ne dérive aucun verdict. Chaque ligne de contrôle, chaque décompte
et le verdict lui-même viennent du moteur et sont republiés sans modification.
La réponse le dit dans chaque charge :

```json
"verdict": { "source": "evidence-engine", "computed_by_gateway": false }
```

Cette abstention est le produit, pas une économie. Une passerelle qui
réimplémenterait la vérification serait un second vérificateur, avec ses
propres divergences — exactement ce que la
[spécification Evidence](verifier/spec/SPECIFICATION.md)
est écrite pour éviter. [`tests/test_no_verification_logic.py`](tests/test_no_verification_logic.py)
échoue si une primitive de vérification apparaît dans les sources du produit,
et confronte le verdict republié, champ par champ, à un appel **direct** au
moteur sur le même artefact.

## Cinq situations, cinq codes de sortie

Le moteur répond `0`, `1` et `2`. Deux situations lui échappent, parce
qu'elles portent sur le fait d'atteindre le moteur — et un consommateur ne
doit jamais les lire comme une réussite :

| Code | Signification | Une vérification a-t-elle eu lieu ? |
|---|---|---|
| **0** | le moteur a tourné, aucun contrôle n'a échoué | oui |
| **1** | le moteur a tourné, **au moins un contrôle a échoué** | oui |
| **2** | le moteur a tourné, mode strict, une garantie **requise** n'est pas démontrée | oui |
| **3** | **moteur indisponible** — non déclaré, absent, point d'entrée manquant, délai dépassé, rapport illisible | **non** |
| **4** | **requête refusée** — contrat inconnu, opération inconnue, champ absent ou mal typé, chemin hors de la racine d'artefacts | **non** |

`0`, `1` et `2` sont les codes du moteur, transmis sans traduction. Voir
[`docs/INTERFACE.fr.md`](docs/INTERFACE.fr.md).

## L'employer

```sh
export EVIDENCE_ENGINE_HOME=/chemin/vers/le/moteur/evidence

# l'interface stable : une enveloppe de requête en entrée, une réponse en sortie
python gateway.py submit examples/02-verify-corpus-strict.json \
       --artifact-root "$EVIDENCE_ENGINE_HOME" --out reponse.json

# les raccourcis, qui construisent la même enveloppe
python gateway.py verify <archive.zip> --corpus <repertoire> --strict
python gateway.py attest <attestation.jws> --artifact <archive.zip> --trust-store <magasin.json>

# le moteur est-il atteignable, et que déclare-t-il ?
python gateway.py engine
python gateway.py contracts
```

[Configurer l'accès à un moteur privé](docs/ENGINE_ACCESS.fr.md) · [Interface et enveloppes](docs/INTERFACE.fr.md)

## Rejouer les cinq scénarios

```sh
EVIDENCE_ENGINE_HOME=/chemin/vers/le/moteur sh demo/demo.sh   # les cinq scénarios
sh demo/demo.sh --no-engine                                   # scénarios 4 et 5, sans moteur
python tests/test_gateway.py
python tests/test_no_verification_logic.py
```

La démonstration compare chaque code de sortie **observé** au code
**attendu**, et échoue si un seul diffère. Elle emploie le dossier de
démonstration synthétique du moteur ; elle ne touche aucune donnée
confidentielle, et les scénarios 4 et 5 ne touchent aucun artefact.

## Contrats

| | |
|---|---|
| [`contracts/gateway-request-v1.json`](contracts/gateway-request-v1.json) | `neomundi.evidence.gateway.request/1` — ce qu'un appelant soumet |
| [`contracts/gateway-response-v1.json`](contracts/gateway-response-v1.json) | `neomundi.evidence.gateway.response/1` — ce que le gateway rend |

Les deux sont en JSON Schema draft 2020-12 et les deux sont **fermés**
(`additionalProperties: false`) : un champ que le contrat ne prévoit pas est
refusé, jamais ignoré. C'est la discipline des contrats Evidence, et ce
gateway ne la relâche pas.

Les contrats de rapport du moteur — `neomundi.evidence.verification-report/1`
et `neomundi.evidence.attestation-report/1` — ne sont **pas redéfinis ici**.
Leur charge est transportée verbatim sous `engine_report`. Ils sont documentés
dans le `docs/INTEGRATION.fr.md` du moteur, qui n'est **pas public**.
Ce qui l'est : chaque rapport nomme son propre contrat dans son champ
`schema`, et les champs sont lisibles dans
[`verifier/verify.py`](verifier/verify.py) et
[`verifier/spec/SPECIFICATION.md`](verifier/spec/SPECIFICATION.md).

## Le dossier public

Le moteur est un dépôt privé. Ce dont un tiers a besoin pour **vérifier**,
tracer, citer ou confronter le travail est publié **ici**, et ne dépend pas de
l'accès à celui-ci :

| | |
|---|---|
| [`trust/trust-store.json`](trust/trust-store.json) | le **magasin de confiance public**, à l'octet, `sha256 dac94e8a…` — l'artefact, pas seulement son empreinte. [Notice](trust/README.fr.md) |
| [`references/REVIEWS.fr.md`](references/REVIEWS.fr.md) | les trois **revues indépendantes** : ce que chaque relecteur a fait, les limites de chaque revue, et la PR du moteur, son commit de fusion et sa date |
| [`references/VERIFICATION_RESULTS.fr.md`](references/VERIFICATION_RESULTS.fr.md) | ce qui a été **mesuré**, contre quelle révision, avec quelle empreinte — et quelles empreintes n'ont aucun artefact atteignable |
| [`verifier/`](verifier) | 🟢 la **surface publique de vérification** — spécification, corpus de conformité gelé, vérificateurs Python et deux vérificateurs Rust indépendants. 227 fichiers, bibliothèque standard seule. [Notice](verifier/README.fr.md) |
| [`references/LIMITS.fr.md`](references/LIMITS.fr.md) | les **limites connues** — ce qu'une vérification n'établit toujours pas, et ce que l'indépendance veut dire ici, ou ne veut pas dire |

## Maturité — à lire avant de citer quoi que ce soit

**Expérimental, version 0.1.0.** Ce gateway n'a jamais été exercé par un
tiers. Ses enveloppes sont versionnées pour pouvoir être modifiées en
ajoutant une version, non en déplaçant celle qui existe — mais rien de ce
qu'elles portent n'a été qualifié hors de NeoMundi.

Deux limites sont republiées dans **chaque** réponse, et aucune n'est une
formalité :

- **périmètre du gateway** — il ne fait aucune vérification de son propre fait ;
- **indépendance** — le gateway et le moteur qu'il invoque tournent chez le
  même opérateur, sauf déclaration contraire de celui-ci. Un rapport produit
  ici est une vérification faite par *cet opérateur*. Ce n'est **pas** une
  vérification indépendante par un tiers, et cela ne doit jamais être
  présenté comme tel.

Tout ce que le moteur lui-même n'établit pas — vérité du contenu, capacité
juridique d'un signataire, horodatage indépendant, ancrage tiers — est recopié
dans le tableau `limits` de la réponse, préfixé `engine:`. Voir les
document de limitations propre au moteur, qui n'est pas public — ses
lignes `does_not_establish` sont recopiées dans
[`references/LIMITS.fr.md`](references/LIMITS.fr.md).

## Prérequis

Python 3.11, 3.12 ou 3.13 — les versions sur lesquelles les suites sont
lancées, et celles du moteur — **bibliothèque standard seule**. Les versions
antérieures ne sont pas annoncées parce qu'elles ne sont pas éprouvées : les
runners Ubuntu 26.04 n'offrent plus 3.9 ni 3.10. `jsonschema` est
optionnelle et sert aux suites à valider les enveloppes contre les contrats
publiés ; sans elle, ce contrôle rend `NOT TESTED`, jamais `PASS`.

Le moteur qui **produit et signe** n'est pas embarqué ici : il est localisé à
l'exécution, par configuration, et c'est ce qui lui permet de rester privé. Le
moteur qui **vérifie** est publié, dans [`verifier/`](verifier) — il suffit
donc d'y pointer le gateway :

```sh
EVIDENCE_ENGINE_HOME="$PWD/verifier" python gateway.py   verify verifier/conformance/fixtures/A-valid/A-05-archive-valid/archive.zip   --artifact-root "$PWD/verifier"
```

## Droits

Aucune licence de réemploi n'est accordée par ce dépôt ; les droits sont
réservés. C'est une décision, pas un oubli. Signaler une faille en privé à
[contact@neomundi.io](mailto:contact@neomundi.io) — ne jamais envoyer de clé
privée, de matériel de signature de magasin de confiance ni de secret de
pilote.

Les travaux de relecture et de qualification indépendantes du moteur Evidence
sont crédités dans le dépôt du moteur, pas ici.

**[Découvrir NeoMundi](https://neomundi.io)** · **[Discuter d'un pilote](mailto:contact@neomundi.io)**
