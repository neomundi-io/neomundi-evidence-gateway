#!/usr/bin/env python3
"""Générateur du corpus de conformité Evidence — DÉTERMINISTE.

CE QUE CE PROGRAMME EST, ET QUAND IL TOURNE
===========================================

Il tourne **une fois**, et sa sortie est **versionnée**. Le banc
(`run.py`) ne le rappelle jamais : il vérifie les empreintes des fixtures
figées et s'arrête si elles ont bougé.

C'est la règle qui rend le corpus utilisable comme référence :

    « Les artefacts figés ne doivent pas être régénérés silencieusement
      lors des tests. »

Relancer ce générateur et obtenir des octets différents est donc un
**événement**, pas une routine : il faut une nouvelle version du corpus et
une nouvelle empreinte.

POURQUOI IL EST DÉTERMINISTE, ET COMMENT
========================================

  - aucune horloge : toutes les dates sont des constantes du corpus ;
  - aucun aléa : aucune clef n'est générée ici (voir plus bas) ;
  - ZIP à `date_time` FIXE et `ZIP_STORED` : deux exécutions produisent les
    mêmes octets, y compris les 30 octets d'en-tête local ;
  - JSON à `sort_keys=True`, `indent=2`, `ensure_ascii=False` ;
  - aucun parcours de répertoire : la liste des membres est écrite en clair.

LES CLEFS CRYPTOGRAPHIQUES
==========================

**Aucune clef n'est générée ici**, et aucune clef privée n'est écrite dans le
corpus. Les fixtures cryptographiques **réutilisent l'attestation de
démonstration du dépôt** — `examples/dossier-v1/`, dont la clef porte
`status: test` et est documentée comme « éphémère, détruite aussitôt après
signature ».

Conséquence assumée : les contre-exemples cryptographiques de ce corpus sont
des **altérations d'octets** (signature retournée, en-tête réécrit, segment
réencodé), jamais des signatures forgées avec une autre clef. Forger
demanderait de signer, donc d'embarquer une clef privée dans un corpus
public — ce qui est exclu.

Les cas « mauvaise clef » et « substitution de clef » sont donc obtenus en
altérant le **magasin de confiance**, qui ne contient que du public.

PROVENANCE
==========

Tout est **synthétique**, sauf trois fichiers repris de `examples/dossier-v1/`
— l'archive de démonstration, son attestation et son magasin — qui sont déjà
publics dans ce dépôt et dont l'en-tête déclare « aucune donnée réelle ».

Aucun dossier de pilote n'est repris. Aucune donnée d'un tiers.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import sys
import zipfile
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
CORPUS = RACINE / "conformance"
FIXTURES = CORPUS / "fixtures"
ATTENDUS = CORPUS / "expected"
DOSSIER_REEL = RACINE / "examples" / "dossier-v1"

# 1.1.0 : la seule evolution est une ATTENTE, pas un octet de fixture.
#
# `C-09-archive-deflate-invalid` etait un echec DECLARE en 1.0.0 : Python
# tombait sur le flux DEFLATE invalide sans rendre de verdict. Le defaut
# est corrige ; le cas passe. La declaration part de
# `known_failures.json` vers sa section `resolved`, qui en conserve le
# resultat d origine -- voir `conformance/CHANGELOG.md`.
#
# Les 121 fichiers de fixtures gardent leurs octets et leurs empreintes :
# l entree n a pas change, seule la facon dont elle est TRAITEE a change.
# 1.2.0 : encore une evolution de METADONNEES D ATTENTE, pas un octet.
#
# `G-06` et `G-07` figent desormais leur comportement PAR VERIFICATEUR,
# comme `G-01` a `G-05` le faisaient deja. Sans cette declaration, la
# divergence mesurable de `G-07` -- python ACCEPTE, rust-crypto REJETE --
# restait invisible : le banc l observait et ne la comparait pas.
#
# Les 121 fichiers de fixtures gardent leurs octets et leurs empreintes.
VERSION_CORPUS = "1.3.0"
SCHEMA_FICHE = "neomundi.evidence.conformance-case/1"
SCHEMA_MANIFESTE = "neomundi.evidence.conformance-corpus/1"

#: Toutes les dates du corpus sont des CONSTANTES. Aucune horloge n'est lue.
DATE_ZIP = (2026, 1, 1, 0, 0, 0)
INSTANT_SOUMISSION = "2026-01-01T00:00:00Z"

#: Une empreinte SHA-256 qui n'est celle de rien. Employée là où le cas
#: exige une empreinte syntaxiquement valide mais fausse.
SHA_FAUX = "0" * 64

# --------------------------------------------------------------------------
# Outils déterministes
# --------------------------------------------------------------------------


def sha(octets: bytes) -> str:
    return hashlib.sha256(octets).hexdigest()


def jsonb(valeur) -> bytes:
    """JSON canonique du corpus : trié, indenté, UTF-8, sans échappement."""
    return (json.dumps(valeur, sort_keys=True, indent=2, ensure_ascii=False)
            + "\n").encode("utf-8")


def ecrire_zip(membres: list[tuple[str, bytes]]) -> bytes:
    """Un ZIP aux octets reproductibles.

    `date_time` est fixe et la méthode est `ZIP_STORED` : sans cela, deux
    exécutions produiraient des octets différents et le corpus ne serait pas
    figé.
    """
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_STORED) as z:
        for nom, contenu in membres:
            info = zipfile.ZipInfo(nom, date_time=DATE_ZIP)
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o644 << 16
            info.create_system = 3          # Unix, fixe
            z.writestr(info, contenu)
    return tampon.getvalue()


# --------------------------------------------------------------------------
# Les briques des paquets de SOUMISSION
# --------------------------------------------------------------------------

PROMPT = b"abc"
#: FIPS 180-4 annexe B.1 -- un vecteur publié, pas une valeur recopiée d'une
#: exécution.
PROMPT_SHA = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
REPONSE = b"la reponse\n"
REPONSE_SHA = sha(REPONSE)
VIDE_SHA = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def artefact(chemin: str, empreinte: str, octets: int, role: str) -> dict:
    return {"path": chemin, "sha256": empreinte, "bytes": octets, "role": role}


def manifeste_v1(artefacts: list[dict], **ecarts) -> dict:
    doc = {
        "schema": "neomundi.evidence.submission/1",
        "submission_id": "conformance-v1-001",
        "submitted_at_declared": INSTANT_SOUMISSION,
        "pilot": {"name_declared": "Corpus de conformite"},
        "execution": {
            "kind_declared": "replay",
            "model_declared": "modele-de-corpus-v1",
            "executed_at_declared": INSTANT_SOUMISSION,
        },
        "artifacts": artefacts,
    }
    doc.update(ecarts)
    return doc


def manifeste_v2(artefacts: list[dict], **ecarts) -> dict:
    doc = {
        "schema": "neomundi.evidence.submission/2",
        "submission_id": "conformance-v2-001",
        "submitted_at_declared": INSTANT_SOUMISSION,
        "pilot": {"name_declared": "Corpus de conformite"},
        "execution": {
            "kind_declared": "replay",
            "model_declared": None,
            "model_absence_reason_declared": "not_applicable",
            "model_absence_note_declared":
                "Aucun modele d IA n intervient : fixture deterministe.",
        },
        "artifacts": artefacts,
    }
    doc.update(ecarts)
    return doc


ARTEFACTS_TYPE = [
    artefact("artefacts/prompt.txt", PROMPT_SHA, len(PROMPT), "prompt"),
    artefact("artefacts/reponse.txt", REPONSE_SHA, len(REPONSE), "response"),
]
FICHIERS_TYPE = [("artefacts/prompt.txt", PROMPT),
                 ("artefacts/reponse.txt", REPONSE)]


# --------------------------------------------------------------------------
# Déclaration des cas
# --------------------------------------------------------------------------

#: Chaque cas est un dict. `fabriquer` rend la liste des fichiers du cas :
#: [(chemin relatif au cas, octets)]. Un cas ZIP rend un seul fichier.
CAS: list[dict] = []


def cas(ident, famille, genre, description, regle, attendu, fabriquer, **extra):
    """Déclare un cas. `attendu` et `regle` sont écrits ICI, avant toute
    exécution d'un vérificateur."""
    CAS.append({
        "id": ident, "famille": famille, "genre": genre,
        "description": description, "regle": regle, "attendu": attendu,
        "fabriquer": fabriquer, **extra,
    })


def paquet_dossier(manifeste: dict, fichiers=None, nom_manifeste="submission.json"):
    """Un paquet de soumission en DOSSIER."""
    def f():
        out = [(nom_manifeste, jsonb(manifeste))]
        out += list(fichiers if fichiers is not None else FICHIERS_TYPE)
        return out
    return f


