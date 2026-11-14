#!/usr/bin/env python3
"""Banc de conformité Evidence — exécute le corpus figé contre un vérificateur.

    python conformance/runners/run.py --verifier python
    python conformance/runners/run.py --verifier rust-core   --bin <chemin>
    python conformance/runners/run.py --verifier rust-crypto --bin <chemin>
    python conformance/runners/run.py --verifier all --json rapport.json

CE QUE CE PROGRAMME NE FAIT PAS
===============================

  - il ne **régénère jamais** les fixtures : il vérifie leurs empreintes et
    s'arrête si elles ont bougé ;
  - il ne **dérive aucune attente** d'une exécution : les attentes vivent
    dans `conformance/expected/`, écrites avant que le moindre vérificateur
    n'ait tourné ;
  - il n'appelle **ni l'API NeoMundi, ni Station, ni aucun service distant**.
    Tout est local et hors ligne.

LES SEPT ÉTATS, ET CE QU'ILS NE SONT PAS
========================================

    PASS            le comportement observé est celui que la fiche attend
    FAIL            il le contredit
    NOT TESTED      le contrôle n'a pas été exécuté par ce vérificateur
    NOT APPLICABLE  le cas ne s'adresse pas à ce vérificateur
    NOT RUNNABLE    le cas s'adresse bien à ce vérificateur, mais un
                    PRÉREQUIS de l'environnement manque : il n'a pas pu être
                    éprouvé, et ce n'est ni une réussite ni un échec de
                    conformité
    AMBIGUOUS       le contrat ne permet pas d'imposer un résultat unique
    ERROR           une erreur technique empêche de conclure

**`NOT RUNNABLE` n'est PAS `NOT APPLICABLE`.** `NOT APPLICABLE` dit que le
vérificateur n'annonce pas ce sujet — le lui reprocher serait une mesure
fausse. `NOT RUNNABLE` dit l'inverse : il l'annonce, et c'est la machine qui
ne porte pas ce qu'il lui faut. Les confondre ferait disparaître un défaut
d'installation dans un dénominateur, là où il doit être lu et corrigé.

**`AMBIGUOUS` est un état de ce banc, pas un verdict du protocole.** Aucun
vérificateur ne rend « AMBIGU » : c'est ce rapport qui refuse de trancher là
où le contrat est muet.

Et la règle qui compte le plus :

    UN REFUS ATTENDU EST UNE RÉUSSITE.

Un vérificateur qui refuse correctement un paquet malformé **réussit** le
test de conformité correspondant. Confondre les deux produirait un taux de
« conformité » qui récompenserait la permissivité.

LES CODES DE SORTIE
===================

Comparés **séparément** du verdict sémantique. Un code peut légitimement
différer d'un vérificateur à l'autre — `--strict` en est un exemple
contractuel — alors que le verdict, lui, doit concorder. Les deux sont donc
mesurés, et un écart de code sur un verdict concordant est rapporté comme
tel, non comme un échec de conformité.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

CORPUS = Path(__file__).resolve().parent.parent
RACINE = CORPUS.parent

PASS, FAIL = "PASS", "FAIL"
#: Un septieme etat, et il n est pas dans la liste de la mission : il la SERT.
#:
#: `KNOWN FAIL` designe un echec CONSTATE et DECLARE dans
#: `conformance/known_failures.json`. Sans lui, la seule facon de rendre la
#: CI verte serait de RETIRER le cas du corpus -- c est-a-dire de supprimer
#: la mesure qui derange. Avec lui, l echec reste VISIBLE a chaque execution,
#: et seule une regression NOUVELLE fait rougir la CI.
ECHEC_CONNU = "KNOWN FAIL"
NON_TESTE, NON_APPLICABLE = "NOT TESTED", "NOT APPLICABLE"
AMBIGU, ERREUR = "AMBIGUOUS", "ERROR"
#: Un PREREQUIS de l environnement manque. Distinct de `NOT APPLICABLE` :
#: voir l en-tete. Signale par Olusanya Timothy le 2026-11-13 -- le banc
#: rapportait une dependance absente comme une REGRESSION du verificateur.
NON_EXECUTABLE = "NOT RUNNABLE"

#: La CLASSIFICATION d une execution, qui n est pas son etat de conformite.
#:
#: L etat (`PASS`/`FAIL`/...) dit si l observation concorde avec la fiche.
#: La classification dit ce que l outil a repondu, et elle distingue les
#: quatre situations que le CODE DE SORTIE seul confond -- c est tout le
#: sujet de `docs/INTEGRATION.md`.
CL_ACCEPTE, CL_REJETE = "ACCEPTE", "REJETE"
CL_INCOMPLET, CL_NON_EXECUTABLE = "INCOMPLET", "NON EXECUTABLE"

#: Quel vérificateur sait traiter quel sujet.
#:
#: `rust-core` ne connaît QUE le paquet de soumission : l'archive et
#: l'attestation sont le périmètre de `rust-crypto`. Un cas hors du
#: périmètre d'un vérificateur rend `NOT APPLICABLE`, jamais `FAIL` —
#: reprocher à un outil de ne pas faire ce qu'il n'annonce pas serait une
#: mesure fausse.
PERIMETRES = {
    "python":      {"submission", "archive", "attestation"},
    "rust-core":   {"submission"},
    "rust-crypto": {"archive", "attestation"},
}


def sha(octets: bytes) -> str:
    return hashlib.sha256(octets).hexdigest()


def charger_echecs_connus() -> dict:
    """(cas, verificateur) -> l entree declaree."""
    f = CORPUS / "known_failures.json"
    if not f.is_file():
        return {}
    d = json.loads(f.read_bytes())
    return {(e["case"], e["verifier"]): e for e in d.get("failures", [])}


# --------------------------------------------------------------------------
# Intégrité du corpus — avant toute exécution
# --------------------------------------------------------------------------


def verifier_corpus() -> tuple[bool, list[str]]:
    """Les empreintes de `SHA256SUMS` sont-elles celles des fichiers ?

    C'est le premier contrôle, et il est bloquant : un corpus dont les octets
    ont bougé ne mesure plus ce que ses fiches annoncent.
    """
    sommes = CORPUS / "SHA256SUMS"
    if not sommes.is_file():
        return False, ["SHA256SUMS absent"]
    ecarts = []
    n = 0
    for ligne in sommes.read_text(encoding="utf-8").splitlines():
        if not ligne.strip():
            continue
        attendue, _, chemin = ligne.partition("  ")
        cible = CORPUS / chemin
        if not cible.is_file():
            ecarts.append("absent : %s" % chemin)
            continue
        reelle = sha(cible.read_bytes())
        n += 1
        if reelle != attendue:
            ecarts.append("empreinte differente : %s" % chemin)
    return (not ecarts), (ecarts or ["%d fichier(s) verifie(s)" % n])


# --------------------------------------------------------------------------
# Lancement d'un vérificateur
# --------------------------------------------------------------------------


def lancer(cmd: list[str], timeout=300) -> dict:
    try:
        x = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout,
                           env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        return {"code": x.returncode, "stdout": x.stdout or "",
                "stderr": x.stderr or "", "timeout": False}
    except subprocess.TimeoutExpired:
        return {"code": None, "stdout": "", "stderr": "", "timeout": True}


def dossier_du_cas(fiche: dict) -> Path:
    return (CORPUS / fiche["files"][0]["path"]).parent


def entree_du_cas(fiche: dict, nom: str) -> Path | None:
    for f in fiche["files"]:
        if Path(f["path"]).name == nom:
            return CORPUS / f["path"]
    return None


def construire_commande(fiche: dict, verificateur: str, binaires: dict,
                        travail: Path, strict: bool) -> list[str] | None:
    sujet = fiche["subject"]
    options = list(fiche.get("options", []))
    rapport = travail / ("%s.%s.json" % (fiche["id"], verificateur))

    if sujet == "submission":
        # Un cas de soumission est soit un DOSSIER, soit un seul `.zip`.
        zip_ = entree_du_cas(fiche, "paquet.zip")
        cible = zip_ if zip_ is not None else dossier_du_cas(fiche)
        if verificateur == "python":
            cmd = [sys.executable, "-B", str(RACINE / "adapters/ingest.py"),
                   str(cible), "--out", str(rapport), "--lang", "fr"]
        elif verificateur == "rust-core":
            cmd = [binaires["rust-core"], str(cible), "--json", str(rapport)]
        else:
            return None
        return cmd + (["--strict"] if strict else [])

    if sujet == "archive":
        archive = entree_du_cas(fiche, "archive.zip")
        if archive is None:
            return None
        if verificateur == "python":
            # `--strict` etait PERDU ici, comme sur le chemin d attestation
            # ci-dessous : le banc comparait alors `exit_code_strict` a un
            # outil lance en mode NON strict. Les deux seules attentes que
            # ce silence masquait -- `A-05` et `F-03` -- sont corrigees dans
            # le corpus 1.3.0.
            return ([sys.executable, "-B", str(RACINE / "verify.py"),
                     str(archive)]
                    + (["--strict"] if strict else []))
        if verificateur == "rust-crypto":
            return ([binaires["rust-crypto"], "--archive", str(archive),
                     "--json", str(rapport)]
                    + (["--strict"] if strict else []))
        return None

    if sujet == "attestation":
        att = entree_du_cas(fiche, "attestation.jws")
        archive = entree_du_cas(fiche, "archive.zip")
        magasin = entree_du_cas(fiche, "trust-store.json")
        if att is None:
            return None
        if verificateur == "python":
            cmd = [sys.executable, "-B",
                   str(RACINE / "verify_attestation.py"), str(att),
                   "--lang", "fr"]
            if archive:
                cmd += ["--archive", str(archive)]
            if magasin:
                cmd += ["--trust-store", str(magasin)]
            # `--json` : le rapport STRUCTURE plutot que la prose. Il porte
            # `counts`, `required_not_demonstrated` et `attained_level`,
            # donc de quoi distinguer un refus d une verification
            # INCOMPLETE -- ce que le code de sortie seul ne permet pas.
            cmd += ["--json", str(rapport)]
            return cmd + options + (["--strict"] if strict else [])
        if verificateur == "rust-crypto":
            cmd = [binaires["rust-crypto"], "--attestation", str(att),
                   "--json", str(rapport)]
            if archive:
                cmd += ["--archive", str(archive)]
            if magasin:
                cmd += ["--trust-store", str(magasin)]
            return cmd + options + (["--strict"] if strict else [])
        return None

    return None


# --------------------------------------------------------------------------
# Lecture de ce qu'un vérificateur a répondu
# --------------------------------------------------------------------------


def verdict_observe(sortie: dict, fiche: dict, verificateur: str,
                    travail: Path) -> dict:
    """Le verdict et le niveau, lus du rapport structuré si possible.

    Le rapport JSON est préféré à la prose : il est stable, et la prose est
    traduite. Pour `verify.py` et `verify_attestation.py`, qui n'écrivent pas
    de rapport sur ce chemin, on lit la sortie lisible — et on le dit.
    """
    rapport = travail / ("%s.%s.json" % (fiche["id"], verificateur))
    source = "prose"
    verdict = None
    niveau = None
    structure = None

    if rapport.is_file():
        try:
            d = json.loads(rapport.read_bytes())
            structure = d
            verdict = d.get("verdict")
            niveau = d.get("attested_level")
            source = "rapport structure"
        except ValueError:
            source = "rapport ILLISIBLE"

    # `verify.py` et `verify_attestation.py` ecrivent un rapport dont le
    # VOCABULAIRE n est pas celui des fiches : le premier rend
    # `verdict: "no_failure"`, le second n a pas de champ `verdict` du tout.
    # Lire ces jetons tels quels ferait echouer des cas conformes ; on les
    # ecarte ici, et le verdict est derive plus bas.
    if verdict is not None and verdict not in ("ACCEPTE", "REJETE",
                                               "INCOMPLET"):
        verdict = None

    texte = sortie["stdout"]
    if verdict is None:
        for ligne in texte.splitlines():
            if ligne.startswith("VERDICT"):
                verdict = ligne.split(":", 1)[1].strip()
                break
    if verdict is None and fiche["subject"] == "archive":
        # `verify.py` ne rend pas de ligne VERDICT : son verdict se lit à
        # l'absence de FAIL. C'est documenté dans son en-tête.
        a_fail = any(l.startswith("[FAIL") for l in texte.splitlines())
        if "BILAN" in texte:
            verdict = "REJETE" if a_fail else "ACCEPTE"
            source = "derive de l absence de FAIL (verify.py)"
    if verdict is None and fiche["subject"] == "attestation"             and verificateur == "python":
        # CORRECTION D INSTRUMENT.
        #
        # `verify_attestation.py` ne rend PAS de verdict : il rend un
        # NIVEAU (`Niveau atteint : ...`). C est une difference de SURFACE
        # entre les deux outils, pas une divergence : l un repond
        # << a quel niveau cette attestation est-elle etablie >>, l autre
        # << ce paquet est-il accepte >>.
        #
        # Le premier passage du banc lisait un verdict absent et rendait six
        # faux echecs. La grandeur comparable est le NIVEAU.
        #
        # CORRECTION DU 2026-11-13. Le verdict etait derive du CODE DE
        # SORTIE : `REJETE if code == 1 else ACCEPTE`. Deux defauts.
        #
        #   1. le code 2 -- garantie REQUISE non demontree sous `--strict` --
        #      tombait dans le `else`, donc en ACCEPTE. Une verification
        #      INCOMPLETE etait lue comme une acceptation ;
        #   2. `docs/INTEGRATION.md` ouvre sur << ne lisez pas le code de
        #      sortie par defaut >>. Le banc du depot faisait exactement ce
        #      que le depot interdit a ses integrateurs.
        #
        # Le verdict se derive maintenant du DECOMPTE DE FAIL -- la meme
        # grandeur que sur le chemin d archive. Aucun verdict fige ne
        # change : les cas qui rendaient 1 portent une ligne FAIL, ceux qui
        # rendaient 0 n en portent pas.
        if structure is not None and isinstance(structure.get("counts"), dict):
            verdict = "REJETE" if structure["counts"].get("fail", 0) else "ACCEPTE"
            source = ("derive de counts.fail du rapport structure "
                      "(verify_attestation.py rend un NIVEAU, pas un verdict)")
        elif "BILAN" in texte:
            a_fail = any(l.startswith("[FAIL") for l in texte.splitlines())
            verdict = "REJETE" if a_fail else "ACCEPTE"
            source = ("derive de l absence de FAIL dans la prose -- aucun "
                      "rapport structure ecrit")
    if niveau is None and "cryptographically_attested" in texte:
        niveau = "cryptographically_attested"

    # LES QUATRE SITUATIONS QUE LE CODE DE SORTIE CONFOND.
    #
    # Publiees a cote du verdict, jamais a sa place : l etat de conformite
    # se compare a la fiche, la classification DECRIT l execution. Un
    # integrateur qui ne lit qu un code non nul n est pas induit en erreur ;
    # un lecteur de ce rapport, lui, voit la difference.
    requises = (structure or {}).get("required_not_demonstrated") or []
    if verdict == "REJETE":
        classification = CL_REJETE
    elif requises:
        classification = CL_INCOMPLET
    else:
        classification = CL_ACCEPTE

    return {"verdict": verdict, "attested_level": niveau,
            "exit_code": sortie["code"], "lu_depuis": source,
            "rapport_ecrit": rapport.is_file(),
            "classification": classification,
            "required_not_demonstrated": requises}


# --------------------------------------------------------------------------
# Comparaison
# --------------------------------------------------------------------------


def comparer(fiche: dict, verificateur: str, observe: dict,
             strict: bool) -> dict:
    attendu = dict(fiche["expected"])
    # UNE ATTENTE PAR VERIFICATEUR, QUAND ELLE EST JUSTIFIEE.
    #
    # Les deux outils n ont pas la meme surface : `verify_attestation.py`
    # rend un niveau, `evidence-verify-crypto` rend un verdict ET un niveau,
    # et son verdict devient INCOMPLET quand une ligne REQUISE n est pas
    # demontree -- ce que Python ne modelise pas.
    #
    # La fiche peut donc porter `expected_by_verifier`, qui SURCHARGE
    # l attente commune. C est une difference DECLAREE, pas une tolerance :
    # chaque surcharge porte sa raison dans la fiche.
    surcharge = (fiche.get("expected_by_verifier") or {}).get(verificateur)
    if isinstance(surcharge, dict):
        attendu.update(surcharge)

    if attendu.get("ambiguous"):
        # Le contrat est muet : ce banc ne tranche pas. Si la fiche porte une
        # attente PAR VERIFICATEUR -- un comportement observé et déclaré --,
        # elle est confrontée, mais l'état reste AMBIGU.
        par_verif = attendu.get(verificateur)
        note = attendu.get("note", "")
        detail = "le contrat ne permet pas d imposer un resultat unique"
        if isinstance(par_verif, dict):
            concorde = observe["verdict"] == par_verif.get("verdict")
            detail = ("comportement declare %s, observe %s -- %s"
                      % (par_verif.get("verdict"), observe["verdict"],
                         "conforme au declare" if concorde
                         else "DIFFERENT du declare"))
        return {"etat": AMBIGU, "detail": detail, "note": note}

    cle_code = "exit_code_strict" if strict else "exit_code"
    verdict_attendu = attendu.get("verdict")
    code_attendu = attendu.get(cle_code)
    niveau_attendu = attendu.get("attested_level", "__absent__")

    problemes = []
    if verdict_attendu is not None and observe["verdict"] != verdict_attendu:
        problemes.append("verdict attendu %s, observe %s"
                         % (verdict_attendu, observe["verdict"]))
    if niveau_attendu != "__absent__" and observe["attested_level"] != niveau_attendu:
        problemes.append("niveau attendu %r, observe %r"
                         % (niveau_attendu, observe["attested_level"]))

    ecart_code = None
    if code_attendu is not None and observe["exit_code"] != code_attendu:
        ecart_code = ("code attendu %s, observe %s"
                      % (code_attendu, observe["exit_code"]))

    if problemes:
        return {"etat": FAIL, "detail": " ; ".join(problemes),
                "ecart_code": ecart_code}
    if ecart_code:
        # Le VERDICT concorde, le CODE non. Rapporté comme un écart de code,
        # pas comme un échec de conformité sémantique.
        return {"etat": PASS, "detail": "verdict conforme",
                "ecart_code": ecart_code}
    return {"etat": PASS, "detail": "verdict et code conformes",
            "ecart_code": None}


# --------------------------------------------------------------------------


def cryptography_disponible() -> bool:
    """`cryptography` est-elle importable par l interpreteur qui verifiera ?

    Mesuree sur `sys.executable`, et non par un `import` dans ce programme :
    c est l autre processus qui en a besoin, et rien ne garantit que les deux
    partagent leurs paquets.
    """
    r = subprocess.run([sys.executable, "-c", "import cryptography"],
                       capture_output=True)
    return r.returncode == 0


#: Les prerequis par (verificateur, sujet). Un prerequis absent rend
#: `NOT RUNNABLE`, jamais `FAIL` : une bibliotheque manquante sur la machine
#: n est pas une non-conformite du vérificateur.
def prerequis_absent(verificateur: str, sujet: str, crypto: bool) -> str | None:
    if verificateur == "python" and sujet == "attestation" and not crypto:
        return ("`cryptography` est absente de l environnement de %s. "
                "`verify_attestation.py` rend alors `NOT TESTED` sur le "
                "pilier `signature cryptographique` -- jamais `PASS`, jamais "
                "`FAIL` -- donc ce cas ne peut pas etre eprouve ici. "
                "Installer : `python3 -m pip install cryptography`. "
                "`verify.py` et les cas d archive n en ont AUCUN besoin."
                % sys.executable)
    return None


def executer(verificateur: str, fiches: list[dict], binaires: dict,
             travail: Path, strict: bool, bavard: bool,
             connus: dict, crypto: bool = True) -> list[dict]:
    resultats = []
    for fiche in fiches:
        sujet = fiche["subject"]
        manque = (prerequis_absent(verificateur, sujet, crypto)
                  if sujet in PERIMETRES[verificateur] else None)
        if manque is not None:
            resultats.append({
                "id": fiche["id"], "family": fiche["family"],
                "subject": sujet, "verifier": verificateur,
                "etat": NON_EXECUTABLE, "detail": manque,
                "observed": {"classification": CL_NON_EXECUTABLE},
            })
            continue
        if sujet not in PERIMETRES[verificateur]:
            resultats.append({
                "id": fiche["id"], "family": fiche["family"],
                "subject": sujet, "verifier": verificateur,
                "etat": NON_APPLICABLE,
                "detail": "`%s` ne traite pas le sujet `%s` ; il ne l annonce "
                          "pas, et le lui reprocher serait une mesure fausse"
                          % (verificateur, sujet),
            })
            continue

        cmd = construire_commande(fiche, verificateur, binaires, travail, strict)
        if cmd is None:
            resultats.append({
                "id": fiche["id"], "family": fiche["family"],
                "subject": sujet, "verifier": verificateur,
                "etat": NON_APPLICABLE,
                "detail": "aucune commande applicable pour ce cas",
            })
            continue

        sortie = lancer(cmd)
        if sortie["timeout"]:
            resultats.append({
                "id": fiche["id"], "family": fiche["family"],
                "subject": sujet, "verifier": verificateur,
                "etat": ERREUR, "detail": "delai depasse",
            })
            continue

        observe = verdict_observe(sortie, fiche, verificateur, travail)
        if observe["exit_code"] not in (0, 1, 2, 3):
            resultats.append({
                "id": fiche["id"], "family": fiche["family"],
                "subject": sujet, "verifier": verificateur,
                "etat": ERREUR,
                "detail": "code de sortie %s hors du contrat {0,1,2,3}"
                          % observe["exit_code"],
                "observed": observe,
            })
            continue

        c = comparer(fiche, verificateur, observe, strict)
        declare = connus.get((fiche["id"], verificateur))
        if c["etat"] == FAIL and declare is not None:
            c = {"etat": ECHEC_CONNU,
                 "detail": "%s -- DEFAUT DECLARE : %s"
                           % (c["detail"], declare["defect"][:160]),
                 "ecart_code": c.get("ecart_code"),
                 "note": declare.get("proposed_fix")}
        resultats.append({
            "id": fiche["id"], "family": fiche["family"],
            "subject": sujet, "verifier": verificateur,
            "rule_status": fiche["rule"]["statut"],
            "etat": c["etat"], "detail": c["detail"],
            "ecart_code": c.get("ecart_code"),
            "note": c.get("note"),
            "expected": fiche["expected"], "observed": observe,
        })
        if bavard:
            print("  %-12s %-40s %-14s %s"
                  % (verificateur, fiche["id"], c["etat"], c["detail"][:60]))
    return resultats


def resumer(resultats: list[dict]) -> dict:
    etats = {}
    for r in resultats:
        etats[r["etat"]] = etats.get(r["etat"], 0) + 1
    return etats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verifier", default="all",
                    choices=["python", "rust-core", "rust-crypto", "all"])
    ap.add_argument("--bin-rust-core", default=None)
    ap.add_argument("--bin-rust-crypto", default=None)
    ap.add_argument("--strict", action="store_true",
                    help="passer --strict aux verificateurs qui le prennent")
    ap.add_argument("--json", dest="sortie", default=None)
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--skip-digests", action="store_true",
                    help="NE PAS verifier les empreintes du corpus. A "
                         "n employer que pour deboguer : un corpus non "
                         "verifie ne mesure plus ce que ses fiches annoncent")
    a = ap.parse_args()

    print("Corpus de conformite Evidence")
    version = (CORPUS / "VERSION")
    print("  version : %s" % (version.read_text().strip()
                              if version.is_file() else "ABSENTE"))

    # ---- 1. integrite du corpus -----------------------------------------
    if a.skip_digests:
        print("  empreintes : NON VERIFIEES (--skip-digests)")
    else:
        ok, details = verifier_corpus()
        print("  empreintes : %s -- %s"
              % ("conformes" if ok else "EN ECART", details[0]))
        if not ok:
            for d in details[:10]:
                print("    %s" % d)
            print("\nLe corpus est fige : ses octets ne doivent pas changer "
                  "sans\nnouvelle VERSION. Arret.")
            return 2

    fiches = [json.loads(p.read_bytes())
              for p in sorted((CORPUS / "expected").glob("*.json"))]
    print("  cas        : %d" % len(fiches))

    binaires = {}
    cible = os.environ.get("CARGO_TARGET_DIR", str(Path.home() / "evr-target"))
    cible_c = os.environ.get("CARGO_TARGET_DIR_CRYPTO",
                             str(Path.home() / "evc-target"))
    binaires["rust-core"] = a.bin_rust_core or \
        "%s/release/evidence-verify-rs" % cible
    binaires["rust-crypto"] = a.bin_rust_crypto or \
        "%s/release/evidence-verify-crypto" % cible_c

    verificateurs = (["python", "rust-core", "rust-crypto"]
                     if a.verifier == "all" else [a.verifier])
    absents = [v for v in verificateurs
               if v != "python" and not Path(binaires[v]).is_file()]
    if absents:
        print("\nbinaire(s) absent(s) : %s" % ", ".join(
            "%s -> %s" % (v, binaires[v]) for v in absents))
        print("compiler d abord :")
        print("  cd verifier-rs        && cargo build --release")
        print("  cd verifier-rs-crypto && cargo build --release")
        return 2

    connus = charger_echecs_connus()
    if connus:
        print("  echecs DECLARES : %d (voir known_failures.json)" % len(connus))

    travail = Path(os.environ.get("TMPDIR", "/tmp")) / "evidence-conformance"
    shutil.rmtree(travail, ignore_errors=True)
    travail.mkdir(parents=True)

    # L ENVIRONNEMENT, ANNONCE AVANT LES RESULTATS.
    #
    # Signale par Olusanya Timothy le 2026-11-13 : sans `cryptography`, le
    # banc rendait cinq `FAIL` sous l intitule << ECHECS NON DECLARES --
    # regression >>, sans nommer une seule fois la dependance. Un lecteur
    # externe en concluait que le verificateur avait regresse.
    crypto = cryptography_disponible()
    print()
    print("ENVIRONNEMENT : python %s | cryptography %s"
          % (".".join(str(n) for n in sys.version_info[:3]),
             "disponible" if crypto else "ABSENTE"))
    if not crypto and "python" in verificateurs:
        print()
        print("  ATTENTION -- les cas d ATTESTATION ne seront PAS eprouves")
        print("  cote `python` : ils sortiront en `NOT RUNNABLE`, qui n est")
        print("  ni un succes ni un echec de conformite. Les cas de")
        print("  soumission et d ARCHIVE, eux, ne demandent RIEN :")
        print("  `verify.py` n importe que la bibliotheque standard.")
        print("  Pour eprouver les attestations : pip install cryptography")

    tout = []
    print()
    for v in verificateurs:
        print("--- %s%s ---" % (v, " (--strict)" if a.strict else ""))
        r = executer(v, fiches, binaires, travail, a.strict, not a.quiet,
                     connus, crypto)
        tout += r
        e = resumer(r)
        print("    %s" % "  ".join("%s=%d" % (k, e[k]) for k in sorted(e)))

    # ---- rapport ---------------------------------------------------------
    print()
    echecs = [r for r in tout if r["etat"] == FAIL]
    connus_vus = [r for r in tout if r["etat"] == ECHEC_CONNU]
    erreurs = [r for r in tout if r["etat"] == ERREUR]
    non_executables = [r for r in tout if r["etat"] == NON_EXECUTABLE]
    ambigus = [r for r in tout if r["etat"] == AMBIGU]
    ecarts_code = [r for r in tout if r.get("ecart_code")]

    e = resumer(tout)
    print("BILAN : %s" % "  ".join("%s=%d" % (k, e[k]) for k in sorted(e)))
    print("ecarts de CODE sur verdict concordant : %d" % len(ecarts_code))

    if connus_vus:
        print("\nECHECS DECLARES -- visibles, et NON comptes comme regression :")
        for r in connus_vus:
            print("  %-12s %-40s %s"
                  % (r["verifier"], r["id"], r["detail"][:90]))
            if r.get("note"):
                print("               correctif propose : %s" % r["note"][:86])
    if echecs:
        print("\nECHECS **NON DECLARES** -- regression :")
        for r in echecs:
            print("  %-12s %-40s %s" % (r["verifier"], r["id"], r["detail"]))
    if non_executables:
        print("\nCAS NON EPROUVES -- un PREREQUIS manque. Ce n est NI un")
        print("succes NI un echec de conformite : rien n a ete mesure.")
        for r in non_executables:
            print("  %-12s %-40s" % (r["verifier"], r["id"]))
        print("  motif : %s" % non_executables[0]["detail"])
    if erreurs:
        print("\nERREURS TECHNIQUES :")
        for r in erreurs:
            print("  %-12s %-40s %s" % (r["verifier"], r["id"], r["detail"]))
    if ecarts_code:
        print("\nECARTS DE CODE (verdict conforme) :")
        for r in ecarts_code:
            print("  %-12s %-40s %s" % (r["verifier"], r["id"], r["ecart_code"]))
    # LES DIVERGENCES SUR CAS AMBIGUS, calculées et PUBLIÉES.
    #
    # Le défaut que ceci corrige : le banc MESURAIT le verdict observé de
    # chaque vérificateur sur un cas ambigu — il est dans `observed` du
    # rapport depuis le début — et ne le COMPARAIT JAMAIS d'un vérificateur
    # à l'autre. La divergence de `G-07` (python ACCEPTE, rust-crypto
    # REJETE) était donc dans la donnée et invisible dans tout ce qu'un
    # lecteur regarde : ni sommaire, ni section ambiguë, ni matrice.
    #
    # Une divergence sur un cas ambigu n'est PAS un échec : le contrat ne
    # tranche pas. Mais elle doit se VOIR, parce que c'est exactement ce
    # qu'une ambiguïté normative produit de dangereux — deux vérificateurs
    # honnêtes, un seul fichier, deux verdicts.
    divergences = []
    for cid in sorted({r["id"] for r in ambigus}):
        lignes_du_cas = [r for r in ambigus if r["id"] == cid]
        par_verif = {r["verifier"]: (r.get("observed") or {}).get("verdict")
                     for r in lignes_du_cas}
        distincts = {v for v in par_verif.values() if v is not None}
        if len(distincts) > 1:
            divergences.append({
                "id": cid,
                "observed_by_verifier": par_verif,
                "distinct_verdicts": sorted(distincts),
                # La fiche fige-t-elle ce comportement, verificateur par
                # verificateur ? `G-01` a `G-05` le font ; `G-06` et `G-07`
                # ne le faisaient pas, et c est ce silence qui rendait la
                # divergence inverifiable.
                "declared": all("declare" in (r.get("detail") or "")
                                for r in lignes_du_cas),
            })

    if ambigus and not a.quiet:
        print("\nCAS AMBIGUS -- le contrat ne tranche pas, et ce banc non plus :")
        vus = set()
        for r in ambigus:
            if r["id"] in vus:
                continue
            vus.add(r["id"])
            print("  %-40s %s" % (r["id"], (r.get("note") or "")[:70]))

    if divergences and not a.quiet:
        print("\nDIVERGENCES MESUREES SUR CAS AMBIGUS -- deux verificateurs,")
        print("un seul fichier, deux verdicts. Le contrat ne tranchant pas,")
        print("ce n est PAS un echec de conformite : c est ce qu une")
        print("ambiguite normative produit, et c est pour cela qu on la publie.")
        for d in divergences:
            vus_v = ", ".join("%s=%s" % (k, v)
                              for k, v in sorted(d["observed_by_verifier"].items())
                              if v is not None)
            print("  %-40s %s%s"
                  % (d["id"], vus_v,
                     "" if d["declared"]
                     else "   [NON DECLARE PAR LA FICHE]"))

    print()
    print("RAPPEL : un refus ATTENDU est une REUSSITE. Les %d cas en PASS"
          % e.get(PASS, 0))
    print("comprennent des paquets correctement REFUSES.")
    print("Le denominateur de tout taux cite ici est le nombre de cas")
    print("APPLICABLES au verificateur concerne, et non les %d cas du corpus."
          % len(fiches))

    if a.sortie:
        Path(a.sortie).write_text(json.dumps({
            "corpus_version": version.read_text().strip() if version.is_file() else None,
            "strict": a.strict,
            "verifiers": verificateurs,
            # CONTRAT D ENVIRONNEMENT. Deux executions de meme schema
            # rendaient 40 PASS et 5 FAIL sans qu un seul champ ne dise
            # pourquoi : un rapport archive etait donc ininterpretable
            # apres coup. Ces trois champs le rendent lisible.
            "environment": {
                "python_version": ".".join(str(n) for n in sys.version_info[:3]),
                "python_executable": sys.executable,
                "cryptography_available": crypto,
            },
            "not_runnable": [
                {"verifier": r["verifier"], "id": r["id"],
                 "detail": r["detail"]} for r in non_executables],
            "summary": e,
            "known_failures_observed": [
                {"verifier": r["verifier"], "id": r["id"]}
                for r in connus_vus],
            "code_mismatches": [{"verifier": r["verifier"], "id": r["id"],
                                 "detail": r["ecart_code"]} for r in ecarts_code],
            # Mesurées, non fatales, et désormais VISIBLES.
            "ambiguous_divergences": divergences,
            "failures": [{"verifier": r["verifier"], "id": r["id"],
                          "detail": r["detail"]} for r in echecs],
            "errors": [{"verifier": r["verifier"], "id": r["id"],
                        "detail": r["detail"]} for r in erreurs],
            "results": tout,
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        print("rapport machine : %s" % a.sortie)

    vus = {(r["id"], r["verifier"]) for r in connus_vus}
    perimes = [k for k in connus if k not in vus
               and any(r["id"] == k[0] and r["verifier"] == k[1] for r in tout)]
    if perimes:
        print()
        print("ENTREES PERIMEES de known_failures.json :")
        for cas_, v in perimes:
            print("  %-12s %-40s n echoue PLUS -- a instruire : corrige, ou "
                  "le cas ne l eprouve plus ?" % (v, cas_))

    shutil.rmtree(travail, ignore_errors=True)
    # Le MEME contrat que celui des trois outils, et pour la meme raison :
    # 1 = quelque chose a echoue, 2 = rien n a echoue mais tout n a pas ete
    # eprouve, 0 = la mesure est complete. Rendre 0 avec des cas
    # `NOT RUNNABLE` reproduirait, au niveau du banc, le piege que
    # `docs/INTEGRATION.md` decrit au niveau des outils.
    if echecs or erreurs or perimes:
        return 1
    return 2 if non_executables else 0


if __name__ == "__main__":
    raise SystemExit(main())
