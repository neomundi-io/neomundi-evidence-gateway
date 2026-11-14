# -*- coding: utf-8 -*-
"""Ce gateway ne duplique pas le moteur. Cette suite le MESURE.

« Ne pas dupliquer la logique de verification » est facile a ecrire dans un
README et impossible a verifier en le lisant. Trois epreuves ici :

  A. aucune primitive de verification n est importee par le gateway --
     ni empreinte, ni ZIP, ni inflation. Un gateway qui en aurait besoin
     serait en train de refaire le travail du moteur ;

  B. aucun vocabulaire de verdict n est FABRIQUE : les etats PASS / FAIL /
     NOT TESTED et le verdict n apparaissent pas comme des valeurs
     construites par le gateway ;

  C. le verdict republie est, champ par champ, celui qu un appel DIRECT au
     moteur produit sur le meme artefact. C est l epreuve la plus forte :
     si le gateway calculait quoi que ce soit, cette egalite casserait.

L epreuve C exige le moteur. A et B non.

Emploi :
    python tests/test_no_verification_logic.py
    EVIDENCE_ENGINE_HOME=<racine> python tests/test_no_verification_logic.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import gateway  # noqa: E402
import engine  # noqa: E402

#: Modules que le moteur emploie pour verifier, et que ce gateway ne doit
#: jamais importer. `zipfile` est permis dans les SUITES (elles fabriquent
#: un artefact altere) mais pas dans le produit.
MODULES_INTERDITS = ("hashlib", "zlib", "zipfile", "hmac", "binascii", "base64")

#: Appels qui trahiraient un calcul de verification.
APPELS_INTERDITS = (
    r"\bsha256\s*\(",
    r"\bhashlib\b",
    r"\bZipFile\b",
    r"\bdecompressobj\b",
    r"\bcrc32\b",
)

SOURCES_DU_PRODUIT = ("gateway.py", "engine.py")

BILAN: list[tuple[str, str, str]] = []


def noter(etat: str, intitule: str, detail: str = "") -> None:
    BILAN.append((etat, intitule, detail))
    print(f"[{etat:10}] {intitule}" + (f" - {detail}" if detail else ""))


def epreuve_a_imports() -> None:
    for nom in SOURCES_DU_PRODUIT:
        texte = (RACINE / nom).read_text(encoding="utf-8")
        trouves = []
        for module in MODULES_INTERDITS:
            motif = rf"^\s*(?:import\s+{module}\b|from\s+{module}\b)"
            if re.search(motif, texte, flags=re.MULTILINE):
                trouves.append(module)
        if trouves:
            noter("FAIL", f"A : {nom} n importe aucune primitive de verification",
                  "importe : " + ", ".join(trouves))
        else:
            noter("PASS", f"A : {nom} n importe aucune primitive de verification",
                  f"{len(MODULES_INTERDITS)} module(s) confronte(s)")


def epreuve_a_appels() -> None:
    for nom in SOURCES_DU_PRODUIT:
        texte = (RACINE / nom).read_text(encoding="utf-8")
        # Les lignes de commentaire et de docstring parlent de verification :
        # c est leur role. Seul le code est confronte.
        code = "\n".join(
            ligne for ligne in texte.splitlines()
            if not ligne.lstrip().startswith("#")
        )
        trouves = [motif for motif in APPELS_INTERDITS if re.search(motif, code)]
        if trouves:
            noter("FAIL", f"A : {nom} n appelle aucune primitive de verification",
                  "motifs trouves : " + ", ".join(trouves))
        else:
            noter("PASS", f"A : {nom} n appelle aucune primitive de verification",
                  f"{len(APPELS_INTERDITS)} motif(s) confronte(s)")


def epreuve_b_vocabulaire() -> None:
    """Le gateway ne doit pas FABRIQUER d etat de controle.

    Il republie `counts`, `verdict` et les lignes de controle tels que le
    moteur les a ecrits. Trouver la chaine `"PASS"` comme valeur assignee
    dans le produit signifierait qu il en fabrique une.
    """
    for nom in SOURCES_DU_PRODUIT:
        texte = (RACINE / nom).read_text(encoding="utf-8")
        code = "\n".join(
            ligne for ligne in texte.splitlines()
            if not ligne.lstrip().startswith("#")
        )
        # On cherche les litteraux d etat, hors docstring : une occurrence
        # dans une docstring est de la prose, pas une valeur.
        sans_docstring = re.sub(r'""".*?"""', "", code, flags=re.DOTALL)
        suspects = re.findall(r'"(PASS|FAIL|NOT TESTED)"', sans_docstring)
        if suspects:
            noter("FAIL", f"B : {nom} ne fabrique aucun etat de controle",
                  "litteraux trouves : " + ", ".join(sorted(set(suspects))))
        else:
            noter("PASS", f"B : {nom} ne fabrique aucun etat de controle",
                  "aucun litteral PASS/FAIL/NOT TESTED en position de valeur")


def epreuve_c_egalite(moteur: Path) -> None:
    dossier = moteur / "examples" / "dossier-v1"
    archive = dossier / "NEOMUNDI_EVIDENCE_V1_DEMO.zip"
    corpus = dossier / "corpus"
    if not archive.is_file():
        noter("NOT TESTED", "C : le verdict est celui d un appel direct au moteur",
              "le moteur declare ne porte pas examples/dossier-v1")
        return

    with tempfile.TemporaryDirectory(prefix="nm-gw-direct-") as temporaire:
        direct = Path(temporaire) / "direct.json"
        acheve = subprocess.run(  # noqa: S603
            [engine.interpreteur(), "verify.py", str(archive),
             "--corpus", str(corpus), "--strict", "--lang", "fr",
             "--json", str(direct)],
            cwd=str(moteur), capture_output=True,
        )
        if not direct.is_file():
            noter("FAIL", "C : le verdict est celui d un appel direct au moteur",
                  "l appel direct n a produit aucun rapport")
            return
        rapport = json.loads(direct.read_text(encoding="utf-8"))
        code_direct = acheve.returncode

    requete = {
        "schema": gateway.CONTRAT_REQUETE,
        "operation": "verify",
        "artifact": {"name": "demo", "path": "examples/dossier-v1/NEOMUNDI_EVIDENCE_V1_DEMO.zip"},
        "inputs": {"corpus": "examples/dossier-v1/corpus"},
        "options": {"strict": True, "language": "fr"},
    }
    reponse = gateway.traiter(requete, moteur, str(moteur))
    verdict = reponse.get("verdict") or {}

    ecarts = []
    if verdict.get("value") != rapport.get("verdict"):
        ecarts.append(f"verdict {verdict.get('value')!r} != {rapport.get('verdict')!r}")
    if verdict.get("counts") != rapport.get("counts"):
        ecarts.append(f"counts {verdict.get('counts')} != {rapport.get('counts')}")
    if verdict.get("required_not_demonstrated") != rapport.get("required_not_demonstrated"):
        ecarts.append("required_not_demonstrated differe")
    if reponse.get("exit_code") != code_direct:
        ecarts.append(f"code de sortie {reponse.get('exit_code')} != {code_direct}")

    lignes_moteur = [
        (c.get("state"), c.get("control")) for c in rapport.get("controls") or []
    ]
    lignes_gateway = [
        (c.get("state"), c.get("control"))
        for c in (reponse.get("engine_report") or {}).get("controls") or []
    ]
    if lignes_moteur != lignes_gateway:
        ecarts.append(
            f"{len(lignes_gateway)} ligne(s) de controle republiee(s) pour "
            f"{len(lignes_moteur)} produite(s), ou dans un autre ordre"
        )

    if ecarts:
        noter("FAIL", "C : le verdict est celui d un appel direct au moteur",
              " ; ".join(ecarts))
    else:
        noter("PASS", "C : le verdict est celui d un appel direct au moteur",
              f"{len(lignes_moteur)} ligne(s) de controle identiques, "
              f"comptes identiques, code {code_direct} identique")


def main() -> int:
    epreuve_a_imports()
    epreuve_a_appels()
    epreuve_b_vocabulaire()

    moteur = engine.racine_du_moteur(None)
    if moteur is None or not (moteur / "verify.py").is_file():
        noter("NOT TESTED", "C : le verdict est celui d un appel direct au moteur",
              f"aucun moteur atteignable : poser {engine.VAR_MOTEUR}")
    else:
        epreuve_c_egalite(moteur)

    reussis = sum(1 for e, _, _ in BILAN if e == "PASS")
    echoues = sum(1 for e, _, _ in BILAN if e == "FAIL")
    non_eprouves = sum(1 for e, _, _ in BILAN if e == "NOT TESTED")
    print(f"\nBILAN : {reussis} PASS, {echoues} FAIL, {non_eprouves} NOT TESTED")
    return 1 if echoues else 0


if __name__ == "__main__":
    sys.exit(main())