def paquet_dossier_brut(octets_manifeste: bytes, fichiers=None):
    """Idem, mais le manifeste est fourni en OCTETS -- pour les cas où le
    JSON lui-même est l'objet du test."""
    def f():
        out = [("submission.json", octets_manifeste)]
        out += list(fichiers if fichiers is not None else FICHIERS_TYPE)
        return out
    return f


def paquet_zip(manifeste: dict, fichiers=None, nom="paquet.zip"):
    def f():
        membres = [("submission.json", jsonb(manifeste))]
        membres += list(fichiers if fichiers is not None else FICHIERS_TYPE)
        return [(nom, ecrire_zip(membres))]
    return f


# ========== FAMILLE A — paquets VALIDES ==================================

cas("A-01-submission-v1-valid", "A-valid", "submission",
    "Soumission v1 valide : deux artefacts, empreintes et tailles exactes.",
    {"statut": "NORMATIVE",
     "reference": "schemas/evidence-submission-v1.json",
     "texte": "Un paquet dont tous les champs requis sont presents et dont "
              "chaque empreinte declaree egale l empreinte recalculee est "
              "ACCEPTE."},
    {"verdict": "ACCEPTE", "exit_code": 0, "exit_code_strict": 0},
    paquet_dossier(manifeste_v1(ARTEFACTS_TYPE)))

cas("A-02-submission-v2-valid", "A-valid", "submission",
    "Soumission v2 valide : `model_declared` nul et MOTIVE, ce que seul "
    "`/2` autorise.",
    {"statut": "NORMATIVE",
     "reference": "schemas/evidence-submission-v2.json"
                  "#/properties/execution/allOf",
     "texte": "`/2` admet `model_declared: null` a condition que "
              "`model_absence_reason_declared` et "
              "`model_absence_note_declared` soient fournis."},
    {"verdict": "ACCEPTE", "exit_code": 0, "exit_code_strict": 0},
    paquet_dossier(manifeste_v2(ARTEFACTS_TYPE)))

cas("A-03-submission-v2-zip-valid", "A-valid", "submission",
    "Le meme paquet v2, en archive ZIP plutot qu en dossier.",
    {"statut": "NORMATIVE",
     "reference": "COMPORTEMENT OBSERVE -- adapters/ingest.py",
     "texte": "Un paquet peut etre remis en dossier ou en ZIP ; le verdict "
              "ne doit pas dependre du conteneur."},
    {"verdict": "ACCEPTE", "exit_code": 0, "exit_code_strict": 0},
    paquet_zip(manifeste_v2(ARTEFACTS_TYPE)))

cas("A-04-empty-artifact-allowed", "A-valid", "submission",
    "Un artefact de ZERO octet, declare avec l empreinte de la chaine vide.",
    {"statut": "NORMATIVE",
     "reference": "schemas/evidence-submission-v2.json"
                  "#/properties/artifacts/items/properties/bytes",
     "texte": "`bytes: 0` est une taille valide. Un fichier vide est un "
              "fichier, et son empreinte est celle de la chaine vide."},
    {"verdict": "ACCEPTE", "exit_code": 0, "exit_code_strict": 0},
    paquet_dossier(
        manifeste_v2([artefact("artefacts/vide.bin", VIDE_SHA, 0, "other")]),
        [("artefacts/vide.bin", b"")]))

cas("A-05-archive-valid", "A-valid", "archive",
    "L archive Evidence de demonstration du depot, reprise telle quelle.",
    {"statut": "NORMATIVE",
     "reference": "verify.py -- 22 controles ; "
                  "examples/dossier-v1/attendu.json",
     "texte": "Une archive dont les membres, les decomptes, les references "
              "croisees et les empreintes concordent est acceptee."},
    # `exit_code_strict` valait 0 jusqu au corpus 1.2.0 inclus. C etait
    # FAUX, et le banc ne pouvait pas le voir : il ne transmettait pas
    # `--strict` a `verify.py`. La seule garantie REQUISE de cet outil est
    # celle des << empreintes des entrees rejouees >>, qui exige
    # `--corpus` ; le banc n en fournit pas, et aucune fixture d archive
    # n en porte. Le 2 est donc le comportement CONTRACTUEL : rien n a
    # echoue, et une garantie requise n est pas demontree.
    {"verdict": "ACCEPTE", "exit_code": 0, "exit_code_strict": 2},
    None, source_reelle="NEOMUNDI_EVIDENCE_V1_DEMO.zip",
    attendu_par_verificateur={
        "rust-crypto": {"exit_code": 0, "exit_code_strict": 0,
                        "raison": "La garantie REQUISE qui vaut 2 cote `verify.py` est celle des << empreintes des entrees rejouees >>, que seul `--corpus` demontre. `evidence-verify-crypto` ne modelise PAS cette garantie sur une archive : il n a aucune entree a rejouer, donc aucune garantie requise non demontree, donc 0. Difference de SURFACE declaree, et non divergence de regle.",}})

cas("A-06-attestation-valid", "A-valid", "attestation",
    "L attestation Ed25519/JWS de demonstration, avec son archive et son "
    "magasin. Clef de statut `test` : exige `--allow-test-keys`.",
    {"statut": "NORMATIVE",
     "reference": "verify_attestation.py -- les cinq piliers ; RFC 8032",
     "texte": "Le niveau `cryptographically_attested` est derive si et "
              "seulement si les cinq piliers sont PASS et qu aucune ligne "
              "n est FAIL."},
    {"attested_level": "cryptographically_attested",
     "verdict": "ACCEPTE", "exit_code": 0, "exit_code_strict": 0},
    None, source_reelle="ATTESTATION",
    options=["--allow-test-keys", "--store-digest", "@STORE_DIGEST@"])

cas("A-07-attestation-store-not-confronted", "A-valid", "attestation",
    "La MEME attestation, SANS `--store-digest`. Le niveau est derive ; le "
    "verdict de `evidence-verify-crypto` devient INCOMPLET.",
    {"statut": "NORMATIVE",
     "reference": "verify_attestation.py -- ligne « empreinte du magasin "
                  "confrontee », marquee REQUISE",
     "texte": "Sans empreinte obtenue par un SECOND canal, le magasin et "
              "l archive arrivent par la MEME route, et qui controle cette "
              "route controle les deux. Un magasin non confronte n est pas "
              "faux : il est NON CONFRONTE, et la ligne le dit. Les cinq "
              "piliers restent PASS, donc le NIVEAU est derive des deux "
              "cotes -- seule la SURFACE du verdict differe."},
    # Meme correction qu en `A-05`, et c est ICI qu elle compte le plus :
    # la ligne << empreinte du magasin confrontee >> est marquee REQUISE
    # par `verify_attestation.py` lui-meme, et c est le sujet de ce cas.
    # Sous `--strict`, Python rend donc 2 -- exactement comme
    # `evidence-verify-crypto`. Le corpus 1.2.0 declarait 0 et imputait le 2
    # du Rust a sa modelisation d un verdict : l imputation etait fausse,
    # les deux outils appliquent la meme regle de garantie requise. Seule la
    # SURFACE du verdict differe, et cette divergence-la est conservee.
    {"attested_level": "cryptographically_attested",
     "verdict": "ACCEPTE", "exit_code": 0, "exit_code_strict": 2},
    None, source_reelle="ATTESTATION", options=["--allow-test-keys"],
    attendu_par_verificateur={
        "rust-crypto": {
            "verdict": "INCOMPLET", "exit_code": 0, "exit_code_strict": 2,
            "raison": "`evidence-verify-crypto` modelise un VERDICT en plus "
                      "du niveau, et une ligne REQUISE non demontree rend "
                      "INCOMPLET. `verify_attestation.py` ne modelise pas de "
                      "verdict : il rend un niveau. C est une difference de "
                      "SURFACE, declaree, et non une divergence de regle. "
                      "Le CODE DE SORTIE, lui, ne diverge PAS : les deux "
                      "rendent 2 sous `--strict`, par la meme regle de "
                      "garantie requise -- le corpus 1.2.0 l imputait a tort "
                      "a la seule modelisation du verdict.",
        }})


# ========== FAMILLE B — paquets INCOMPLETS ==============================

cas("B-01-artifact-file-missing", "B-incomplete", "submission",
    "Un artefact est DECLARE mais son fichier est absent du paquet.",
    {"statut": "NORMATIVE",
     "reference": "COMPORTEMENT OBSERVE -- adapters/ingest.py",
     "texte": "Un artefact declare et absent rend le paquet INCOMPLET et "
              "non REJETE : il manque quelque chose que le soumetteur peut "
              "fournir. `--strict` change le CODE, jamais le verdict."},
    {"verdict": "INCOMPLET", "exit_code": 0, "exit_code_strict": 2},
    paquet_dossier(manifeste_v2(ARTEFACTS_TYPE),
                   [("artefacts/prompt.txt", PROMPT)]))

