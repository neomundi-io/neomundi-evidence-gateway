<sub>🇬🇧 <a href="VERIFICATION_RESULTS.md">English</a> · 🇫🇷 <b>Français</b> · <a href="../README.fr.md">← README</a></sub>

# Résultats de vérification et empreintes de traçabilité

Ce qui a été mesuré, quand, contre quelle révision, et avec quelle empreinte.
Tout ce qui figure ici est une **mesure consignée**, pas une affirmation de
qualité. Lire [`LIMITS.fr.md`](LIMITS.fr.md) avant d'en citer quoi que ce
soit.

**Date de référence : 2026-11-14.**

---

## Les révisions auxquelles ces chiffres appartiennent

| Composant | Révision | Note |
|---|---|---|
| moteur Evidence | **`3391c768f55b08590624aa1c24fe65fdb6420191`** | `main` au moment de la mesure ; commit de fusion de la PR #39 du moteur |
| arbre du moteur | `75fd66b4df098b60b4a08f1e52a8b92aefacc1df` | — |
| tag de gel | **`v1.0.0-rc1`** → `ee36e9470ee17117b6794ad886021c33355b1ca0` | seul tag ; **aucune release GitHub n'existe** |
| corpus de conformité | **1.3.0** | 50 cas, 7 familles, 121 fichiers de fixture |
| ce gateway | **`2573760b2f153a48ce74e7250dd3598908aabf50`** | arbre `1aa54e9ba3dbdb8efedcb524ab514c8c0634c091` |

Un identifiant de révision est une déclaration jusqu'à ce qu'il soit
confronté à des octets. Les empreintes ci-dessous sont ce qui rend ces lignes
contrôlables.

## Empreintes — les ancrages de traçabilité

| Artefact | sha256 | Accessible ici ? |
|---|---|---|
| **magasin de confiance** (3038 o) | `dac94e8ad4baf0a48fe94b8006a238d970d242cdc52b8d9dd51294777751598d` | 🟢 **oui** — [`../trust/trust-store.json`](../trust/trust-store.json) |
| `SHA256SUMS` du corpus (21 202 o, 172 lignes) | `e3edeb26c54363ace46737563f4824f79a0adab2baebcb8351bb15d632a6a297` | 🔴 non — empreinte consignée, artefact dans le dépôt du moteur |
| `manifest.json` du corpus | `2720995161e6b98ee707c72ba3000a5029d8e49a07f1e80de3cf6da82fdd5ec2` | 🔴 non — idem |
| archive de démonstration V1 (celle des cinq scénarios) | `e31e12bb7e32c7a33db1ecacc8c38cd18225fa10618c7e1aa5d6f9540f2ad7d6` | 🔴 non — dans le dépôt du moteur |

🔴 **Une empreinte sans artefact atteignable est un ancrage, pas une preuve.**
Trois des quatre lignes ci-dessus sont exactement cela, et le tableau le dit
au lieu de laisser croire autre chose. Le magasin de confiance a été déplacé
ici précisément pour ne pas en être une.

## Mesures du moteur, telles que consignées sur `3391c768`

| Mesure | Résultat |
|---|---|
| CI du moteur sur `main` | **11 check-runs, 11 success** |
| suites déclarées en CI | **29** fichiers `test_*.py`, **28 invoqués** — le seul non invoqué est `test_timestamp_network.py`, exclu délibérément (réseau). Mesuré contre le workflow, lignes de commentaire écartées |
| corpus de conformité, vérificateur Python | **40 PASS, 10 AMBIGUOUS, 0 FAIL**, et **0 écart de code de sortie sur un verdict concordant** |
| `sha256sum --check SHA256SUMS` sur le corpus | **OK** |
| suite de falsification nommée | **10/10 détectées**, 1 limite déclarée |
| suite d'attestation | 24/24, dont un `alg` falsifié (`none` / `HS256` / `RS256`) → **3/3 refusés** |
| falsification d'archive | 10/10 · lien externe | 18 contrôles |
| schémas publiés | **10** fichiers dans `schemas/`, **10** valides draft-2020-12, **10** fermés (`additionalProperties: false`) — mesuré |

