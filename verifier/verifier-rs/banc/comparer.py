#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Banc comparatif Python / Rust sur le MÊME paquet, séparément.

    python3 verifier-rs/banc/comparer.py [--binaire <chemin>] [--json <sortie>]
                                         [--corpus-reel <racine>]
                                         [--exiger-corpus-reel]

DEUX NIVEAUX DE VALIDATION, ET IL NE FAUT PAS LES CONFONDRE
-----------------------------------------------------------

**Niveau 1 — CI publique.** Corpus **publics et synthétiques** seulement. Le
paquet tiers n'est pas dans ce dépôt et n'y entrera pas : la CI ne le détient
donc **jamais**. Le cas `reel-ogs-b3-v2` y est **déclaré NON EXÉCUTÉ**, avec
sa raison, et il n'est compté ni en succès ni en échec. La CI reste verte —
l'absence d'un matériau confidentiel qu'elle n'est pas censée posséder n'est
pas une faute — mais **elle ne peut plus laisser croire que le paquet tiers a
été vérifié**.

**Niveau 2 — qualification privée.** Sur une machine qui détient
légitimement le paquet :

    EVIDENCE_BANC_CORPUS_REEL=/chemin/vers/candidate \\
    EVIDENCE_BANC_EXIGER_REEL=1 \\
    python3 verifier-rs/banc/comparer.py --json rapport.json

Le matériau est **injecté par un chemin**, jamais publié. Et
`--exiger-corpus-reel` retourne la règle : dans un environnement qui se
**déclare** capable de mesurer le cas réel, son absence devient un **échec
net** (code 4). Rejouable **sans modifier une ligne de code**.

LA POLITIQUE DE COMPARAISON
---------------------------

