<div align="center">

<sub><a href="README.md">English</a> · <b>Français</b></sub>

# NeoMundi Evidence

**Un résultat d'IA est contesté. Pouvez-vous prouver ce qui s'est passé ?**

**Des observations de l'IA aux preuves vérifiables indépendamment.**

Conservez des preuves techniques, vérifiez leur intégrité et transmettez des dossiers contrôlables par un tiers.

**INSTALL → TRACE → MEASURE → VERIFY → ACT**

[Architecture produit](https://github.com/neomundi-io/.github/blob/main/docs/PRODUCT_ARCHITECTURE.md) · [Audit des capacités](https://github.com/neomundi-io/.github/blob/main/docs/V2_FUNCTIONAL_AUDIT_2026-11-15.md) · [Tous les composants](https://github.com/orgs/neomundi-io/repositories)

### Donnez à vos clients et auditeurs des preuves à vérifier, pas des affirmations à croire.

[![PyPI](https://img.shields.io/pypi/v/neomundi-evidence-verify?style=flat-square&label=PyPI&color=0f766e)](https://pypi.org/project/neomundi-evidence-verify/) [![Statut](https://img.shields.io/badge/Statut-expérimental-a16207?style=flat-square)](#maturité--à-lire-avant-de-citer-quoi-que-ce-soit) [![Dépendances](https://img.shields.io/badge/Dépendances-stdlib_Python-0f766e?style=flat-square)](#prérequis) [![Licence](https://img.shields.io/badge/Licence-Apache_2.0-0f766e?style=flat-square)](LICENSE)

**Mesure → Station → Evidence → Gateway**

[![Mesure](https://img.shields.io/badge/Mesure-Mesurer-2563eb?style=flat-square)](https://github.com/neomundi-io/neomundi-runtime-measurement)
[![Station](https://img.shields.io/badge/Station-Observer-0f766e?style=flat-square)](https://github.com/neomundi-io/neomundi-station-public)
[![Evidence](https://img.shields.io/badge/Evidence-Vérifier-D4A545?style=flat-square)](verifier/README.fr.md)
[![Gateway](https://img.shields.io/badge/Gateway-Intégrer-475569?style=flat-square)](https://github.com/neomundi-io/neomundi-evidence-gateway)

</div>

---

## 1. Le problème — pouvez-vous prouver ce qui s'est passé ?

Un client conteste un résultat produit par une IA. Un auditeur demande les preuves d'une affirmation. Votre équipe doit reconstituer un incident des mois plus tard. Des journaux détenus par le seul opérateur ne rendent pas les artefacts contrôlables de façon autonome.

## 2. Le bénéfice — des preuves techniques contrôlables par des tiers

**Conserver** un dossier de preuves structuré. **Vérifier** l'intégrité des archives, les signatures et horodatages disponibles avec des résultats explicites. **Démontrer** ce qui a réussi, échoué ou n'a pas pu être testé, sans demander de croire votre tableau de bord.

Evidence contrôle le dossier technique ; il n'établit **ni** la vérité d'une réponse d'IA, **ni** la réalité d'une action externe, **ni** la conformité réglementaire.

## 3. Comment ça marche — conserver → vérifier → démontrer

1. **Conserver :** le moteur privé Evidence construit le dossier de preuves et sa provenance déclarée.
2. **Vérifier :** le vérificateur public contrôle les propriétés d'archives et d'attestations qu'il sait traiter, y compris hors ligne. Le Gateway transmet les soumissions au moteur et publie son verdict sans modification ; il ne vérifie rien lui-même.
3. **Démontrer :** remettre le dossier, les instructions et les statuts explicites pour permettre à un tiers de répéter les contrôles applicables.

## 4. Pour qui — hypothèse de premier marché

| Situation | Acheteur potentiel | Valeur à valider |
| --- | --- | --- |
| Éditeur de logiciel IA sollicité par des clients sur l'audit ou la sécurité | CTO / direction technique | Transmettre des éléments contrôlables plutôt que des captures d'écran |
| Équipe opérationnelle enquêtant sur des sorties IA contestées | Responsable plateforme / qualité IA | Reconstituer les pièces conservées et les contrôles réalisés |
| Fournisseur IA d'un secteur réglementé préparant sa documentation | Risques / conformité avec l'ingénierie | Étayer des travaux de conformité sans prétendre s'y substituer |

**Hypothèse beachhead, non encore validée commercialement :** éditeurs B2B de logiciels IA confrontés aux demandes de preuves de clients entreprises.

## 5. Voir la démonstration — reproduire les contrôles

- [Installer le vérificateur public](#installer-le-vérificateur-public) avec `pip install neomundi-evidence-verify`.
- [Vérifier une archive valide et une archive altérée](#vérifier-une-preuve-en-trois-commandes) avec les jeux d'essai publics.
- [Consulter les vérificateurs Python/Rust et le corpus](verifier/README.fr.md), avec leurs périmètres distincts.
- [Lire les limites de vérification](references/LIMITS.md) avant d'utiliser un résultat.

## 6. Architecture technique — aller plus loin

| Composant | Rôle | Référence |
| --- | --- | --- |
| Moteur Evidence (privé) | Produit les dossiers de preuves et les verdicts du moteur | [Architecture produit](https://github.com/neomundi-io/.github/blob/main/docs/PRODUCT_ARCHITECTURE.fr.md) |
| Evidence Gateway (public) | Transmet les soumissions et restitue les réponses sans inventer de vérification | [Frontière du Gateway](#le-gateway-ne-vérifie-rien--et-cest-le-produit) |
| Vérificateur public | Implémentations Python et deux implémentations Rust aux périmètres distincts | [Inventaire](verifier/README.fr.md) |
| Spécification et corpus | Règles normatives, cas figés et comparaison de couverture | [Spécification](verifier/spec/SPECIFICATION.md) · [Corpus](verifier/conformance/README.md) |

### Une promesse fondée sur une architecture que vous pouvez examiner

Les capacités d'Evidence reposent sur des composants documentés, des contrats de vérification explicites et des limites clairement établies. Découvrez comment Evidence produit, conserve et vérifie les éléments de preuve techniques — et ce que ces contrôles ne permettent pas d'établir. Chaque capacité porte son état 🟢 🟡 🔴 et le périmètre dans lequel il vaut.

**[Explorer l'architecture Evidence →](ARCHITECTURE.md)**

*Nous exposons l'architecture parce que la promesse repose sur des mécanismes contrôlables : le vérificateur, la spécification et le corpus figé sont publics, et les limites sont écrites à côté des capacités. Le document est rédigé en anglais.*

Les sections suivantes conservent les commandes d'installation, contrats de verdicts et codes de sortie, démonstrations reproductibles, résultats, maturité et limites.

---

## Pourquoi cela existe — contexte technique

**Le problème.** Les organisations emploient de l'IA en production, puis
doivent en répondre — un audit, la diligence d'un client, l'analyse d'un
incident, des mois plus tard. Des journaux et des captures d'écran détenus par
le seul opérateur répondent mal : qui les conserve peut les modifier.

**Ce que vous obtenez.** Evidence emballe une opération dans une archive dont
l'intégrité, les attestations et les horodatages restent contrôlables après
coup. Ce dépôt en est la **moitié publique** : le **vérificateur** que
n'importe qui installe en une commande, et le **gateway** qui soumet les
artefacts au moteur. La vérification tourne **hors ligne** — aucun compte,
aucune clé d'API, aucun appel réseau au moment de vérifier, et aucun accès aux
systèmes de NeoMundi.

**Ce que ce n'est pas.** Cela n'établit pas qu'une réponse d'IA était *vraie*.
Cela ne certifie rien, et ce n'est pas une garantie de conformité
réglementaire. Ce qu'un `0` signifie — et ce qu'il ne signifie pas — est écrit
dans [Lire le verdict](#lire-le-verdict) : à lire avant de citer un résultat.

## Installer le vérificateur public

```sh
pip install neomundi-evidence-verify
```

Aucune dépendance n'est tirée : le vérificateur tourne sur la seule
bibliothèque standard de Python. Deux extras optionnels achètent deux
contrôles précis — `[attestations]` pour les signatures Ed25519/JWS,
`[timestamps]` pour lire l'arbre d'attestations d'une preuve OpenTimestamps —
et l'outil rend `NOT TESTED`, jamais `PASS`, quand l'un manque.

📦 [**`neomundi-evidence-verify` sur PyPI**](https://pypi.org/project/neomundi-evidence-verify/) · Apache-2.0 · Python 3.11+ · [procédure de publication](PUBLISHING.md)

## Vérifier une preuve en trois commandes

```sh
# 1. que sait faire cette installation, et que coûte chaque absence ?
neomundi-evidence doctor

# 2. vérifier une archive qu'on vous a remise
neomundi-evidence verify <archive.zip>
echo $?

# 3. la même, en exigeant que toute garantie *requise* soit démontrée
neomundi-evidence verify <archive.zip> --strict
```

**L'éprouver sur le corpus public de conformité.** Le corpus n'est **pas**
livré dans la roue — il vit dans ce dépôt, il faut donc le cloner pour rejouer
les deux cas ci-dessous :

```sh
git clone https://github.com/neomundi-io/neomundi-evidence-gateway
cd neomundi-evidence-gateway

# une archive valide
neomundi-evidence verify verifier/conformance/fixtures/A-valid/A-05-archive-valid/archive.zip
echo $?        # 0 - aucun contrôle n'a échoué

# la même commande sur une archive altérée
neomundi-evidence verify verifier/conformance/fixtures/D-tampered/D-10-archive-member-tampered/archive.zip
echo $?        # 1 - un contrôle a ÉCHOUÉ, et la ligne dit quel membre

# une preuve OpenTimestamps (exige l'extra optionnel)
pip install "neomundi-evidence-verify[timestamps]"
cd verifier/examples/timestamp
neomundi-evidence timestamp NEOMUNDI_EVIDENCE_DEMO_V0.1.zip.jws.confirmed.ots \
                  --subject NEOMUNDI_EVIDENCE_DEMO_V0.1.zip.jws
```

### Lire le verdict

Lire le **code de sortie**, pas l'absence de texte rouge.

| Code | Signification | Une vérification a-t-elle eu lieu ? |
|---|---|---|
| **0** | aucun contrôle n'a échoué | oui |
| **1** | **au moins un contrôle a ÉCHOUÉ** | oui |
| **2** | mode strict : une garantie **requise** n'est pas démontrée | oui |
| **3** | vérificateur embarqué introuvable — installation abîmée | **non** |
| **4** | emploi incorrect — fichier ou option manquant | **non** |

> ⚠ **`0` n'est pas un certificat.** Il signifie *aucun contrôle n'a échoué* —
> ce qui inclut les contrôles qui **n'ont pas pu être faits**. `NOT TESTED`
> n'est pas une réussite. Ajouter `--strict` pour qu'une garantie *requise*
> non satisfaite rende `2`. Le mode strict ne change **aucune ligne de
> verdict** : seulement le code.

`neomundi-evidence doctor` imprime ce qui est installé, ce qui manque, et ce
que chaque absence coûte.

### OpenTimestamps — quatre états, jamais confondus

| Observé | Rapporté | `--strict` |
|---|---|---|
| une attestation **Bitcoin** est présente | `PASS` — confirmée par la chaîne, avec son ou ses blocs | `0` |
| **PENDING** seulement | `NOT TESTED` — un calendrier s'est engagé à inclure l'empreinte dans une transaction future ; **il n'atteste aucune date** | **`2`** |
| la preuve s'engage sur une autre empreinte | **`FAIL`** — la liaison est réfutée | `1` |
| `opentimestamps` non installée | `NOT TESTED` — état inconnu ; la **liaison** est tout de même contrôlée | `2` |

Mesuré sur les deux preuves livrées dans `verifier/examples/timestamp/` : la
confirmée rapporte *2 attestations Bitcoin, blocs 974714 et 974715* ; celle en
attente rapporte *4 PENDING et AUCUNE Bitcoin*.

> 🔴 Une preuve `PENDING` n'est **jamais** présentée comme un horodatage
> confirmé, et **aucun horodatage qualifié eIDAS n'est revendiqué** —
> OpenTimestamps n'est pas un prestataire de services de confiance qualifié au
> sens du règlement.
>
> Même sur une preuve confirmée, *le temps vérifié par un tiers* reste
> `NOT TESTED` : valider une attestation Bitcoin demande un en-tête de bloc,
> donc une source de confiance que cet outil n'a pas. Ce contrôle est délégué
> au client officiel (`ots verify`). Un outil qui prétendrait vérifier le
> temps sans en-tête de bloc mentirait.

### Ce que le résultat permet d'affirmer — et ce qu'il ne permet pas

Un `0` dit : la structure de cette archive, ses empreintes et ses absences
déclarées sont cohérentes entre elles, selon les contrôles qui ont tourné.

Il n'établit **pas** l'authenticité (`verify` ne contrôle aucune signature),
la vérité du contenu (une signature valide sur une archive fabriquée reste
cryptographiquement valide), la capacité juridique du signataire, un
horodatage indépendant, ni un ancrage tiers. Et une observation effacée
*cohéremment* — décomptes et sommes refaits — passe tous les contrôles
internes ; seule une empreinte conservée ailleurs la détecte.

Liste complète : [`references/LIMITS.fr.md`](references/LIMITS.fr.md).
L'indépendance, en une ligne : ce sont **nos** vérificateurs sur **notre**
corpus — les exécuter confirme que nos outils se comportent comme décrit, pas
que la conception est juste.

## Ce qui est démontrable aujourd'hui

| | |
|---|---|
| **Corpus de conformité gelé** | 50 cas, 121 fixtures, **172 entrées sous empreinte** — rejouables depuis un clone anonyme, sans aucun identifiant |
| **Spécification** | **102 règles normatives**, chacune avec sa couverture publiée : 81 `COVERED`, 12 `PARTIAL`, **3 `GAP`**, 6 `NOT TESTABLE` |
| **Revues indépendantes** | **trois** relecteurs externes — pour chacun le périmètre, les limites, la PR du moteur, son commit de fusion et sa date dans [`references/REVIEWS.fr.md`](references/REVIEWS.fr.md) |
| **Implémentations de référence** | les vérificateurs Python **et deux vérificateurs Rust indépendants** |
| 🔴 **Ce que ce n'est pas** | ce sont **nos** vérificateurs, sur **notre** spécification, contre **notre** corpus. Un tiers qui les exécute confirme que nos outils se comportent comme annoncé — **pas** que la conception est juste. |

## Trois choses, et elles ne sont pas interchangeables

| | | |
|---|---|---|
| **Moteur Evidence** | 🔴 **privé** | produit et **signe**. Non publié, non installable, non embarqué ici. |
| **Evidence Gateway** | 🟢 public, *ce dépôt* | la frontière d'entrée/sortie autour du moteur : une enveloppe de requête versionnée en entrée, une enveloppe de réponse versionnée en sortie. **Il ne vérifie rien lui-même.** |
| **Vérificateur public** | 🟢 public — [`verifier/`](verifier) et sur [PyPI](https://pypi.org/project/neomundi-evidence-verify/) | **revérifie** ce que le moteur a produit : spécification, corpus gelé, vérificateurs Python, deux vérificateurs Rust. Apache-2.0. |

Seul le **moteur** produit de la preuve. Le **vérificateur** est ce qu'on
remet à quelqu'un qui ne devrait pas avoir à nous faire confiance. Lire
[`NOTICE`](NOTICE) avant tout réemploi : ce dépôt est délibérément à licences
mixtes.

## Le gateway ne vérifie rien — et c'est le produit

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

## Employer le gateway

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
| [`verifier/`](verifier) | 🟢 la **surface publique de vérification** — spécification, corpus de conformité gelé, vérificateurs Python et deux vérificateurs Rust indépendants. Bibliothèque standard seule. [Notice](verifier/README.fr.md) |
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
dans le tableau `limits` de la réponse, préfixé `engine:`. Voir le document de
limitations propre au moteur, qui n'est pas public — ses lignes
`does_not_establish` sont recopiées dans
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
EVIDENCE_ENGINE_HOME="$PWD/verifier" python gateway.py \
  verify conformance/fixtures/A-valid/A-05-archive-valid/archive.zip \
  --artifact-root "$PWD/verifier"
```

⚠ `artifact.path` est résolu **relativement à `--artifact-root`**, jamais au
répertoire courant. Un chemin qui sort de cette racine est refusé avec le code
`4` et `artifact_not_found` — le gateway n'élargit jamais la racine en
silence.

## Droits

Le **vérificateur public est sous Apache-2.0** — voir
[`LICENSE`](LICENSE). La concession porte sur le vérificateur et sur ce
gateway, et sur **rien d'autre** : le moteur Evidence reste propriétaire, et
[`NOTICE`](NOTICE) énumère ligne par ligne ce qui est couvert et ce qui ne
l'est pas. Lire `NOTICE` avant tout réemploi : ce dépôt est délibérément à
licences mixtes.

Apache-2.0 concède des droits sur le *logiciel*. Elle ne concède rien sur ce
qu'une vérification établit, et son §6 ne concède aucun droit de marque.

Signaler une faille en privé à
[contact@neomundi.io](mailto:contact@neomundi.io) — ne jamais envoyer de clé
privée, de matériel de signature de magasin de confiance ni de secret de
pilote.

Les travaux de relecture et de qualification indépendantes du moteur Evidence
sont crédités dans le dépôt du moteur, pas ici.

**[Découvrir NeoMundi](https://neomundi.io)** · **[Discuter d'un pilote](mailto:contact@neomundi.io)**