cas("B-02-required-field-absent", "B-incomplete", "submission",
    "`submission_id` absent : un champ REQUIS par le schema.",
    {"statut": "NORMATIVE",
     "reference": "schemas/evidence-submission-v2.json#/required",
     "texte": "Un champ requis absent est un REFUS, non une incompletude : "
              "le paquet ne satisfait pas son propre contrat."},
    {"verdict": "REJETE", "exit_code": 1, "exit_code_strict": 1},
    paquet_dossier({k: v for k, v in manifeste_v2(ARTEFACTS_TYPE).items()
                    if k != "submission_id"}))

cas("B-03-v2-null-model-with-reason", "B-incomplete", "submission",
    "`model_declared: null` AVEC motif et note : autorise par `/2`.",
    {"statut": "NORMATIVE",
     "reference": "schemas/evidence-submission-v2.json",
     "texte": "Le motif rend l absence de modele declarable sans inventer "
              "un identifiant."},
    {"verdict": "ACCEPTE", "exit_code": 0, "exit_code_strict": 0},
    paquet_dossier(manifeste_v2(ARTEFACTS_TYPE)))

cas("B-04-v2-null-model-without-reason", "B-incomplete", "submission",
    "`model_declared: null` SANS motif : refuse meme en `/2`.",
    {"statut": "NORMATIVE",
     "reference": "schemas/evidence-submission-v2.json"
                  "#/properties/execution/allOf",
     "texte": "Un modele nul SANS motif ne dit rien : ni qu aucun modele "
              "n est intervenu, ni que son identite est perdue."},
    {"verdict": "REJETE", "exit_code": 1, "exit_code_strict": 1},
    paquet_dossier(manifeste_v2(
        ARTEFACTS_TYPE,
        execution={"kind_declared": "replay", "model_declared": None})))

cas("B-05-v1-null-model-refused", "B-incomplete", "submission",
    "`model_declared: null` en `/1` : refuse, car `/1` ne l autorise pas.",
    {"statut": "NORMATIVE",
     "reference": "schemas/evidence-submission-v1.json"
                  "#/properties/execution/properties/model_declared",
     "texte": "`/1` exige un identifiant de modele non vide. La VERSION "
              "separe les deux lectures : elargir `/1` aurait rendu valides, "
              "sous une reference inchangee, des documents qu il refusait."},
    {"verdict": "REJETE", "exit_code": 1, "exit_code_strict": 1},
    paquet_dossier(manifeste_v1(
        ARTEFACTS_TYPE,
        execution={"kind_declared": "replay", "model_declared": None})))

cas("B-06-optional-fields-absent", "B-incomplete", "submission",
    "Les champs FACULTATIFS absents : `provenance_declared`, "
    "`limits_declared`, `notes_declared`.",
    {"statut": "NORMATIVE",
     "reference": "schemas/evidence-submission-v2.json#/required",
     "texte": "Un champ facultatif absent n affecte pas le verdict. Il peut "
              "en revanche produire une ligne NOT TESTED, qui n est pas un "
              "echec."},
    {"verdict": "ACCEPTE", "exit_code": 0, "exit_code_strict": 0},
    paquet_dossier(manifeste_v2(ARTEFACTS_TYPE)))


# ========== FAMILLE C — paquets MALFORMES ===============================

cas("C-01-invalid-json", "C-malformed", "submission",
    "Manifeste JSON tronque au milieu.",
    {"statut": "NORMATIVE", "reference": "RFC 8259",
     "texte": "Un document JSON incomplet n est pas du JSON."},
    {"verdict": "REJETE", "exit_code": 1, "exit_code_strict": 1},
    paquet_dossier_brut(jsonb(manifeste_v2(ARTEFACTS_TYPE))[:120]))

cas("C-02-invalid-utf8", "C-malformed", "submission",
    "Un octet 0xFF dans un nom de membre : pas de l UTF-8 valide.",
    {"statut": "NORMATIVE", "reference": "RFC 8259 §8.1",
     "texte": "Un texte JSON echange entre systemes est encode en UTF-8. "
              "Un octet invalide est un refus, jamais un remplacement "
              "silencieux."},
    {"verdict": "REJETE", "exit_code": 1, "exit_code_strict": 1},
    paquet_dossier_brut(
        jsonb(manifeste_v2(ARTEFACTS_TYPE)).replace(b'"pilot"', b'"pil\xffot"')))

cas("C-03-unexpected-structure", "C-malformed", "submission",
    "`pilot` est un TABLEAU la ou le contrat attend un objet.",
    {"statut": "NORMATIVE",
     "reference": "schemas/evidence-submission-v2.json"
                  "#/properties/pilot/type",
     "texte": "Un type inattendu est un refus, et le refus doit NOMMER le "
              "champ."},
    {"verdict": "REJETE", "exit_code": 1, "exit_code_strict": 1},
    paquet_dossier(manifeste_v2(ARTEFACTS_TYPE, pilot=["Corpus"])))

cas("C-04-unknown-version", "C-malformed", "submission",
    "`schema` annonce une version de contrat inconnue.",
    {"statut": "NORMATIVE",
     "reference": "schemas/evidence-submission-v2.json"
                  "#/properties/schema/const",
     "texte": "Une version inconnue est refusee, jamais interpretee au "
              "mieux : lire un document selon un contrat qu on ne connait "
              "pas serait decider a la place de son auteur."},
    {"verdict": "REJETE", "exit_code": 1, "exit_code_strict": 1},
    paquet_dossier(manifeste_v2(
        ARTEFACTS_TYPE, schema="neomundi.evidence.submission/99")))

cas("C-05-field-not-allowed-by-schema", "C-malformed", "submission",
    "Un champ en SURPLUS dans `pilot`, que `additionalProperties: false` "
    "interdit.",
    {"statut": "AMBIGUOUS",
     "reference": "schemas/evidence-submission-v2.json"
                  "#/properties/pilot/additionalProperties",
     "texte": "Le schema publie `additionalProperties: false`. "
              "`adapters/ingest.py` a tranche autrement : il NOMME le champ "
              "en surplus en NOT TESTED plutot que de refuser, pour ne pas "
              "rompre un paquet que le contrat precedent acceptait. La "
              "divergence est ASSUMEE et documentee dans le code. Un corpus "
              "de conformite ne peut donc pas imposer un verdict unique."},
    {"ambiguous": True,
     "python": {"verdict": "ACCEPTE", "exit_code": 0},
     "note": "Le schema impose un refus ; l implementation de reference "
             "nomme et poursuit. Les deux lectures sont defendables, et "
             "aucune n est imposee par ce corpus."},
    paquet_dossier(manifeste_v2(
        ARTEFACTS_TYPE,
        pilot={"name_declared": "Corpus", "champ_en_surplus": "x"})))

cas("C-06-not-a-zip", "C-malformed", "submission",
    "Un fichier `.zip` qui n est pas une archive.",
    {"statut": "NORMATIVE", "reference": "APPNOTE ZIP §4.3.16",
     "texte": "Sans fin de repertoire central, il n y a pas d archive."},
    {"verdict": "REJETE", "exit_code": 1, "exit_code_strict": 1},
    lambda: [("paquet.zip", b"\x00" * 2048)])

cas("C-07-archive-crc-invalid", "C-malformed", "archive",
    "Archive Evidence dont le CRC-32 d un membre contredit ses donnees.",
    {"statut": "NORMATIVE", "reference": "APPNOTE ZIP §4.3.12",
     "texte": "Le CRC-32 du repertoire central doit egaler celui des "
              "donnees. `unzip` et `zipfile` refusent une archive ou il "
              "diverge ; un verificateur de preuve ne doit pas conclure "
              "<< accepte >> la ou tout outil standard dit << corrompu >>."},
    {"verdict": "REJETE", "exit_code": 1, "exit_code_strict": 1},
    None, derive_de="A-05-archive-valid", mutation="crc")

cas("C-08-archive-local-header-mismatch", "C-malformed", "archive",
    "L en-tete LOCAL nomme un autre membre que le repertoire central.",
    {"statut": "NORMATIVE", "reference": "APPNOTE ZIP §4.3.7 et §4.3.12",
     "texte": "Les deux noms doivent coincider. Sinon deux lecteurs "
              "conformes tirent des octets differents sous le meme nom."},
    {"verdict": "REJETE", "exit_code": 1, "exit_code_strict": 1},
    None, derive_de="A-05-archive-valid", mutation="nom-local")

cas("C-09-archive-deflate-invalid", "C-malformed", "archive",
    "Un membre annonce la methode 8 (deflate) et porte un flux invalide.",
    {"statut": "NORMATIVE", "reference": "RFC 1951",
     "texte": "Un flux DEFLATE dont les arbres de Huffman sont invalides "
              "doit etre refuse, non decode au mieux."},
    {"verdict": "REJETE", "exit_code": 1, "exit_code_strict": 1},
    None, derive_de="A-05-archive-valid", mutation="deflate")


