# Corpus de conformité Evidence — synthèse française

> La référence complète est [`README.md`](README.md), en anglais : ce corpus
> est destiné à des développeurs externes. Ce document en est la synthèse,
> pas une traduction ligne à ligne.

**Version 1.3.0** · 50 cas · 7 familles · 121 fichiers de fixtures ·
172 empreintes dans `SHA256SUMS`

Aucune infrastructure NeoMundi n'est nécessaire. Tout tourne hors ligne.

Les codes de sortie, le mode `--strict` et la lecture des rapports JSON sont
contractuels : [`../docs/INTEGRATION.fr.md`](../docs/INTEGRATION.fr.md).

---

## Les trois questions, et les trois non-réponses

Le corpus permet de décider :

1. un paquet est-il **conforme** à une version donnée du protocole ?
2. un vérificateur **applique-t-il** correctement les règles correspondantes ?
3. deux implémentations indépendantes **concordent-elles** sur les contrôles
   qu'elles déclarent prendre en charge ?

Il ne permet pas de décider :

| Hors de portée | Pourquoi |
|---|---|
| l'événement attesté est-il **vrai** ? | l'intégrité n'est pas la vérité, et aucun cas ne la mesure |
| le signataire est-il **qui il prétend être** ? | un magasin de confiance *déclare* des identités ; aucun code ne les vérifie |
| l'implémentation est-elle **sûre** ? | un corpus produit des contre-exemples, pas une preuve d'absence |

---

## Prérequis

| Vérificateur | Périmètre | Dépendances |
|---|---|---|
| `python` — soumissions, archives | Python 3.11+ | **aucune** — `verify.py` n'importe que la bibliothèque standard |
| `python` — **attestations** | Python 3.11+ | **`cryptography`** |
| `rust-core` | soumissions seulement | **aucune** — `Cargo.lock` a une seule entrée |
| `rust-crypto` | archives et attestations | `ed25519-dalek` (23 paquets verrouillés) |

```bash
python3 -m pip install cryptography     # pour les cas d ATTESTATION seulement
```

**Sans `cryptography`**, les neuf cas d'attestation sortent en
`NOT RUNNABLE` : le banc annonce la dépendance absente avant tout résultat,
et il sort en **code 2** — rien n'a échoué, mais tout n'a pas été éprouvé.
Ce n'est **ni** un `PASS` **ni** un échec de conformité. Les cas de
soumission et d'archive, eux, ne demandent rien.

> Ce comportement a été corrigé après le signalement d'un relecteur externe
> le 13 novembre 2026 : le banc rapportait alors cinq `FAIL` sous l'intitulé
> « échecs non déclarés — régression », sans nommer une seule fois la
> dépendance manquante.

---

## Vérifier, puis lancer

```bash
cd conformance
sha256sum --check SHA256SUMS            # d abord ceci
python3 runners/build_fixtures.py --check   # le generateur reproduit-il le corpus ?
python3 runners/run.py --verifier all
python3 runners/matrix.py --results reports/latest.json --out /tmp/COVERAGE.md
```

Le corpus est **figé**. Si un octet a bougé, le banc refuse d'aller plus
loin : il ne mesurerait plus ce que ses fiches annoncent.

---

## Les trois pièges de lecture

### 1. Un refus attendu est une RÉUSSITE

Un vérificateur qui **refuse** correctement un paquet malformé **réussit**
le test de conformité correspondant. Les familles B à E sont pour l'essentiel
des refus attendus. Les compter comme des échecs produirait un « taux de
conformité » qui récompense la permissivité.

### 2. `NOT APPLICABLE` n'est pas un échec

`rust-core` ne couvre que la **soumission** ; `rust-crypto` que l'**archive**
et l'**attestation**. Aucun des deux ne prétend le contraire. Reprocher à un
outil de ne pas faire ce qu'il n'annonce pas serait une mesure fausse — et
gonflerait le dénominateur de l'autre.

| Vérificateur | Cas applicables, sur 50 |
|---|---|
| `python` | **50** |
| `rust-core` | **35** |
| `rust-crypto` | **15** |

### 3. `AMBIGUOUS` est un état du banc, pas un verdict du protocole

Aucun vérificateur ne rend « ambigu ». C'est **ce rapport** qui refuse de
trancher là où le contrat est muet. Dix cas sur cinquante sont ambigus, et
chacun nomme la lacune : clefs JSON en double, `NaN`, `Infinity`, demi-paire
de substitution, bourrage et alphabet base64url, champ en surplus, chemin à
segment `.`, chemin déclaré deux fois.

**Et une divergence sur un cas ambigu est désormais publiée.** Le banc
compare les verdicts observés des vérificateurs applicables et les rapporte
sous `ambiguous_divergences`, dans une section dédiée et dans la colonne
**Divergent ?** de la matrice. **6 des 10** cas ambigus divergent.

