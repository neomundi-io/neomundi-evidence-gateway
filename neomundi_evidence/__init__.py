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
__version__ = "0.1.0"

#: Version du corpus de conformite dont les verificateurs embarques sont
#: issus, et revision du protocole qu ils implementent. Ce sont les deux
#: chiffres a citer : la version du paquet ne dit rien du contrat.
VERSION_DU_CORPUS = "1.3.0"
REVISION_DU_PROTOCOLE = "1.0.0-rc.1"
