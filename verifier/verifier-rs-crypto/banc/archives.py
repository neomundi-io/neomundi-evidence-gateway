#!/usr/bin/env python3
"""Banc différentiel des ARCHIVES Evidence — `verify.py` contre Rust.

CE QUE CE BANC COMPARE, ET CE QU'IL NE COMPARE PAS
--------------------------------------------------
Les deux vérificateurs n'implémentent **pas le même nombre de contrôles**,
et c'est déclaré : Rust en couvre un sous-ensemble, documenté en
`COMPLETUDE_RUST_EVIDENCE/04_ARCHIVES_RUST.md`. Comparer les totaux
`PASS`/`FAIL` n'aurait donc aucun sens.

Ce banc compare ce qui est comparable :

  1. le VERDICT global — accepté contre refusé ;
  2. les contrôles COMMUNS, un par un, par leur intitulé ;
  3. l'empreinte de l'archive, qui doit être identique à l'octet ;
  4. les trois lignes que les deux déclarent HORS DE PORTÉE.

Et il compte séparément les contrôles que l'un exécute et l'autre pas :
c'est une COUVERTURE partielle, pas une divergence.

LES ATTENTES NE VIENNENT PAS DE PYTHON
--------------------------------------
Pour le témoin, elles viennent de `examples/dossier-v1/attendu.json`, source
de vérité du dépôt ANTÉRIEURE à ce banc. Pour les cas adversariaux, elles
viennent de la propriété qu'on altère : qui change un octet d'un membre
attend un refus sur l'empreinte de ce membre.

Hors ligne. Aucun accès à la production.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
DOSSIER = RACINE / "examples" / "dossier-v1"

#: Les intitulés que les DEUX vérificateurs produisent. Comparer par
#: intitulé, et non par position : l'ordre n'est fixé par aucun contrat.
COMMUNS = (
    "aucun membre ne sort du repertoire cible",
    "integrite interne du ZIP",
    "chaque membre est couvert par une empreinte",
    "aucun orphelin dans measurements.jsonl",
    "aucun orphelin dans reference_evaluations.jsonl",
    "aucun orphelin dans replay_provenance.jsonl",
    "les absences declarees sont reelles",
    "completude de l export",
    "origine et horodatage de l archive",
)

#: Les intitulés qui désignent le MÊME contrôle sous deux libellés.
#:
#: Les deux vérificateurs ont été rédigés séparément, et leur prose n'est
#: fixée par aucun contrat. Apparier par libellé exact ferait compter comme
#: « exclusif » un contrôle que les deux exécutent — ce qui sous-estimerait
#: l'accord. La correspondance est donc DÉCLARÉE, et non devinée.
CORRESPONDANCES = {
    "chainage JCS": "chainage canonique du registre d origine",
}

#: Les intitulés dont le libellé porte un décompte variable : on compare la
#: TÊTE de l'intitulé, pas le nombre.
COMMUNS_PREFIXES = (
    "membres attendus par le schema",
    # `"empreintes des"` seul etait AMBIGU : il attrapait aussi
    # `empreintes des entrees rejouees`, exclusif a Python, et lisait son
    # etat comme celui des empreintes de membres. Correction d instrument :
    # trois faux desaccords venaient de la.
    "empreintes des membres declares",
    "le manifeste compte les observations livrees",
    "le manifeste compte les enregistrements de measurements.jsonl",
    "le manifeste compte les enregistrements de reference_evaluations.jsonl",
    "le manifeste compte les enregistrements de replay_provenance.jsonl",
)


def lancer(cmd, timeout=300):
    try:
        x = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout,
                           env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        return x.returncode, x.stdout or "", x.stderr or ""
    except subprocess.TimeoutExpired:
        return "DELAI", "", ""


def lignes_de(sortie: str) -> dict[str, str]:
    """intitulé -> état. L'intitulé est ce qui précède le premier ` - `."""
    out: dict[str, str] = {}
    for ligne in sortie.splitlines():
        if not ligne.startswith("["):
            continue
        etat = ligne[1:ligne.index("]")].strip()
        tete = ligne.rsplit("] ", 1)[-1]
        intitule = tete.split(" - ", 1)[0].strip()
        out.setdefault(intitule, etat)
    return out