Ce n'est pas un échec de conformité — le contrat ne tranche pas — mais c'est
ce qu'un silence normatif produit de dangereux : **deux vérificateurs
honnêtes, un seul fichier, deux verdicts.** Jusqu'en 1.1.0 le banc mesurait
chaque verdict sans jamais les comparer ; la divergence de `G-07` était dans
la donnée et invisible partout. Une divergence que les fiches ne déclarent
pas fait désormais rougir la CI.

---

## La famille F, et pourquoi elle attend des ACCEPTATIONS

Un paquet dont le contenu a été remplacé **et dont les empreintes ont été
recalculées** est cohérent avec son manifeste. **Il franchit une
vérification d'intégrité, et c'est correct.**

Chaque fiche de cette famille porte donc :

> `PLAFOND DECLARE` — le résultat attendu est une **acceptation**. Ne jamais
> convertir ce cas en `FAIL` pour améliorer un taux de détection.

Ce qui distingue un original d'une réécriture soignée est une **ancre
externe** : signature, horodatage tiers, empreinte conservée ailleurs.
`F-02` le montre — la même archive réécrite, confrontée à l'attestation
d'**origine**, est refusée.

---

## Les échecs déclarés, et pourquoi on ne les cache pas

`known_failures.json` liste les échecs **constatés et déclarés**. Le banc les
rapporte en `KNOWN FAIL` : visibles à chaque exécution, ils ne font pas
échouer la CI.

Sans ce mécanisme, la seule façon de rendre la CI verte serait de **retirer
le cas du corpus** — c'est-à-dire de supprimer la mesure qui dérange.

Un échec **non déclaré** fait rougir la CI. Une entrée **périmée** aussi : un
défaut déclaré qui ne se produit plus signifie soit qu'il est corrigé — et
l'entrée doit partir —, soit que le cas ne l'éprouve plus. Les deux demandent
une décision.

En 1.0.0 il y avait **un** échec déclaré, et ce corpus l'a trouvé :
`verify.py` levait une `zlib.error` non rattrapée sur un flux DEFLATE
invalide, et sortait en 1 **sans aucun verdict**.

**En 1.1.0 il n'y en a aucun** : le défaut est corrigé, et `C-09` passe sur
les trois vérificateurs. L'entrée n'est pas supprimée pour autant — elle vit
dans la section `resolved`, qui conserve son résultat d'origine. Et comme elle
n'est plus déclarée, un retour du défaut arriverait en échec **non déclaré** :
la régression se signale toute seule.

**Aucune attente n'a changé.** `C-09` attendait `REJETE` en 1.0.0 et l'attend
toujours. Le corpus avait raison ; l'implémentation, non.

---

## Les chiffres, et leur dénominateur

| | python | rust-core | rust-crypto |
|---|---|---|---|
| `PASS` | **40** | 27 | 13 |
| `AMBIGUOUS` | 10 | 8 | 2 |
| `KNOWN FAIL` | **0** | 0 | 0 |
| `NOT APPLICABLE` | 0 | 15 | 35 |
| écarts de **code** sur verdict concordant | 0 | 0 | 0 |

**Aucun pourcentage de conformité n'est publié.** Les comptes sont absolus,
avec leur dénominateur, parce qu'un taux calculé sur un corpus partiel se
lirait comme un taux sur le protocole.

---

## Provenance et publication

| | |
|---|---|
| licence | Apache-2.0, celle du dépôt |
| provenance | tout est **synthétique**, sauf trois fichiers repris de `examples/dossier-v1/` — déjà publics ici, déclarés « aucune donnée réelle » |
| données de pilote | **aucune** |
| clefs privées | **aucune**, nulle part |

Les contre-exemples cryptographiques sont des **altérations d'octets**,
jamais des signatures forgées : forger demanderait d'embarquer une clef
privée dans un corpus public. Les cas « mauvaise clef » et « substitution »
altèrent le **magasin**, qui ne contient que du public.

---

## Les dix limites

1. l'intégrité ne démontre pas la vérité ;
2. une signature valide ne certifie pas l'événement ;
3. une concordance Python/Rust ne garantit pas l'absence de défaut **commun** ;
4. le corpus **n'est pas exhaustif** — 50 cas citent 38 références
   normatives, et les contrats en comportent davantage ;
5. le fuzzing ne garantit pas l'absence de vulnérabilité ;
6. une falsification **cohérente** peut être acceptée ;
7. les ambiguïtés normatives ne sont pas masquées ;
8. une signature se lit **à travers sa politique de confiance** ;
9. une vérification hors ligne ne prouve aucun horodatage externe ;
10. aucun résultat n'établit une conformité **réglementaire**.