# ========== FAMILLE D — FALSIFICATIONS ==================================

cas("D-01-artifact-tampered", "D-tampered", "submission",
    "Un octet ajoute a un artefact, son empreinte declaree inchangee.",
    {"statut": "NORMATIVE",
     "reference": "schemas/evidence-submission-v2.json"
                  "#/properties/artifacts/items/properties/sha256",
     "texte": "L empreinte declaree est RECALCULEE sur les octets du "
              "fichier. Une divergence est un refus, et les DEUX valeurs "
              "doivent figurer au rapport."},
    {"verdict": "REJETE", "exit_code": 1, "exit_code_strict": 1},
    paquet_dossier(manifeste_v2(ARTEFACTS_TYPE),
                   [("artefacts/prompt.txt", PROMPT + b"x"),
                    ("artefacts/reponse.txt", REPONSE)]))

cas("D-02-manifest-digest-wrong", "D-tampered", "submission",
    "L empreinte DECLAREE est fausse, les octets sont intacts.",
    {"statut": "NORMATIVE",
     "reference": "schemas/evidence-submission-v2.json",
     "texte": "Le sens du refus est le meme : declare et recalcule "
              "divergent. Qui des deux a change n est pas decidable depuis "
              "le paquet seul."},
    {"verdict": "REJETE", "exit_code": 1, "exit_code_strict": 1},
    paquet_dossier(manifeste_v2(
        [artefact("artefacts/prompt.txt", SHA_FAUX, len(PROMPT), "prompt")]),
        [("artefacts/prompt.txt", PROMPT)]))

cas("D-03-size-wrong", "D-tampered", "submission",
    "La TAILLE declaree est fausse, l empreinte est juste.",
    {"statut": "NORMATIVE",
     "reference": "schemas/evidence-submission-v2.json"
                  "#/properties/artifacts/items/properties/bytes",
     "texte": "La taille est elle aussi recalculee. Deux controles "
              "independants valent mieux qu un."},
    {"verdict": "REJETE", "exit_code": 1, "exit_code_strict": 1},
    paquet_dossier(manifeste_v2(
        [artefact("artefacts/prompt.txt", PROMPT_SHA, 999, "prompt")]),
        [("artefacts/prompt.txt", PROMPT)]))

cas("D-04-file-substituted", "D-tampered", "submission",
    "Les octets de DEUX artefacts sont echanges, les empreintes declarees "
    "restant a leur place.",
    {"statut": "NORMATIVE",
     "reference": "schemas/evidence-submission-v2.json",
     "texte": "Une substitution se voit sur les deux empreintes a la fois."},
    {"verdict": "REJETE", "exit_code": 1, "exit_code_strict": 1},
    paquet_dossier(manifeste_v2(ARTEFACTS_TYPE),
                   [("artefacts/prompt.txt", REPONSE),
                    ("artefacts/reponse.txt", PROMPT)]))

cas("D-05-artifact-removed", "D-tampered", "submission",
    "Un artefact declare est SUPPRIME du paquet.",
    {"statut": "NORMATIVE",
     "reference": "COMPORTEMENT OBSERVE -- adapters/ingest.py",
     "texte": "Un artefact absent rend INCOMPLET, pas REJETE : c est une "
              "difference de nature, et un corpus de conformite doit la "
              "preserver."},
    {"verdict": "INCOMPLET", "exit_code": 0, "exit_code_strict": 2},
    paquet_dossier(manifeste_v2(ARTEFACTS_TYPE),
                   [("artefacts/reponse.txt", REPONSE)]))

cas("D-06-attestation-signature-invalid", "D-tampered", "attestation",
    "Un octet de la SIGNATURE est retourne.",
    {"statut": "NORMATIVE", "reference": "RFC 8032 §5.1.7",
     "texte": "Une signature alteree ne verifie pas. Aucun niveau n est "
              "derive."},
    {"attested_level": None, "verdict": "REJETE",
     "exit_code": 1, "exit_code_strict": 1},
    None, derive_de="A-06-attestation-valid", mutation="signature",
    options=["--allow-test-keys"])

cas("D-07-attestation-payload-tampered", "D-tampered", "attestation",
    "La CHARGE est remplacee apres la signature : les octets signes ne sont "
    "plus ceux qui voyagent.",
    {"statut": "NORMATIVE", "reference": "RFC 7515 §5.2",
     "texte": "La verification porte sur les octets PORTES par le jeton."},
    {"attested_level": None, "verdict": "REJETE",
     "exit_code": 1, "exit_code_strict": 1},
    None, derive_de="A-06-attestation-valid", mutation="charge",
    options=["--allow-test-keys"])

cas("D-08-attestation-wrong-key", "D-tampered", "attestation",
    "Le magasin porte une AUTRE clef publique sous le meme `kid`.",
    {"statut": "NORMATIVE", "reference": "RFC 8032",
     "texte": "Une clef substituee ne verifie pas la signature. La "
              "substitution est obtenue en alterant le MAGASIN, qui ne "
              "contient que du public : aucune clef privee n est embarquee "
              "dans ce corpus."},
    {"attested_level": None, "verdict": "REJETE",
     "exit_code": 1, "exit_code_strict": 1},
    None, derive_de="A-06-attestation-valid", mutation="cle-substituee",
    options=["--allow-test-keys"])

cas("D-09-attestation-replaced-by-other", "D-tampered", "attestation",
    "L attestation porte sur une AUTRE archive que celle fournie.",
    {"statut": "NORMATIVE",
     "reference": "verify_attestation.py -- pilier `concordance`",
     "texte": "La concordance confronte `bundle_sha256`, `manifest_sha256` "
              "et `checksums_sha256` aux octets de l archive tenue."},
    {"attested_level": None, "verdict": "REJETE",
     "exit_code": 1, "exit_code_strict": 1},
    None, derive_de="A-06-attestation-valid", mutation="autre-archive",
    options=["--allow-test-keys"])

cas("D-10-archive-member-tampered", "D-tampered", "archive",
    "Un octet ajoute a `rapport.md` d une archive Evidence.",
    {"statut": "NORMATIVE", "reference": "verify.py -- empreintes des membres",
     "texte": "`checksums.sha256` declare l empreinte de chaque membre ; "
              "elle est recalculee."},
    {"verdict": "REJETE", "exit_code": 1, "exit_code_strict": 1},
    None, derive_de="A-05-archive-valid", mutation="membre")


# ========== FAMILLE E — CHEMINS DANGEREUX ===============================

for _ident, _chemin, _quoi in (
    ("E-01-path-traversal", "../dehors.txt", "remontee `..`"),
    ("E-02-path-absolute-unix", "/etc/passwd", "chemin absolu Unix"),
    ("E-03-path-absolute-windows", "C:\\Windows\\x.txt",
     "lettre de lecteur Windows"),
    ("E-04-path-backslash", "artefacts\\x.txt", "antislash comme separateur"),
    ("E-05-path-empty", "", "chemin vide"),
):
    cas(_ident, "E-paths", "submission",
        "Artefact declare avec un chemin dangereux : %s." % _quoi,
        {"statut": "NORMATIVE",
         "reference": "schemas/evidence-submission-v2.json"
                      "#/properties/artifacts/items/properties/path "
                      "(prose : « un chemin relatif, sans remontee »)",
         "texte": "Un chemin qui sort du paquet est refuse AVANT toute "
                  "lecture. Le contrat l exige en prose ; le MOTIF exact "
                  "applique par les implementations n est pas publie, et "
                  "c est AMBIGUITE-1 des rapports precedents."},
        {"verdict": "REJETE", "exit_code": 1, "exit_code_strict": 1},
        paquet_dossier(
            manifeste_v2([artefact(_chemin, PROMPT_SHA, len(PROMPT), "other")]),
            [("artefacts/prompt.txt", PROMPT)]))

cas("E-06-path-declared-twice", "E-paths", "submission",
    "Le MEME chemin declare deux fois dans `artifacts`, avec deux "
    "empreintes differentes.",
    {"statut": "AMBIGUOUS",
     "reference": "schemas/evidence-submission-v2.json"
                  "#/properties/artifacts -- aucun `uniqueItems`",
     "texte": "Le schema ne publie aucune contrainte d unicite sur "
              "`artifacts[].path`. Un meme chemin ne peut pourtant pas "
              "porter deux empreintes. Le contrat est MUET : ce corpus ne "
              "peut pas imposer un verdict."},
    {"ambiguous": True,
     "note": "Au moins une des deux empreintes sera fausse, donc un refus "
             "est probable -- mais pour une raison incidente, non parce que "
             "le doublon serait interdit."},
    paquet_dossier(manifeste_v2([
        artefact("artefacts/prompt.txt", PROMPT_SHA, len(PROMPT), "prompt"),
        artefact("artefacts/prompt.txt", SHA_FAUX, len(PROMPT), "other"),
    ])))