def apparier(py: dict[str, str], rs: dict[str, str]):
    """Rend (communs, seulement_python, seulement_rust).

    `communs` est une table intitulé -> (etat_py, etat_rs)."""
    communs: dict[str, tuple[str, str]] = {}
    vus_py, vus_rs = set(), set()

    def chercher(table, cible):
        if cible in table:
            return cible
        for k in table:
            if k.startswith(cible):
                return k
        # Un libelle a decompte variable : `empreintes des 7 membres
        # declares`. On cherche alors sur les mots, dans l ordre.
        mots = cible.split()
        for k in table:
            reste = k
            if all((p := reste.find(m)) >= 0 and (reste := reste[p + len(m):], True)[1]
                   for m in mots):
                return k
        return None

    for cible in COMMUNS + COMMUNS_PREFIXES:
        kp, kr = chercher(py, cible), chercher(rs, cible)
        if kp and kr:
            communs[cible] = (py[kp], rs[kr])
            vus_py.add(kp)
            vus_rs.add(kr)
    # Les libelles DIFFERENTS qui designent le meme controle.
    for cote_py, cote_rs in CORRESPONDANCES.items():
        kp, kr = chercher(py, cote_py), chercher(rs, cote_rs)
        if kp and kr and kp not in vus_py and kr not in vus_rs:
            communs["%s = %s" % (cote_py, cote_rs)] = (py[kp], rs[kr])
            vus_py.add(kp)
            vus_rs.add(kr)
    return (communs,
            sorted(k for k in py if k not in vus_py),
            sorted(k for k in rs if k not in vus_rs))


def mesurer(nom: str, risque: str, attente: str, archive: Path,
            binaire: Path, corpus: Path | None = None) -> dict:
    cmd_py = [sys.executable, "-B", str(RACINE / "verify.py"), str(archive)]
    if corpus is not None:
        cmd_py += ["--corpus", str(corpus)]
    cp, op, _ = lancer(cmd_py)
    cr, orr, er = lancer([str(binaire), "--archive", str(archive)])

    lp, lr = lignes_de(op), lignes_de(orr)
    communs, seul_py, seul_rs = apparier(lp, lr)
    desaccords = {k: v for k, v in communs.items() if v[0] != v[1]}

    verdict_py = "REJETE" if any(e == "FAIL" for e in lp.values()) else "ACCEPTE"
    verdict_rs = next((l.split(":", 1)[1].strip()
                       for l in orr.splitlines() if l.startswith("VERDICT")),
                      None)
    emp_py = next((l.split(":", 1)[1].strip() for l in op.splitlines()
                   if "empreinte de l archive" in l), None)
    emp_rs = next((l.split(":", 1)[1].strip() for l in orr.splitlines()
                   if l.startswith("empreinte")), None)

    verdict_rs_norm = "REJETE" if verdict_rs == "REJETE" else "ACCEPTE"
    conforme = verdict_rs_norm == attente
    print("%-28s attendu=%-9s rust=%-9s py=%-9s communs %d/%d  seul_py=%d seul_rs=%d %s"
          % (nom, attente, verdict_rs_norm, verdict_py,
             len(communs) - len(desaccords), len(communs),
             len(seul_py), len(seul_rs),
             "" if conforme else "  <<< HORS ATTENTE"))
    if desaccords:
        print("      controles communs en desaccord : %s" % desaccords)
    if emp_py and emp_rs and emp_py != emp_rs:
        print("      EMPREINTES DIFFERENTES : py=%s rs=%s" % (emp_py, emp_rs))
    if cr == 3:
        print("      rust stderr : %s" % er.strip().splitlines()[:1])

    return {"id": nom, "risque": risque, "attente": attente,
            "rust": {"verdict": verdict_rs_norm, "code": cr, "empreinte": emp_rs},
            "python": {"verdict": verdict_py, "code": cp, "empreinte": emp_py},
            "communs": {k: list(v) for k, v in communs.items()},
            "desaccords": {k: list(v) for k, v in desaccords.items()},
            "seulement_python": seul_py,
            "seulement_rust": seul_rs,
            "conforme": conforme,
            "empreintes_identiques": emp_py == emp_rs}