⚠ **Les 10 AMBIGUOUS ne sont ni des échecs ni des réussites.** Ce sont les cas
où le contrat ne tranche pas, et sur trois d'entre eux les deux
implémentations de référence sont **mesurées comme divergentes**. Le corpus
les nomme au lieu de les lisser. Un décompte de PASS n'est pas probant en
soi.

## Mesures du gateway, telles que consignées sur `2573760b`

| Mesure | Avec le moteur | Sans le moteur |
|---|---|---|
| `tests/test_gateway.py` | **26 PASS, 0 FAIL, 0 NOT TESTED** | 17 PASS, 0 FAIL, **1 NOT TESTED** |
| `tests/test_no_verification_logic.py` | **7 PASS, 0 FAIL, 0 NOT TESTED** | 6 PASS, 0 FAIL, **1 NOT TESTED** |
| `demo/demo.sh` | 5 scénarios, **5 codes observés = 5 attendus** | 2 scénarios, 2 = 2 |
| CI du gateway sur `main` | **4 check-runs, 4 success** | — |

Les lignes `NOT TESTED` sont les cas qui exigent le moteur. Ils sont rapportés
comme non éprouvés, jamais comme réussis.

### Les cinq scénarios, et le code que chacun rend

| # | Scénario | Statut | Code | Verdict du moteur |
|---|---|---|---|---|
| 1 | artefact valide, corpus fourni, strict | `completed` | **0** | `no_failure` — 19 PASS / 0 FAIL / 3 NOT TESTED |
| 2 | artefact altéré (un membre réécrit) | `completed` | **1** | `fail` — 16 PASS / **1 FAIL** / 4 NOT TESTED |
| 3 | artefact non vérifiable (sans corpus, strict) | `completed` | **2** | garantie requise nommée : empreintes des entrées rejouées |
| 4 | erreur d'entrée ou de schéma | `rejected` | **4** | aucun — **aucune vérification n'a eu lieu** |
| 5 | moteur indisponible | `engine_unavailable` | **3** | aucun — **aucune vérification n'a eu lieu** |

### La mesure qui compte le plus

`tests/test_no_verification_logic.py`, épreuve **C** : le verdict que le
gateway republie est confronté, champ par champ, à un appel **direct** au
moteur sur le même artefact.

> **22 lignes de contrôle identiques** (états et intitulés, même ordre),
> `counts` identiques, `required_not_demonstrated` identique, **même code de
> sortie**.

C'est cela qui fonde « le gateway ne duplique aucune logique de
vérification ». Pas le README qui le dit.

### Reproductibilité, mesurée — et sa limite

Deux passages successifs de la démonstration : **verdicts et codes de sortie
identiques**, et **4 des 5 réponses identiques à l'octet**.

⚠ La cinquième ne l'est pas. Le scénario 2 refabrique l'archive altérée à
chaque passage ; un ZIP porte l'horodatage de ses membres, donc son `sha256`
change (`f16a0844…` puis `0df147d7…`). **Le verdict et les comptes, eux, sont
identiques** (`fail`, 16/1/4). Comparer les verdicts, jamais l'empreinte
d'une archive refabriquée.

## Ce qui n'est *pas* sur cette page

- aucun résultat produit par un tiers sur sa propre infrastructure. Chaque
  chiffre ci-dessus a été mesuré par NeoMundi, sur des machines NeoMundi ou
  dans la CI de NeoMundi. Les observations de relecteurs consignées dans
  [`REVIEWS.fr.md`](REVIEWS.fr.md) ont été **reproduites** par NeoMundi — et
  reproduire n'est pas être indépendant ;
- aucune affirmation selon laquelle `external-link/1` aurait été exercé hors
  de NeoMundi. Il ne l'a pas été ;
- aucun chiffre des dossiers privés Q-1 / Q-2, qui ne sont pas publiés.