cas("E-07-zip-member-duplicate", "E-paths", "submission",
    "Un ZIP portant DEUX membres de meme nom.",
    {"statut": "NORMATIVE", "reference": "APPNOTE ZIP",
     "texte": "Deux membres de meme nom rendent l archive ambigue : un "
              "lecteur prendrait le premier, un autre le dernier, et les "
              "deux condenseraient des octets differents sous le meme "
              "chemin declare."},
    {"verdict": "REJETE", "exit_code": 1, "exit_code_strict": 1},
    lambda: [("paquet.zip", ecrire_zip(
        [("submission.json", jsonb(manifeste_v2(ARTEFACTS_TYPE)))]
        + FICHIERS_TYPE
        + [("artefacts/prompt.txt", b"un autre contenu")]))])

cas("E-08-path-dot-segment", "E-paths", "submission",
    "Un segment `.` dans le chemin : `artefacts/./prompt.txt`.",
    {"statut": "AMBIGUOUS",
     "reference": "AMBIGUITE-1 -- CONSOLIDATION_RUST_PR26/07",
     "texte": "Le contrat interdit les chemins dangereux en PROSE. Le motif "
              "effectivement applique par les implementations admet `a/./b` "
              "et refuse `a/../b` : cette bizarrerie n est publiee nulle "
              "part. Un corpus de conformite la CONSIGNE sans la trancher."},
    {"ambiguous": True,
     # FIGE EN 1.2.0, et la note de 1.1.0 etait FAUSSE.
     #
     # Elle affirmait que << les implementations de reference admettent le
     # segment `.` >>. Mesure du 11 novembre : elles ne font pas la meme
     # chose, et l ecart est net.
     #
     #   python       ACCEPTE (code 0) -- et son propre rapport signale
     #                `artefacts/prompt.txt` comme fichier NON DECLARE,
     #                alors qu il vient d accepter la declaration
     #                `artefacts/./prompt.txt`. Les deux ecritures ne se
     #                reconnaissent donc pas entre elles.
     #   rust-core    REJETE (code 1) -- il refuse le chemin, et compte
     #                l artefact declare comme << 1 refuse >>.
     #
     # Cette divergence n avait ete nommee par personne : le banc mesurait
     # les deux verdicts et ne les comparait jamais. Elle est apparue des
     # que l instrument a ete corrige.
     "python": {"verdict": "ACCEPTE", "exit_code": 0},
     "rust-core": {"verdict": "REJETE", "exit_code": 1},
     "note": "FIGE par verificateur en 1.2.0. La note de 1.1.0 affirmait que "
             "les deux implementations admettent le segment `.` : c est FAUX. "
             "python ACCEPTE, rust-core REFUSE. Et python signale le meme "
             "fichier comme NON DECLARE dans son propre rapport : les deux "
             "ecritures du chemin ne se reconnaissent pas entre elles."},
    paquet_dossier(
        manifeste_v2([artefact("artefacts/./prompt.txt", PROMPT_SHA,
                               len(PROMPT), "prompt")]),
        [("artefacts/prompt.txt", PROMPT)]))


# ========== FAMILLE F — REECRITURES COHERENTES ==========================

#: UN ARTEFACT REECRIT, ET SON EMPREINTE RECALCULEE EN CONSEQUENCE.
#:
#: Le resultat attendu est ACCEPTE, et c est le point de cette famille.
#: Un paquet dont le contenu a change et dont les empreintes ont ete
#: refaites est COHERENT avec son propre manifeste. Aucun controle
#: d integrite interne ne peut le voir.
#:
#: « Ne jamais creer artificiellement un FAIL pour ameliorer un taux de
#:   detection. »
REPONSE_REECRITE = b"une autre reponse, entierement reecrite\n"

cas("F-01-coherent-rewrite-accepted", "F-coherent-rewrite", "submission",
    "Le contenu d un artefact est REMPLACE et son empreinte RECALCULEE. "
    "Le paquet est coherent, et il est ACCEPTE.",
    {"statut": "NORMATIVE",
     "reference": "COMPLETUDE_RUST_EVIDENCE/08 §2 -- plafond declare",
     "texte": "Un paquet reecrit puis re-hache proprement est coherent avec "
              "son manifeste. L accepter est CORRECT : l integrite interne "
              "ne dit rien de l authenticite. Seule une ancre externe -- "
              "signature, horodatage tiers, empreinte conservee ailleurs -- "
              "distingue l original du refait."},
    {"verdict": "ACCEPTE", "exit_code": 0, "exit_code_strict": 0,
     "ceiling": True},
    paquet_dossier(
        manifeste_v2([
            artefact("artefacts/prompt.txt", PROMPT_SHA, len(PROMPT), "prompt"),
            artefact("artefacts/reponse.txt", sha(REPONSE_REECRITE),
                     len(REPONSE_REECRITE), "response"),
        ]),
        [("artefacts/prompt.txt", PROMPT),
         ("artefacts/reponse.txt", REPONSE_REECRITE)]))

cas("F-02-coherent-rewrite-breaks-attestation", "F-coherent-rewrite",
    "attestation",
    "La MEME archive reecrite de façon coherente, confrontee a "
    "l attestation d ORIGINE. L attestation refuse.",
    {"statut": "NORMATIVE",
     "reference": "verify_attestation.py -- pilier `concordance`",
     "texte": "Une attestation porte sur une EMPREINTE. Une archive "
              "reecrite, meme parfaitement coherente, n a plus cette "
              "empreinte. C est la raison pour laquelle l ancre doit etre "
              "exterieure a l archive."},
    {"attested_level": None, "verdict": "REJETE",
     "exit_code": 1, "exit_code_strict": 1},
    None, derive_de="A-06-attestation-valid", mutation="archive-reecrite",
    options=["--allow-test-keys"])

cas("F-03-archive-amputated-no-contract", "F-coherent-rewrite", "archive",
    "Une observation retiree PARTOUT, decomptes et sommes refaits, sur une "
    "archive qui ne declare PAS de contrat de completude.",
    {"statut": "NORMATIVE",
     "reference": "DEVELOPPEMENT_CORPUS_CONFORMITE/06 -- scenario D",
     "texte": "Sur une archive sans contrat de completude, aucun controle "
              "interne ne voit ce qui a ete retire. Le resultat attendu est "
              "donc ACCEPTE, et c est un PLAFOND declare, pas un echec du "
              "verificateur."},
    # Meme cause qu en `A-05` : derive de cette archive, meme garantie
    # requise non demontree faute de `--corpus`. `F-01` porte le meme
    # couple et reste a 0 : c est un cas de SOUMISSION, et ce chemin
    # recevait deja `--strict`.
    {"verdict": "ACCEPTE", "exit_code": 0, "exit_code_strict": 2,
     "ceiling": True},
    None, derive_de="A-05-archive-valid", mutation="amputation",
    attendu_par_verificateur={
        "rust-crypto": {"exit_code": 0, "exit_code_strict": 0,
                        "raison": "La garantie REQUISE qui vaut 2 cote `verify.py` est celle des << empreintes des entrees rejouees >>, que seul `--corpus` demontre. `evidence-verify-crypto` ne modelise PAS cette garantie sur une archive : il n a aucune entree a rejouer, donc aucune garantie requise non demontree, donc 0. Difference de SURFACE declaree, et non divergence de regle.",}})


# ========== FAMILLE G — AMBIGUITES ET DIVERGENCES =======================

cas("G-01-duplicate-json-keys", "G-ambiguous", "submission",
    "`submission_id` declare DEUX fois dans le manifeste.",
    {"statut": "AMBIGUOUS",
     "reference": "RFC 8259 §4 ; CONSOLIDATION_RUST_PR26/AMBIGUITE_4_DECISION.md",
     "texte": "La RFC dit que les noms « SHOULD be unique » et laisse le cas "
              "INDEFINI. Les deux contrats Evidence n en disent rien : "
              "`duplicate`, `unique` et `RFC 8259` ont zero occurrence dans "
              "les schemas publies. Une implementation qui refuse et une qui "
              "garde la derniere sont toutes deux defendables."},
    {"ambiguous": True,
     "python": {"verdict": "ACCEPTE", "exit_code": 0},
     "rust-core": {"verdict": "REJETE", "exit_code": 1},
     "note": "Recommandation consignee : interdire. Compatibilite mesuree : "
             "0 doublon sur 494 documents JSON du depot. NON arbitre."},
    paquet_dossier_brut(
        jsonb(manifeste_v2(ARTEFACTS_TYPE)).replace(
            b'"submission_id": "conformance-v2-001"',
            b'"submission_id": "premier", "submission_id": "conformance-v2-001"',
            1)))

