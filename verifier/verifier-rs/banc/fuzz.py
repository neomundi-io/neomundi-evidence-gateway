#!/usr/bin/env python3
"""Fuzzing BORNÉ, GRAINÉ et REPRODUCTIBLE des deux analyseurs écrits à la main.

CE QUE CE BANC PEUT ÉTABLIR, ET CE QU'IL NE PEUT PAS
----------------------------------------------------
Il peut produire des CONTRE-EXEMPLES. Il ne peut pas établir l'absence de
défaut. « 0 anomalie sur 50 000 tours » veut dire : aucun contre-exemple sur
ce corpus, cette graine, ce nombre de tours. Ce n'est pas une preuve de
sécurité, et ce rapport ne la présente jamais comme telle.

LES RÉFÉRENCES SONT INDÉPENDANTES DU DÉPÔT
------------------------------------------
`zlib` et le module `json` ne partagent pas une ligne avec le vérificateur
Rust. Un désaccord désigne donc l'une des deux implémentations, et il faut
l'instruire -- jamais le faire taire.

DEUX CORRECTIONS D'INSTRUMENT, CONSERVÉES ICI PARCE QU'ELLES INSTRUISENT
-----------------------------------------------------------------------
1. La première version comparait à `decompressobj().decompress()`, qui est
   un décompresseur EN FLUX : il rend ce qu'il peut d'un flux incomplet.
   Elle signalait 21 « désaccords » qui étaient des flux tronqués refusés
   des deux côtés. La référence doit exiger `eof`.
2. La deuxième exigeait aussi `unused_data` vide. Elle signalait
   1 293 « désaccords » qui n'étaient que des octets APRÈS le bloc final --
   que le lecteur de ZIP ignore légitimement, puisqu'il passe exactement
   `taille_compressee` octets. Ces octets sont désormais comptés à part.

Deux fois, c'est l'instrument qui avait tort, pas le code. Le signal utile
n'est apparu qu'après : quatre flux que `zlib` refuse et que Rust acceptait,
tous dus à un arbre de Huffman INCOMPLET. Ils sont corrigés, et conservés
dans `src/essais.rs::inflate_refuse_un_arbre_de_distance_incomplet`.

CRITÈRES D'ANOMALIE, écrits avant la campagne
---------------------------------------------
  1. code de sortie hors {0, 1}          -> panique ou abandon : DÉFAUT
  2. les deux acceptent, octets différents -> DÉFAUT de décodage
  3. la référence accepte, Rust refuse     -> à instruire
  4. Rust accepte, la référence refuse     -> à instruire
  5. durée > 5 s sur une entrée < 4 Kio    -> amplification CPU

Hors ligne. Aucun accès à la production. Aucun appel payant.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import subprocess
import sys
import time
import zlib
from collections import Counter
from pathlib import Path

BORNE = 1 << 22

# --------------------------------------------------------------------------
# DEFLATE
# --------------------------------------------------------------------------


def reference_deflate(flux: bytes):
    """(accepte, octets, motif). Voir les deux corrections d'instrument."""
    d = zlib.decompressobj(-15)
    try:
        out = d.decompress(flux) + d.flush()
    except Exception as e:
        return False, b"", "erreur:" + type(e).__name__
    if not d.eof:
        return False, b"", "flux_incomplet"
    if d.unused_data:
        return True, out, "octets_en_trop_apres_le_bloc_final"
    return True, out, "complet"


def graines_deflate(rng):
    """Des flux VALIDES : c'est d'eux que part la mutation. Un flux
    entièrement aléatoire ne franchit presque jamais l'en-tête, et ne
    visiterait donc jamais le décodeur de Huffman."""
    sources = [
        b"", b"a", b"ab" * 200, b"\x00" * 5000,
        bytes(rng.randrange(256) for _ in range(3000)),
        b"le meme mot " * 400,
        bytes(range(256)) * 8,
        b"abcabcabd" * 300,
    ]
    out = []
    for s in sources:
        for niveau in (0, 1, 6, 9):
            co = zlib.compressobj(niveau, zlib.DEFLATED, -15)
            out.append(co.compress(s) + co.flush())
    return out


# --------------------------------------------------------------------------
# JSON
# --------------------------------------------------------------------------