Les deux rapports **ne sont pas comparés octet par octet**, et n'ont pas à
l'être : ils n'ont même pas le même identifiant de schéma, délibérément.
Ce qui est comparé est l'**équivalence sémantique**, sur cinq axes de
CONCLUSION :

  1. VERDICT        `ACCEPTE` / `REJETE` / `INCOMPLET` -- doit être identique
  2. CODE DE SORTIE doit être identique, hors le code 3 propre à Rust
                    (erreur d'exécution), qui est une divergence DÉCLARÉE
  3. EMPREINTES     pour tout artefact lu des DEUX côtés, le SHA-256
                    recalculé doit être identique, et l'état
                    (concordant / discordant / absent / chemin_refuse) aussi
  4. SIGNATURES     la ligne « signatures existantes » doit porter le même
                    ÉTAT, si les DEUX vérificateurs l'ont atteinte
  5. ERREURS        un refus d'un côté doit être un refus de l'autre ; le
                    LIBELLÉ peut différer, la CLASSE non

Ce qui n'est PAS comparé, et pourquoi : le nombre exact de lignes de
rapport, leur ordre, leur prose, et les décomptes PASS/FAIL/NOT TESTED. Les
deux implémentations découpent leurs contrôles différemment -- Rust émet par
exemple une ligne distincte pour la forme des empreintes déclarées -- et
exiger l'égalité des décomptes imposerait à la seconde implémentation de
copier le découpage de la première. Ce serait reproduire Python, pas le
vérifier.

CE QUI A ÉTÉ AFFINÉ APRÈS LE PREMIER PASSAGE, ET CE QUI NE L'A PAS ÉTÉ
---------------------------------------------------------------------

La mission demande des règles fixées AVANT les tests. Elles l'étaient. Le
premier passage a toutefois montré que l'instrument confondait deux choses :
un **désaccord de conclusion**, et une **différence de profondeur de refus**
-- deux vérificateurs qui refusent le même paquet, avec le même verdict et
le même code, mais dont l'un refuse avant d'avoir énuméré les artefacts.

L'axe « ensembles d'artefacts rapportés » a donc été reclassé de
« divergence » à « différence de profondeur », consignée et affichée.
**Aucun axe de conclusion n'a été assoupli** : le verdict, le code de
sortie, l'empreinte recalculée sur l'intersection et la classe d'erreur
sont inchangés et toujours exigés identiques.

C'est une correction de l'instrument de mesure, et elle est déclarée ici
plutôt que passée sous silence. Le détail, et les deux cas concernés,
figurent en **D-B** de `04_MATRICE_PYTHON_RUST.md`.

PYTHON N'EST PAS L'ORACLE
-------------------------

Une divergence est enregistrée, pas arbitrée. La colonne « cause probable »
est une hypothèse à instruire, et la règle contractuelle applicable est
citée. Rien n'est corrigé ici pour obtenir une concordance.

AUCUNE DÉPENDANCE FONCTIONNELLE
-------------------------------

Ce banc lance les deux programmes et compare leurs sorties. Le vérificateur
Rust ne lit jamais le rapport Python, et réciproquement. Le banc lui-même
n'est pas le vérificateur : il est un témoin.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]

# --------------------------------------------------------------------------
# Les cas. Chacun porte son VERDICT ATTENDU, écrit AVANT exécution, et
# dérivé du contrat publié -- pas du comportement observé.
# --------------------------------------------------------------------------

#: Les profils de `tests/make_submission.py`, avec le verdict qu'exige le
#: contrat. Corpus SYNTHÉTIQUE du dépôt.
PROFILS = {
    "valide": "ACCEPTE",
    "empreinte-fausse": "REJETE",
    "paquet-modifie": "REJETE",
    "champ-absent": "REJETE",
    "artefact-absent": "INCOMPLET",
    "chemin-malveillant": "REJETE",
    "provenance-insuffisante": "ACCEPTE",
    "v1-modele-nul": "REJETE",
    "v1-modele-nul-motive": "REJETE",
    "v1-modele-blanc": "ACCEPTE",
    "v2-modele-nomme": "ACCEPTE",
    "v2-non-applicable": "ACCEPTE",
    "v2-indisponible": "ACCEPTE",
    "v2-non-applicable-avec-fournisseur": "ACCEPTE",
    "v2-sans-motif": "REJETE",
    "v2-sans-note": "REJETE",
    "v2-note-vide": "REJETE",
    "v2-note-blanche": "REJETE",
    "v2-motif-inconnu": "REJETE",
    "v2-motif-non-textuel": "REJETE",
    "v2-note-non-textuelle": "REJETE",
    "v2-contradiction": "REJETE",
    "v2-modele-vide": "REJETE",
    "v2-modele-blanc": "REJETE",
    "v2-execution-malformee": "REJETE",
}


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def sha_arbre(racine: Path) -> str:
    """Empreinte d'un paquet-dossier : chemins relatifs + condensés, triés.

    Un paquet n'a pas d'empreinte propre ; celle-ci en est une, stable et
    reproductible, pour que chaque fixture du corpus soit identifiable.
    """
    lignes = []
    for p in sorted(racine.rglob("*"), key=lambda x: x.as_posix()):
        if p.is_file():
            lignes.append("%s %s" % (p.relative_to(racine).as_posix(), sha(p)))
    return hashlib.sha256("\n".join(lignes).encode()).hexdigest()


def lancer_python(paquet: Path, sortie: Path, strict: bool) -> dict:
    rapport = sortie / "py.json"
    if rapport.exists():
        rapport.unlink()
    cmd = [sys.executable, "-B", str(RACINE / "adapters/ingest.py"), str(paquet),
           "--out", str(rapport), "--lang", "fr"]
    if strict:
        cmd.append("--strict")
    x = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=300,
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    d = json.loads(rapport.read_bytes()) if rapport.exists() else None
    return {"code": x.returncode, "rapport": d, "stderr": x.stderr or ""}


def lancer_rust(binaire: Path, paquet: Path, sortie: Path, strict: bool) -> dict:
    rapport = sortie / "rs.json"
    if rapport.exists():
        rapport.unlink()
    cmd = [str(binaire), str(paquet), "--json", str(rapport)]
    if strict:
        cmd.append("--strict")
    x = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=300)
    d = json.loads(rapport.read_bytes()) if rapport.exists() else None
    return {"code": x.returncode, "rapport": d, "stderr": x.stderr or ""}


def etat_signatures(rapport: dict | None) -> str | None:
    """L'état de la ligne « signatures existantes », des deux côtés."""
    if not rapport:
        return None
    for l in rapport.get("lines", []):
        if l.get("intitule") in ("signatures existantes", "existing signatures"):
            return l.get("etat")
    return None


def empreintes(rapport: dict | None) -> dict:
    """chemin -> (etat, sha256 recalculé). Les clefs diffèrent entre les
    deux rapports, et c'est tout ce qui diffère : Python publie `sha256`,
    Rust `sha256_recomputed`."""
    if not rapport:
        return {}
    out = {}
    for a in rapport.get("artifacts", []):
        chemin = a.get("path")
        etat = a.get("etat")
        rec = a.get("sha256") or a.get("sha256_recomputed") or a.get("sha256_recalcule")
        out[chemin] = (etat, rec)
    return out


