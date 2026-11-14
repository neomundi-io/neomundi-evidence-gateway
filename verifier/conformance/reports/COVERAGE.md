# Matrice de couverture du corpus de conformité Evidence

**Corpus `1.3.0`** · 50 cas · 7 familles · généré par `conformance/runners/matrix.py`

Résultats mesurés sur : `python`, `rust-core`, `rust-crypto`

---

## 1. Les dénominateurs, avant tout chiffre

| Vérificateur | Périmètre annoncé | Cas applicables | sur 50 |
|---|---|---|---|
| `python` | soumission, archive, attestation | **50** | 50 |
| `rust-core` | **soumission seulement** | **35** | 50 |
| `rust-crypto` | **archive et attestation seulement** | **15** | 50 |

> Un cas hors du périmètre d'un vérificateur rend `NOT APPLICABLE`, jamais `FAIL`. Reprocher à un outil de ne pas faire ce qu'il n'annonce pas serait une mesure fausse — et gonflerait artificiellement le dénominateur de l'autre.

## 2. Couverture par famille

| Famille | Cas | `python` | `rust-core` | `rust-crypto` |
|---|---|---|---|---|
| **A-valid** | 7 | PASS=7 | NOT APPLICABLE=3 PASS=4 | NOT APPLICABLE=4 PASS=3 |
| **B-incomplete** | 6 | PASS=6 | PASS=6 | NOT APPLICABLE=6 |
| **C-malformed** | 9 | AMBIGUOUS=1 PASS=8 | AMBIGUOUS=1 NOT APPLICABLE=3 PASS=5 | NOT APPLICABLE=6 PASS=3 |
| **D-tampered** | 10 | PASS=10 | NOT APPLICABLE=5 PASS=5 | NOT APPLICABLE=5 PASS=5 |
| **E-paths** | 8 | AMBIGUOUS=2 PASS=6 | AMBIGUOUS=2 PASS=6 | NOT APPLICABLE=8 |
| **F-coherent-rewrite** | 3 | PASS=3 | NOT APPLICABLE=2 PASS=1 | NOT APPLICABLE=1 PASS=2 |
| **G-ambiguous** | 7 | AMBIGUOUS=7 | AMBIGUOUS=5 NOT APPLICABLE=2 | AMBIGUOUS=2 NOT APPLICABLE=5 |

## 3. Statut des règles citées

| Statut | Cas | Ce que le corpus en fait |
|---|---|---|
| **AMBIGUOUS** | 10 | le contrat ne tranche pas : le corpus **consigne** les comportements observés et **ne déclare personne fautif** |
| **NORMATIVE** | 40 | le contrat tranche : un verdict unique est attendu, et un écart est un **échec de conformité** |

## 4. La matrice, cas par cas

`attendu` est la valeur **écrite dans la fiche avant toute exécution**. Pour un cas ambigu, aucun verdict n'est imposé.

