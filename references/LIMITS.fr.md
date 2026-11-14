<sub>🇬🇧 <a href="LIMITS.md">English</a> · 🇫🇷 <b>Français</b> · <a href="../README.fr.md">← README</a></sub>

# Limites connues du dispositif

Ce que ce gateway, et la séparation dont il fait partie, **ne peuvent pas**
établir. Cette page fait partie du produit ; ce n'est pas une clause ajoutée
après coup.

---

## État du dépôt du moteur

> **`neomundi-io/neomundi-evidence-public` est PRIVÉ depuis le 2026-11-14.**
>
> Vérifié en anonyme, sans aucun jeton, au moment même de la bascule : le
> dépôt, sa fiche d'API, ses URL `raw` et ses pages de pull request répondent
> toutes **404**.
>
> **Rien n'a été supprimé et aucun historique n'a été réécrit.** `main` vaut
> toujours `3391c768f55b08590624aa1c24fe65fdb6420191`, les **7** branches sont
> intactes, le tag annoté `v1.0.0-rc1` est intact, et le dépôt comptait
> **0 fork** — donc aucune copie publique ne subsiste ailleurs. Tout le
> contenu et tout l'historique existent inchangés ; l'accès y est **accordé,
> non public**. Le demander à
> [contact@neomundi.io](mailto:contact@neomundi.io).

## 🟢 La re-vérification indépendante — rétablie, et bornée

Jusqu'au 14 novembre 2026, cette section disait que personne hors du moteur
ne pouvait rejouer une vérification. **Ce n'est plus vrai, et c'était à
corriger plutôt qu'à assumer.**

La surface de vérification est publiée dans
[`../verifier/`](../verifier) : la spécification normative, le corpus de
conformité gelé (50 cas, 121 fixtures, 172 entrées couvertes par empreinte),
les vérificateurs Python et les deux vérificateurs Rust indépendants.
227 fichiers, bibliothèque standard seule.

Mesuré en salle blanche le 2026-11-14 — ces seuls fichiers, aucun accès au
dépôt privé :

| | |
|---|---|
| `sha256sum --check SHA256SUMS` | **172 / 172 OK** |
| corpus, les trois vérificateurs | **80 PASS, 20 AMBIGUOUS, 50 non applicables**, **0 écart de code de sortie sur un verdict concordant** |
| artefact valide / artefact altéré | code **0** / code **1** |
| attestation sans magasin, puis avec `--strict` | code **0**, puis code **2** |

**Ce qui reste borné, et n'est pas une formalité :**

- ce sont **nos** vérificateurs, sur **notre** spécification, contre **notre**
  corpus. Les exécuter confirme que nos outils se comportent comme nous le
  décrivons — pas que la conception est juste. Le vérificateur Rust existe
  pour que deux implémentations puissent être *comparées* ; leurs divergences
  déclarées sont publiées en `AMBIGUOUS` plutôt que réconciliées ;
- le corpus est **gelé** : une preuve sur les cas qu'il contient, muet sur
  tous les autres ;
- `verifier-rs-crypto` exige un accès réseau à un registre de caisses à la
  première compilation (23 entrées de `Cargo.lock`). `verifier-rs`, non : il
  compile hors ligne avec rien, et cette asymétrie est délibérée ;
- **ce qui produit et signe reste privé** : génération de clés et attestation,
  construction de liaison, horodatage, publication du magasin de confiance,
  adaptateurs de réconciliation pilote. Rien d'ici ne peut forger une
  attestation.

## 🔴 Indépendance

Le gateway et le moteur qu'il invoque tournent **chez le même opérateur**,
sauf déclaration contraire de celui-ci. Chaque réponse le dit dans son
tableau `limits`, et la formulation est délibérée :

> *independence: […] A report produced here is a verification performed by
> that operator, not an independent third-party verification.*

Trois points de même poids :

- les observations de relecteurs de [`REVIEWS.fr.md`](REVIEWS.fr.md) ont été
  **reproduites** par NeoMundi. Reproduire soi-même n'est pas une
  confirmation indépendante ;
- les deux canaux du magasin de confiance
  ([`../trust/README.fr.md`](../trust/README.fr.md)) sont techniquement
  distincts mais tous deux sous la gouvernance de NeoMundi. Ils détectent un
  fichier substitué ; ils ne font pas de NeoMundi un tiers par rapport à
  lui-même ;
