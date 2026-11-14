<sub>🇬🇧 <a href="README.md">English</a> · 🇫🇷 <b>Français</b> · <a href="../README.fr.md">← README</a></sub>

# La surface publique de vérification

Tout ce qu'un tiers doit détenir pour vérifier un artefact NeoMundi Evidence
**sans aucun accès au dépôt privé du moteur** — et pour contrôler nos
chiffres au lieu de les croire.

```
227 fichiers · 2,1 Mo · bibliothèque standard Python seule (une dépendance Rust optionnelle)
```

---

## Pourquoi ceci existe

Le moteur Evidence est privé. Si la vérification y était restée, chaque
chiffre que nous publions aurait été infalsifiable par quiconque hors de
NeoMundi. Ces fichiers sont la part qui doit être publique pour que
« vérification indépendante » veuille dire quelque chose.

**Ce n'est pas le moteur.** Ce qui reste privé est tout ce qui *produit* et
*signe* : génération de clés et attestation (`sign.py`), construction de
liaison, horodatage, publication du magasin de confiance, les adaptateurs de
réconciliation pilote, les dossiers privés et les rapports internes datés. Ce
qui est ici ne fait jamais que *lire et juger*.

## Ce qui est ici

| | |
|---|---|
| [`spec/`](spec) | la **spécification normative** — Evidence Protocol v1, Candidate Specification. Écrite pour être suffisante seule : l'implémenter ne doit pas exiger de lire `verify.py` |
| [`conformance/`](conformance) | le **corpus public gelé** — 50 cas, 7 familles, 121 fichiers de fixture, 172 entrées couvertes par empreinte, `VERSION` 1.3.0 |
| [`verify.py`](verify.py) | vérificateur d'archive — **bibliothèque standard seule**, aucun réseau |
| [`verify_attestation.py`](verify_attestation.py) | vérificateur d'attestation détachée Ed25519/JWS (exige `cryptography`, et rend `NOT TESTED` sans elle — jamais `PASS`) |
| [`canonical.py`](canonical.py) | le profil de canonicalisation dont dépend `verify_attestation.py` |
| [`i18n.py`](i18n.py) | les traductions. **Optionnel** : le supprimer laisse les outils tourner, rendre les mêmes verdicts et les mêmes codes de sortie, en français |
| [`adapters/ingest.py`](adapters/ingest.py) | vérificateur de paquet de soumission. **35 des 50 cas du corpus en ont besoin** |
| [`verifier-rs/`](verifier-rs) | un **second vérificateur indépendant**, en Rust — son `Cargo.lock` ne porte **qu'une** entrée, donc l'absence de dépendance se constate **sans compiler** |
| [`verifier-rs-crypto/`](verifier-rs-crypto) | le vérificateur de signatures et d'archives en Rust. Ed25519 n'est **pas** réimplémenté : il emploie `ed25519-dalek` |

## Contrôler nos chiffres — les quatre commandes

```sh
# 1. le corpus est intact, a l'octet
cd conformance && sha256sum --check SHA256SUMS      # 172/172 OK attendu

# 2. le jouer avec le verificateur Python
python3 runners/run.py --verifier python            # 40 PASS, 10 AMBIGUOUS attendu

# 3. un artefact valide, puis un artefact altere
cd .. && python3 verify.py conformance/fixtures/A-valid/A-05-archive-valid/archive.zip
python3 verify.py conformance/fixtures/D-tampered/D-10-archive-member-tampered/archive.zip
echo $?                                             # 1 attendu : un controle a ECHOUE

# 4. le piege pour lequel le mode strict existe
F=conformance/fixtures/A-valid/A-07-attestation-store-not-confronted
python3 verify_attestation.py $F/attestation.jws --archive $F/archive.zip ; echo $?          # 0
python3 verify_attestation.py $F/attestation.jws --archive $F/archive.zip --strict ; echo $? # 2
```

Le dernier couple est tout l'objet du produit : **quatre situations
différentes rendent `0`** par défaut, et seul `--strict` sépare « démontré »
de « non éprouvable ». Les lignes de contrôle sont **identiques à l'octet**
avec et sans le drapeau — le mode strict change le code de sortie, jamais un
verdict.

### Les deux vérificateurs Rust

```sh
cd verifier-rs       && cargo build --release && cargo test --release
cd ../verifier-rs-crypto && cargo build --release
cd ../conformance && python3 runners/run.py --verifier all \
   --bin-rust-core   ../verifier-rs/target/release/evidence-verify-rs \
   --bin-rust-crypto ../verifier-rs-crypto/target/release/evidence-verify-crypto
```

⚠ `verifier-rs-crypto` tire `ed25519-dalek` et sa fermeture transitive —
**23 entrées dans son `Cargo.lock`**. Une première compilation exige donc un
accès réseau à un registre de caisses. `verifier-rs`, lui, non : il compile
hors ligne avec rien.

