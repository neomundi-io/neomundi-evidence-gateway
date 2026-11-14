# -*- coding: utf-8 -*-
"""`neomundi-evidence` — front-end en ligne de commande du verificateur public.

CE QUE CE MODULE FAIT, ET NE FAIT PAS
-------------------------------------

Il ne verifie rien. Il localise le verificateur embarque dans le paquet, le
lance en SOUS-PROCESSUS, et transmet sa sortie et son code de sortie
**verbatim**. C est la meme discipline que le gateway : un front-end qui
reimplementerait un controle serait un second verificateur, avec ses propres
divergences.

Consequence utile : le verdict que vous lisez est, a l octet, celui que rend
un appel direct a `verify.py`. `tests/test_paquet_pip.py` le mesure.

CODES DE SORTIE
---------------

  0  le verificateur a tourne, aucun controle n a echoue
  1  le verificateur a tourne, au moins un controle a ECHOUE
  2  le verificateur a tourne, mode strict, une garantie requise n est pas
     demontree
  3  AUCUNE verification n a eu lieu -- le verificateur embarque est
     introuvable ou illisible (installation abimee)
  4  AUCUNE verification n a eu lieu -- emploi incorrect (fichier absent,
     option manquante)

0, 1 et 2 sont ceux du verificateur, transmis sans traduction. 3 et 4 sont
propres a ce front-end, et c est pour cela qu ils existent : sans eux, « rien
n a echoue » et « rien n a tourne » rendraient le meme 0.

RESEAU ET CLES
--------------

Aucun appel reseau, aucune cle d API NeoMundi, aucun acces au moteur prive.
Les quatre operations sont integralement hors ligne.

Bibliotheque standard seule. `cryptography` et `opentimestamps` sont
OPTIONNELLES : sans elles, les lignes correspondantes rendent `NOT TESTED` --
jamais `PASS`.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from . import REVISION_DU_PROTOCOLE, VERSION_DU_CORPUS, __version__

#: Repertoire des verificateurs embarques, relatif a ce module.
_EMBARQUE = "_verifier"

#: Les outils du verificateur, par operation exposee. Ce sont les noms de
#: fichiers REELS, republies a l octet depuis le depot du moteur.
OUTILS = {
    "verify": "verify.py",
    "attest": "verify_attestation.py",
    "timestamp": "timestamp.py",
    "submission": os.path.join("adapters", "ingest.py"),
}

CODE_VERIFICATEUR_ABSENT = 3
CODE_EMPLOI_INCORRECT = 4

#: Dependances optionnelles, et ce que leur absence coute. Affiche par
#: `neomundi-evidence doctor`.
OPTIONNELLES = {
    "cryptography": (
        "verification des signatures Ed25519/JWS. Absente, `attest` rend "
        "NOT TESTED sur la signature et la confiance -- jamais PASS."
    ),
    "opentimestamps": (
        "lecture de l arbre d attestations d une preuve `.ots`. Absente, "
        "`timestamp` lit toujours la LIAISON (sans dependance) mais rend "
        "NOT TESTED sur l etat PENDING/BITCOIN."
    ),
}


def racine_du_verificateur() -> Path:
    """Rend le repertoire des verificateurs embarques."""
    return Path(__file__).resolve().parent / _EMBARQUE


def _outil(operation: str) -> Path:
    return racine_du_verificateur() / OUTILS[operation]


def _exiger(operation: str) -> Path | None:
    """Rend le chemin de l outil, ou None en l imprimant sur stderr."""
    chemin = _outil(operation)
    if chemin.is_file():
        return chemin
    print(
        f"[neomundi-evidence] le verificateur embarque est introuvable : "
        f"{OUTILS[operation]} attendu sous {racine_du_verificateur()}.\n"
        f"[neomundi-evidence] AUCUNE verification n a eu lieu. "
        f"Reinstaller le paquet.",
        file=sys.stderr,
    )
    return None


def _fichier_present(chemin: str, intitule: str) -> bool:
    if Path(chemin).exists():
        return True
    print(
        f"[neomundi-evidence] {intitule} introuvable : {chemin}\n"
        f"[neomundi-evidence] AUCUNE verification n a eu lieu.",
        file=sys.stderr,
    )
    return False


def _lancer(outil: Path, arguments: list[str]) -> int:
    """Lance un outil du verificateur et transmet tout verbatim.

    La sortie n est NI capturee NI reformatee : elle va directement au
    terminal de l appelant. Le code de sortie est celui de l outil.
    """
    try:
        acheve = subprocess.run(  # noqa: S603 -- commande construite ici
            [sys.executable, "-B", str(outil), *arguments],
            cwd=str(outil.parent if outil.parent.name != "adapters"
                    else outil.parent.parent),
        )
    except OSError as exc:
        print(
            f"[neomundi-evidence] impossible de lancer le verificateur : {exc}\n"
            f"[neomundi-evidence] AUCUNE verification n a eu lieu.",
            file=sys.stderr,
        )
        return CODE_VERIFICATEUR_ABSENT
    return acheve.returncode


# ---------------------------------------------------------------------------
# Les quatre operations.
# ---------------------------------------------------------------------------


def commande_verify(args: argparse.Namespace) -> int:
    outil = _exiger("verify")
    if outil is None:
        return CODE_VERIFICATEUR_ABSENT
    if not _fichier_present(args.archive, "archive"):
        return CODE_EMPLOI_INCORRECT
    arguments = [str(Path(args.archive).resolve())]
    if args.corpus:
        if not _fichier_present(args.corpus, "corpus"):
            return CODE_EMPLOI_INCORRECT
        arguments += ["--corpus", str(Path(args.corpus).resolve())]
    if args.json:
        arguments += ["--json", str(Path(args.json).resolve())]
    arguments += ["--lang", args.lang]
    if args.strict:
        arguments.append("--strict")
    return _lancer(outil, arguments)


def commande_attest(args: argparse.Namespace) -> int:
    outil = _exiger("attest")
    if outil is None:
        return CODE_VERIFICATEUR_ABSENT
    for chemin, intitule in ((args.attestation, "attestation"),
                             (args.archive, "archive"),
                             (args.trust_store, "magasin de confiance")):
        if not _fichier_present(chemin, intitule):
            return CODE_EMPLOI_INCORRECT
    arguments = [
        str(Path(args.attestation).resolve()),
        "--archive", str(Path(args.archive).resolve()),
        "--trust-store", str(Path(args.trust_store).resolve()),
    ]
    if args.store_digest:
        arguments += ["--store-digest", args.store_digest]
    if args.allow_test_keys:
        arguments.append("--allow-test-keys")
    if args.json:
        arguments += ["--json", str(Path(args.json).resolve())]
    arguments += ["--lang", args.lang]
    if args.strict:
        arguments.append("--strict")
    return _lancer(outil, arguments)


def commande_timestamp(args: argparse.Namespace) -> int:
    """Verifie une preuve OpenTimestamps detachee. HORS LIGNE.

    ⚠ Cette commande n expose QUE la sous-commande `verify` de l outil
    d horodatage. `stamp` et `upgrade`, qui soumettent une empreinte a des
    calendriers publics, ne sont PAS exposees : ce paquet verifie, il ne
    produit pas.
    """
    outil = _exiger("timestamp")
    if outil is None:
        return CODE_VERIFICATEUR_ABSENT
    for chemin, intitule in ((args.preuve, "preuve .ots"),
                             (args.subject, "sujet")):
        if not _fichier_present(chemin, intitule):
            return CODE_EMPLOI_INCORRECT
    arguments = [
        "verify",
        str(Path(args.preuve).resolve()),
        "--subject", str(Path(args.subject).resolve()),
    ]
    if args.descriptor:
        if not _fichier_present(args.descriptor, "descripteur"):
            return CODE_EMPLOI_INCORRECT
        arguments += ["--descriptor", str(Path(args.descriptor).resolve())]
    if args.json:
        arguments += ["--json", str(Path(args.json).resolve())]
    arguments += ["--lang", args.lang]
    if args.strict:
        arguments.append("--strict")
    return _lancer(outil, arguments)


def commande_submission(args: argparse.Namespace) -> int:
    outil = _exiger("submission")
    if outil is None:
        return CODE_VERIFICATEUR_ABSENT
    if not _fichier_present(args.paquet, "paquet de soumission"):
        return CODE_EMPLOI_INCORRECT
    arguments = [str(Path(args.paquet).resolve())]
    if args.trust_store:
        if not _fichier_present(args.trust_store, "magasin de confiance"):
            return CODE_EMPLOI_INCORRECT
        arguments += ["--trust-store", str(Path(args.trust_store).resolve())]
    if args.out:
        arguments += ["--out", str(Path(args.out).resolve())]
    arguments += ["--lang", args.lang]
    if args.strict:
        arguments.append("--strict")
    return _lancer(outil, arguments)


# ---------------------------------------------------------------------------
# Diagnostic.
# ---------------------------------------------------------------------------


def commande_doctor(args: argparse.Namespace) -> int:
    """Dit ce qui est installe, ce qui manque, et ce que l absence coute."""
    racine = racine_du_verificateur()
    print(f"neomundi-evidence {__version__}")
    print(f"  protocole  : evidence-protocol/1, revision {REVISION_DU_PROTOCOLE}")
    print(f"  corpus     : {VERSION_DU_CORPUS} (les verificateurs en sont issus)")
    print(f"  python     : {sys.version.split()[0]}")
    print(f"  verificateur embarque : {racine}")

    manquants = []
    for operation, fichier in sorted(OUTILS.items()):
        present = (racine / fichier).is_file()
        print(f"    {'OK     ' if present else 'ABSENT '} {operation:11} {fichier}")
        if not present:
            manquants.append(fichier)

    print("  dependances OPTIONNELLES :")
    for nom, effet in sorted(OPTIONNELLES.items()):
        try:
            __import__(nom)
            etat = "presente"
        except ImportError:
            etat = "ABSENTE "
        print(f"    {etat} {nom}")
        if etat.strip() == "ABSENTE":
            print(f"             -> {effet}")

    print("")
    print("  Aucun appel reseau, aucune cle d API, aucun acces a un depot prive.")
    if manquants:
        print("")
        print("  INSTALLATION ABIMEE : " + ", ".join(manquants))
        return CODE_VERIFICATEUR_ABSENT
    return 0


def construire_analyseur() -> argparse.ArgumentParser:
    analyseur = argparse.ArgumentParser(
        prog="neomundi-evidence",
        description=(
            "Verificateur public NeoMundi Evidence. Hors ligne, sans cle "
            "d API. Ne verifie rien lui-meme : il transmet le verdict du "
            "verificateur qu il embarque."
        ),
        epilog=(
            "Codes de sortie : 0 aucun echec · 1 un controle a ECHOUE · "
            "2 mode strict, garantie requise non demontree · "
            "3 verificateur introuvable (AUCUNE verification) · "
            "4 emploi incorrect (AUCUNE verification)."
        ),
    )
    analyseur.add_argument("--version", action="version",
                           version=f"neomundi-evidence {__version__} "
                                   f"(protocole {REVISION_DU_PROTOCOLE}, "
                                   f"corpus {VERSION_DU_CORPUS})")
    sous = analyseur.add_subparsers(dest="commande", required=True)

    def communs(p: argparse.ArgumentParser) -> None:
        p.add_argument("--strict", action="store_true",
                       help="exiger les garanties requises ; ne change aucun verdict, "
                            "seulement le code de sortie")
        p.add_argument("--json", default=None, metavar="FICHIER",
                       help="ecrire aussi le rapport machine")
        p.add_argument("--lang", default="fr", choices=("fr", "en"))

    p = sous.add_parser("verify", help="verifier une archive Evidence")
    p.add_argument("archive")
    p.add_argument("--corpus", default=None, metavar="REPERTOIRE",
                   help="entrees rejouees ; les fournir rend eprouvable "
                        "l empreinte des entrees")
    communs(p)
    p.set_defaults(fonction=commande_verify)

    p = sous.add_parser("attest", help="verifier une attestation Ed25519/JWS detachee")
    p.add_argument("attestation")
    p.add_argument("--archive", required=True)
    p.add_argument("--trust-store", required=True,
                   help="obligatoire : sans magasin, aucune identite n est etablie")
    p.add_argument("--store-digest", default=None,
                   help="empreinte du magasin, obtenue par un AUTRE canal")
    p.add_argument("--allow-test-keys", action="store_true",
                   help="accepter une cle de statut `test`, qui n accorde "
                        "aucune attestation")
    communs(p)
    p.set_defaults(fonction=commande_attest)

    p = sous.add_parser("timestamp",
                        help="verifier une preuve OpenTimestamps detachee (hors ligne)")
    p.add_argument("preuve", metavar="PREUVE.ots")
    p.add_argument("--subject", required=True,
                   help="le fichier sur lequel la preuve doit s engager")
    p.add_argument("--descriptor", default=None,
                   help="descripteur de liaison, s il existe")
    communs(p)
    p.set_defaults(fonction=commande_timestamp)

    p = sous.add_parser("submission", help="verifier un paquet de soumission tiers")
    p.add_argument("paquet")
    p.add_argument("--trust-store", default=None)
    p.add_argument("--out", default=None, metavar="FICHIER")
    communs(p)
    p.set_defaults(fonction=commande_submission)

    p = sous.add_parser("doctor",
                        help="ce qui est installe, ce qui manque, et ce que ca coute")
    p.set_defaults(fonction=commande_doctor)

    return analyseur


def main(argv: list[str] | None = None) -> int:
    args = construire_analyseur().parse_args(argv)
    return int(args.fonction(args))


if __name__ == "__main__":
    sys.exit(main())