| Cas | Sujet | Règle | Attendu | `python` | `rust-core` | `rust-crypto` |
|---|---|---|---|---|---|---|
| `A-01-submission-v1-valid` | submission | NORMATIVE | ACCEPTE | PASS | PASS | NOT APPLICABLE |
| `A-02-submission-v2-valid` | submission | NORMATIVE | ACCEPTE | PASS | PASS | NOT APPLICABLE |
| `A-03-submission-v2-zip-valid` | submission | NORMATIVE | ACCEPTE | PASS | PASS | NOT APPLICABLE |
| `A-04-empty-artifact-allowed` | submission | NORMATIVE | ACCEPTE | PASS | PASS | NOT APPLICABLE |
| `A-05-archive-valid` | archive | NORMATIVE | ACCEPTE | PASS | NOT APPLICABLE | PASS |
| `A-06-attestation-valid` | attestation | NORMATIVE | ACCEPTE / niveau=cryptographically_attested | PASS | NOT APPLICABLE | PASS |
| `A-07-attestation-store-not-confronted` | attestation | NORMATIVE | ACCEPTE / niveau=cryptographically_attested | PASS | NOT APPLICABLE | PASS |
| `B-01-artifact-file-missing` | submission | NORMATIVE | INCOMPLET | PASS | PASS | NOT APPLICABLE |
| `B-02-required-field-absent` | submission | NORMATIVE | REJETE | PASS | PASS | NOT APPLICABLE |
| `B-03-v2-null-model-with-reason` | submission | NORMATIVE | ACCEPTE | PASS | PASS | NOT APPLICABLE |
| `B-04-v2-null-model-without-reason` | submission | NORMATIVE | REJETE | PASS | PASS | NOT APPLICABLE |
| `B-05-v1-null-model-refused` | submission | NORMATIVE | REJETE | PASS | PASS | NOT APPLICABLE |
| `B-06-optional-fields-absent` | submission | NORMATIVE | ACCEPTE | PASS | PASS | NOT APPLICABLE |
| `C-01-invalid-json` | submission | NORMATIVE | REJETE | PASS | PASS | NOT APPLICABLE |
| `C-02-invalid-utf8` | submission | NORMATIVE | REJETE | PASS | PASS | NOT APPLICABLE |
| `C-03-unexpected-structure` | submission | NORMATIVE | REJETE | PASS | PASS | NOT APPLICABLE |
| `C-04-unknown-version` | submission | NORMATIVE | REJETE | PASS | PASS | NOT APPLICABLE |
| `C-05-field-not-allowed-by-schema` | submission | AMBIGUOUS | *(ambigu)* | AMBIGUOUS | AMBIGUOUS | NOT APPLICABLE |
| `C-06-not-a-zip` | submission | NORMATIVE | REJETE | PASS | PASS | NOT APPLICABLE |
| `C-07-archive-crc-invalid` | archive | NORMATIVE | REJETE | PASS | NOT APPLICABLE | PASS |
| `C-08-archive-local-header-mismatch` | archive | NORMATIVE | REJETE | PASS | NOT APPLICABLE | PASS |
| `C-09-archive-deflate-invalid` | archive | NORMATIVE | REJETE | PASS | NOT APPLICABLE | PASS |
| `D-01-artifact-tampered` | submission | NORMATIVE | REJETE | PASS | PASS | NOT APPLICABLE |
| `D-02-manifest-digest-wrong` | submission | NORMATIVE | REJETE | PASS | PASS | NOT APPLICABLE |
| `D-03-size-wrong` | submission | NORMATIVE | REJETE | PASS | PASS | NOT APPLICABLE |
| `D-04-file-substituted` | submission | NORMATIVE | REJETE | PASS | PASS | NOT APPLICABLE |
| `D-05-artifact-removed` | submission | NORMATIVE | INCOMPLET | PASS | PASS | NOT APPLICABLE |
| `D-06-attestation-signature-invalid` | attestation | NORMATIVE | REJETE / niveau=aucun | PASS | NOT APPLICABLE | PASS |
| `D-07-attestation-payload-tampered` | attestation | NORMATIVE | REJETE / niveau=aucun | PASS | NOT APPLICABLE | PASS |
| `D-08-attestation-wrong-key` | attestation | NORMATIVE | REJETE / niveau=aucun | PASS | NOT APPLICABLE | PASS |
| `D-09-attestation-replaced-by-other` | attestation | NORMATIVE | REJETE / niveau=aucun | PASS | NOT APPLICABLE | PASS |
| `D-10-archive-member-tampered` | archive | NORMATIVE | REJETE | PASS | NOT APPLICABLE | PASS |
| `E-01-path-traversal` | submission | NORMATIVE | REJETE | PASS | PASS | NOT APPLICABLE |
| `E-02-path-absolute-unix` | submission | NORMATIVE | REJETE | PASS | PASS | NOT APPLICABLE |
| `E-03-path-absolute-windows` | submission | NORMATIVE | REJETE | PASS | PASS | NOT APPLICABLE |
| `E-04-path-backslash` | submission | NORMATIVE | REJETE | PASS | PASS | NOT APPLICABLE |
| `E-05-path-empty` | submission | NORMATIVE | REJETE | PASS | PASS | NOT APPLICABLE |
| `E-06-path-declared-twice` | submission | AMBIGUOUS | *(ambigu)* | AMBIGUOUS | AMBIGUOUS | NOT APPLICABLE |
| `E-07-zip-member-duplicate` | submission | NORMATIVE | REJETE | PASS | PASS | NOT APPLICABLE |
| `E-08-path-dot-segment` | submission | AMBIGUOUS | *(ambigu)* | AMBIGUOUS | AMBIGUOUS | NOT APPLICABLE |
| `F-01-coherent-rewrite-accepted` | submission | NORMATIVE | ACCEPTE / **PLAFOND** | PASS | PASS | NOT APPLICABLE |
| `F-02-coherent-rewrite-breaks-attestation` | attestation | NORMATIVE | REJETE / niveau=aucun | PASS | NOT APPLICABLE | PASS |
| `F-03-archive-amputated-no-contract` | archive | NORMATIVE | ACCEPTE / **PLAFOND** | PASS | NOT APPLICABLE | PASS |
| `G-01-duplicate-json-keys` | submission | AMBIGUOUS | *(ambigu)* | AMBIGUOUS | AMBIGUOUS | NOT APPLICABLE |
| `G-02-duplicate-key-on-digest` | submission | AMBIGUOUS | *(ambigu)* | AMBIGUOUS | AMBIGUOUS | NOT APPLICABLE |
| `G-03-nan-outside-rfc` | submission | AMBIGUOUS | *(ambigu)* | AMBIGUOUS | AMBIGUOUS | NOT APPLICABLE |
| `G-04-infinity-outside-rfc` | submission | AMBIGUOUS | *(ambigu)* | AMBIGUOUS | AMBIGUOUS | NOT APPLICABLE |
| `G-05-lone-surrogate` | submission | AMBIGUOUS | *(ambigu)* | AMBIGUOUS | AMBIGUOUS | NOT APPLICABLE |
| `G-06-base64url-padding` | attestation | AMBIGUOUS | *(ambigu)* | AMBIGUOUS | NOT APPLICABLE | AMBIGUOUS |
| `G-07-base64url-standard-alphabet` | attestation | AMBIGUOUS | *(ambigu)* | AMBIGUOUS | NOT APPLICABLE | AMBIGUOUS |