⚠ Les deux caisses **doivent rester sœurs**. `verifier-rs-crypto` atteint six
modules partagés par `#[path = "../../verifier-rs/src/…"]` — ce sont *les
mêmes fichiers*, pas une copie à faire dériver. Déplacer l'un des deux
répertoires casse la compilation.

## Ce que le corpus vous dira, y compris sur nous

Mesuré en salle blanche le 2026-11-14, depuis ces seuls fichiers, sans aucun
accès au dépôt privé :

| Vérificateur | Résultat |
|---|---|
| Python | **40 PASS, 10 AMBIGUOUS** |
| `evidence-verify-rs` | 27 PASS, 8 AMBIGUOUS, 15 non applicables |
| `evidence-verify-crypto` | 13 PASS, 2 AMBIGUOUS, 35 non applicables |
| les trois | **80 PASS, 20 AMBIGUOUS, 50 non applicables — 0 écart de code de sortie sur un verdict concordant** |

Trois choses à lire correctement :

- **un refus attendu est une réussite.** Le décompte de PASS comprend des
  paquets correctement *refusés* ;
- **les 10 AMBIGUOUS ne sont ni l'un ni l'autre.** Ce sont les cas que le
  contrat ne tranche pas, et sur certains les deux implémentations de
  référence sont **mesurées comme divergentes**. Le corpus les nomme au lieu
  de les lisser ;
- **« non applicable » n'est ni un échec ni une réussite.** Le dénominateur
  de tout taux est le nombre de cas applicables au vérificateur concerné —
  pas 50.

## Le fichier de traçabilité est la partie honnête

[`spec/traceability.json`](spec/traceability.json) consigne chaque règle
normative et ce qui l'éprouve. Mesuré sur cette révision (`1.0.0-rc.1`,
corpus 1.3.0) : **102 règles**.

| `coverage` — existe-t-il un test ? | | `reference_implementations` — la respectons-nous ? | |
|---|---|---|---|
| COVERED | **81** | CONFORMING | **97** |
| PARTIAL | 12 | PARTIAL | 2 |
| GAP | **3** | UNKNOWN | **3** |
| NOT TESTABLE | 6 | | |

Les deux colonnes sont **délibérément séparées** : une règle peut être bien
couverte et pourtant violée, et c'est précisément ce qu'il faut pouvoir lire.
Les 3 `GAP` et les 3 `UNKNOWN` sont déclarés, pas cachés.

> ⚠ Notre propre README a longtemps dit « 97 règles normatives ». C'était le
> compte d'une révision antérieure ; des règles ont été ajoutées par les
> consolidations du 13 novembre. **102** est le chiffre mesuré ici. Préférer
> le fichier à toute prose, y compris la nôtre.

## Ce que cela ne donne pas

- **cela ne rend pas la vérification indépendante de nous.** Ce sont *nos*
  vérificateurs, sur *notre* spécification, contre *notre* corpus. Un tiers
  qui les exécute confirme que nos outils se comportent comme nous le disons
  — pas que la conception est juste. L'indépendance supposerait un
  vérificateur écrit par un autre ; celui en Rust existe précisément pour que
  deux implémentations puissent être *comparées*, et leurs divergences
  déclarées sont publiées ;
- cela n'établit rien sur la vérité d'un contenu, la capacité juridique d'un
  signataire, un horodatage indépendant ou un ancrage tiers — voir
  [`../references/LIMITS.fr.md`](../references/LIMITS.fr.md) ;
- le corpus est **gelé**. Il est une preuve sur les cas qu'il contient, et
  muet sur tous ceux qu'il ne contient pas.

## Une conséquence du fait de republier sans modifier

Ces 227 fichiers sont une republication **à l'octet** de ce que porte le
moteur — propriété affirmée dans l'historique de ce dépôt et vérifiée par
`tests/test_corpus_public.py`. Donc certains d'entre eux portent encore des
liens et des instructions de clonage vers
`neomundi-io/neomundi-evidence-public`, qui est privé :
`conformance/README.md` en est le cas le plus net.

Ces liens sont laissés tels quels, délibérément. Éditer un artefact gelé
republié pour faire le ménage dans un lien coûterait la seule propriété qui
rend ce corpus digne d'être publié. **Lire un tel lien comme nommant la
provenance du fichier, non comme un endroit où aller.** Pour cloner le
corpus, cloner ce dépôt-ci.

## Droits

Ces fichiers sont publiés pour la **vérification et la revue**. Aucune licence
de réemploi n'est accordée par ce dépôt ; les droits sont réservés. Les deux
caisses Rust portent `license = "Apache-2.0"` dans leur propre `Cargo.toml`,
comme à leur première publication — cette déclaration subsiste et n'est pas
retirée ici. Voir [`../references/LIMITS.fr.md`](../references/LIMITS.fr.md),
*Les droits*.
