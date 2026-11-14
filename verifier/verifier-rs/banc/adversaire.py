#!/usr/bin/env python3
"""Banc ADVERSARIAL différentiel — les analyseurs écrits à la main.

CE QUE CE BANC AJOUTE À `comparer.py`
-------------------------------------
`comparer.py` éprouve les VERDICTS sur des paquets plausibles. Celui-ci
attaque les trois analyseurs écrits à la main — JSON, ZIP, DEFLATE — avec
des entrées qu'aucune bibliothèque n'accepte de produire : répertoire
central mensonger, en-tête local contradictoire, CRC faux, clef JSON en
double, grammaire élargie, amplification mémoire.

CHAQUE CAS PORTE, ÉCRIT D'AVANCE
--------------------------------
  - le RISQUE exploré ;
  - la RÈGLE DE RÉFÉRENCE qui tranche (RFC, schéma publié, ou comportement
    de `zipfile`/`json` de Python) ;
  - l'ATTENTE côté Rust.

Les attentes sont écrites avant l'exécution. Une case qui ne correspond pas
est signalée, jamais réécrite pour obtenir un vert.

L'ÉTAT ATTENDU CÔTÉ PYTHON N'EST PAS UNE ATTENTE
------------------------------------------------
Python est MESURÉ, pas supposé correct. Les trois états observés sont
distingués, parce qu'ils ne veulent pas dire la même chose :

  CONCORDANT       les deux rendent le même verdict ;
  PY_PLUS_LAXISTE  Python accepte ce que Rust refuse ;
  PY_SANS_RAPPORT  Python sort en 1 sans écrire de rapport machine —
                   c'est-à-dire qu'il lève une exception non rattrapée.

Le troisième état est un DÉFAUT de Python, trouvé ici, consigné ici, et
NON corrigé : le périmètre de correction de cette consolidation est Rust.

Hors ligne. Aucun accès à la production. Aucun appel payant.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
SIG_L, SIG_C, SIG_E = 0x04034B50, 0x02014B50, 0x06054B50

# --------------------------------------------------------------------------
# Lancement des deux vérificateurs
# --------------------------------------------------------------------------


def lancer(cmd, timeout=300):
    try:
        x = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout,
                           env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        return x.returncode, x.stdout or "", x.stderr or ""
    except subprocess.TimeoutExpired:
        return "DELAI", "", ""


def rapport(p: Path):
    if not p.exists():
        return None
    try:
        return json.loads(p.read_bytes())
    except ValueError:
        return "ILLISIBLE"


def mesurer(binaire: Path, cible: Path, sortie: Path, nom: str) -> dict:
    rp, rr = sortie / f"{nom}.py.json", sortie / f"{nom}.rs.json"
    for r in (rp, rr):
        if r.exists():
            r.unlink()
    cp, _, _ = lancer([sys.executable, "-B", str(RACINE / "adapters/ingest.py"),
                       str(cible), "--out", str(rp), "--lang", "fr"])
    cr, _, er = lancer([str(binaire), str(cible), "--json", str(rr)])
    dp, dr = rapport(rp), rapport(rr)

    def lire(d):
        if not isinstance(d, dict):
            return None, [], []
        nd = [l.get("etat") for l in d.get("lines", [])
              if "non declare" in (l.get("detail") or "").lower()
              or "undeclared" in (l.get("detail") or "").lower()]
        return d.get("verdict"), [a.get("path") for a in d.get("artifacts", [])], nd

    vp, ap, np_ = lire(dp)
    vr, ar, nr = lire(dr)
    return {
        "python": {"code": cp, "verdict": vp, "artefacts": ap,
                   "fichiers_non_declares": np_, "rapport_ecrit": dp is not None},
        "rust": {"code": cr, "verdict": vr, "artefacts": ar,
                 "fichiers_non_declares": nr, "rapport_ecrit": dr is not None,
                 "stderr": er.strip()[:300]},
    }


def classer(m: dict) -> str:
    p, r = m["python"], m["rust"]
    if not p["rapport_ecrit"]:
        return "PY_SANS_RAPPORT"
    if p["verdict"] == r["verdict"] and p["code"] == r["code"]:
        return "CONCORDANT"
    ordre = {"ACCEPTE": 0, "INCOMPLET": 1, "REJETE": 2}
    if ordre.get(p["verdict"], 9) < ordre.get(r["verdict"], 9):
        return "PY_PLUS_LAXISTE"
    return "RUST_PLUS_LAXISTE"


# --------------------------------------------------------------------------
# Forgeur de ZIP
# --------------------------------------------------------------------------


def forger(membres, *, nb_total=None, taille_rc=None, decalage_rc=None,
           nom_local=None, crc_faux=False, methode=0, entre_rc_et_eocd=0):
    nom_local = nom_local or {}
    o = bytearray()
    entrees = []
    for nom, donnees in membres:
        crc = zlib.crc32(donnees) & 0xFFFFFFFF
        if crc_faux:
            crc ^= 0xFFFFFFFF
        if methode == 8:
            co = zlib.compressobj(9, zlib.DEFLATED, -15)
            comp = co.compress(donnees) + co.flush()
        else:
            comp = donnees
        nl = nom_local.get(nom, nom).encode("utf-8")
        decalage = len(o)
        o += struct.pack("<IHHHHHIIIHH", SIG_L, 20, 0, methode, 0, 0,
                         crc, len(comp), len(donnees), len(nl), 0)
        o += nl + comp
        entrees.append((nom, crc, len(comp), len(donnees), methode, decalage))

    depart = len(o)
    rc = bytearray()
    for nom, crc, nc, nd, meth, decalage in entrees:
        nb = nom.encode("utf-8")
        rc += struct.pack("<IHHHHHHIIIHHHHHII", SIG_C, 20, 20, 0, meth, 0, 0,
                          crc, nc, nd, len(nb), 0, 0, 0, 0, 0, decalage)
        rc += nb
    o += rc
    o += b"\x00" * entre_rc_et_eocd
    n = len(entrees) if nb_total is None else nb_total
    t = len(rc) if taille_rc is None else taille_rc
    d = depart if decalage_rc is None else decalage_rc
    o += struct.pack("<IHHHHIIH", SIG_E, 0, 0, n, n, t, d, 0)
    return bytes(o)


# --------------------------------------------------------------------------
# Les cas
# --------------------------------------------------------------------------
#
# (identifiant, risque, regle_de_reference, attente_rust, fabrique)
#
# `attente_rust` est l'un de : ACCEPTE, INCOMPLET, REJETE.


def cas_json(base: Path, travail: Path) -> list[dict]:
    brut = (base / "submission.json").read_bytes()
    t = json.dumps(json.loads(brut), ensure_ascii=False, indent=2)
    out = []

    def ajout(nom, octets, risque, regle, attente):
        cible = travail / nom
        shutil.rmtree(cible, ignore_errors=True)
        shutil.copytree(base, cible)
        (cible / "submission.json").write_bytes(octets)
        out.append({"id": nom, "famille": "json", "risque": risque,
                    "regle": regle, "attente_rust": attente, "chemin": cible})

    # --- AMBIGUITE-4, sur toute sa portée ---------------------------------
    ajout("j-double-sha256",
          t.replace('"sha256":', '"sha256": "' + "0" * 64 + '",\n      "sha256":', 1)
          .encode() + b"\n",
          "DEUX empreintes pour UN artefact : laquelle est controlee ?",
          "RFC 8259 §4 : les noms DEVRAIENT etre uniques, cas laisse indefini",
          "REJETE")
    ajout("j-double-schema",
          t.replace('"schema":', '"schema": "neomundi.evidence.submission/99",\n  "schema":', 1)
          .encode() + b"\n",
          "DEUX versions de contrat : laquelle regit la validation ?",
          "RFC 8259 §4", "REJETE")
    ajout("j-double-identique",
          t.replace('"submission_id":', '"submission_id": "pilot-ogs-b3-v2",\n  "submission_id":', 1)
          .encode() + b"\n",
          "doublon dont les deux valeurs sont EGALES",
          "RFC 8259 §4", "REJETE")
    ajout("j-double-imbriquee",
          t.replace('"name_declared":', '"name_declared": "AUTRE",\n      "name_declared":', 1)
          .encode() + b"\n",
          "doublon dans un objet IMBRIQUE, non a la racine",
          "RFC 8259 §4", "REJETE")

    # --- grammaire élargie de Python --------------------------------------
    ajout("j-nan-hors-contrat",
          t.replace('"schema":', '"champ_en_surplus": NaN,\n  "schema":', 1).encode() + b"\n",
          "`NaN` n existe pas dans la RFC 8259 ; `json` de Python l accepte",
          "RFC 8259 §6 : la grammaire des nombres n a ni NaN ni Infinity",
          "REJETE")
    ajout("j-infinity-hors-contrat",
          t.replace('"schema":', '"champ_en_surplus": Infinity,\n  "schema":', 1).encode() + b"\n",
          "`Infinity` : meme famille", "RFC 8259 §6", "REJETE")
    ajout("j-surrogate-solitaire",
          t.replace('"name_declared": "', '"name_declared": "\\ud800', 1).encode() + b"\n",
          "demi-paire UTF-16 : `str` de Python peut la porter, Unicode non",
          "RFC 8259 §7 : une paire de substitution doit etre complete",
          "REJETE")

    # --- amplification ----------------------------------------------------
    ajout("j-largeur-au-dela-de-la-borne",
          ('{"schema":"neomundi.evidence.submission/1","x":['
           + ",".join(["1"] * 1000001) + "]}").encode(),
          "largeur du document : amplification memoire de l arbre d analyse",
          "COMPORTEMENT CHOISI ICI : `json::NOEUDS_MAX`, non contractuel",
          "REJETE")
    ajout("j-profondeur-100k", b"[" * 100000 + b"]" * 100000,
          "100 000 niveaux : debordement de pile d un analyseur recursif",
          "COMPORTEMENT CHOISI ICI : `json::PROFONDEUR_MAX`, non contractuel",
          "REJETE")
    ajout("j-bom", b"\xef\xbb\xbf" + brut,
          "un BOM UTF-8 est banal : il ne doit pas accuser le partenaire",
          "COMPORTEMENT OBSERVE : les deux le tolerent", "ACCEPTE")

    # --- entrées tronquées ------------------------------------------------
    for nom, octets, risque in (
        ("j-tronque-echappement", b'{"a":"\\u00', "echappement \\u coupe"),
        ("j-tronque-surrogate", b'{"a":"\\ud800\\u', "paire coupee en deux"),
        ("j-tronque-utf8", b'{"a":"\xe2\x82', "sequence UTF-8 de 3 octets coupee"),
        ("j-nul-hors-chaine", b'{"a"\x00:1}', "octet NUL hors chaine"),
        ("j-deux-documents", (t + "\n" + t).encode(), "deux documents concatenes"),
        ("j-espace-insecable", t.replace("{", "{\xa0", 1).encode(),
         "espace insecable comme blanc : la RFC n en a que quatre"),
    ):
        ajout(nom, octets, risque, "RFC 8259", "REJETE")
    return out


def cas_zip(base: Path, travail: Path) -> list[dict]:
    membres = [(p.relative_to(base).as_posix(), p.read_bytes())
               for p in sorted(base.rglob("*"), key=lambda x: x.as_posix())
               if p.is_file()]
    manifeste = [x for x in membres if x[0] == "submission.json"]
    autres = [x for x in membres if x[0] != "submission.json"]
    ordonne = manifeste + autres
    out = []

    def ajout(nom, octets, risque, regle, attente):
        f = travail / f"{nom}.zip"
        f.write_bytes(octets)
        out.append({"id": nom, "famille": "zip", "risque": risque,
                    "regle": regle, "attente_rust": attente, "chemin": f})

    ajout("z-temoin-stocke", forger(ordonne),
          "temoin : une archive bien formee doit passer",
          "sans quoi tous les cas suivants passeraient pour la mauvaise raison",
          "ACCEPTE")
    ajout("z-temoin-deflate", forger(ordonne, methode=8),
          "temoin, methode 8", "idem", "ACCEPTE")

    ajout("z-crc-faux", forger(ordonne, crc_faux=True),
          "le CRC-32 contredit les donnees",
          "APPNOTE ZIP §4.3.12 ; `zipfile` et `unzip` refusent tous deux",
          "REJETE")
    ajout("z-crc-faux-deflate", forger(ordonne, crc_faux=True, methode=8),
          "CRC faux sur un flux deflate", "idem", "REJETE")
    ajout("z-nom-local-divergent",
          forger(ordonne, nom_local={"submission.json": "autre.json"}),
          "l en-tete LOCAL nomme un autre fichier que le repertoire central",
          "`zipfile` compare les deux et leve BadZipFile", "REJETE")

    ajout("z-nb-total-sous-declare", forger(ordonne, nb_total=1),
          "nb_total sous-declare : des membres deviennent-ils invisibles ?",
          "APPNOTE ZIP §4.4.21 : nb_total compte les entrees du repertoire",
          "REJETE")
    ajout("z-nb-total-sur-declare", forger(ordonne, nb_total=len(ordonne) + 3),
          "nb_total sur-declare", "idem", "REJETE")
    ajout("z-taille-rc-sous-declaree", forger(ordonne, taille_rc=46),
          "taille du repertoire central sous-declaree : lecture au-dela ?",
          "APPNOTE ZIP §4.4.20", "REJETE")
    ajout("z-decalage-rc-faux", forger(ordonne, decalage_rc=0),
          "decalage du repertoire central faux", "APPNOTE ZIP §4.4.21", "REJETE")
    ajout("z-entre-rc-et-eocd", forger(ordonne, entre_rc_et_eocd=22),
          "octets entre la fin du repertoire central et l EOCD",
          "aucune partie du format ne les decrit ; `zipfile` refuse", "REJETE")
    ajout("z-zip64-nb-total", forger(ordonne, nb_total=0xFFFF),
          "marqueur ZIP64 sans EOCD64 : refus NOMME ou accidentel ?",
          "APPNOTE ZIP §4.4.1.4 : 0xFFFF renvoie a l EOCD64", "REJETE")

    ajout("z-nom-en-double", forger(ordonne + [("submission.json", b"{}")]),
          "deux membres de MEME nom : quels octets sont condenses ?",
          "deux lecteurs en tirent des octets differents", "REJETE")
    ajout("z-methode-99", forger(ordonne, methode=99),
          "methode de compression inconnue", "APPNOTE ZIP §4.4.5", "REJETE")

    vrai = forger(ordonne)
    for part, nom in ((0.5, "moitie"), (0.95, "95pc")):
        ajout(f"z-tronque-{nom}", vrai[: int(len(vrai) * part)],
              "archive coupee : refus propre, sans panique",
              "APPNOTE ZIP : sans EOCD, il n y a pas d archive", "REJETE")

    # Le vecteur de DISSIMULATION : un fichier non declare, cache par un
    # `nb_total` amput'e d une unite.
    furtif = ordonne + [("artefacts/clandestin.bin", b"octets non declares")]
    ajout("z-clandestin-visible", forger(furtif),
          "un fichier NON DECLARE est present : il doit etre SIGNALE",
          "`additionalProperties` ne couvre pas les fichiers ; les deux "
          "verificateurs publient une ligne NOT TESTED",
          "ACCEPTE")
    ajout("z-clandestin-cache", forger(furtif, nb_total=len(ordonne)),
          "MEME archive, nb_total ampute de 1 : le fichier disparait-il "
          "du rapport ?",
          "APPNOTE ZIP §4.4.21 ; c est le contournement du controle "
          "« fichiers non declares »",
          "REJETE")

    # Un membre dont le CONTENU est un chemin absolu : rien ne doit etre cree.
    lien = manifeste + [("artefacts/lien", b"/etc/passwd")]
    ajout("z-membre-contenu-chemin", forger(lien),
          "un membre dont le contenu est un chemin : rien ne doit etre ecrit",
          "ce module n extrait rien, par conception", "INCOMPLET")

    # Entrées hostiles : seul le CODE DE SORTIE est en jeu.
    for nom, octets in (
        ("z-vide", b""),
        ("z-un-octet", b"P"),
        ("z-eocd-seul", struct.pack("<IHHHHIIH", SIG_E, 0, 0, 0, 0, 0, 0, 0)),
        ("z-nuls", b"\x00" * 2048),
        ("z-ff", b"\xff" * 2048),
    ):
        ajout(nom, octets,
              "entree hostile : le code doit rester dans {0,1,2,3}",
              "contrat de sortie du vérificateur", "REJETE")
    return out


# --------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--binaire", default=None,
                    help="le verificateur Rust (defaut : $CARGO_TARGET_DIR)")
    ap.add_argument("--travail", default=None)
    ap.add_argument("--json", dest="sortie_json", default=None)
    a = ap.parse_args()

    cible = os.environ.get("CARGO_TARGET_DIR",
                           str(Path.home() / "evr-target"))
    binaire = Path(a.binaire or f"{cible}/release/evidence-verify-rs")
    if not binaire.exists():
        print("binaire absent : %s" % binaire, file=sys.stderr)
        print("lancer d abord `bash verifier-rs/banc/build.sh`", file=sys.stderr)
        return 2

    travail = Path(a.travail or (Path(os.environ.get("TMPDIR", "/tmp"))
                                 / "evr-adversaire"))
    shutil.rmtree(travail, ignore_errors=True)
    travail.mkdir(parents=True)
    base = travail / "_base"
    subprocess.run([sys.executable, "-B", str(RACINE / "tests/make_submission.py"),
                    str(base), "--profil", "valide"],
                   check=True, capture_output=True)

    cas = cas_json(base, travail) + cas_zip(base, travail)
    sortie = travail / "rapports"
    sortie.mkdir(exist_ok=True)

    print("%-32s %-10s %-10s %-10s %-17s %s"
          % ("cas", "attendu", "rust", "python", "classe", "famille"))
    print("-" * 104)
    resultats = []
    hors_attente = []
    classes = {}
    for c in cas:
        m = mesurer(binaire, c["chemin"], sortie, c["id"])
        cl = classer(m)
        classes[cl] = classes.get(cl, 0) + 1
        conforme = m["rust"]["verdict"] == c["attente_rust"]
        # Les entrées hostiles n'ont pas de verdict attendu précis : seul le
        # code compte. Elles sont marquées par leur risque.
        code_ok = m["rust"]["code"] in (0, 1, 2, 3)
        if not conforme:
            hors_attente.append({**{k: v for k, v in c.items() if k != "chemin"},
                                 "mesure": m})
        print("%-32s %-10s %-10s %-10s %-17s %s%s"
              % (c["id"], c["attente_rust"], m["rust"]["verdict"],
                 m["python"]["verdict"], cl, c["famille"],
                 "" if conforme else "   <<< HORS ATTENTE"))
        if not code_ok:
            print("      CODE HORS CONTRAT : %s" % m["rust"]["code"])
        resultats.append({**{k: str(v) for k, v in c.items() if k == "chemin"},
                          "id": c["id"], "famille": c["famille"],
                          "risque": c["risque"], "regle": c["regle"],
                          "attente_rust": c["attente_rust"],
                          "classe": cl, "conforme": conforme,
                          "code_dans_le_contrat": code_ok, "mesure": m})

    print()
    print("cas executes                        : %d" % len(resultats))
    print("conformes a l attente ECRITE d avance: %d / %d"
          % (sum(1 for r in resultats if r["conforme"]), len(resultats)))
    print("codes de sortie dans le contrat     : %d / %d"
          % (sum(1 for r in resultats if r["code_dans_le_contrat"]), len(resultats)))
    for k in sorted(classes):
        print("  %-17s : %d" % (k, classes[k]))
    print()
    print("Rappel : `PY_SANS_RAPPORT` designe un DEFAUT de Python -- une")
    print("exception non rattrapee, donc un code 1 sans rapport machine. Il")
    print("est consigne ici et NON corrige : le perimetre de correction de")
    print("cette consolidation est Rust. Voir 07_RISQUES_RESIDUELS.md.")

    if a.sortie_json:
        Path(a.sortie_json).write_text(
            json.dumps({"total": len(resultats),
                        "conformes": sum(1 for r in resultats if r["conforme"]),
                        "codes_dans_le_contrat":
                            sum(1 for r in resultats if r["code_dans_le_contrat"]),
                        "classes": classes,
                        "hors_attente": [h["id"] for h in hors_attente],
                        "cas": resultats},
                       indent=2, ensure_ascii=False),
            encoding="utf-8")
        print("\nrapport machine : %s" % a.sortie_json)

    return 1 if hors_attente else 0


if __name__ == "__main__":
    raise SystemExit(main())