## 5. Les règles citées, et où les lire

Une règle **non citée ici n'est pas couverte**. C'est la lecture la plus importante de ce document.

| Référence normative | Statut | Cas |
|---|---|---|
| AMBIGUITE-1 -- CONSOLIDATION_RUST_PR26/07 | AMBIGUOUS | `E-08-path-dot-segment` |
| APPNOTE ZIP | NORMATIVE | `E-07-zip-member-duplicate` |
| APPNOTE ZIP §4.3.12 | NORMATIVE | `C-07-archive-crc-invalid` |
| APPNOTE ZIP §4.3.16 | NORMATIVE | `C-06-not-a-zip` |
| APPNOTE ZIP §4.3.7 et §4.3.12 | NORMATIVE | `C-08-archive-local-header-mismatch` |
| COMPLETUDE_RUST_EVIDENCE/08 §2 -- plafond declare | NORMATIVE | `F-01-coherent-rewrite-accepted` |
| COMPORTEMENT OBSERVE -- adapters/ingest.py | NORMATIVE | `A-03-submission-v2-zip-valid`, `B-01-artifact-file-missing`, `D-05-artifact-removed` |
| DEVELOPPEMENT_CORPUS_CONFORMITE/06 -- scenario D | NORMATIVE | `F-03-archive-amputated-no-contract` |
| RFC 1951 | NORMATIVE | `C-09-archive-deflate-invalid` |
| RFC 7515 §2 | AMBIGUOUS | `G-07-base64url-standard-alphabet` |
| RFC 7515 §2 ; COMPLETUDE_RUST_EVIDENCE/03 §8 | AMBIGUOUS | `G-06-base64url-padding` |
| RFC 7515 §5.2 | NORMATIVE | `D-07-attestation-payload-tampered` |
| RFC 8032 | NORMATIVE | `D-08-attestation-wrong-key` |
| RFC 8032 §5.1.7 | NORMATIVE | `D-06-attestation-signature-invalid` |
| RFC 8259 | NORMATIVE | `C-01-invalid-json` |
| RFC 8259 §4 | AMBIGUOUS | `G-02-duplicate-key-on-digest` |
| RFC 8259 §4 ; CONSOLIDATION_RUST_PR26/AMBIGUITE_4_DECISION.md | AMBIGUOUS | `G-01-duplicate-json-keys` |
| RFC 8259 §6 | AMBIGUOUS | `G-04-infinity-outside-rfc` |
| RFC 8259 §6 ; COMPLETUDE_RUST_EVIDENCE/08 §4 | AMBIGUOUS | `G-03-nan-outside-rfc` |
| RFC 8259 §8.1 | NORMATIVE | `C-02-invalid-utf8` |
| RFC 8259 §8.2 | AMBIGUOUS | `G-05-lone-surrogate` |
| schemas/evidence-submission-v1.json | NORMATIVE | `A-01-submission-v1-valid` |
| schemas/evidence-submission-v1.json#/properties/execution/properties/model_declared | NORMATIVE | `B-05-v1-null-model-refused` |
| schemas/evidence-submission-v2.json | NORMATIVE | `B-03-v2-null-model-with-reason`, `D-02-manifest-digest-wrong`, `D-04-file-substituted` |
| schemas/evidence-submission-v2.json#/properties/artifacts -- aucun `uniqueItems` | AMBIGUOUS | `E-06-path-declared-twice` |
| schemas/evidence-submission-v2.json#/properties/artifacts/items/properties/bytes | NORMATIVE | `A-04-empty-artifact-allowed`, `D-03-size-wrong` |
| schemas/evidence-submission-v2.json#/properties/artifacts/items/properties/path (prose : « un chemin relatif, sans remontee ») | NORMATIVE | `E-01-path-traversal`, `E-02-path-absolute-unix`, `E-03-path-absolute-windows`, `E-04-path-backslash`, `E-05-path-empty` |
| schemas/evidence-submission-v2.json#/properties/artifacts/items/properties/sha256 | NORMATIVE | `D-01-artifact-tampered` |
| schemas/evidence-submission-v2.json#/properties/execution/allOf | NORMATIVE | `A-02-submission-v2-valid`, `B-04-v2-null-model-without-reason` |
| schemas/evidence-submission-v2.json#/properties/pilot/additionalProperties | AMBIGUOUS | `C-05-field-not-allowed-by-schema` |
| schemas/evidence-submission-v2.json#/properties/pilot/type | NORMATIVE | `C-03-unexpected-structure` |
| schemas/evidence-submission-v2.json#/properties/schema/const | NORMATIVE | `C-04-unknown-version` |
| schemas/evidence-submission-v2.json#/required | NORMATIVE | `B-02-required-field-absent`, `B-06-optional-fields-absent` |
| verify.py -- 22 controles ; examples/dossier-v1/attendu.json | NORMATIVE | `A-05-archive-valid` |
| verify.py -- empreintes des membres | NORMATIVE | `D-10-archive-member-tampered` |
| verify_attestation.py -- les cinq piliers ; RFC 8032 | NORMATIVE | `A-06-attestation-valid` |
| verify_attestation.py -- ligne « empreinte du magasin confrontee », marquee REQUISE | NORMATIVE | `A-07-attestation-store-not-confronted` |
| verify_attestation.py -- pilier `concordance` | NORMATIVE | `D-09-attestation-replaced-by-other`, `F-02-coherent-rewrite-breaks-attestation` |