def muter_zip(source: Path, cible: Path, mutation) -> Path:
    """Recopie une archive membre par membre, en appliquant `mutation`.

    `mutation(nom, octets)` rend les nouveaux octets, ou `None` pour retirer
    le membre. L'ordre des membres est conservé.
    """
    with zipfile.ZipFile(source) as z:
        infos = z.infolist()
        contenus = [(i, z.read(i.filename)) for i in infos]
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_STORED) as w:
        for i, octets in contenus:
            nouveaux = mutation(i.filename, octets)
            if nouveaux is None:
                continue
            w.writestr(i.filename, nouveaux)
    cible.write_bytes(tampon.getvalue())
    return cible


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--binaire", default=None)
    ap.add_argument("--json", dest="sortie", default=None)
    a = ap.parse_args()

    cible = os.environ.get("CARGO_TARGET_DIR_CRYPTO",
                           str(Path.home() / "evc-target"))
    binaire = Path(a.binaire or f"{cible}/release/evidence-verify-crypto")
    if not binaire.exists():
        print("binaire absent : %s" % binaire, file=sys.stderr)
        return 2

    travail = Path(os.environ.get("TMPDIR", "/tmp")) / "evc-archives"
    shutil.rmtree(travail, ignore_errors=True)
    travail.mkdir(parents=True)

    reelle = DOSSIER / "NEOMUNDI_EVIDENCE_V1_DEMO.zip"
    res = []

    print("%-28s %-18s %-14s %-14s %s"
          % ("cas", "attendu", "rust", "python", "communs / exclusifs"))
    print("-" * 132)

    # ---- 1. le TEMOIN : l archive REELLE du depot -----------------------
    attendu_depot = json.loads((DOSSIER / "attendu.json").read_bytes())
    res.append(mesurer(
        "reel-dossier-v1",
        "l archive REELLE du depot doit etre acceptee par les deux",
        "ACCEPTE", reelle, binaire, DOSSIER / "corpus"))
    # L empreinte doit etre celle que le depot publie, ANTERIEUREMENT a ce banc.
    emp_publiee = attendu_depot["empreintes"]["archive"]
    emp_mesuree = hashlib.sha256(reelle.read_bytes()).hexdigest()
    print("      empreinte publiee par le depot : %s" % emp_publiee)
    print("      empreinte recalculee ici       : %s  %s"
          % (emp_mesuree, "IDENTIQUE" if emp_publiee == emp_mesuree else "DIFFERENTE"))
    assert emp_publiee == emp_mesuree, "l archive du depot a change"

    # ---- 2. un OCTET d un membre modifie --------------------------------
    res.append(mesurer(
        "membre-altere",
        "un octet de `rapport.md` modifie : l empreinte declaree ne tient plus",
        "REJETE",
        muter_zip(reelle, travail / "membre-altere.zip",
                  lambda n, o: o + b"x" if n == "rapport.md" else o),
        binaire))

    # ---- 3. un membre RETIRE --------------------------------------------
    res.append(mesurer(
        "membre-retire",
        "`rapport.md` retire : le schema l attend, et son empreinte est declaree",
        "REJETE",
        muter_zip(reelle, travail / "membre-retire.zip",
                  lambda n, o: None if n == "rapport.md" else o),
        binaire))

    # ---- 4. un membre AJOUTE, non couvert -------------------------------
    def ajouter(source: Path, cible: Path, nom: str, octets: bytes) -> Path:
        with zipfile.ZipFile(source) as z:
            contenus = [(i.filename, z.read(i.filename)) for i in z.infolist()]
        tampon = io.BytesIO()
        with zipfile.ZipFile(tampon, "w", zipfile.ZIP_STORED) as w:
            for n, o in contenus:
                w.writestr(n, o)
            w.writestr(nom, octets)
        cible.write_bytes(tampon.getvalue())
        return cible

    res.append(mesurer(
        "membre-non-couvert",
        "un fichier ajoute apres l export : aucune empreinte ne le couvre",
        "REJETE",
        ajouter(reelle, travail / "membre-non-couvert.zip",
                "clandestin.txt", b"ajoute apres l export"),
        binaire))

    # ---- 5. le MANIFESTE altere : un decompte faux ----------------------
    def manifeste_mute(cle_chemin, valeur):
        def f(n, o):
            if n != "manifest.json":
                return o
            d = json.loads(o)
            cur = d
            for c in cle_chemin[:-1]:
                cur = cur[c]
            cur[cle_chemin[-1]] = valeur
            return json.dumps(d, indent=2, ensure_ascii=False,
                              sort_keys=True).encode("utf-8")
        return f

    # Note : alterer le manifeste casse AUSSI son empreinte declaree. Les
    # deux refus sont legitimes, et le banc compare les CONTROLES, pas
    # seulement le verdict.
    res.append(mesurer(
        "decompte-faux",
        "`decomptes.observations` annonce 99 au lieu de 4",
        "REJETE",
        muter_zip(reelle, travail / "decompte-faux.zip",
                  manifeste_mute(["decomptes", "observations"], 99)),
        binaire))

    res.append(mesurer(
        "schema-inconnu",
        "`schema` annonce une version d export inconnue",
        "REJETE",
        muter_zip(reelle, travail / "schema-inconnu.zip",
                  manifeste_mute(["schema"], "station.export.campagne/99")),
        binaire))

    # ---- 6. `checksums.sha256` altere -----------------------------------
    res.append(mesurer(
        "checksums-altere",
        "une empreinte declaree est remplacee par des zeros",
        "REJETE",
        muter_zip(reelle, travail / "checksums-altere.zip",
                  lambda n, o: (
                      b"\n".join(
                          (b"0" * 64 + b"  manifest.json") if b"manifest.json" in l
                          else l
                          for l in o.split(b"\n")) if n == "checksums.sha256" else o)),
        binaire))

    # ---- 7. un ORPHELIN : une mesure sans observation -------------------
    def orpheliner(n, o):
        if n != "measurements.jsonl":
            return o
        lignes = [l for l in o.split(b"\n") if l.strip()]
        d = json.loads(lignes[0])
        # LE VRAI CHAMP DE LIAISON : `payload.observation_id`.
        #
        # CORRECTION DE FIXTURE. La premiere version alterait
        # `observation_record_id`, un champ que ce format NE PORTE PAS -- il
        # vaut `null` dans l archive reelle. Le cas ne fabriquait donc aucun
        # orphelin pour Python, et un orphelin fictif pour Rust : la
        # divergence observee venait entierement de la fixture.
        d["payload"]["observation_id"] = "obs-inexistante"
        lignes[0] = json.dumps(d, sort_keys=True,
                               separators=(",", ":")).encode("utf-8")
        return b"\n".join(lignes) + b"\n"

    res.append(mesurer(
        "orphelin-mesure",
        "une mesure refere une observation absente du registre livre",
        "REJETE",
        muter_zip(reelle, travail / "orphelin.zip", orpheliner), binaire))

    # ---- 8. entrees hostiles : le code doit rester dans le contrat ------
    for nom, octets in (
        ("vide", b""),
        ("pas-un-zip", b"\x00" * 2048),
        ("zip-sans-manifeste", None),
    ):
        chemin = travail / f"hostile-{nom}.zip"
        if octets is None:
            tampon = io.BytesIO()
            with zipfile.ZipFile(tampon, "w") as w:
                w.writestr("autre.txt", b"rien")
            chemin.write_bytes(tampon.getvalue())
        else:
            chemin.write_bytes(octets)
        res.append(mesurer(
            f"hostile-{nom}",
            "entree hostile : refus propre, code dans {0,1,2,3}",
            "REJETE", chemin, binaire))

    # ---- bilan -----------------------------------------------------------
    print()
    conformes = sum(1 for r in res if r["conforme"])
    desaccords = [r for r in res if r["desaccords"]]
    verdicts_divergents = [r for r in res
                           if r["rust"]["verdict"] != r["python"]["verdict"]]
    codes_hors = [r for r in res if r["rust"]["code"] not in (0, 1, 2, 3)]
    empreintes_ok = sum(1 for r in res if r["empreintes_identiques"])
    total_communs = sum(len(r["communs"]) for r in res)
    total_accord = sum(len(r["communs"]) - len(r["desaccords"]) for r in res)

    print("cas executes                           : %d" % len(res))
    print("conformes a l attente ECRITE d avance   : %d / %d" % (conformes, len(res)))
    print("verdicts globaux identiques             : %d / %d"
          % (len(res) - len(verdicts_divergents), len(res)))
    print("controles COMMUNS en accord             : %d / %d"
          % (total_accord, total_communs))
    print("empreintes d archive identiques         : %d / %d"
          % (empreintes_ok, len(res)))
    print("codes de sortie hors du contrat         : %d" % len(codes_hors))
    if verdicts_divergents:
        for r in verdicts_divergents:
            print("  VERDICT : %-26s rust=%s python=%s"
                  % (r["id"], r["rust"]["verdict"], r["python"]["verdict"]))
    if desaccords:
        for r in desaccords:
            print("  COMMUN  : %-26s %s" % (r["id"], r["desaccords"]))
    print()
    print("COUVERTURE : Rust implemente un SOUS-ENSEMBLE declare des controles")
    print("de `verify.py`. Les contoles exclusifs a chacun sont comptes, non")
    print("presentes comme des divergences. Voir 04_ARCHIVES_RUST.md.")
    if res:
        print("  controles seulement Python (temoin) : %s"
              % res[0]["seulement_python"])
        print("  controles seulement Rust  (temoin) : %s"
              % res[0]["seulement_rust"])

    if a.sortie:
        Path(a.sortie).write_text(
            json.dumps({"total": len(res), "conformes": conformes,
                        "verdicts_divergents": [r["id"] for r in verdicts_divergents],
                        "controles_communs_en_accord": total_accord,
                        "controles_communs": total_communs,
                        "cas": res}, indent=2, ensure_ascii=False),
            encoding="utf-8")
        print("\nrapport machine : %s" % a.sortie)

    return 1 if (conformes != len(res) or desaccords or codes_hors) else 0


if __name__ == "__main__":
    raise SystemExit(main())
