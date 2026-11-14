# -*- coding: utf-8 -*-
"""Localisation et invocation du moteur NeoMundi Evidence.

Ce module ne verifie RIEN. Il ne lit pas une archive, ne calcule pas une
empreinte, ne derive pas un verdict. Il sait trois choses, et seulement
trois :

  1. ou se trouve le moteur (un repertoire, qui peut etre prive) ;
  2. si le point d entree demande y existe ;
  3. comment lancer ce point d entree et recuperer son code de sortie.

C est deliberement peu. Un gateway qui contiendrait une seconde
implementation de la verification serait un second verificateur, avec sa
propre surface de bug et ses propres divergences : exactement ce que la
specification Evidence demande d eviter. Voir `docs/INTERFACE.md`.

Bibliotheque standard seule.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

#: Les points d entree du moteur, par operation du gateway.
#: Ce sont les noms de fichiers REELS du depot Evidence, pas une invention.
POINTS_D_ENTREE = {
    "verify": "verify.py",
    "attestation": "verify_attestation.py",
}

#: Variables d environnement reconnues.
VAR_MOTEUR = "EVIDENCE_ENGINE_HOME"
VAR_PYTHON = "EVIDENCE_PYTHON"
VAR_REVISION = "EVIDENCE_ENGINE_REVISION"

#: Delai maximal d une invocation, en secondes. Un moteur qui pend n est
#: pas un moteur qui refuse : les deux doivent etre distingues.
DELAI_PAR_DEFAUT = 300


class MoteurIndisponible(Exception):
    """Le moteur n a pas pu etre atteint. AUCUNE verification n a eu lieu."""

    def __init__(self, raison: str, detail: str) -> None:
        super().__init__(detail)
        self.raison = raison
        self.detail = detail


def racine_du_moteur(explicite: str | None = None) -> Path | None:
    """Rend la racine declaree du moteur, ou None si rien n est declare.

    Ordre de precedence : argument explicite, puis EVIDENCE_ENGINE_HOME.
    Il n y a volontairement AUCUNE valeur par defaut : deviner un chemin
    ferait passer pour une panne de configuration ce qui est une absence de
    configuration.
    """
    valeur = explicite or os.environ.get(VAR_MOTEUR) or ""
    valeur = valeur.strip()
    if not valeur:
        return None
    return Path(valeur).expanduser()


def interpreteur() -> str:
    """Rend l interpreteur Python a employer pour le moteur."""
    return os.environ.get(VAR_PYTHON) or sys.executable


def revision_declaree() -> str | None:
    """Rend la revision du moteur telle que DECLAREE par l operateur.

    Declaree, donc non verifiee : ce gateway ne lance pas `git`, et n a
    aucun moyen d etablir qu un repertoire correspond a un commit. La
    valeur est republiee avec cette reserve dans la reponse.
    """
    valeur = (os.environ.get(VAR_REVISION) or "").strip()
    return valeur or None


def sonder(explicite: str | None = None) -> dict:
    """Rend l etat du moteur, sans rien lui demander de verifier."""
    racine = racine_du_moteur(explicite)
    etat: dict = {
        "declare": racine is not None,
        "racine_presente": False,
        "points_d_entree": {},
        "manquants": [],
        "interpreteur": interpreteur(),
        "revision_declaree": revision_declaree(),
        "corpus_de_conformite_declare": None,
        "disponible": False,
    }
    if racine is None:
        etat["raison"] = "engine_not_declared"
        etat["detail"] = (
            f"aucune racine de moteur declaree : poser {VAR_MOTEUR} ou passer "
            "--engine-home. Sans moteur, ce gateway ne peut produire aucun verdict."
        )
        return etat

    etat["racine_presente"] = racine.is_dir()
    if not etat["racine_presente"]:
        etat["raison"] = "engine_home_absent"
        etat["detail"] = f"la racine declaree n est pas un repertoire lisible : {racine}"
        return etat

    for operation, fichier in sorted(POINTS_D_ENTREE.items()):
        present = (racine / fichier).is_file()
        etat["points_d_entree"][operation] = {"fichier": fichier, "present": present}
        if not present:
            etat["manquants"].append(fichier)

    version = racine / "conformance" / "VERSION"
    if version.is_file():
        try:
            etat["corpus_de_conformite_declare"] = version.read_text(
                encoding="utf-8"
            ).strip()
        except OSError:
            etat["corpus_de_conformite_declare"] = None

    etat["disponible"] = not etat["manquants"]
    if not etat["disponible"]:
        etat["raison"] = "engine_entrypoint_missing"
        etat["detail"] = (
            "la racine existe mais il y manque : " + ", ".join(etat["manquants"])
        )
    return etat


def exiger(operation: str, explicite: str | None = None) -> tuple[Path, dict]:
    """Rend la racine du moteur pour une operation, ou leve MoteurIndisponible."""
    etat = sonder(explicite)
    if not etat["declare"] or not etat["racine_presente"]:
        raise MoteurIndisponible(etat["raison"], etat["detail"])
    fichier = POINTS_D_ENTREE.get(operation)
    if fichier is None:
        raise MoteurIndisponible(
            "unknown_operation", f"operation inconnue du gateway : {operation!r}"
        )
    if not etat["points_d_entree"][operation]["present"]:
        raise MoteurIndisponible(
            "engine_entrypoint_missing",
            f"le point d entree {fichier} est absent de la racine du moteur",
        )
    racine = racine_du_moteur(explicite)
    assert racine is not None  # garanti par etat["declare"] ci-dessus
    return racine, etat


def invoquer(
    racine: Path,
    operation: str,
    arguments: list[str],
    delai: int = DELAI_PAR_DEFAUT,
) -> dict:
    """Lance un point d entree du moteur et rend ce qu il a produit.

    Rend un dictionnaire brut : code de sortie, sortie standard, sortie
    d erreur. Aucune interpretation. Le code de sortie du moteur est celui
    du moteur -- ce module ne le traduit pas.
    """
    fichier = POINTS_D_ENTREE[operation]
    commande = [interpreteur(), fichier] + arguments
    try:
        acheve = subprocess.run(  # noqa: S603 -- commande construite ici, pas par l appelant
            commande,
            cwd=str(racine),
            capture_output=True,
            timeout=delai,
        )
    except subprocess.TimeoutExpired as exc:
        raise MoteurIndisponible(
            "engine_timeout",
            f"le moteur n a pas rendu la main en {delai} s : {fichier}",
        ) from exc
    except OSError as exc:
        raise MoteurIndisponible(
            "engine_not_executable",
            f"impossible de lancer {commande[0]} : {exc}",
        ) from exc

    return {
        "commande": [fichier] + arguments,
        "code_de_sortie": acheve.returncode,
        "sortie_standard": acheve.stdout.decode("utf-8", errors="replace"),
        "sortie_erreur": acheve.stderr.decode("utf-8", errors="replace"),
    }


def lire_rapport(chemin: Path) -> dict:
    """Lit le rapport machine ecrit par le moteur.

    Leve MoteurIndisponible si le fichier manque ou n est pas du JSON : un
    rapport illisible ne vaut pas un verdict, et ce gateway ne doit jamais
    reconstituer un verdict depuis la sortie texte.
    """
    if not chemin.is_file():
        raise MoteurIndisponible(
            "engine_report_absent",
            "le moteur n a ecrit aucun rapport machine : aucun verdict ne peut etre republie",
        )
    try:
        texte = chemin.read_text(encoding="utf-8")
    except OSError as exc:
        raise MoteurIndisponible(
            "engine_report_unreadable", f"rapport illisible : {exc}"
        ) from exc
    try:
        charge = json.loads(texte)
    except json.JSONDecodeError as exc:
        raise MoteurIndisponible(
            "engine_report_unreadable", f"rapport non conforme a JSON : {exc}"
        ) from exc
    if not isinstance(charge, dict):
        raise MoteurIndisponible(
            "engine_report_unreadable",
            "le rapport du moteur n est pas un objet JSON",
        )
    return charge