#: Les classes de divergence DÉCLARÉES entre les deux analyseurs. Elles sont
#: exclues de la comparaison d'acceptation parce qu'elles sont voulues et
#: testées ailleurs -- et l'exclusion est NOMMÉE, non silencieuse.
#:   - clef en double : AMBIGUÏTÉ-4, voir `AMBIGUITE_4_DECISION.md` ;
#:   - NaN / Infinity : grammaire élargie de `json`, hors RFC 8259 ;
#:   - demi-paire de substitution : `str` de Python peut la porter.
EXCLUSIONS = ("clef_double", "nan_infinity", "surrogate")


class CDouble(Exception):
    pass


def _paires(p):
    vus = set()
    for k, _ in p:
        if k in vus:
            raise CDouble()
        vus.add(k)
    return dict(p)


def classe_exclue(octets: bytes) -> str | None:
    """Le document relève-t-il d'une divergence DÉCLARÉE ?"""
    texte = octets.decode("utf-8", "replace")
    if "NaN" in texte or "Infinity" in texte:
        return "nan_infinity"
    for h in ("\\ud8", "\\uD8", "\\ud9", "\\uD9", "\\uda", "\\uDA",
              "\\udb", "\\uDB", "\\udc", "\\uDC", "\\udd", "\\uDD",
              "\\ude", "\\uDE", "\\udf", "\\uDF"):
        if h in texte:
            return "surrogate"
    try:
        json.loads(octets, object_pairs_hook=_paires)
    except CDouble:
        return "clef_double"
    except Exception:
        pass
    return None


def reference_json(octets: bytes) -> bool:
    try:
        json.loads(octets)
        return True
    except Exception:
        return False


def graines_json(rng):
    return [
        b"{}", b"[]", b'{"a":1}', b'{"a":[1,2,3],"b":{"c":"d"}}',
        b'{"schema":"neomundi.evidence.submission/1","artifacts":[]}',
        b'"texte"', b"123", b"-0.5e10", b"true", b"false", b"null",
        b'{"e":"\\u00e9\\ud83d\\ude00","f":"\\t\\n\\\\"}',
        b'[[[[[1]]]]]', b'{"a":{"b":{"c":{"d":[1,"deux",null]}}}}',
        b"\xef\xbb\xbf{}",
    ]


def muter(rng, base: bytes) -> bytes:
    o = bytearray(base)
    if not o:
        return bytes(rng.randrange(256) for _ in range(rng.randrange(1, 40)))
    for _ in range(rng.randrange(1, 6)):
        g = rng.randrange(6)
        i = rng.randrange(len(o))
        if g == 0:
            o[i] ^= 1 << rng.randrange(8)
        elif g == 1:
            o[i] = rng.randrange(256)
        elif g == 2:
            del o[i:i + rng.randrange(1, 8)]
        elif g == 3:
            o[i:i] = bytes(rng.randrange(256) for _ in range(rng.randrange(1, 8)))
        elif g == 4:
            del o[rng.randrange(len(o)):]
        else:
            j = rng.randrange(len(o))
            o[i], o[j] = o[j], o[i]
        if not o:
            break
    return bytes(o)


# --------------------------------------------------------------------------


