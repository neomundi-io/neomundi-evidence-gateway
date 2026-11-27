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
#: ⚠ Mettre a jour ce numero NE PUBLIE RIEN. La publication passe par
#: `workflow_dispatch` sur `publish.yml`, avec confirmation tapee et
#: environnement GitHub. Tant qu elle n a pas eu lieu, l index sert
#: encore la 0.1.0, et toute page qui annoncerait le contraire serait
#: fausse -- PyPI est immuable, une page perimee ne se retire pas.
__version__ = "0.2.0"

#: Version du corpus de conformite dont les verificateurs embarques sont
#: issus, et revision du protocole qu ils implementent. Ce sont les deux
#: chiffres a citer : la version du paquet ne dit rien du contrat.
VERSION_DU_CORPUS = "1.3.0"
REVISION_DU_PROTOCOLE = "1.0.0-rc.1"