def comparer(py: dict, rs: dict) -> tuple[list[dict], list[dict]]:
    """Rend (divergences de CONCLUSION, différences de PROFONDEUR DE REFUS).

    LA DISTINCTION, ET POURQUOI ELLE A ÉTÉ AJOUTÉE
    ----------------------------------------------

    Le premier passage du banc a signalé trois divergences. Deux d'entre
    elles ne portaient pas sur la CONCLUSION : les deux vérificateurs
    refusaient le même paquet, avec le même verdict et le même code de
    sortie, mais l'un refusait **plus tôt** que l'autre — avant d'avoir
    énuméré les artefacts. Le banc comptait cette différence de profondeur
    comme une divergence.

    C'était un défaut de l'INSTRUMENT, pas des vérificateurs. Exiger des
    ENSEMBLES d'artefacts identiques imposerait à la seconde implémentation
    d'adopter l'ordre de refus de la première — c'est-à-dire de reproduire
    Python au lieu de le vérifier.

    La politique est donc affinée, et **aucun critère de conclusion n'est
    assoupli** : le verdict et le code de sortie doivent toujours être
    identiques, et une empreinte recalculée des deux côtés doit toujours
    concorder. Seule la comparaison des ENSEMBLES d'artefacts passe de
    « divergence » à « différence de profondeur », consignée et non
    masquée. Voir **D-B** de `04_MATRICE_PYTHON_RUST.md`.
    """
    conclusion: list[dict] = []
    profondeur: list[dict] = []
    vpy = (py["rapport"] or {}).get("verdict")
    vrs = (rs["rapport"] or {}).get("verdict")

    # --- axes de CONCLUSION : jamais assouplis ---------------------
    if vpy != vrs:
        conclusion.append({"axe": "verdict", "python": vpy, "rust": vrs})
    if py["code"] != rs["code"]:
        conclusion.append(
            {"axe": "code_de_sortie", "python": py["code"], "rust": rs["code"]})

    epy, ers = empreintes(py["rapport"]), empreintes(rs["rapport"])
    # L'INTERSECTION : pour tout artefact lu des DEUX côtés, l'état et
    # l'empreinte recalculée doivent coïncider. C'est le cœur du critère.
    for chemin in sorted(set(epy) & set(ers)):
        if epy[chemin] != ers[chemin]:
            conclusion.append({
                "axe": "empreinte",
                "artefact": chemin,
                "python": epy[chemin],
                "rust": ers[chemin],
            })

    # Un refus d'un côté doit être un refus de l'autre.
    refus_py = vpy == "REJETE" or py["rapport"] is None
    refus_rs = vrs == "REJETE" or rs["rapport"] is None
    if refus_py != refus_rs:
        conclusion.append(
            {"axe": "classe_d_erreur", "python": refus_py, "rust": refus_rs})

    # L'état de la ligne « signatures » n'est comparé que si les DEUX
    # vérificateurs sont allés jusqu'à ce contrôle. Un refus antérieur n'est
    # pas un désaccord sur les signatures.
    spy, srs = etat_signatures(py["rapport"]), etat_signatures(rs["rapport"])
    if spy is not None and srs is not None and spy != srs:
        conclusion.append({"axe": "signatures", "python": spy, "rust": srs})

    # --- PROFONDEUR DE REFUS : consignée, non masquée --------------
    if set(epy) != set(ers):
        profondeur.append({
            "axe": "artefacts_rapportes",
            "python_seulement": sorted(set(epy) - set(ers)),
            "rust_seulement": sorted(set(ers) - set(epy)),
            "note": "un verificateur a refuse AVANT d enumerer les artefacts",
        })
    if (spy is None) != (srs is None):
        profondeur.append({
            "axe": "ligne_signatures_atteinte",
            "python": spy, "rust": srs,
            "note": "un verificateur a refuse AVANT d atteindre ce controle",
        })
    return conclusion, profondeur


# --------------------------------------------------------------------------
# Les cas ADVERSARIAUX construits ici : ils n'existent pas dans le dépôt.
# Chacun est SYNTHÉTIQUE, et porte son verdict attendu, écrit d'avance.
# --------------------------------------------------------------------------