## 6. Comportements propres à une implémentation

| Cas | Vérificateur | Attente surchargée | Raison déclarée |
|---|---|---|---|
| `A-05-archive-valid` | `rust-crypto` | exit_code=0, exit_code_strict=0 | La garantie REQUISE qui vaut 2 cote `verify.py` est celle des << empreintes des entrees rejouees >>, que seul `--corpus` demontre. `evidence-verify-crypto` ne modelise PAS cette garantie sur une archive : il n a aucune entree a rejouer, donc aucune garantie requise non demontree, donc 0. Difference de SURFACE declaree, et non divergence de regle. |
| `A-07-attestation-store-not-confronted` | `rust-crypto` | exit_code=0, exit_code_strict=2, verdict=INCOMPLET | `evidence-verify-crypto` modelise un VERDICT en plus du niveau, et une ligne REQUISE non demontree rend INCOMPLET. `verify_attestation.py` ne modelise pas de verdict : il rend un niveau. C est une difference de SURFACE, declaree, et non une divergence de regle. Le CODE DE SORTIE, lui, ne diverge PAS : les deux rendent 2 sous `--strict`, par la meme regle de garantie requise -- le corpus 1.2.0 l imputait a tort a la seule modelisation du verdict. |
| `F-03-archive-amputated-no-contract` | `rust-crypto` | exit_code=0, exit_code_strict=0 | La garantie REQUISE qui vaut 2 cote `verify.py` est celle des << empreintes des entrees rejouees >>, que seul `--corpus` demontre. `evidence-verify-crypto` ne modelise PAS cette garantie sur une archive : il n a aucune entree a rejouer, donc aucune garantie requise non demontree, donc 0. Difference de SURFACE declaree, et non divergence de regle. |

> Une surcharge n'est **pas une tolérance** : c'est une différence de **surface** entre deux outils, déclarée avec sa raison. `verify_attestation.py` rend un *niveau* ; `evidence-verify-crypto` rend un *verdict* **et** un niveau, et son verdict devient `INCOMPLET` quand une ligne requise n'est pas démontrée — ce que Python ne modélise pas.

## 7. Les cas ambigus, et ce qu'ils consignent

