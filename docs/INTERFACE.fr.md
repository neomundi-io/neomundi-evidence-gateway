<sub>🇬🇧 <a href="INTERFACE.md">English</a> · 🇫🇷 <b>Français</b> · <a href="../README.fr.md">← README</a></sub>

# L'interface — enveloppes, codes de sortie, rédaction, versionnement

Pour qui intègre ce gateway. Les règles d'intégration du moteur lui-même
(codes `0/1/2`, mode strict, rapports machine) sont documentées dans le dépôt
du moteur et **ne sont pas redites ici** ; ce document ne couvre que ce que le
gateway ajoute.

---

## La règle, en une phrase

> **Lire `exit_code` et `status`. Un `status` à `completed` ne veut pas dire
> que l'artefact est passé — il veut dire que le moteur a tourné.**

---

## Opérations

| Opération | Point d'entrée du moteur | Entrées obligatoires |
|---|---|---|
| `verify` | `verify.py` | — (`inputs.corpus` facultatif) |
| `attestation` | `verify_attestation.py` | `inputs.attestation`, `inputs.trust_store` |

`attestation` **refuse** une requête sans magasin de confiance. Sans magasin,
le moteur n'établit aucune identité et ne pourrait répondre que `NOT TESTED` ;
un gateway qui laisserait passer l'appel rendrait un rapport qui ressemble à
une vérification sans en être une.

Opérations que le moteur offre et que ce gateway n'expose **pas encore** :
liaison (`bind.py`), signature (`sign.py`), horodatage (`timestamp.py`),
ingestion et réconciliation de paquets tiers (`adapters/`). Ce sont des
développements futurs, pas des oublis — en ajouter une suppose d'ajouter une
opération au contrat de requête et un cas aux suites.

## L'enveloppe de requête

`neomundi.evidence.gateway.request/1` —
[`contracts/gateway-request-v1.json`](../contracts/gateway-request-v1.json).

```json
{
  "schema": "neomundi.evidence.gateway.request/1",
  "operation": "verify",
  "request_id": "ce-que-l-appelant-veut-correler",
  "artifact": { "name": "evidence-v1-demo", "path": "examples/dossier-v1/NEOMUNDI_EVIDENCE_V1_DEMO.zip" },
  "inputs":   { "corpus": "examples/dossier-v1/corpus" },
  "options":  { "strict": true, "language": "fr" }
}
```

**`request_id` n'est jamais engendré par le gateway.** Un identifiant qu'il
inventerait ne corrélerait avec rien de ce que l'appelant détient. Absent en
entrée, `null` en sortie.

### La racine d'artefacts

Tout chemin d'une requête est résolu sous un répertoire — `--artifact-root`,
le répertoire courant par défaut. Un chemin dont la forme **résolue** en sort
est refusé par `path_outside_root`. Le contrôle porte sur le chemin résolu,
parce qu'un segment `..` ou un lien symbolique ne se voit pas sur la chaîne de
caractères.

Les requêtes d'exemple livrées dans [`examples/`](../examples) emploient des
chemins relatifs au **moteur**, parce que c'est là que vit son dossier de
démonstration synthétique. D'où le `--artifact-root "$EVIDENCE_ENGINE_HOME"`
du démarrage rapide. Dans une intégration réelle, la racine d'artefacts est le
répertoire où arrivent les soumissions de l'appelant, et ce n'est normalement
**pas** le moteur.

## L'enveloppe de réponse

`neomundi.evidence.gateway.response/1` —
[`contracts/gateway-response-v1.json`](../contracts/gateway-response-v1.json).

| Champ | Ce qu'il est |
|---|---|
| `status` | `completed`, `rejected` ou `engine_unavailable` |
| `verification_performed` | un fait sur **cette exécution du gateway**, pas sur l'artefact : vrai seulement si le moteur a tourné et si son rapport a été lu |
| `verdict` | `null` tant que le moteur n'a pas tourné. Chaque champ est copié du rapport du moteur, avec `source: "evidence-engine"` et `computed_by_gateway: false` |
| `artifact.sha256_reported_by_engine` | pris dans le rapport du moteur. Le gateway ne calcule **pas** l'empreinte de l'artefact : ce serait une seconde implémentation de l'intégrité |
| `engine_report` | le rapport du moteur, verbatim à la rédaction des chemins près. Son propre champ `schema` nomme le contrat qu'il suit |
| `engine.revision_declared` | déclarée par l'opérateur via `EVIDENCE_ENGINE_REVISION`, et **jamais vérifiée ici** — `revision_is_declared_not_verified` vaut toujours `true` |
| `limits` | toujours non vide : les deux limites du gateway, plus chaque ligne `does_not_establish` du rapport du moteur, préfixée `engine:` |
| `errors` | `reason`, `field`, `detail` — une entrée sur `rejected` et sur `engine_unavailable` |

