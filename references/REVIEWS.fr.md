<sub>🇬🇧 <a href="REVIEWS.md">English</a> · 🇫🇷 <b>Français</b> · <a href="../README.fr.md">← README</a></sub>

# Revues indépendantes — attributions et références techniques

Trois relecteurs externes ont examiné NeoMundi Evidence en novembre 2026.
Chaque revue a changé le produit. Cette page consigne **ce que chacun a
réellement fait**, et garde la trace technique atteignable quelle que soit la
visibilité du dépôt du moteur.

> **Pourquoi cette page existe.** Chaque référence technique ci-dessous pointe
> dans le dépôt du **moteur** Evidence,
> `neomundi-io/neomundi-evidence-public`. L'accès à ce dépôt est **accordé,
> non présumé** — voir [`LIMITS.fr.md`](LIMITS.fr.md) pour son état courant.
> Rien n'a été supprimé et aucun historique n'a été réécrit : les pull
> requests, leurs diffs et leurs commits de fusion existent inchangés. Mais
> une attribution ne doit pas dépendre de qui peut ouvrir un lien : tout
> identifiant, date, commit de fusion et chiffre mesuré est donc consigné ici
> en entier.

---

## Mark Mocnaj — Project Petunia × Judicator (OGS)

**Périmètre examiné.** Interopérabilité et ingestion : la soumission OGS B-3
v2 a servi à éprouver l'ingestion Evidence, la compatibilité de schéma,
l'intégrité des artefacts et le rejeu déterministe.

**Ce que la revue a trouvé.** Quatre anomalies d'ingestion, chacune un défaut
réel de l'adaptateur et non de la soumission :

| | Anomalie | Cause dans l'adaptateur |
|---|---|---|
| A | représentation du type d'exécution | un test de **vacuité** au lieu d'un test d'appartenance — toute chaîne non vide passait, alors que le message disait lui-même « absent » |
| B | format d'horodatage déclaré | **aucun contrôle**, pas même de type : les sept formes JSON éprouvées étaient acceptées |
| C | rôle d'artefact manquant | une lecture optionnelle qui rendait `None` sans objecter |
| D | métadonnée pilote valuée en liste | une garde qui ne protégeait pas d'une **liste non vide** → plantage, et **aucun rapport** |

**Ce qui a changé.** L'adaptateur a été corrigé et éprouvé en régression ; les
quatre règles rejettent désormais avec le code 1, et le cas D rejette **avec**
rapport. La cause structurelle a été traitée aussi : l'adaptateur
réimplémentait à la main les règles des schémas, donnant deux sources de
vérité. **Aucun fichier de `schemas/` n'a été modifié — le contrat `/2` n'a
pas été touché**, et les 25 profils existants ont gardé leurs verdicts.

Le candidat **inchangé** a ensuite passé les contrôles techniques d'ingestion
documentés, dont **19 empreintes et décomptes d'octets d'artefacts** et
**cinq cas de rejeu déterministe**.

**Limite.** Ceci établit une compatibilité d'ingestion **bornée** — ni
certification des revendications amont, ni aptitude générale à la production,
ni validation scientifique complète.

**Référence technique.** Pull request **#24** du moteur, *« fix(ingestion) :
le code applique les regles que le contrat /2 publie »* — fusionnée le
**2026-11-11T11:21:23Z**, commit de fusion **`330ecb03`**, tête `4be3fca9`,
7 commits, 13 fichiers, +3457/−35. **Archivée dans le dépôt du moteur.**