- `external-link/1` n'a **jamais** été exercé hors de NeoMundi.

## Ce qu'une vérification, quand elle a lieu, n'établit toujours pas

Recopié dans chaque réponse du gateway depuis le rapport du moteur :

- **l'authenticité** — le vérificateur d'archive ne contrôle aucune
  signature ;
- **la vérité du contenu** — une signature parfaitement valide sur une
  archive fabriquée est cryptographiquement valide. Signer établit un
  engagement et une custody, pas un fait ;
- **la capacité juridique du signataire** — aucun code ne l'établit. Le
  magasin de confiance publié déclare `legal_capacity_to_attest:
  experimental` pour son unique signataire, et énonce qu'**aucune
  vérification de ses pouvoirs n'a été faite** ;
- **l'horodatage indépendant** — `attested_at_declared` est déclaré par le
  signataire. Aucune horloge de confiance n'intervient ;
- **l'ancrage tiers** — déclaré `planned`, et **aucune vérification d'ancrage
  n'est implémentée**. Un ancrage non vérifié ne vaut pas mieux qu'un champ
  texte ;
- **le chaînage du registre** — hors de portée : le recalculer serait une
  seconde implémentation du registre ;
- **l'origine de l'archive** — aucune signature tierce, aucun ancrage.

Et une limite qu'aucun contrôle n'atteint : une observation effacée
*cohéremment* — décomptes et sommes refaits — passe tous les contrôles
internes. Seule une empreinte conservée ailleurs la détecte.

## Limites propres à ce gateway

- **2 des 12 points d'entrée du moteur sont exposés** : `verify` et
  `attestation`. Liaison, signature, horodatage, ingestion de paquet tiers et
  réconciliation ne le sont **pas** — nommés comme développements futurs dans
  [`../docs/INTERFACE.fr.md`](../docs/INTERFACE.fr.md), non tus. À noter que
  `verifier/adapters/ingest.py` **est** publié, parce que le corpus en a
  besoin ; c'est seulement le gateway qui n'expose pas encore d'opération
  pour lui ;
- **`engine.revision_declared` est déclarée, jamais vérifiée.** Ce gateway ne
  lance aucun `git` et ne contrôle aucune signature sur l'arbre du moteur. Il
  ne peut pas établir qu'un répertoire correspond à un commit ;
- **le rapport republié n'est pas identique à l'octet** à ce que le moteur a
  écrit : les chemins locaux sont rédigés. `engine_report_redacted` et
  `redactions_applied` le disent dans chaque réponse ;
- **aucune enveloppe n'a été exercée par un tiers.** Version `0.1.0`. C'est la
  seule chose qui la sépare d'une version ;
- l'attestation de la démonstration emploie une clé de statut **`test`**, qui
  n'accorde aucune attestation. La lancer avec `--allow-test-keys` montre une
  **déclaration**, pas une vérification d'identité.

## Les droits, tels qu'ils sont réellement constitués

| | |
|---|---|
| ce gateway | aucune licence de réemploi accordée ; droits réservés |
| le dépôt du moteur | aucun fichier `LICENSE`, `NOTICE` ni `CONTRIBUTING` présent (mesuré sur `3391c768`) ; son README énonce des droits réservés |
| 🟡 **les deux caisses Rust du vérificateur** | leurs `Cargo.toml` déclarent **`license = "Apache-2.0"`** |

🟡 **Cette déclaration n'est pas retirée ici, et ne pourrait pas l'être.** Ces
fichiers ont été publiés dans un dépôt public portant cette métadonnée de
paquet. Quiconque les a obtenus pendant cette période peut se fonder sur la
concession qu'elle exprime ; rendre le dépôt privé ne revient pas en arrière
et ne la révoque pas. Aucune des deux caisses n'a jamais été publiée sur un
registre (`publish = false` sur les deux).

La contradiction entre cette métadonnée et la mention de droits réservés est
**non résolue**, et elle est consignée ici comme non résolue plutôt que
tranchée dans un sens par le silence. C'est une question à laquelle NeoMundi
doit répondre explicitement.

## Ce qui n'est délibérément pas publié

Clés privées, matériel de signature du magasin de confiance, secrets de
pilote, dossiers privés Q-1/Q-2, paquets d'exécution de pilote, et tout
matériau dérivé d'un pilote qui l'identifie. Rien de cela n'est dans ce
dépôt, et rien de cela ne doit jamais lui être envoyé.