| Cas | Ambiguïté | Comportements déclarés | Divergent ? |
|---|---|---|---|
| `C-05-field-not-allowed-by-schema` | Un champ en SURPLUS dans `pilot`, que `additionalProperties: false` interdit | `python`→ACCEPTE | non |
| `E-06-path-declared-twice` | Le MEME chemin declare deux fois dans `artifacts`, avec deux empreintes differentes | *non déclarés* | — |
| `E-08-path-dot-segment` | Un segment ` | `python`→ACCEPTE, `rust-core`→REJETE | **OUI** |
| `G-01-duplicate-json-keys` | `submission_id` declare DEUX fois dans le manifeste | `python`→ACCEPTE, `rust-core`→REJETE | **OUI** |
| `G-02-duplicate-key-on-digest` | DEUX `sha256` pour UN artefact : laquelle est controlee ? | `python`→ACCEPTE, `rust-core`→REJETE | **OUI** |
| `G-03-nan-outside-rfc` | `NaN` dans un champ hors contrat : la RFC 8259 ne le definit pas | `python`→ACCEPTE, `rust-core`→REJETE | **OUI** |
| `G-04-infinity-outside-rfc` | `Infinity` dans un champ hors contrat | `python`→ACCEPTE, `rust-core`→REJETE | **OUI** |
| `G-05-lone-surrogate` | Une demi-paire de substitution UTF-16 dans un champ declare | `python`→REJETE, `rust-core`→REJETE | non |
| `G-06-base64url-padding` | Un segment du JWS porte un bourrage `=`, que la RFC 7515 §2 interdit | `python`→REJETE, `rust-crypto`→REJETE | non |
| `G-07-base64url-standard-alphabet` | Le segment de SIGNATURE est reecrit en base64 STANDARD (`+`/`/`) | `python`→ACCEPTE, `rust-crypto`→REJETE | **OUI** |

**6 des 10 cas ambigus DIVERGENT** : deux vérificateurs honnêtes, un seul fichier, deux verdicts. C'est ce qu'une ambiguïté normative produit de dangereux, et c'est pour cela que le corpus la fige vérificateur par vérificateur plutôt que de la résumer en « ambigu ».

> Jusqu'au corpus 1.1.0, trois de ces lignes portaient *non déclarés* — et le banc, qui mesurait pourtant les deux verdicts, ne les comparait jamais. La divergence de `G-07` était dans la donnée et invisible partout. Corrigé en 1.2.0.

> **Aucun de ces cas ne déclare une implémentation fautive.** Le contrat ne permet pas de trancher ; le corpus le dit, et s'arrête là.

## 8. Plafonds déclarés — les cas où une ACCEPTATION est correcte

| Cas | Pourquoi l'acceptation est correcte |
|---|---|
| `F-01-coherent-rewrite-accepted` | Un paquet reecrit puis re-hache proprement est coherent avec son manifeste. L accepter est CORRECT : l integrite interne ne dit rien de l authenticite. Seule une ancre externe -- signature, horodatage |
| `F-03-archive-amputated-no-contract` | Sur une archive sans contrat de completude, aucun controle interne ne voit ce qui a ete retire. Le resultat attendu est donc ACCEPTE, et c est un PLAFOND declare, pas un echec du verificateur. |

> 🔴 **Ne jamais convertir ces cas en `FAIL` pour améliorer un taux de détection.** Un paquet réécrit puis re-haché proprement *est* cohérent avec son manifeste ; l'accepter est la réponse juste, et le refuser serait une mesure fausse.

## 9. Échecs déclarés et régressions

| | Nombre | Lecture |
|---|---|---|
| échecs **déclarés** observés | 0 | visibles, et **non** comptés comme régression |
| échecs **non déclarés** | **0** | une régression, et la CI échoue |
| erreurs techniques | 0 | une conclusion impossible, jamais un verdict |
| écarts de **code** sur verdict concordant | 0 | rapportés à part : un code peut légitimement différer |

## 10. Ce que cette matrice ne dit pas

| | |
|---|---|
| **la couverture du protocole** | 50 cas citent 38 références normatives. Les contrats Evidence en comportent davantage : ce qui n'est pas cité en §5 n'est **pas couvert** |
| **l'exhaustivité** | un corpus n'est jamais exhaustif, et celui-ci a été écrit par une seule personne |
| **la vérité des événements** | aucun cas ne la mesure, et aucun ne peut la mesurer |
| **l'absence de défaut commun** | deux implémentations qui concordent ont le même périmètre d'erreur résiduel |
| **la conformité réglementaire** | aucune norme n'est invoquée, et aucune n'est satisfaite par construction |

**Aucun pourcentage de « conformité » n'est publié dans ce document.** Les comptes y sont absolus, avec leur dénominateur, parce qu'un taux calculé sur un corpus partiel se lirait comme un taux sur le protocole.

