# -*- coding: utf-8 -*-
"""Construction du paquet — le seul role de ce fichier est de NE PAS DUPLIQUER.

Les verificateurs vivent dans `verifier/`, republies a l octet depuis le
moteur Evidence. Les recopier dans `neomundi_evidence/` donnerait deux
exemplaires dans le depot, qui divergeraient un jour : c est exactement ce
que ce projet refuse ailleurs, et il n y a pas de raison de l accepter ici.

Donc ils sont materialises **a la construction**, dans la roue, sous
`neomundi_evidence/_verifier/`. Une seule source dans le depot, un paquet
autonome a l arrivee.

Les deux chemins de construction sont couverts :

  * depuis un clone      -- `verifier/` est la, le crochet copie ;
  * depuis une archive   -- `MANIFEST.in` embarque `verifier/*.py` dans la
    source                  distribution, donc le crochet retrouve ses
                            fichiers et se comporte a l identique.

⚠ Le crochet ECHOUE BRUYAMMENT si un fichier attendu manque. Une roue
construite sans verificateur s installerait sans erreur et ne verifierait
rien : c est precisement le genre de silence que ce paquet existe pour
eviter.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py

RACINE = Path(__file__).resolve().parent

#: Ce qui est materialise dans la roue, et depuis ou. Chemins relatifs a
#: `verifier/` cote source, a `neomundi_evidence/_verifier/` cote paquet.
A_EMBARQUER = (
    "verify.py",
    "verify_attestation.py",
    "canonical.py",
    "i18n.py",
    "timestamp.py",
    "adapters/ingest.py",
)

SOURCE = "verifier"
CIBLE = Path("neomundi_evidence") / "_verifier"


class build_py(_build_py):
    """`build_py` qui materialise les verificateurs avant d emballer."""

    def run(self) -> None:  # noqa: D102
        self._materialiser_le_verificateur()
        super().run()

    def _materialiser_le_verificateur(self) -> None:
        source = RACINE / SOURCE
        if not source.is_dir():
            raise SystemExit(
                f"construction impossible : le repertoire `{SOURCE}/` est absent.\n"
                f"Les verificateurs ne sont pas recopies dans le depot ; ils sont "
                f"lus ici a la construction. Construire depuis la racine du depot, "
                f"ou depuis une archive produite par `python -m build --sdist`."
            )

        cible = RACINE / CIBLE
        cible.mkdir(parents=True, exist_ok=True)

        manquants = []
        copies = 0
        for relatif in A_EMBARQUER:
            origine = source / relatif
            if not origine.is_file():
                manquants.append(relatif)
                continue
            destination = cible / relatif
            destination.parent.mkdir(parents=True, exist_ok=True)
            # `copyfile`, pas `copy2` : on veut les octets, pas les
            # metadonnees de l hote qui construit.
            shutil.copyfile(origine, destination)
            copies += 1

        if manquants:
            raise SystemExit(
                "construction interrompue : verificateur(s) introuvable(s) sous "
                f"`{SOURCE}/` -- " + ", ".join(manquants) + ".\n"
                "Une roue construite sans eux s installerait sans erreur et ne "
                "verifierait rien."
            )

        # `adapters/` doit etre importable comme sous-paquet de donnees : les
        # outils sont lances en sous-processus, mais `ingest.py` est atteint
        # par son chemin, donc le repertoire doit exister dans la roue.
        print(f"[build] {copies} verificateur(s) materialise(s) dans {CIBLE}")


setup(
    cmdclass={"build_py": build_py},
    # Les fichiers materialises ne sont pas dans l arbre versionne : ils sont
    # declares comme donnees du paquet pour que `build_py` les emballe.
    package_data={
        "neomundi_evidence": [
            "_verifier/*.py",
            "_verifier/adapters/*.py",
            "LISEZ-MOI-PYPI.md",
        ]
    },
)
