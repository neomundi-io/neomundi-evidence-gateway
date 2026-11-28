# -*- coding: utf-8 -*-
"""NeoMundi Evidence — public verifier, installable by pip.

This package DISTRIBUTES the public Evidence verifiers; it does not
reimplement them. Every verdict, control line and exit code you see comes
from the verifier the package ships, invoked as a subprocess and passed
through verbatim.

    neomundi-evidence verify <archive.zip>

See `cli.py` for what that means in practice, and the project README for what
a verification does and does not establish.
"""

from __future__ import annotations

__all__ = ["__version__", "VERSION_DU_CORPUS", "REVISION_DU_PROTOCOLE"]

#: Version du paquet. Elle versionne la DISTRIBUTION, pas le protocole.
#:
#: 0.2.0 -- EVPACK-001. La 0.1.0 refusait toute archive
#: `station.export.campagne/4`, donc toute archive produite par la
#: Station depuis le 2026-11-25 : `controle_schema` rendait FAIL des le
#: premier controle. Mesure du 2026-11-27 sur une archive reelle :
#: `2 PASS, 1 FAIL, 0 NOT TESTED`, code 1.
#:
#: Cette version embarque aussi EVPACK-014 : le contrat de completude
#: ne comptait pas les membres de `/3` et `/4` qu il declare pourtant,
#: et devenait insatisfiable pour une archive portant une couverture.
#:
#: 🟢 PUBLIEE sur PyPI le 2026-11-27 a 23:10:50Z, 111 588 octets. Eprouvee
#: depuis l index dans un venv vierge : `18 PASS, 0 FAIL, 3 NOT TESTED`,
#: code 0, sur deux archives `/4` reelles. Le travail `interop` de la
#: Station est passe au vert sur LE MEME COMMIT, sans qu une ligne de code
#: change -- la preuve que l arete mesure l index, et non l accord des
#: depots entre eux.
#:
#: ⚠ Mettre a jour ce numero NE PUBLIE RIEN. La publication passe par
#: `workflow_dispatch` sur `publish.yml`, avec confirmation tapee et
#: environnement GitHub a relecteur requis. Tant qu elle n a pas eu lieu,
#: l index sert la version precedente, et toute page qui annoncerait le
#: contraire serait fausse -- PyPI est immuable, une page perimee ne se
#: retire pas.
#:
#: 🔴 EVPACK-022 -- l etape `testpypi` que ce depot recommande N EST PAS
#: OUTILLEE : le projet n existe pas sur TestPyPI et aucun editeur de
#: confiance n y est configure. La 0.2.0 a donc ete publiee SANS repetition
#: generale. A configurer avant la prochaine.
#:
#: 0.2.1 -- EVPACK-023. La 0.2.0 refusait toute archive dont une reponse
#: porte une liste markdown : le controle anti-formule lisait des LIGNES
#: PHYSIQUES et coupait sur `;`, donc il voyait des cellules la ou il n y
#: en avait pas. Mesure du 2026-11-27 sur un export REEL du registre de
#: production : 121 enregistrements CSV pour 13 172 lignes physiques, dont
#: 4 339 commencant par une amorce de formule -- et ZERO cellule fautive.
#: Le verificateur rendait FAIL sur une archive saine.
#:
#: 🔴 Une liste a tirets est ubiquitaire dans une reponse de modele :
#: presque toute archive portant de la prose reelle echouait. Un tiers en
#: concluait que l archive etait fautive -- l inverse exact de ce que ce
#: paquet existe pour etablir.
__version__ = "0.2.1"

#: Version du corpus de conformite dont les verificateurs embarques sont
#: issus, et revision du protocole qu ils implementent. Ce sont les deux
#: chiffres a citer : la version du paquet ne dit rien du contrat.
VERSION_DU_CORPUS = "1.3.0"
REVISION_DU_PROTOCOLE = "1.0.0-rc.1"