cas("G-02-duplicate-key-on-digest", "G-ambiguous", "submission",
    "DEUX `sha256` pour UN artefact : laquelle est controlee ?",
    {"statut": "AMBIGUOUS",
     "reference": "RFC 8259 §4",
     "texte": "La meme ambiguite, portee sur le champ le plus sensible du "
              "contrat. Un producteur qui ecrit la premiere valeur et un "
              "verificateur qui lit la seconde ne parlent pas du meme "
              "document."},
    {"ambiguous": True,
     "python": {"verdict": "ACCEPTE", "exit_code": 0},
     "rust-core": {"verdict": "REJETE", "exit_code": 1},
     "note": "C est le cas qui rend l ambiguite grave : l empreinte est le "
             "coeur du dispositif."},
    paquet_dossier_brut(
        jsonb(manifeste_v2(ARTEFACTS_TYPE)).replace(
            b'"sha256": "%s"' % PROMPT_SHA.encode(),
            b'"sha256": "%s", "sha256": "%s"' % (SHA_FAUX.encode(),
                                                 PROMPT_SHA.encode()),
            1)))

cas("G-03-nan-outside-rfc", "G-ambiguous", "submission",
    "`NaN` dans un champ hors contrat : la RFC 8259 ne le definit pas.",
    {"statut": "AMBIGUOUS",
     "reference": "RFC 8259 §6 ; COMPLETUDE_RUST_EVIDENCE/08 §4",
     "texte": "La grammaire des nombres de la RFC n a ni `NaN` ni "
              "`Infinity`. `json` de Python les accepte comme extension ; un "
              "analyseur strict les refuse. Les contrats Evidence n en "
              "disent rien."},
    {"ambiguous": True,
     "python": {"verdict": "ACCEPTE", "exit_code": 0},
     "rust-core": {"verdict": "REJETE", "exit_code": 1},
     "note": "Meme famille que G-01. A trancher avec elle, pas separement."},
    paquet_dossier_brut(
        jsonb(manifeste_v2(ARTEFACTS_TYPE)).replace(
            b'"artifacts"', b'"champ_hors_contrat": NaN,\n  "artifacts"', 1)))

cas("G-04-infinity-outside-rfc", "G-ambiguous", "submission",
    "`Infinity` dans un champ hors contrat.",
    {"statut": "AMBIGUOUS", "reference": "RFC 8259 §6",
     "texte": "Variante de G-03."},
    {"ambiguous": True,
     "python": {"verdict": "ACCEPTE", "exit_code": 0},
     "rust-core": {"verdict": "REJETE", "exit_code": 1},
     "note": "Meme decision que G-03."},
    paquet_dossier_brut(
        jsonb(manifeste_v2(ARTEFACTS_TYPE)).replace(
            b'"artifacts"', b'"champ_hors_contrat": Infinity,\n  "artifacts"', 1)))

cas("G-05-lone-surrogate", "G-ambiguous", "submission",
    "Une demi-paire de substitution UTF-16 dans un champ declare.",
    {"statut": "AMBIGUOUS", "reference": "RFC 8259 §8.2",
     "texte": "La RFC reconnait que sa grammaire autorise des chaines qui ne "
              "representent pas de l Unicode, et declare un tel texte NON "
              "INTEROPERABLE -- sans l interdire. `json` l accepte ; un "
              "analyseur strict le refuse."},
    {"ambiguous": True,
     "python": {"verdict": "REJETE", "exit_code": 1},
     "rust-core": {"verdict": "REJETE", "exit_code": 1},
     "note": "Les DEUX refusent desormais, pour deux raisons DIFFERENTES : "
             "Python parce que la valeur ne peut pas etre reportee verbatim, "
             "Rust parce que son analyseur refuse la demi-paire. La "
             "concordance de verdict ne resout pas l ambiguite."},
    paquet_dossier_brut(
        jsonb(manifeste_v2(ARTEFACTS_TYPE)).replace(
            b'"name_declared": "Corpus de conformite"',
            b'"name_declared": "' + bytes([0x5C]) + b'ud800Corpus"', 1)))

cas("G-06-base64url-padding", "G-ambiguous", "attestation",
    "Un segment du JWS porte un bourrage `=`, que la RFC 7515 §2 interdit.",
    {"statut": "AMBIGUOUS",
     "reference": "RFC 7515 §2 ; COMPLETUDE_RUST_EVIDENCE/03 §8",
     "texte": "La RFC impose base64url SANS bourrage. `base64` de Python le "
              "tolere. Consequence : une attestation a PLUSIEURS "
              "serialisations acceptees d un cote et une seule de l autre."},
    {"ambiguous": True,
     # FIGE EN 1.2.0. Les deux refusent, et leurs MOTIFS differaient :
     # `rust-crypto` nomme le bourrage ; `verify_attestation.py` annoncait
     # que la clef n avait pas signe ces octets -- vrai des octets mutes,
     # et il accusait la mauvaise piece. Le motif est corrige, le verdict
     # est inchange, et il est desormais FIGE ici.
     "python": {"verdict": "REJETE", "exit_code": 1},
     "rust-crypto": {"verdict": "REJETE", "exit_code": 1},
     "note": "Troisieme ambiguite de la meme famille. NON arbitree. Les "
             "deux REFUSENT, et le comportement est desormais fige par "
             "verificateur -- il ne l etait pas en 1.1.0."},
    None, derive_de="A-06-attestation-valid", mutation="b64-bourrage",
    options=["--allow-test-keys"])

cas("G-07-base64url-standard-alphabet", "G-ambiguous", "attestation",
    "Le segment de SIGNATURE est reecrit en base64 STANDARD (`+`/`/`).",
    {"statut": "AMBIGUOUS", "reference": "RFC 7515 §2",
     "texte": "Les octets de signature sont IDENTIQUES ; seule leur "
              "ecriture change. Python decode et atteste ; un lecteur strict "
              "refuse le jeton."},
    {"ambiguous": True,
     # FIGE EN 1.2.0 -- et c est la raison d etre de cette version.
     #
     # La DIVERGENCE etait reelle et reproductible des 1.1.0, et le corpus
     # ne la publiait pas : la fiche ne figeait aucun comportement par
     # verificateur, contrairement a `G-01` a `G-05`. Le banc mesurait les
     # deux verdicts, les rangeait dans `observed`, et ne les comparait
     # jamais. Mesure du 11 novembre, memes options, memes octets :
     #
     #   python       code 0, pilier signature PASS   -> ACCEPTE
     #   rust-crypto  code 1, et il NOMME l alphabet  -> REJETE
     "python": {"verdict": "ACCEPTE", "exit_code": 0},
     "rust-crypto": {"verdict": "REJETE", "exit_code": 1},
     "note": "C est le cas ou la divergence est la plus visible : un meme "
             "engagement cryptographique est atteste d un cote et refuse de "
             "l autre, sans qu aucun octet signe ne differe. FIGE par "
             "verificateur en 1.2.0 : le corpus 1.1.0 mesurait cette "
             "divergence sans la publier."},
    None, derive_de="A-06-attestation-valid", mutation="b64-standard",
    options=["--allow-test-keys"])


# --------------------------------------------------------------------------
# Les mutations dérivées des artefacts réels
# --------------------------------------------------------------------------


def _lire_zip(octets: bytes) -> list[tuple[str, bytes]]:
    with zipfile.ZipFile(io.BytesIO(octets)) as z:
        return [(i.filename, z.read(i.filename)) for i in z.infolist()]


def _resommer(membres: list[tuple[str, bytes]]) -> list[tuple[str, bytes]]:
    table = dict(membres)
    lignes = []
    for nom in sorted(table):
        if nom == "checksums.sha256":
            continue
        lignes.append("%s  %s" % (sha(table[nom]), nom))
    table["checksums.sha256"] = ("\n".join(lignes) + "\n").encode("utf-8")
    return [(n, table[n]) for n in sorted(table)]