def campagne_deflate(outil: Path, graine: int, tours: int) -> dict:
    rng = random.Random(graine)
    bases = graines_deflate(rng)
    anomalies, lents = [], []
    accepte_rs = accepte_ref = surplus = 0
    t0 = time.monotonic()
    for tour in range(tours):
        if rng.randrange(10) == 0:
            flux = bytes(rng.randrange(256) for _ in range(rng.randrange(1, 200)))
            origine = "aleatoire"
        else:
            flux = muter(rng, bases[rng.randrange(len(bases))])
            origine = "mutation"
        t1 = time.monotonic()
        try:
            x = subprocess.run([str(outil), "inflate", str(BORNE)], input=flux,
                               capture_output=True, timeout=60)
        except subprocess.TimeoutExpired:
            anomalies.append({"tour": tour, "genre": "delai_depasse",
                              "origine": origine, "flux": flux.hex()[:800]})
            continue
        duree = time.monotonic() - t1
        code = x.returncode
        sortie = x.stdout.decode("ascii", "replace").strip()
        if code not in (0, 1):
            anomalies.append({"tour": tour, "genre": "code_hors_contrat",
                              "code": code, "origine": origine,
                              "flux": flux.hex()[:800],
                              "stderr": x.stderr.decode("utf-8", "replace")[:300]})
            continue
        if duree > 5.0 and len(flux) < 4096:
            lents.append({"tour": tour, "duree": round(duree, 2),
                          "taille": len(flux), "flux": flux.hex()[:800]})
        ref_ok, ref_octets, motif = reference_deflate(flux)
        rs_ok = code == 0
        accepte_rs += rs_ok
        accepte_ref += ref_ok
        if ref_ok and rs_ok:
            if motif == "octets_en_trop_apres_le_bloc_final":
                surplus += 1
            if sortie != hashlib.sha256(ref_octets).hexdigest():
                anomalies.append({"tour": tour, "genre": "octets_differents",
                                  "origine": origine, "flux": flux.hex()[:800],
                                  "attendu": hashlib.sha256(ref_octets).hexdigest(),
                                  "obtenu": sortie})
        elif ref_ok:
            anomalies.append({"tour": tour, "genre": "zlib_accepte_rust_refuse",
                              "origine": origine, "flux": flux.hex()[:800],
                              "taille_sortie": len(ref_octets),
                              "stderr": x.stderr.decode("utf-8", "replace")[:200]})
        elif rs_ok:
            anomalies.append({"tour": tour, "genre": "rust_accepte_zlib_refuse",
                              "motif_reference": motif, "origine": origine,
                              "flux": flux.hex()[:800], "sortie_sha": sortie})
    return {"tours": tours, "duree_s": round(time.monotonic() - t0, 1),
            "acceptes_rust": accepte_rs, "acceptes_zlib": accepte_ref,
            "octets_en_trop_ignores_des_deux_cotes": surplus,
            "anomalies": anomalies, "entrees_lentes": lents}