**État de l'attribution.** 🟢 **Approuvée.** Publiée avec l'accord de ce
contributeur dans [`neomundi-use-cases`](https://github.com/neomundi-io/neomundi-use-cases)
le 2026-11-14.

---

## Dennis Christie — ASIN-HHC / CP8

**Périmètre examiné.** Reproductibilité et preuve d'exécution. Le relecteur a
examiné des reçus de mesure NeoMundi et les frontières de vérification
d'Evidence, à partir d'un paquet d'exécution CP8 contrôlé existant et de
matériaux de réconciliation.

**Ce que la revue a trouvé.**

- une **mesure IA** rapportée est un objet différent de l'**exécution de
  l'outil externe** sous-jacente, et les deux n'étaient pas distinguées assez
  clairement ;
- un agrégat **brut** (**0,3863**) face à un affichage de tableau de bord
  **normalisé** plus ancien (**0,594**) — **deux représentations NeoMundi de
  la même chose, et non deux mesures contradictoires venues de deux
  parties**.

**Ce qui a changé.** Un traitement plus strict de la couverture d'empreintes,
une séparation plus nette entre relations déclarées et relations vérifiées
indépendamment, des contrôles de régression supplémentaires, et des
corrections de documentation. La consolidation a en outre découvert, en
agissant sur la revue, que **trois champs déclarés du contrat étaient morts**
— `byte_length_declared`, `declared_by`, `issuer_declared` : leur prose de
schéma énonçait la règle correcte alors qu'aucun code ne l'appliquait.
Falsifié sur matériel réel : **999999** octets annoncés sur un fichier de
**1416** rendaient **VÉRIFIÉE**. Cela rend désormais **CONTRADICTOIRE**.

**Limites.** L'exécution externe n'est **pas encore** liée
cryptographiquement ni opérationnellement à la mesure IA distincte. Une
empreinte SHA-256 n'est pas une signature et n'authentifie pas un émetteur.
L'authentification de l'émetteur et la conservation des extraits restent
ouvertes. C'est une revue méthodologique **bornée** — ni validation
indépendante de bout en bout, ni certification de performance, ni approbation
de la plateforme.

**Référence technique.** Pull request **#38** du moteur, *« Consolidation
après audit externe : trois champs déclarés cessent d'être des champs
morts »* — fusionnée le **2026-11-13T16:03:04Z**, commit de fusion
**`439d1549`**, tête `ef66edca`, 6 commits, 17 fichiers, +2010/−43.
**Archivée dans le dépôt du moteur.**

**État de l'attribution.** 🟢 **Approuvée.** Publiée avec l'accord de ce
contributeur dans [`neomundi-use-cases`](https://github.com/neomundi-io/neomundi-use-cases)
le 2026-11-14.

---

## Un relecteur externe — corpus de conformité et mode strict

🟡 **Aucun remerciement nominatif n'est fait sur cette page**, et c'est
délibéré. Un tel remerciement a été rédigé dans la pull request **#40** du
moteur, qui porte une barrière de publication explicite — *« DO NOT MERGE
without the reviewer's approval of their name and exact wording »* — et qui
**reste ouverte et non fusionnée**. Présenter comme approuvée une attribution
en attente serait précisément ce que cette page ne doit pas faire. La place
est réservée ; le remerciement sera fait quand, et seulement quand, cet
accord existera.

⚠ **Une distinction, énoncée plutôt que laissée à découvrir.** Le relecteur
**est** nommé dans [`../verifier/conformance/CHANGELOG.md`](../verifier/conformance/CHANGELOG.md)
et dans deux commentaires de `../verifier/conformance/runners/run.py`, comme
**rapporteur** des observations ci-dessous — exactement comme le moteur l'a
consigné lors de la fusion du 13 novembre. Publier le corpus de conformité a
emporté ce compte rendu avec lui, verbatim. Retirer un crédit de rapporteur
pour pouvoir republier un corpus gelé aurait été pire que le conserver : cela
aurait édité un compte rendu daté et dépouillé une attribution. Le compte
rendu subsiste donc, et le *remerciement* reste en attente. Ce sont deux
choses différentes, et cette page ne les confond pas.

**Périmètre examiné.** Une vérification indépendante du dépôt du moteur alors
public, menée le **13 novembre 2026**.

**Ce que le relecteur a réellement signalé — deux observations, toutes deux
reproduites à la ligne.**

1. `verify_attestation.py` sortant en **0** sur une signature falsifiée
   lorsqu'**aucun magasin de confiance** n'est fourni ;
2. **cinq échecs de corpus supplémentaires** dans un environnement sans la
   dépendance optionnelle `cryptography`.

**Ce que ces deux observations se sont révélées être.**

- la première était **intentionnelle et déjà documentée** : le code 0
  signifie « aucun contrôle n'a échoué », et un magasin absent rend
  `NOT TESTED`, non un échec. Mais `docs/ATTESTATION.md` présentait encore le
  mode strict comme un *besoin futur*, ce qui a très probablement motivé la
  recommandation de le construire. C'est la documentation qui était fausse,
  pas le comportement ;
- la seconde était **réelle au niveau du banc** : une dépendance absente
  était rapportée comme *« échecs non déclarés — régression »*, sans nommer
  nulle part la dépendance.

**Ce qu'il ne faut PAS attribuer à ce relecteur.** Aucune des deux
observations ne portait sur `exit_code_strict`. C'est **l'enquête qu'elles
ont déclenchée** qui a mis au jour un défaut distinct : le banc de conformité
n'ajoutait `--strict` qu'à **cinq de ses sept** chemins de commande, de sorte
que trois valeurs attendues fausses ne pouvaient pas apparaître et que la CI
restait verte sur une affirmation qu'elle n'éprouvait pas. Ce constat, et les
trois fiches corrigées, **ne sont pas** les revendications de ce relecteur :
ce sont les conséquences de ce que sa revue a fait chercher.

**Ce qui n'a PAS changé** dans le corpus 1.3.0 : **121 fichiers de fixture,
0 modifié** — mêmes octets, mêmes empreintes ; et 50 cas, 7 familles,
40 normatifs + 10 ambigus, tous inchangés.

**Référence technique.** Pull request **#39** du moteur, *« Audit externe : le
banc ne transmettait pas --strict, et une dependance absente passait pour une
regression »* — fusionnée le **2026-11-13T22:07:50Z**, commit de fusion
**`3391c768`**, tête `1c248d02`, 69 fichiers, +1334/−348. Pull request **#40**
(remerciement nominatif) **ouverte, non fusionnée**, tête `cc5f3223`. Les
deux **archivées dans le dépôt du moteur**.

**État de l'attribution.** 🟡 **En attente de l'accord du relecteur.** Non
approuvée, et non présentée comme approuvée.

---

## Ce que cette page n'est pas

- ce n'est **pas** une certification, une approbation ni une revendication de
  partenariat, par ou envers un relecteur ;
- aucun relecteur n'est présenté comme l'organisme de certification de
  NeoMundi, et aucun n'hérite d'une autorité de NeoMundi ;
- une revue établit ce qu'elle a examiné, dans le périmètre qu'elle a
  examiné. Les *Limites* propres à chaque revue ci-dessus font partie de
  l'attribution, ce n'est pas une clause ajoutée après coup ;
- la paternité du **code correctif** est celle de **NeoMundi**, et elle est
  distincte des contributions de relecture consignées ici.

Voir aussi [`VERIFICATION_RESULTS.fr.md`](VERIFICATION_RESULTS.fr.md) pour ce
qui a été mesuré, et [`LIMITS.fr.md`](LIMITS.fr.md) pour ce que coûte le
passage du moteur en privé.