def _zip_crc_faux(octets: bytes) -> bytes:
    """Reecrit le ZIP a la main pour poser un CRC-32 FAUX.

    `zipfile` ne sait pas produire un CRC faux : il le calcule. Il faut donc
    forger les octets, et c est pour cela que ce cas existe.
    """
    import struct
    import zlib
    membres = _lire_zip(octets)
    sortie = bytearray()
    entrees = []
    for nom, donnees in membres:
        crc = zlib.crc32(donnees) & 0xFFFFFFFF
        if nom == "rapport.md":
            crc ^= 0xFFFFFFFF          # LE mensonge, sur un seul membre
        nb = nom.encode("utf-8")
        decalage = len(sortie)
        sortie += struct.pack("<IHHHHHIIIHH", 0x04034B50, 20, 0, 0, 0, 0,
                              crc, len(donnees), len(donnees), len(nb), 0)
        sortie += nb + donnees
        entrees.append((nom, crc, len(donnees), decalage))
    depart = len(sortie)
    rc = bytearray()
    for nom, crc, n, decalage in entrees:
        nb = nom.encode("utf-8")
        rc += struct.pack("<IHHHHHHIIIHHHHHII", 0x02014B50, 20, 20, 0, 0, 0, 0,
                          crc, n, n, len(nb), 0, 0, 0, 0, 0, decalage)
        rc += nb
    sortie += rc
    sortie += struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, len(entrees),
                          len(entrees), len(rc), depart, 0)
    return bytes(sortie)


def _zip_nom_local_divergent(octets: bytes) -> bytes:
    """L en-tete LOCAL nomme autre chose que le repertoire central."""
    import struct
    import zlib
    membres = _lire_zip(octets)
    sortie = bytearray()
    entrees = []
    for nom, donnees in membres:
        crc = zlib.crc32(donnees) & 0xFFFFFFFF
        nom_local = "autre.md" if nom == "rapport.md" else nom
        nb = nom_local.encode("utf-8")
        decalage = len(sortie)
        sortie += struct.pack("<IHHHHHIIIHH", 0x04034B50, 20, 0, 0, 0, 0,
                              crc, len(donnees), len(donnees), len(nb), 0)
        sortie += nb + donnees
        entrees.append((nom, crc, len(donnees), decalage))
    depart = len(sortie)
    rc = bytearray()
    for nom, crc, n, decalage in entrees:
        nb = nom.encode("utf-8")
        rc += struct.pack("<IHHHHHHIIIHHHHHII", 0x02014B50, 20, 20, 0, 0, 0, 0,
                          crc, n, n, len(nb), 0, 0, 0, 0, 0, decalage)
        rc += nb
    sortie += rc
    sortie += struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, len(entrees),
                          len(entrees), len(rc), depart, 0)
    return bytes(sortie)


def _zip_deflate_invalide(octets: bytes) -> bytes:
    """Un membre annonce la methode 8 et porte un flux invalide."""
    import struct
    import zlib
    membres = _lire_zip(octets)
    sortie = bytearray()
    entrees = []
    for nom, donnees in membres:
        crc = zlib.crc32(donnees) & 0xFFFFFFFF
        if nom == "rapport.md":
            # Genre de bloc 3, reserve par la RFC 1951 §3.2.3.
            comp, methode = b"\x07\xff\xff\xff", 8
        else:
            comp, methode = donnees, 0
        nb = nom.encode("utf-8")
        decalage = len(sortie)
        sortie += struct.pack("<IHHHHHIIIHH", 0x04034B50, 20, 0, methode, 0, 0,
                              crc, len(comp), len(donnees), len(nb), 0)
        sortie += nb + comp
        entrees.append((nom, crc, len(comp), len(donnees), methode, decalage))
    depart = len(sortie)
    rc = bytearray()
    for nom, crc, nc, nd, meth, decalage in entrees:
        nb = nom.encode("utf-8")
        rc += struct.pack("<IHHHHHHIIIHHHHHII", 0x02014B50, 20, 20, 0, meth, 0,
                          0, crc, nc, nd, len(nb), 0, 0, 0, 0, 0, decalage)
        rc += nb
    sortie += rc
    sortie += struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, len(entrees),
                          len(entrees), len(rc), depart, 0)
    return bytes(sortie)


def _zip_membre_altere(octets: bytes) -> bytes:
    membres = [(n, (o + b"x") if n == "rapport.md" else o)
               for n, o in _lire_zip(octets)]
    return ecrire_zip(membres)


def _zip_amputation(octets: bytes) -> bytes:
    """Une observation retiree PARTOUT, decomptes et sommes refaits.

    C est le faussaire du scenario D, reconstruit ici. Il ne touche PAS
    `registre.enregistrements_exportes` -- voir
    `DEVELOPPEMENT_CORPUS_CONFORMITE/06`, qui montre que ce champ decide du
    resultat.
    """
    table = dict(_lire_zip(octets))
    observations = [json.loads(l) for l in
                    table["observations.jsonl"].splitlines() if l.strip()]
    victime = observations[-1]["payload"]["observation_id"]

    def sans(membre: str) -> int:
        if membre not in table:
            return 0
        gardees = [l for l in table[membre].splitlines()
                   if l.strip()
                   and json.loads(l)["payload"].get("observation_id") != victime]
        table[membre] = b"\n".join(gardees) + b"\n" if gardees else b""
        return len(gardees)

    d = {
        "observations": sans("observations.jsonl"),
        "mesures": sans("measurements.jsonl"),
        "evaluations": sans("reference_evaluations.jsonl"),
        "provenances_de_rejeu": sans("replay_provenance.jsonl"),
    }
    lignes = table["observations.csv"].split(b"\r\n")
    table["observations.csv"] = b"\r\n".join(
        l for l in lignes if victime.encode("utf-8") not in l)
    m = json.loads(table["manifest.json"])
    m["decomptes"].update(d)
    table["manifest.json"] = jsonb(m)
    return ecrire_zip(_resommer(list(table.items())))


def _zip_reecriture_coherente(octets: bytes) -> bytes:
    """`rapport.md` remplace, et TOUTES les sommes refaites."""
    table = dict(_lire_zip(octets))
    table["rapport.md"] = b"# Rapport entierement reecrit\n\nCoherent, et faux.\n"
    return ecrire_zip(_resommer(list(table.items())))


MUTATIONS_ZIP = {
    "crc": _zip_crc_faux,
    "nom-local": _zip_nom_local_divergent,
    "deflate": _zip_deflate_invalide,
    "membre": _zip_membre_altere,
    "amputation": _zip_amputation,
    "archive-reecrite": _zip_reecriture_coherente,
}


def _jws_mutation(jeton: str, quoi: str) -> str:
    """Altere un JWS SANS jamais signer. Toutes ces mutations sont des
    reecritures d octets."""
    e, c, s = jeton.strip().split(".")
    if quoi == "signature":
        brut = bytearray(_deb64u(s))
        brut[0] ^= 0xFF
        return "%s.%s.%s" % (e, c, _b64u(bytes(brut)))
    if quoi == "charge":
        charge = json.loads(_deb64u(c))
        charge["subject"]["observation_count"] = "99"
        nouvelle = json.dumps(charge, sort_keys=True, separators=(",", ":"),
                              ensure_ascii=False).encode("utf-8")
        return "%s.%s.%s" % (e, _b64u(nouvelle), s)
    if quoi == "b64-bourrage":
        return "%s=.%s.%s" % (e, c, s)
    if quoi == "b64-standard":
        return "%s.%s.%s" % (e, c, s.replace("-", "+").replace("_", "/"))
    raise AssertionError("mutation de JWS inconnue : %s" % quoi)


