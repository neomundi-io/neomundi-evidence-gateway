# -*- coding: utf-8 -*-
"""Le corpus public de conformite est une PREUVE : cette suite le garde.

`verifier/` porte la surface de verification publique -- specification,
corpus gele, verificateurs. Republier un corpus gele cree un risque precis :
qu il DERIVE sans que personne ne s en apercoive. Un fichier reecrit, une fin
de ligne normalisee, un chiffre de README qui ne correspond plus, et le
corpus publie n est plus celui dont nous citons les resultats.

Cette suite ne verifie rien d un artefact : elle verifie que le corpus
publie EST celui que nous annoncons, et qu il se comporte comme annonce.

Emploi :  python tests/test_corpus_public.py

Bibliotheque standard seule. Les deux verificateurs Rust exigent `cargo` :
sans lui, les lignes correspondantes rendent NOT TESTED, jamais PASS.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
V = RACINE / "verifier"
CORPUS = V / "conformance"

#: Mesure du 2026-11-14, sur le corpus repris du moteur a `3391c768`.
EMPREINTE_SOMMES = "e3edeb26c54363ace46737563f4824f79a0adab2baebcb8351bb15d632a6a297"
EMPREINTE_MANIFESTE = "2720995161e6b98ee707c72ba3000a5029d8e49a07f1e80de3cf6da82fdd5ec2"
VERSION_ATTENDUE = "1.3.0"
ENTREES_COUVERTES = 172

#: Bilan attendu du verificateur Python sur le corpus, selon que la
#: dependance OPTIONNELLE `cryptography` est presente ou non.
#:
#: Un refus ATTENDU est une reussite : les 40 PASS comprennent des paquets
#: correctement refuses.
#:
#: ⚠ Ces deux lignes sont la trace d une observation de relecture externe du
#: 13 novembre 2026 : sans `cryptography`, le banc rendait « echecs non
#: declares -- regression » sans nommer nulle part la dependance. Neuf cas
#: deviennent ineprouvables, et c est une ABSENCE, pas une regression. Cette
#: suite le dit donc au lieu de l absorber.
ATTENDU_AVEC_CRYPTO = {"PASS": 40, "AMBIGUOUS": 10}
ATTENDU_SANS_CRYPTO = {"PASS": 33, "AMBIGUOUS": 8}

BILAN: list[tuple[str, str, str]] = []


def noter(etat: str, intitule: str, detail: str = "") -> None:
    BILAN.append((etat, intitule, detail))
    print(f"[{etat:10}] {intitule}" + (f" - {detail}" if detail else ""))


def _sha256(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def controle_empreintes_couvertes() -> None:
    """Rejoue `SHA256SUMS` sans depende de l outil `sha256sum`."""
    sommes = CORPUS / "SHA256SUMS"
    if not sommes.is_file():
        noter("FAIL", "le corpus publie existe", "verifier/conformance/SHA256SUMS absent")
        return
    lignes = [l for l in sommes.read_text(encoding="utf-8").splitlines() if l.strip()]
    manquants, divergents = [], []
    for ligne in lignes:
        attendu, _, nom = ligne.partition("  ")
        nom = nom.lstrip("*").strip()
        cible = CORPUS / nom
        if not cible.is_file():
            manquants.append(nom)
        elif _sha256(cible) != attendu.strip():
            divergents.append(nom)
    if len(lignes) != ENTREES_COUVERTES:
        noter("FAIL", "nombre d entrees couvertes",
              f"{len(lignes)} au lieu de {ENTREES_COUVERTES}")
    elif manquants:
        noter("FAIL", "chaque entree couverte est presente",
              f"{len(manquants)} absente(s) : " + ", ".join(manquants[:3]))
    elif divergents:
        noter("FAIL", "chaque entree couverte concorde",
              f"{len(divergents)} divergente(s) : " + ", ".join(divergents[:3]))
    else:
        noter("PASS", "le corpus gele concorde a l octet",
              f"{len(lignes)}/{ENTREES_COUVERTES} entrees")


def controle_identite_du_corpus() -> None:
    for nom, chemin, attendu in (
        ("SHA256SUMS", CORPUS / "SHA256SUMS", EMPREINTE_SOMMES),
        ("manifest.json", CORPUS / "manifest.json", EMPREINTE_MANIFESTE),
    ):
        if not chemin.is_file():
            noter("FAIL", f"empreinte de {nom}", "fichier absent")
            continue
        obtenu = _sha256(chemin)
        if obtenu != attendu:
            noter("FAIL", f"empreinte de {nom}", f"{obtenu} != {attendu}")
        else:
            noter("PASS", f"empreinte de {nom}", obtenu[:16] + "...")

    version = CORPUS / "VERSION"
    if not version.is_file():
        noter("FAIL", "version du corpus", "VERSION absent")
    else:
        lu = version.read_text(encoding="utf-8").strip()
        if lu != VERSION_ATTENDUE:
            noter("FAIL", "version du corpus", f"{lu!r} au lieu de {VERSION_ATTENDUE!r}")
        else:
            noter("PASS", "version du corpus", lu)


def controle_autonomie() -> None:
    """Les proprietes que la notice du verificateur ANNONCE.

    Chacune est annoncee dans `verifier/README.md`. Une notice qui annonce
    une propriete que rien n eprouve est une prose, pas une garantie.
    """
    # 1. `verifier-rs` sans aucune dependance -- constatable sans compiler.
    verrou = V / "verifier-rs" / "Cargo.lock"
    if not verrou.is_file():
        noter("FAIL", "verifier-rs : zero dependance", "Cargo.lock absent")
    else:
        paquets = verrou.read_text(encoding="utf-8").count("[[package]]")
        if paquets != 1:
            noter("FAIL", "verifier-rs : zero dependance",
                  f"{paquets} paquet(s) dans Cargo.lock, 1 attendu")
        else:
            noter("PASS", "verifier-rs : zero dependance",
                  "1 entree dans Cargo.lock -- constatable sans compiler")

    # 2. Les deux caisses doivent rester SŒURS : `#[path]` les relie.
    principal = V / "verifier-rs-crypto" / "src" / "main.rs"
    if not principal.is_file():
        noter("FAIL", "les deux caisses Rust sont soeurs", "main.rs absent")
    else:
        chemins = re.findall(r'#\[path\s*=\s*"([^"]+)"\]',
                             principal.read_text(encoding="utf-8"))
        brises = [c for c in chemins if not (principal.parent / c).resolve().is_file()]
        if not chemins:
            noter("FAIL", "les deux caisses Rust sont soeurs", "aucun #[path] trouve")
        elif brises:
            noter("FAIL", "les deux caisses Rust sont soeurs",
                  f"{len(brises)} chemin(s) partage(s) brise(s) : " + ", ".join(brises[:2]))
        else:
            noter("PASS", "les deux caisses Rust sont soeurs",
                  f"{len(chemins)} module(s) partage(s) resolu(s)")

    # 3. `i18n.py` est OPTIONNEL : la notice le dit, donc il faut l eprouver.
    for outil in ("verify.py", "verify_attestation.py", "adapters/ingest.py"):
        chemin = V / outil
        if not chemin.is_file():
            noter("FAIL", f"{outil} est publie", "absent")
            continue
        texte = chemin.read_text(encoding="utf-8")
        if "import i18n" in texte and "except ImportError" not in texte:
            noter("FAIL", f"{outil} : i18n optionnel",
                  "importe i18n sans repli -- la notice annonce l inverse")
        else:
            noter("PASS", f"{outil} : publie, i18n optionnel", "repli present")


def _cryptography_disponible() -> bool:
    """`cryptography` est-elle importable par l interpreteur courant ?"""
    try:
        import cryptography  # noqa: F401
    except ImportError:
        return False
    return True


def controle_corpus_python() -> None:
    """Joue le corpus avec le verificateur Python et confronte le bilan."""
    runner = CORPUS / "runners" / "run.py"
    if not runner.is_file():
        noter("FAIL", "le banc du corpus est publie", "runners/run.py absent")
        return

    avec_crypto = _cryptography_disponible()
    attendu = ATTENDU_AVEC_CRYPTO if avec_crypto else ATTENDU_SANS_CRYPTO
    if not avec_crypto:
        noter("NOT TESTED", "les cas d attestation du corpus",
              "`cryptography` est absente de cet environnement : 7 PASS et "
              "2 AMBIGUOUS deviennent ineprouvables. C est une ABSENCE, pas "
              "une regression -- `pip install cryptography` pour les couvrir")
    try:
        acheve = subprocess.run(  # noqa: S603
            [sys.executable, "-B", "runners/run.py", "--verifier", "python"],
            cwd=str(CORPUS), capture_output=True, timeout=600,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        noter("FAIL", "le corpus se joue", str(exc))
        return
    sortie = acheve.stdout.decode("utf-8", errors="replace")
    bilan = [l for l in sortie.splitlines() if l.startswith("BILAN")]
    if not bilan:
        noter("FAIL", "le corpus se joue", "aucune ligne BILAN")
        return
    compte = dict(re.findall(r"([A-Z ]+?)=(\d+)", bilan[-1]))
    compte = {k.strip(): int(v) for k, v in compte.items()}
    ecarts = [f"{k}={compte.get(k)} au lieu de {v}"
              for k, v in attendu.items() if compte.get(k) != v]
    if compte.get("FAIL"):
        ecarts.append(f"FAIL={compte['FAIL']}")
    # Sans `cryptography`, le banc sort en 2 : des cas declares n ont pas pu
    # etre executes. C est le comportement correct, et il ne doit pas passer
    # pour un echec de cette suite.
    code_attendu = 0 if avec_crypto else 2
    if acheve.returncode != code_attendu:
        ecarts.append(f"code={acheve.returncode} au lieu de {code_attendu}")
    contexte = "avec cryptography" if avec_crypto else "SANS cryptography"
    if ecarts:
        noter("FAIL", f"corpus, verificateur Python ({contexte})",
              " ; ".join(ecarts))
    else:
        noter("PASS", f"corpus, verificateur Python ({contexte})",
              f"PASS={compte.get('PASS')} AMBIGUOUS={compte.get('AMBIGUOUS')} FAIL=0")
        if "ecarts de CODE sur verdict concordant : 0" not in sortie:
            noter("FAIL", "aucun ecart de code sur verdict concordant",
                  "la ligne attendue est absente du rapport")
        else:
            noter("PASS", "aucun ecart de code sur verdict concordant", "0")


def controle_tracabilite() -> None:
    """Les deux colonnes de `traceability.json`, telles que la notice les cite."""
    fichier = V / "spec" / "traceability.json"
    if not fichier.is_file():
        noter("FAIL", "la tracabilite est publiee", "spec/traceability.json absent")
        return
    charge = json.loads(fichier.read_text(encoding="utf-8"))
    regles = charge.get("rules") or []
    if len(regles) != 102:
        noter("FAIL", "nombre de regles tracees",
              f"{len(regles)} au lieu de 102 -- corriger verifier/README.md avec le NOUVEAU chiffre")
    else:
        lacunes = sum(1 for r in regles if r.get("coverage") == "GAP")
        inconnus = sum(1 for r in regles
                       if r.get("reference_implementations") == "UNKNOWN")
        noter("PASS", "nombre de regles tracees",
              f"102 regles, dont {lacunes} GAP de couverture et {inconnus} UNKNOWN -- declares")


def main() -> int:
    if not V.is_dir():
        noter("FAIL", "la surface de verification est publiee", "verifier/ absent")
        print("\nBILAN : 0 PASS, 1 FAIL, 0 NOT TESTED")
        return 1
    controle_identite_du_corpus()
    controle_empreintes_couvertes()
    controle_autonomie()
    controle_tracabilite()
    controle_corpus_python()

    reussis = sum(1 for e, _, _ in BILAN if e == "PASS")
    echoues = sum(1 for e, _, _ in BILAN if e == "FAIL")
    non_eprouves = sum(1 for e, _, _ in BILAN if e == "NOT TESTED")
    print(f"\nBILAN : {reussis} PASS, {echoues} FAIL, {non_eprouves} NOT TESTED")
    print("Les deux verificateurs Rust ne sont PAS joues ici : ils exigent")
    print("`cargo`. La recette est dans verifier/README.md.")
    return 1 if echoues else 0


if __name__ == "__main__":
    sys.exit(main())
