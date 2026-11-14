# -*- coding: utf-8 -*-
"""Le magasin de confiance publie ici est une PREUVE, pas une copie decorative.

Ce depot republie `trust/trust-store.json` parce que le moteur Evidence est
prive et que son URL `raw.githubusercontent.com` ne repond plus. Une empreinte
seule ne remplace pas une preuve accessible : c est l artefact qui est publie.

Mais republier un artefact cree deux risques nouveaux, et cette suite les
ferme tous les deux :

  1. **la derive silencieuse.** L empreinte du magasin est ecrite dans six
     pages de ce depot. Si le fichier change sans qu elles changent, ces six
     pages deviennent fausses sans qu aucun test ne rougisse ;
  2. **la fuite de materiel de cle.** Un magasin de confiance ne porte que
     des cles PUBLIQUES. Le jour ou quelqu un y colle un scalaire prive, il
     le publie.

Emploi :  python tests/test_trust_store.py

Bibliotheque standard seule.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
MAGASIN = RACINE / "trust" / "trust-store.json"

#: Empreinte mesuree le 2026-11-14, concordante sur QUATRE sources : l arbre
#: de travail du moteur, cette copie, l URL `raw.githubusercontent.com` tant
#: qu elle repondait, et le second canal `mcp.neomundi.org`.
EMPREINTE = "dac94e8ad4baf0a48fe94b8006a238d970d242cdc52b8d9dd51294777751598d"
OCTETS = 3038

#: Les pages qui ANNONCENT cette empreinte. Chacune devient fausse si le
#: fichier derive.
PAGES = (
    "trust/README.md",
    "trust/README.fr.md",
    "README.md",
    "README.fr.md",
    "references/VERIFICATION_RESULTS.md",
    "references/VERIFICATION_RESULTS.fr.md",
)

#: Motifs qui trahiraient du materiel de cle PRIVEE. `"d"` est le membre
#: prive d une JWK OKP : sa seule presence suffirait a publier une cle.
MOTIFS_INTERDITS = (b"PRIVATE KEY", b"BEGIN OPENSSH", b"BEGIN EC PARAMETERS", b'"d"')

BILAN: list[tuple[str, str, str]] = []


def noter(etat: str, intitule: str, detail: str = "") -> None:
    BILAN.append((etat, intitule, detail))
    print(f"[{etat:10}] {intitule}" + (f" - {detail}" if detail else ""))


def main() -> int:
    if not MAGASIN.is_file():
        noter("FAIL", "le magasin publie existe", "trust/trust-store.json est absent")
        print("\nBILAN : 0 PASS, 1 FAIL, 0 NOT TESTED")
        return 1

    octets = MAGASIN.read_bytes()
    obtenu = hashlib.sha256(octets).hexdigest()

    if obtenu != EMPREINTE:
        noter("FAIL", "empreinte du magasin", f"{obtenu} au lieu de {EMPREINTE}")
    elif len(octets) != OCTETS:
        noter("FAIL", "taille du magasin", f"{len(octets)} octets au lieu de {OCTETS}")
    else:
        noter("PASS", "empreinte du magasin", f"{obtenu} ({len(octets)} octets)")

    # Une seule fin de ligne reecrite change l empreinte, donc la preuve.
    # `.gitattributes` pose `trust/trust-store.json -text` pour cela.
    if octets.count(b"\r\n"):
        noter("FAIL", "aucune reecriture de fin de ligne",
              "le magasin porte des CRLF : son empreinte n est plus celle publiee")
    else:
        noter("PASS", "aucune reecriture de fin de ligne", "0 CRLF")

    trouves = [m for m in MOTIFS_INTERDITS if m in octets]
    if trouves:
        noter("FAIL", "aucun materiel de cle privee",
              "motif(s) present(s) : " + ", ".join(repr(m) for m in trouves))
    else:
        noter("PASS", "aucun materiel de cle privee",
              f"{len(MOTIFS_INTERDITS)} motif(s) confronte(s)")

    # Le magasin reste du JSON lisible, et reste le contrat qu il annonce.
    try:
        charge = json.loads(octets.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        noter("FAIL", "le magasin est du JSON valide", str(exc))
        charge = None
    if isinstance(charge, dict):
        attendu = "neomundi.evidence.trust-store/1"
        if charge.get("schema") != attendu:
            noter("FAIL", "contrat annonce par le magasin",
                  f"{charge.get('schema')!r} au lieu de {attendu!r}")
        else:
            noter("PASS", "contrat annonce par le magasin", attendu)
        cles = charge.get("keys") or []
        sans_x = [k.get("kid") for k in cles if not k.get("x")]
        if sans_x:
            noter("FAIL", "chaque cle porte son point public",
                  "sans `x` : " + ", ".join(str(k) for k in sans_x))
        else:
            noter("PASS", "chaque cle porte son point public",
                  f"{len(cles)} cle(s)")

    echecs_de_page = []
    for page in PAGES:
        chemin = RACINE / page
        if not chemin.is_file():
            echecs_de_page.append(f"{page} (absente)")
            continue
        texte = chemin.read_text(encoding="utf-8")
        if EMPREINTE not in texte and EMPREINTE[:8] not in texte:
            echecs_de_page.append(page)
    if echecs_de_page:
        noter("FAIL", "les pages annoncent l empreinte du fichier",
              "a corriger : " + ", ".join(echecs_de_page))
    else:
        noter("PASS", "les pages annoncent l empreinte du fichier",
              f"{len(PAGES)} page(s) confrontee(s)")

    reussis = sum(1 for e, _, _ in BILAN if e == "PASS")
    echoues = sum(1 for e, _, _ in BILAN if e == "FAIL")
    print(f"\nBILAN : {reussis} PASS, {echoues} FAIL, 0 NOT TESTED")
    print("Le second canal (mcp.neomundi.org) n est PAS interroge ici : une")
    print("suite hors reseau ne doit pas dependre d un service. Le confronter")
    print("a la main -- la recette est dans trust/README.md.")
    return 1 if echoues else 0


if __name__ == "__main__":
    sys.exit(main())