def campagne_json(binaire: Path, graine: int, tours: int, travail: Path) -> dict:
    """Le vérificateur n'expose pas son analyseur JSON : on passe par un
    paquet-dossier dont le manifeste EST l'entrée fuzzée. On n'observe donc
    pas l'arbre, mais ce qui compte ici : l'absence de panique, le code de
    sortie, et l'ACCEPTATION comparée à celle de `json`."""
    rng = random.Random(graine)
    bases = graines_json(rng)
    travail.mkdir(parents=True, exist_ok=True)
    paquet = travail / "paquet"
    paquet.mkdir(exist_ok=True)
    rapport = travail / "r.json"
    anomalies, lents = [], []
    accepte_rs = accepte_ref = 0
    exclus = Counter()
    t0 = time.monotonic()
    for tour in range(tours):
        if rng.randrange(8) == 0:
            doc = bytes(rng.randrange(256) for _ in range(rng.randrange(1, 120)))
        else:
            doc = muter(rng, bases[rng.randrange(len(bases))])
        (paquet / "submission.json").write_bytes(doc)
        if rapport.exists():
            rapport.unlink()
        t1 = time.monotonic()
        try:
            x = subprocess.run([str(binaire), str(paquet), "--json", str(rapport)],
                               capture_output=True, timeout=60)
        except subprocess.TimeoutExpired:
            anomalies.append({"tour": tour, "genre": "delai_depasse",
                              "doc": doc.hex()[:800]})
            continue
        duree = time.monotonic() - t1
        if x.returncode not in (0, 1, 2, 3):
            anomalies.append({"tour": tour, "genre": "code_hors_contrat",
                              "code": x.returncode, "doc": doc.hex()[:800],
                              "stderr": x.stderr.decode("utf-8", "replace")[:300]})
            continue
        if not rapport.exists():
            anomalies.append({"tour": tour, "genre": "aucun_rapport_machine",
                              "code": x.returncode, "doc": doc.hex()[:800]})
            continue
        if duree > 5.0 and len(doc) < 4096:
            lents.append({"tour": tour, "duree": round(duree, 2),
                          "taille": len(doc), "doc": doc.hex()[:800]})
        # CE QU'ON COMPARE ICI : l'ACCEPTATION du document par l'ANALYSEUR
        # JSON, et non le verdict du paquet. Un manifeste parfaitement
        # lisible est presque toujours refusé pour ses CHAMPS, et ce n'est
        # pas ce qu'on mesure.
        #
        # TROISIÈME CORRECTION D'INSTRUMENT. Le critère était
        # « la ligne "manifeste de soumission" est présente » : il signalait
        # 46 faux désaccords, car un document valide mais au `schema`
        # inconnu fait sortir le vérificateur AVANT cette ligne, sur
        # « schema du manifeste ». Le seul marqueur fiable d'un refus
        # D'ANALYSE est le message `illisible`, émis uniquement par la
        # branche `Err` de `json::analyser`.
        sortie = x.stdout.decode("utf-8", "replace")
        rs_json_ok = "illisible" not in sortie
        ref_ok = reference_json(doc)
        accepte_rs += rs_json_ok
        accepte_ref += ref_ok
        if rs_json_ok != ref_ok:
            cl = classe_exclue(doc)
            if cl in EXCLUSIONS:
                exclus[cl] += 1
            else:
                anomalies.append({"tour": tour, "genre": "acceptation_json",
                                  "python": ref_ok, "rust": rs_json_ok,
                                  "doc": doc.hex()[:800]})
    return {"tours": tours, "duree_s": round(time.monotonic() - t0, 1),
            "json_lu_par_rust": accepte_rs, "json_lu_par_python": accepte_ref,
            "divergences_DECLAREES_exclues": dict(exclus),
            "anomalies": anomalies, "entrees_lentes": lents}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--graine", type=int, default=20261111)
    ap.add_argument("--tours", type=int, default=20000)
    ap.add_argument("--tours-json", type=int, default=4000)
    ap.add_argument("--outil", default=None)
    ap.add_argument("--binaire", default=None)
    ap.add_argument("--json", dest="sortie", default=None)
    a = ap.parse_args()

    cible = os.environ.get("CARGO_TARGET_DIR", str(Path.home() / "evr-target"))
    outil = Path(a.outil or f"{cible}/release/examples/banc_primitives")
    binaire = Path(a.binaire or f"{cible}/release/evidence-verify-rs")
    for p, quoi in ((outil, "cargo build --release --example banc_primitives"),
                    (binaire, "bash verifier-rs/banc/build.sh")):
        if not p.exists():
            print("absent : %s\n  lancer : %s" % (p, quoi), file=sys.stderr)
            return 2

    travail = Path(os.environ.get("TMPDIR", "/tmp")) / "evr-fuzz"
    print("=== DEFLATE contre zlib : %d tours, graine %d ==="
          % (a.tours, a.graine))
    d = campagne_deflate(outil, a.graine, a.tours)
    print("  duree %.1fs | acceptes rust=%d zlib=%d | anomalies=%d | lents=%d"
          % (d["duree_s"], d["acceptes_rust"], d["acceptes_zlib"],
             len(d["anomalies"]), len(d["entrees_lentes"])))
    print("  octets en trop apres le bloc final, ignores des deux cotes : %d"
          % d["octets_en_trop_ignores_des_deux_cotes"])
    if d["anomalies"]:
        print("  genres :", dict(Counter(x["genre"] for x in d["anomalies"])))

    print("\n=== JSON contre `json` : %d tours, graine %d ==="
          % (a.tours_json, a.graine + 1))
    j = campagne_json(binaire, a.graine + 1, a.tours_json, travail)
    print("  duree %.1fs | lu par rust=%d par python=%d | anomalies=%d | lents=%d"
          % (j["duree_s"], j["json_lu_par_rust"], j["json_lu_par_python"],
             len(j["anomalies"]), len(j["entrees_lentes"])))
    print("  divergences DECLAREES exclues :", j["divergences_DECLAREES_exclues"])
    if j["anomalies"]:
        print("  genres :", dict(Counter(x["genre"] for x in j["anomalies"])))

    total = len(d["anomalies"]) + len(j["anomalies"])
    print("\nanomalies au total : %d" % total)
    print("Rappel : 0 anomalie n est PAS une preuve de securite. C est")
    print("l absence de contre-exemple sur ce corpus, cette graine et ce")
    print("nombre de tours.")
    if a.sortie:
        Path(a.sortie).write_text(
            json.dumps({"graine": a.graine, "deflate": d, "json": j},
                       indent=2, ensure_ascii=False), encoding="utf-8")
        print("rapport machine : %s" % a.sortie)
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