def muter(base: Path, cible: Path, mutation) -> Path:
    shutil.rmtree(cible, ignore_errors=True)
    shutil.copytree(base, cible)
    chemin = cible / "submission.json"
    doc = json.loads(chemin.read_bytes())
    mutation(doc, cible)
    chemin.write_bytes(
        (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return cible


def octets_bruts(cible: Path, octets: bytes) -> Path:
    """Un manifeste écrit en octets bruts : pour les cas où le JSON lui-même
    est l'objet du test."""
    (cible / "submission.json").write_bytes(octets)
    return cible


ADVERSARIAUX = [
    # (identifiant, description, verdict attendu, construction)
    ("adv-chemin-absolu", "artefact a chemin absolu", "REJETE",
     lambda d, c: d.__setitem__("artifacts", [
         {"path": "/etc/passwd", "sha256": "0" * 64, "bytes": 0, "role": "other"}])),
    ("adv-remontee", "artefact a segment `..`", "REJETE",
     lambda d, c: d.__setitem__("artifacts", [
         {"path": "../../etc/passwd", "sha256": "0" * 64, "bytes": 0,
          "role": "other"}])),
    ("adv-lettre-lecteur", "artefact a lettre de lecteur", "REJETE",
     lambda d, c: d.__setitem__("artifacts", [
         {"path": "C:/x", "sha256": "0" * 64, "bytes": 0, "role": "other"}])),
    ("adv-antislash", "artefact a barre oblique inversee", "REJETE",
     lambda d, c: d.__setitem__("artifacts", [
         {"path": "a\\b.txt", "sha256": "0" * 64, "bytes": 0, "role": "other"}])),
    ("adv-sha-majuscules", "empreinte declaree en MAJUSCULES", "REJETE",
     lambda d, c: d["artifacts"][0].__setitem__(
         "sha256", d["artifacts"][0]["sha256"].upper())),
    ("adv-taille-flottante", "taille declaree `1e3` au lieu d un entier", "REJETE",
     lambda d, c: d["artifacts"][0].__setitem__("bytes", 1e3)),
    ("adv-role-absent", "artefact sans `role`", "REJETE",
     lambda d, c: d["artifacts"][0].pop("role")),
    ("adv-role-inconnu", "`role` hors enumeration", "REJETE",
     lambda d, c: d["artifacts"][0].__setitem__("role", "banana")),
    ("adv-nature-inconnue", "`kind_declared` hors enumeration", "REJETE",
     lambda d, c: d["execution"].__setitem__("kind_declared", "do-anything")),
    ("adv-date-invalide", "`submitted_at_declared` = `hier`", "REJETE",
     lambda d, c: d.__setitem__("submitted_at_declared", "hier")),
    ("adv-pilote-liste", "`pilot` recu sous forme de liste", "REJETE",
     lambda d, c: d.__setitem__("pilot", ["pilot"])),
    ("adv-artefact-vide", "artefact de 0 octet, declare correctement", "ACCEPTE",
     None),  # construction speciale
    ("adv-fichier-non-declare", "fichier present et non declare", "ACCEPTE",
     None),  # construction speciale
    ("adv-reecriture-coherente",
     "artefact ET manifeste reecrits de facon coherente", "ACCEPTE",
     None),  # construction speciale
]


def construire_adversariaux(base: Path, travail: Path) -> list[dict]:
    """Rend la liste des cas construits, chacun avec son verdict attendu."""
    cas = []
    for ident, desc, attendu, mutation in ADVERSARIAUX:
        cible = travail / ident
        if mutation is not None:
            muter(base, cible, mutation)
        elif ident == "adv-artefact-vide":
            shutil.rmtree(cible, ignore_errors=True)
            shutil.copytree(base, cible)
            (cible / "artefacts/vide.txt").write_bytes(b"")
            doc = json.loads((cible / "submission.json").read_bytes())
            doc["artifacts"].append({
                "path": "artefacts/vide.txt",
                "sha256": hashlib.sha256(b"").hexdigest(),
                "bytes": 0, "role": "other", "media_type": None})
            (cible / "submission.json").write_bytes(
                (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode())
        elif ident == "adv-fichier-non-declare":
            shutil.rmtree(cible, ignore_errors=True)
            shutil.copytree(base, cible)
            (cible / "artefacts/intrus.txt").write_bytes(b"non declare\n")
        elif ident == "adv-reecriture-coherente":
            # Le cas le plus instructif : le fichier ET son empreinte
            # declaree sont changes ENSEMBLE. Aucun des deux verificateurs
            # ne peut le detecter, et c est la LIMITE du dispositif -- pas
            # un defaut. Les deux doivent dire ACCEPTE.
            shutil.rmtree(cible, ignore_errors=True)
            shutil.copytree(base, cible)
            neuf = b"contenu entierement reecrit\n"
            (cible / "artefacts/response.txt").write_bytes(neuf)
            doc = json.loads((cible / "submission.json").read_bytes())
            for a in doc["artifacts"]:
                if a["path"] == "artefacts/response.txt":
                    a["sha256"] = hashlib.sha256(neuf).hexdigest()
                    a["bytes"] = len(neuf)
            (cible / "submission.json").write_bytes(
                (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode())
        cas.append({"id": ident, "description": desc, "attendu": attendu,
                    "chemin": cible, "corpus": "synthetique",
                    "origine": "construit par ce banc"})
    return cas


def construire_zips(base: Path, travail: Path) -> list[dict]:
    """Les cas qui n'existent QU'EN ZIP : doublon, traversee, bombe."""
    cas = []
    manifeste = (base / "submission.json").read_bytes()

    def zip_depuis(nom: str, entrees: list[tuple[str, bytes]]) -> Path:
        p = travail / nom
        with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
            for n, o in entrees:
                z.writestr(n, o)
        return p

    # paquet ZIP valide, miroir du dossier
    entrees = [("submission.json", manifeste)]
    for f in sorted((base / "artefacts").glob("*")):
        entrees.append(("artefacts/" + f.name, f.read_bytes()))
    cas.append({
        "id": "zip-valide", "description": "paquet ZIP valide",
        "attendu": "ACCEPTE", "chemin": zip_depuis("zip-valide.zip", entrees),
        "corpus": "synthetique", "origine": "construit par ce banc"})

    # nom de membre en DOUBLE
    cas.append({
        "id": "zip-doublon",
        "description": "deux membres de MEME nom dans l archive",
        "attendu": "REJETE",
        "chemin": zip_depuis("zip-doublon.zip",
                             entrees + [("artefacts/response.txt", b"autre\n")]),
        "corpus": "synthetique", "origine": "construit par ce banc"})

    # membre a chemin de traversee
    cas.append({
        "id": "zip-traversee",
        "description": "membre d archive a segment `..`",
        "attendu": "REJETE",
        "chemin": zip_depuis("zip-traversee.zip",
                             entrees + [("../evade.txt", b"evade\n")]),
        "corpus": "synthetique", "origine": "construit par ce banc"})

    # membre a chemin absolu
    cas.append({
        "id": "zip-absolu",
        "description": "membre d archive a chemin absolu",
        "attendu": "REJETE",
        "chemin": zip_depuis("zip-absolu.zip",
                             entrees + [("/tmp/evade.txt", b"evade\n")]),
        "corpus": "synthetique", "origine": "construit par ce banc"})

    # BOMBE DE DECOMPRESSION.
    #
    # Le membre volumineux est DECLARE comme artefact : sans cela, le cas ne
    # testerait pas la borne mais l absence des artefacts declares, et les
    # deux verificateurs refuseraient pour deux raisons differentes. La
    # premiere version de ce cas commettait exactement cette faute, et le
    # banc l a signalee comme une divergence -- a juste titre : c etait la
    # FIXTURE qui etait fausse, pas les verificateurs. Voir **D-C**.
    gros = b"\0" * (80 * 1024 * 1024)
    doc_bombe = json.loads(manifeste)
    doc_bombe["artifacts"] = [{
        "path": "artefacts/gros.bin",
        "sha256": hashlib.sha256(gros).hexdigest(),
        "bytes": len(gros), "role": "other", "media_type": None}]
    p = travail / "zip-bombe.zip"
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("submission.json",
                   json.dumps(doc_bombe, ensure_ascii=False, indent=2) + "\n")
        z.writestr("artefacts/gros.bin", gros)
    cas.append({
        "id": "zip-bombe",
        "description": "artefact DECLARE de 80 Mio, au-dela de la borne par fichier",
        "attendu": "REJETE", "chemin": p,
        "corpus": "synthetique", "origine": "construit par ce banc"})

    # archive tronquee
    bon = (travail / "zip-valide.zip").read_bytes()
    p = travail / "zip-tronque.zip"
    p.write_bytes(bon[: len(bon) // 2])
    cas.append({
        "id": "zip-tronque", "description": "archive ZIP tronquee de moitie",
        "attendu": "REJETE", "chemin": p,
        "corpus": "synthetique", "origine": "construit par ce banc"})

    # pas un zip du tout
    p = travail / "pasunzip.zip"
    p.write_bytes(b"ceci n est pas un zip")
    cas.append({
        "id": "zip-invalide", "description": "fichier qui n est pas une archive",
        "attendu": "REJETE", "chemin": p,
        "corpus": "synthetique", "origine": "construit par ce banc"})
    return cas


def construire_json_ambigu(base: Path, travail: Path) -> list[dict]:
    """Les cas où le JSON lui-même est l'objet du test.

    `adv-json-clef-double` est LA divergence attendue : la RFC 8259 laisse
    le cas indéfini, Python garde la dernière clef en silence, Rust refuse.
    Le verdict attendu est donc écrit « DIVERGENCE_ATTENDUE », et non un
    verdict unique -- l'annoncer d'avance est la seule façon honnête de
    tester une ambiguïté.
    """
    cas = []
    brut = (base / "submission.json").read_bytes()
    doc = json.loads(brut)

    def avec(nom: str, octets: bytes, desc: str, attendu: str) -> dict:
        cible = travail / nom
        shutil.rmtree(cible, ignore_errors=True)
        shutil.copytree(base, cible)
        (cible / "submission.json").write_bytes(octets)
        return {"id": nom, "description": desc, "attendu": attendu,
                "chemin": cible, "corpus": "synthetique",
                "origine": "construit par ce banc"}

    # Clef en double, injectee textuellement.
    texte = json.dumps(doc, ensure_ascii=False, indent=2)
    double = texte.replace(
        '"submission_id":', '"submission_id": "zzz-premier-identifiant",\n  "submission_id":',
        1)
    cas.append(avec("adv-json-clef-double", double.encode() + b"\n",
                    "`submission_id` declare DEUX fois",
                    "DIVERGENCE_ATTENDUE"))

    # BOM UTF-8 en tete : les deux doivent le tolerer.
    cas.append(avec("adv-json-bom", b"\xef\xbb\xbf" + brut,
                    "manifeste avec BOM UTF-8", "ACCEPTE"))

    # JSON malforme.
    cas.append(avec("adv-json-malforme", brut[: len(brut) // 2],
                    "manifeste JSON tronque", "REJETE"))

    # Encodage invalide au milieu d une chaine.
    casse = brut.replace(b'"pilot"', b'"pil\xffot"', 1)
    cas.append(avec("adv-json-utf8-invalide", casse,
                    "octet UTF-8 invalide dans un nom de membre", "REJETE"))

    # Virgule trainante : la RFC l interdit.
    cas.append(avec("adv-json-virgule-trainante",
                    texte.replace("\n}", ",\n}", 1).encode() + b"\n",
                    "virgule trainante en fin d objet", "REJETE"))
    return cas


def main() -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--binaire", type=Path,
                   default=Path(os.environ.get("CARGO_TARGET_DIR",
                                               str(Path.home() / "evr-target")))
                   / "release" / "evidence-verify-rs")
    a.add_argument("--json", type=Path, default=None)
    # ---- le corpus HISTORIQUE, injecte depuis l EXTERIEUR ---------------
    #
    # Le paquet tiers ne vit PAS dans ce depot et n y entrera pas. Il est
    # donc designe par un chemin, pas embarque. Trois voies, de la plus
    # explicite a la plus implicite :
    #
    #   --corpus-reel <chemin>            l operateur le dit
    #   EVIDENCE_BANC_CORPUS_REEL=<chemin> un script le dit
    #   (defaut historique)               le poste qui le detient deja
    #
    # Aucun service, aucune infrastructure : un chemin suffit.
    a.add_argument(
        "--corpus-reel", type=Path, default=None,
        help="racine du candidat TIERS a confronter (dossier contenant "
             "submission.json). Par defaut : $EVIDENCE_BANC_CORPUS_REEL, "
             "puis le chemin historique de l audit. JAMAIS publie.")
    a.add_argument(
        "--exiger-corpus-reel", action="store_true",
        default=os.environ.get("EVIDENCE_BANC_EXIGER_REEL", "") not in ("", "0"),
        help="ECHOUER si le corpus reel est absent. A poser dans un "
             "environnement de QUALIFICATION PRIVEE, jamais dans la CI "
             "publique, qui n est pas censee detenir ce materiau. "
             "Variable equivalente : EVIDENCE_BANC_EXIGER_REEL=1.")
    arguments = a.parse_args()

    if not arguments.binaire.exists():
        print("binaire Rust absent : %s" % arguments.binaire, file=sys.stderr)
        print("compiler avec verifier-rs/banc/build.sh", file=sys.stderr)
        return 3

    travail = Path(tempfile.mkdtemp(prefix="banc-evr-"))
    sortie = travail / "_rapports"
    sortie.mkdir()
    cas: list[dict] = []
    #: Les cas DECLARES et NON EXECUTES. Ils ne rejoignent jamais `cas` :
    #: ils sont comptes a part, nommes, et jamais additionnes aux succes.
    non_executes: list[dict] = []
    try:
        # ---- corpus 1 : les profils du depot -------------------------
        for profil, attendu in PROFILS.items():
            cible = travail / ("profil-" + profil)
            x = subprocess.run(
                [sys.executable, str(RACINE / "tests/make_submission.py"),
                 str(cible), "--profil", profil],
                capture_output=True, text=True)
            if x.returncode != 0:
                continue
            cas.append({"id": "profil-" + profil,
                        "description": "profil `%s` de make_submission.py" % profil,
                        "attendu": attendu, "chemin": cible,
                        "corpus": "synthetique",
                        "origine": "tests/make_submission.py (depot)"})

        base = travail / "profil-v2-non-applicable"
        if not base.exists():
            base = travail / "profil-valide"

        # ---- corpus 2 : adversariaux ---------------------------------
        cas += construire_adversariaux(base, travail)
        cas += construire_zips(base, travail)
        cas += construire_json_ambigu(base, travail)

        # ---- corpus 3 : le candidat OGS B-3 v2 REEL ------------------
        #
        # Corpus HISTORIQUE. Lu en LECTURE SEULE, jamais modifie, jamais
        # publie dans ce depot.
        #
        # POURQUOI CE BLOC NE SE CONTENTE PLUS D UN `if`
        # ----------------------------------------------
        #
        # Il s ecrivait `if reel.is_dir(): cas.append(...)` -- SANS `else`.
        # Le paquet vivant hors du depot, le cas disparaissait donc partout
        # ou il est absent, c est-a-dire TOUJOURS en CI, et RIEN ne le
        # disait. Mesure du 2026-11-12 : **52 cas sur le poste qui detient
        # le paquet, 51 en CI**. Le seul cas portant un materiau TIERS REEL
        # etait precisement celui qui s evanouissait, et un lecteur du
        # journal lisait << 51 cas, 51/51 conformes >> sans aucun moyen de
        # le savoir.
        #
        # Une preuve non executee ne doit jamais ressembler a une preuve
        # reussie. Le cas est desormais DECLARE dans les deux cas : execute,
        # ou NON EXECUTE avec sa raison, compte a part, et jamais additionne
        # aux succes.
        DEFAUT_REEL = (RACINE.parent / "NeoMundi_Evidence" / "AUDITS_EXTERNES"
                       / "AUDIT_INDEPENDANT" / "work" / "extracted" / "candidate")
        if arguments.corpus_reel is not None:
            reel, source_reel = arguments.corpus_reel, "--corpus-reel"
        elif os.environ.get("EVIDENCE_BANC_CORPUS_REEL"):
            reel = Path(os.environ["EVIDENCE_BANC_CORPUS_REEL"])
            source_reel = "EVIDENCE_BANC_CORPUS_REEL"
        else:
            reel, source_reel = DEFAUT_REEL, "chemin historique par defaut"

        if reel.is_dir() and (reel / "submission.json").is_file():
            cas.append({"id": "reel-ogs-b3-v2",
                        "description": "candidat OGS B-3 v2, 19 artefacts",
                        "attendu": "ACCEPTE", "chemin": reel,
                        "corpus": "historique",
                        "origine": "soumission OGS B-3 v2 (tiers), lecture seule"
                                   " -- designe par %s" % source_reel})
        else:
            if reel.is_dir():
                raison = ("le chemin existe mais ne porte pas `submission.json` :"
                          " ce n est pas une racine de candidat")
            else:
                raison = "le dossier n existe pas sur cette machine"
            non_executes.append({
                "id": "reel-ogs-b3-v2",
                "description": "candidat OGS B-3 v2, 19 artefacts",
                "corpus": "historique",
                "statut": "NON_EXECUTE",
                "attendu": "ACCEPTE",
                "raison": raison,
                "chemin_attendu": str(reel),
                "designe_par": source_reel,
                "comment_le_fournir":
                    "--corpus-reel <racine du candidat> ou "
                    "EVIDENCE_BANC_CORPUS_REEL=<racine>. Le paquet tiers n est "
                    "PAS dans ce depot et n y entrera pas.",
                "exige": bool(arguments.exiger_corpus_reel),
            })

        # ---- exécution ----------------------------------------------
        lignes = []
        print("%-34s %-10s %-10s %-10s %-6s %s"
              % ("cas", "attendu", "python", "rust", "conc.", "corpus"))
        print("-" * 104)
        for c in cas:
            strict = False
            py = lancer_python(c["chemin"], sortie, strict)
            rs = lancer_rust(arguments.binaire, c["chemin"], sortie, strict)
            div, prof = comparer(py, rs)
            vpy = (py["rapport"] or {}).get("verdict") or "AUCUN_RAPPORT"
            vrs = (rs["rapport"] or {}).get("verdict") or "AUCUN_RAPPORT"
            equivalent = not div
            attendu = c["attendu"]
            if attendu == "DIVERGENCE_ATTENDUE":
                conforme = not equivalent
            else:
                conforme = equivalent and vpy == attendu and vrs == attendu
            emp = c["chemin"].is_dir() and sha_arbre(c["chemin"]) or (
                sha(c["chemin"]) if c["chemin"].is_file() else None)
            lignes.append({
                "id": c["id"], "description": c["description"],
                "corpus": c["corpus"], "origine": c["origine"],
                "sha256": emp,
                "attendu": attendu,
                "python": {"verdict": vpy, "code": py["code"]},
                "rust": {"verdict": vrs, "code": rs["code"]},
                "equivalent": equivalent,
                "conforme_a_l_attente": conforme,
                "divergences_de_conclusion": div,
                "differences_de_profondeur_de_refus": prof,
            })
            print("%-34s %-10s %-10s %-10s %-6s %s"
                  % (c["id"][:34], attendu, "%s/%d" % (vpy[:7], py["code"]),
                     "%s/%d" % (vrs[:7], rs["code"]),
                     "OUI" if equivalent else "NON", c["corpus"]))
            for d in div:
                print("      DIVERGENCE : %s" % json.dumps(d, ensure_ascii=False)[:150])
            for d in prof:
                print("      profondeur : %s" % json.dumps(d, ensure_ascii=False)[:150])

        total = len(lignes)
        equiv = sum(1 for l in lignes if l["equivalent"])
        conf = sum(1 for l in lignes if l["conforme_a_l_attente"])
        attendues = [l for l in lignes if l["attendu"] == "DIVERGENCE_ATTENDUE"]
        inattendues = [l for l in lignes
                       if not l["equivalent"] and l["attendu"] != "DIVERGENCE_ATTENDUE"]

        # ---- LES CAS DECLARES ET NON EXECUTES, AVANT LES TOTAUX ---------
        #
        # Ils sont imprimes AVANT les decomptes, et non en note de bas de
        # page : un lecteur qui ne lit que les trois premieres lignes doit
        # deja savoir qu une mesure manque.
        if non_executes:
            print()
            print("!" * 72)
            print("CAS DECLARES ET **NON EXECUTES** : %d" % len(non_executes))
            print("Ils ne sont comptes NI en succes, NI en echec : ils ne sont")
            print("pas mesures. Les decomptes ci-dessous ne les couvrent pas.")
            for n in non_executes:
                print("  - %-22s [%s] corpus %s" % (n["id"], n["statut"], n["corpus"]))
                print("      attendu si execute : %s" % n["attendu"])
                print("      raison             : %s" % n["raison"])
                print("      chemin attendu     : %s" % n["chemin_attendu"])
                print("      designe par        : %s" % n["designe_par"])
                print("      pour le fournir    : %s" % n["comment_le_fournir"])
            print("!" * 72)

        print()
        print("cas DECLARES                        : %d" % (total + len(non_executes)))
        print("cas EXECUTES                        : %d" % total)
        print("cas NON EXECUTES                    : %d%s"
              % (len(non_executes),
                 "" if not non_executes
                 else "   (%s)" % ", ".join(n["id"] for n in non_executes)))
        print("equivalents Python/Rust             : %d / %d" % (equiv, total))
        print("conformes a l attente ECRITE d avance: %d / %d" % (conf, total))
        if non_executes:
            print("                                      ^ sur les cas EXECUTES"
                  " seulement")
        prof_total = sum(len(l["differences_de_profondeur_de_refus"]) for l in lignes)
        print("divergences ATTENDUES et observees  : %d" % len(attendues))
        print("divergences INATTENDUES             : %d" % len(inattendues))
        print("differences de PROFONDEUR de refus  : %d (consignees, verdict identique)"
              % prof_total)
        if inattendues:
            print()
            print("A INSTRUIRE -- aucune n est corrigee automatiquement :")
            for l in inattendues:
                print("  %s : %s" % (l["id"],
                                      json.dumps(l["divergences_de_conclusion"],
                                                 ensure_ascii=False)[:200]))

        if arguments.json:
            arguments.json.parent.mkdir(parents=True, exist_ok=True)
            arguments.json.write_text(
                json.dumps({
                    "politique_de_comparaison": {
                        "axes_de_conclusion_jamais_assouplis": [
                            "verdict", "code_de_sortie",
                            "empreinte recalculee sur l INTERSECTION des artefacts lus",
                            "classe d erreur (refus de part et d autre)",
                            "etat de la ligne signatures si les DEUX l ont atteinte",
                        ],
                        "consigne_mais_non_divergent": [
                            "profondeur de refus : un verificateur refuse plus tot",
                        ],
                        "non_compare": [
                            "nombre et ordre des lignes de rapport",
                            "prose des messages",
                            "decomptes PASS/FAIL/NOT TESTED",
                        ],
                    },
                    # `total` garde son sens historique : les cas EXECUTES.
                    # Un consommateur deja ecrit ne change donc pas de
                    # lecture. Les cas NON EXECUTES sont ajoutes a part, et
                    # ne sont jamais additionnes aux succes.
                    "total": total, "equivalents": equiv,
                    "conformes": conf,
                    "cas_declares": total + len(non_executes),
                    "cas_executes": total,
                    "cas_non_executes": len(non_executes),
                    "divergences_attendues": len(attendues),
                    "divergences_inattendues": len(inattendues),
                    "differences_de_profondeur": prof_total,
                    "corpus_reel_exige": bool(arguments.exiger_corpus_reel),
                    "cas": lignes,
                    "non_executes": non_executes,
                }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print()
            print("rapport machine : %s" % arguments.json)

        # ---- LE CODE DE SORTIE -------------------------------------------
        #
        # Deux causes d echec, et une seule asymetrie assumee :
        #
        #   - une divergence INATTENDUE echoue partout. Inchange ;
        #   - un corpus reel ABSENT echoue seulement si l environnement a
        #     DECLARE l exiger. La CI publique n est pas censee detenir un
        #     materiau confidentiel : la faire rougir pour cela serait la
        #     punir de respecter la confidentialite. Mais un environnement
        #     de qualification PRIVEE qui pose `--exiger-corpus-reel` et ne
        #     trouve rien doit s arreter net, sinon il rendrait un rapport
        #     muet sur la seule mesure qui l interessait.
        if arguments.exiger_corpus_reel and non_executes:
            print()
            print("ECHEC : `--exiger-corpus-reel` est pose, et %d cas reel(s) "
                  "n ont PAS ete executes." % len(non_executes))
            print("        Cet environnement se declare capable de les mesurer ;")
            print("        il ne les a pas mesures. Rien n est conclu a leur sujet.")
            return 4
        return 1 if inattendues else 0
    finally:
        shutil.rmtree(travail, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