def _b64u(o: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(o).rstrip(b"=").decode("ascii")


def _deb64u(s: str) -> bytes:
    import base64
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


# --------------------------------------------------------------------------
# Construction
# --------------------------------------------------------------------------


def construire(verifier_seulement: bool) -> int:
    reel_zip = (DOSSIER_REEL / "NEOMUNDI_EVIDENCE_V1_DEMO.zip").read_bytes()
    reel_jws = (DOSSIER_REEL / "NEOMUNDI_EVIDENCE_V1_DEMO.zip.jws").read_text("ascii")
    reel_magasin = (DOSSIER_REEL / "trust-store.json").read_bytes()

    fiches: list[dict] = []
    tous_fichiers: list[tuple[str, bytes]] = []

    for c in CAS:
        base = "fixtures/%s/%s" % (c["famille"], c["id"])
        fichiers: list[tuple[str, bytes]] = []

        if c["fabriquer"] is not None:
            fichiers = [("%s/%s" % (base, n), o) for n, o in c["fabriquer"]()]

        elif c.get("source_reelle") == "NEOMUNDI_EVIDENCE_V1_DEMO.zip":
            fichiers = [("%s/archive.zip" % base, reel_zip)]

        elif c.get("source_reelle") == "ATTESTATION":
            fichiers = [("%s/archive.zip" % base, reel_zip),
                        ("%s/attestation.jws" % base, reel_jws.encode("ascii")),
                        ("%s/trust-store.json" % base, reel_magasin)]

        elif c.get("derive_de") == "A-05-archive-valid":
            fichiers = [("%s/archive.zip" % base,
                         MUTATIONS_ZIP[c["mutation"]](reel_zip))]

        elif c.get("derive_de") == "A-06-attestation-valid":
            m = c["mutation"]
            if m == "cle-substituee":
                mag = json.loads(reel_magasin)
                # Une AUTRE clef publique, valide en forme, sous le meme kid.
                mag["keys"][0]["x"] = "0" * 43
                fichiers = [
                    ("%s/archive.zip" % base, reel_zip),
                    ("%s/attestation.jws" % base, reel_jws.encode("ascii")),
                    ("%s/trust-store.json" % base, jsonb(mag))]
            elif m == "autre-archive":
                autre = ecrire_zip([("manifest.json", b'{"schema":"autre"}')])
                fichiers = [
                    ("%s/archive.zip" % base, autre),
                    ("%s/attestation.jws" % base, reel_jws.encode("ascii")),
                    ("%s/trust-store.json" % base, reel_magasin)]
            elif m == "archive-reecrite":
                fichiers = [
                    ("%s/archive.zip" % base, _zip_reecriture_coherente(reel_zip)),
                    ("%s/attestation.jws" % base, reel_jws.encode("ascii")),
                    ("%s/trust-store.json" % base, reel_magasin)]
            else:
                fichiers = [
                    ("%s/archive.zip" % base, reel_zip),
                    ("%s/attestation.jws" % base,
                     _jws_mutation(reel_jws, m).encode("ascii")),
                    ("%s/trust-store.json" % base, reel_magasin)]
        else:
            raise AssertionError("cas sans fabrique ni source : %s" % c["id"])

        tous_fichiers += fichiers

        # L empreinte du magasin est connue A LA CONSTRUCTION : la poser
        # dans les options fait de A-06 la configuration COMPLETE, celle ou
        # la confrontation par un second canal a bien lieu.
        options_resolues = [
            sha(reel_magasin) if o == "@STORE_DIGEST@" else o
            for o in c.get("options", [])]

        provenance = ("SYNTHETIQUE, genere par conformance/runners/"
                      "build_fixtures.py")
        if c.get("source_reelle") or c.get("derive_de"):
            provenance = ("DERIVE de examples/dossier-v1/, deja public dans ce "
                          "depot et declare << aucune donnee reelle >>. "
                          "Aucun dossier de pilote n intervient.")

        fiche = {
            "schema": SCHEMA_FICHE,
            "id": c["id"],
            "corpus_version": VERSION_CORPUS,
            "family": c["famille"],
            "subject": c["genre"],
            "description": c["description"],
            "provenance": provenance,
            "publication": {
                "licence": "Apache-2.0 (celle du depot)",
                "authorised": True,
                "contains_private_data": False,
                "contains_private_keys": False,
            },
            "files": [{"path": n, "sha256": sha(o), "bytes": len(o)}
                      for n, o in fichiers],
            "rule": c["regle"],
            "expected": c["attendu"],
            "expected_by_verifier": c.get("attendu_par_verificateur", {}),
            "options": options_resolues,
            "limits": [
                "L integrite ne demontre pas la verite des evenements.",
                "Un verdict de conformite ne vaut que pour les regles que ce "
                "cas cite, et pour les versions de contrat qu il nomme.",
            ],
        }
        if c["attendu"].get("ceiling"):
            fiche["limits"].insert(0,
                "PLAFOND DECLARE : le resultat attendu est une ACCEPTATION, "
                "et c est correct. Ne jamais convertir ce cas en FAIL pour "
                "ameliorer un taux de detection.")
        fiches.append(fiche)

    if verifier_seulement:
        return _comparer(fiches, tous_fichiers)

    # --- ecriture ---------------------------------------------------------
    shutil.rmtree(FIXTURES, ignore_errors=True)
    shutil.rmtree(ATTENDUS, ignore_errors=True)
    for chemin, octets in tous_fichiers:
        cible = CORPUS / chemin
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes(octets)
    ATTENDUS.mkdir(parents=True, exist_ok=True)
    for f in fiches:
        (ATTENDUS / ("%s.json" % f["id"])).write_bytes(jsonb(f))

    # `write_bytes`, et pas `write_text` : sous Windows, `write_text`
    # traduit "\n" en CRLF. MESURE du 11 novembre -- la regeneration de
    # 1.1.0 a produit un `VERSION` et un `SHA256SUMS` en CRLF, donc un
    # `SHA256SUMS` dont les 172 lignes differaient TOUTES de celles du
    # depot alors qu AUCUNE empreinte n avait change. Le corpus doit sortir
    # aux memes octets sur toute machine : c est sa seule propriete non
    # negociable.
    (CORPUS / "VERSION").write_bytes((VERSION_CORPUS + "\n").encode("utf-8"))

    manifeste = {
        "schema": SCHEMA_MANIFESTE,
        "corpus_version": VERSION_CORPUS,
        "generated_by": "conformance/runners/build_fixtures.py",
        "determinism": [
            "Aucune horloge n est lue : toutes les dates sont des constantes.",
            "Aucune clef n est generee : aucune clef privee n existe dans ce "
            "corpus.",
            "Les ZIP ont une date FIXE et la methode ZIP_STORED.",
            "Le JSON est trie, indente de deux espaces, en UTF-8.",
        ],
        "contracts_covered": sorted({
            "neomundi.evidence.submission/1",
            "neomundi.evidence.submission/2",
            "station.export.campagne/2",
            "neomundi.evidence.attestation/1",
            "neomundi.evidence.trust-store/1",
        }),
        "families": sorted({c["famille"] for c in CAS}),
        "cases": [{"id": f["id"], "family": f["family"],
                   "subject": f["subject"],
                   "rule_status": f["rule"]["statut"],
                   "files": [x["path"] for x in f["files"]],
                   "expected": f["expected"]} for f in fiches],
        "counts": {
            "cases": len(fiches),
            "files": len(tous_fichiers),
            "by_family": {fam: sum(1 for c in CAS if c["famille"] == fam)
                          for fam in sorted({c["famille"] for c in CAS})},
            "by_rule_status": {
                s: sum(1 for f in fiches if f["rule"]["statut"] == s)
                for s in sorted({f["rule"]["statut"] for f in fiches})},
        },
    }
    (CORPUS / "manifest.json").write_bytes(jsonb(manifeste))

    sommes = ["%s  %s" % (sha(o), n) for n, o in sorted(tous_fichiers)]
    sommes += ["%s  %s" % (sha(jsonb(f)), "expected/%s.json" % f["id"])
               for f in sorted(fiches, key=lambda x: x["id"])]
    sommes.append("%s  %s" % (sha(jsonb(manifeste)), "manifest.json"))
    # Meme raison que pour `VERSION` ci-dessus : jamais `write_text`.
    (CORPUS / "SHA256SUMS").write_bytes(
        ("\n".join(sommes) + "\n").encode("utf-8"))

    print("corpus %s ecrit" % VERSION_CORPUS)
    print("  cas      : %d" % len(fiches))
    print("  fichiers : %d" % len(tous_fichiers))
    for fam in sorted({c["famille"] for c in CAS}):
        print("  %-20s %d cas" % (fam, sum(1 for c in CAS if c["famille"] == fam)))
    for s in sorted({f["rule"]["statut"] for f in fiches}):
        print("  regles %-12s %d cas"
              % (s, sum(1 for f in fiches if f["rule"]["statut"] == s)))
    return 0


def _comparer(fiches, tous_fichiers) -> int:
    """`--check` : les octets qu on produirait sont-ils ceux du depot ?"""
    ecarts = []
    for chemin, octets in tous_fichiers:
        sur_disque = CORPUS / chemin
        if not sur_disque.is_file():
            ecarts.append("absent : %s" % chemin)
        elif sur_disque.read_bytes() != octets:
            ecarts.append("octets differents : %s" % chemin)
    for f in fiches:
        p = ATTENDUS / ("%s.json" % f["id"])
        if not p.is_file():
            ecarts.append("fiche absente : %s" % f["id"])
        elif p.read_bytes() != jsonb(f):
            ecarts.append("fiche differente : %s" % f["id"])
    if ecarts:
        print("LE GENERATEUR NE REPRODUIT PAS LE CORPUS VERSIONNE :")
        for e in ecarts[:20]:
            print("  %s" % e)
        print("\nSoit le generateur a change, soit le corpus a ete edite a la")
        print("main. Dans les deux cas il faut une nouvelle VERSION et de")
        print("nouvelles empreintes -- pas une regeneration silencieuse.")
        return 1
    print("le generateur reproduit le corpus a l octet (%d fichiers, %d fiches)"
          % (len(tous_fichiers), len(fiches)))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="ne rien ecrire ; verifier que le corpus versionne "
                         "est bien celui que ce generateur produit")
    a = ap.parse_args()
    if not DOSSIER_REEL.is_dir():
        print("examples/dossier-v1/ introuvable", file=sys.stderr)
        return 2
    return construire(a.check)


if __name__ == "__main__":
    raise SystemExit(main())