## Codes de sortie

| Code | Signification | Vérification ? |
|---|---|---|
| `0` | le moteur a tourné, aucun contrôle n'a échoué | oui |
| `1` | le moteur a tourné, **au moins un contrôle a échoué** | oui |
| `2` | le moteur a tourné, mode strict, une garantie **requise** n'est pas démontrée | oui |
| `3` | **moteur indisponible** | **non** |
| `4` | **requête refusée** | **non** |

`0`, `1` et `2` sont ceux du moteur, sans traduction — `1` l'emporte toujours
sur `2`, parce que c'est la règle du moteur et que le gateway ne la
réinterprète pas.

`3` et `4` existent pour une raison : sans eux, « rien n'a échoué » et « rien
n'a tourné » rendraient le même code. Un consommateur qui traite tout code non
nul comme un refus n'est pas induit en erreur ; un consommateur qui ne teste
que `!= 0` pour détecter un échec reste correct.

### Raisons de refus (code 4)

`unsupported_request_schema` · `unknown_operation` · `unexpected_field` ·
`missing_field` · `field_type_invalid` · `request_not_an_object` ·
`request_unreadable` · `artifact_not_found` · `input_not_found` ·
`path_outside_root` · `unsupported_language`

### Raisons d'indisponibilité (code 3)

`engine_not_declared` · `engine_home_absent` · `engine_entrypoint_missing` ·
`engine_not_executable` · `engine_timeout` · `engine_report_absent` ·
`engine_report_unreadable`

Les deux dernières comptent : un moteur qui a tourné sans écrire de rapport
machine lisible ne produit **aucun verdict ici**. Le gateway n'en reconstitue
pas un depuis la sortie texte. Un verdict analysé depuis de la prose serait un
verdict que le gateway aurait calculé.

## Rédaction — et pourquoi le rapport n'est pas identique à l'octet

Le moteur écrit dans son rapport les chemins qu'on lui a donnés, dont le
chemin absolu de l'archive. Sur un poste, ce chemin porte le nom du compte.
Une enveloppe envoyée à un appelant n'a pas à le lui apprendre.

Donc, avant de republier, le gateway réécrit, **dans les valeurs de type
chaîne uniquement** :

| Ce qui est trouvé | Devient |
|---|---|
| la racine du moteur | `<engine>` |
| la racine d'artefacts | `<artifacts>` |
| le répertoire personnel | `<home>` |

Les clés ne sont jamais touchées, et une empreinte ne peut pas l'être : elle
ne contient aucun séparateur de chemin. Le motif le plus long est appliqué
d'abord, de sorte qu'un moteur situé sous le répertoire personnel rende bien
`<engine>`.

Et c'est dit, pas tu : `engine_report_redacted` et `redactions_applied`
annoncent que le rapport republié **n'est plus identique à l'octet** à ce que
le moteur a écrit. Les détails d'erreur et la ligne lisible par un humain sont
rédigés de la même façon.

Pour les octets exacts du moteur, lancer le moteur directement — c'est ce que
fait [`tests/test_no_verification_logic.py`](../tests/test_no_verification_logic.py)
pour prouver que les deux concordent.

## Versionnement

Les identifiants d'enveloppe finissent par `/1`. La politique est celle du
moteur :

- un champ **nouveau** peut apparaître dans une réponse au sein de `/1` ;
- un champ existant ne change jamais de sens ni de type au sein de `/1` ;
- une rupture prend `/2`, et `/1` continue de fonctionner ou est retiré au
  grand jour — jamais déplacé en silence ;
- le contrat de requête est **fermé**. Un champ qu'il ne prévoit pas est
  refusé, pas ignoré : c'est ce qui fait de l'ajout d'un champ un événement
  visible.

La version propre du gateway (`gateway.version`, `0.1.0`) évolue
indépendamment de celle des enveloppes.

## Ce qu'une réponse n'établit pas

Au-delà de tout ce que le moteur lui-même n'établit pas :

- **l'indépendance.** Le gateway et le moteur tournent chez le même opérateur,
  sauf déclaration contraire de celui-ci. Un rapport produit ici est une
  vérification faite par cet opérateur — jamais une vérification indépendante
  par un tiers, et jamais à présenter comme telle.
- **l'identité du moteur.** `revision_declared` est une déclaration. Ce
  gateway ne lance aucun `git`, ne vérifie aucune signature sur l'arbre du
  moteur, et ne peut pas établir qu'un répertoire correspond à un commit.
- **quoi que ce soit sur la justesse du moteur.** C'est le rôle de ses propres
  suites, de son corpus public de conformité et de son second vérificateur
  indépendant.
