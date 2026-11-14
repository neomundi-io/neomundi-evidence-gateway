# -*- coding: utf-8 -*-
"""Le paquet pip ne duplique pas le verificateur, et cette suite le MESURE.

`neomundi-evidence-verify` distribue les verificateurs publics. Deux risques
naissent de cette distribution, et cette suite ferme les deux :

  1. **la duplication.** Si les verificateurs etaient recopies dans
     `neomundi_evidence/`, le depot en porterait DEUX exemplaires, qui
     divergeraient un jour. Une seule source est permise : `verifier/`. Le
     repertoire `_verifier/` est materialise A LA CONSTRUCTION et ne doit
     JAMAIS etre suivi par git.

  2. **le front-end qui reinterprete.** Le CLI lance les outils en
     sous-processus et transmet leur code verbatim. L epreuve D confronte
     le code rendu par le CLI a celui d un appel DIRECT, sur le meme
     artefact.

Emploi :  python tests/test_paquet_pip.py

Les epreuves C et D exigent que le paquet ait ete construit au moins une fois
(`python -m build`), puisque `_verifier/` n existe pas dans un depot propre.
Sans cela elles rendent NOT TESTED -- jamais PASS.

Bibliotheque standard seule.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
import tomllib
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
PAQUET = RACINE / "neomundi_evidence"
EMBARQUE = PAQUET / "_verifier"
SOURCE = RACINE / "verifier"

#: Les OUTILS : un point d entree du verificateur par operation du CLI. Le
#: CLI les nomme, donc il doit les nommer tous.
OUTILS = (
    "verify.py",
    "verify_attestation.py",
    "timestamp.py",
    "adapters/ingest.py",
)

#: Les MODULES DE SOUTIEN : embarques parce que les outils les importent,
#: mais le CLI ne les lance jamais et n a aucune raison de les nommer.
#: `canonical` est importe par `verify_attestation` ; `i18n` est OPTIONNEL --
#: les outils tournent sans lui, en francais.
SOUTIEN = ("canonical.py", "i18n.py")

#: Tout ce que `setup.py` doit materialiser.
ATTENDUS = OUTILS + SOUTIEN

#: Un artefact du corpus public, employe pour les epreuves de bout en bout.
VALIDE = "conformance/fixtures/A-valid/A-05-archive-valid/archive.zip"
ALTERE = "conformance/fixtures/D-tampered/D-10-archive-member-tampered/archive.zip"

BILAN: list[tuple[str, str, str]] = []


def noter(etat: str, intitule: str, detail: str = "") -> None:
    BILAN.append((etat, intitule, detail))
    print(f"[{etat:10}] {intitule}" + (f" - {detail}" if detail else ""))


def _sha256(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def _suivi_par_git(relatif: str) -> bool:
    acheve = subprocess.run(  # noqa: S603
        ["git", "ls-files", "--error-unmatch", relatif],
        cwd=str(RACINE), capture_output=True,
    )
    return acheve.returncode == 0


# ---------------------------------------------------------------------------
# A. Une seule source dans le depot.
# ---------------------------------------------------------------------------


def epreuve_a_pas_de_duplication() -> None:
    suivis = subprocess.run(  # noqa: S603
        ["git", "ls-files", "neomundi_evidence"],
        cwd=str(RACINE), capture_output=True, text=True,
    ).stdout.split()
    fautifs = [f for f in suivis if "/_verifier/" in f.replace("\\", "/")]
    if fautifs:
        noter("FAIL", "A : aucun verificateur duplique dans le depot",
              f"{len(fautifs)} fichier(s) suivi(s) sous _verifier/ : "
              + ", ".join(fautifs[:3]))
    else:
        noter("PASS", "A : aucun verificateur duplique dans le depot",
              f"{len(suivis)} fichier(s) suivi(s) dans le paquet, 0 sous _verifier/")

    # Et la source, elle, DOIT etre suivie.
    manquants = [r for r in ATTENDUS if not _suivi_par_git(f"verifier/{r}")]
    if manquants:
        noter("FAIL", "A : la source unique est suivie",
              "non suivi(s) sous verifier/ : " + ", ".join(manquants))
    else:
        noter("PASS", "A : la source unique est suivie",
              f"{len(ATTENDUS)} outil(s) sous verifier/")


# ---------------------------------------------------------------------------
# B. Les trois declarations disent la meme chose.
# ---------------------------------------------------------------------------


def epreuve_b_declarations_concordantes() -> None:
    """`setup.py`, `cli.py` et cette suite doivent lister les memes outils."""
    texte_setup = (RACINE / "setup.py").read_text(encoding="utf-8")
    texte_cli = (PAQUET / "cli.py").read_text(encoding="utf-8")
    ecarts = []
    # Tout ce qui est attendu doit etre materialise par setup.py.
    for relatif in ATTENDUS:
        if '"' + relatif + '"' not in texte_setup:
            ecarts.append(relatif + " absent de setup.py")
    # Mais seuls les OUTILS doivent etre nommes par le CLI : un module de
    # soutien n est jamais lance, et l exiger serait une fausse attente.
    for relatif in OUTILS:
        fichier = relatif.split("/")[-1]
        if fichier not in texte_cli:
            ecarts.append(fichier + " absent de cli.py")
    if ecarts:
        noter("FAIL", "B : setup.py et cli.py concordent", " ; ".join(ecarts))
    else:
        noter("PASS", "B : setup.py et cli.py concordent",
              str(len(OUTILS)) + " outil(s) nomme(s) par le CLI, "
              + str(len(SOUTIEN)) + " module(s) de soutien embarque(s) sans l etre")

    # Le nom du paquet et celui de la commande, tels que publies.
    charge = tomllib.loads((RACINE / "pyproject.toml").read_text(encoding="utf-8"))
    projet = charge["project"]
    attendu_nom = "neomundi-evidence-verify"
    attendu_script = "neomundi-evidence"
    if projet["name"] != attendu_nom:
        noter("FAIL", "B : nom du paquet", f"{projet['name']!r} au lieu de {attendu_nom!r}")
    elif attendu_script not in projet.get("scripts", {}):
        noter("FAIL", "B : nom de la commande", f"`{attendu_script}` absent de [project.scripts]")
    elif projet["dependencies"]:
        noter("FAIL", "B : aucune dependance obligatoire",
              f"declarees : {projet['dependencies']}")
    else:
        noter("PASS", "B : nom, commande et dependances",
              f"{attendu_nom} -> `{attendu_script}`, 0 dependance obligatoire, "
              f"extras : {', '.join(sorted(projet['optional-dependencies']))}")


# ---------------------------------------------------------------------------
# C. Ce qui est embarque est identique a l octet a la source.
# ---------------------------------------------------------------------------


def _embarque() -> tuple[Path, object] | tuple[None, None]:
    """Rend le repertoire des verificateurs embarques, et de quoi le fermer.

    Deux sources possibles, dans cet ordre :

      * `neomundi_evidence/_verifier/` dans l arbre, s il a ete materialise
        par une construction en place ;
      * sinon la ROUE la plus recente de `dist/`, extraite dans un
        temporaire. C est MIEUX : c est l artefact que l utilisateur recoit,
        et `_verifier/` n existe pas dans un depot propre.
    """
    if EMBARQUE.is_dir():
        return EMBARQUE, None
    dossier = RACINE / "dist"
    roues = sorted(dossier.glob("*.whl")) if dossier.is_dir() else []
    if not roues:
        return None, None
    import tempfile
    import zipfile
    garde = tempfile.TemporaryDirectory(prefix="nm-roue-")
    with zipfile.ZipFile(roues[-1]) as z:
        z.extractall(garde.name)
    extrait = Path(garde.name) / "neomundi_evidence" / "_verifier"
    if not extrait.is_dir():
        garde.cleanup()
        return None, None
    return extrait, garde


def epreuve_c_identite_a_l_octet(embarque) -> None:
    if embarque is None:
        noter("NOT TESTED", "C : ce qui est distribue est la source, a l octet",
              "ni `_verifier/` dans l arbre ni roue dans dist/ : "
              "`python -m build` pour eprouver cette ligne")
        return
    ecarts, manquants = [], []
    for relatif in ATTENDUS:
        origine = SOURCE / relatif
        copie = embarque / relatif
        if not copie.is_file():
            manquants.append(relatif)
        elif _sha256(origine) != _sha256(copie):
            ecarts.append(relatif)
    if manquants:
        noter("FAIL", "C : ce qui est distribue est la source, a l octet",
              "absent(s) de la distribution : " + ", ".join(manquants))
    elif ecarts:
        noter("FAIL", "C : ce qui est distribue est la source, a l octet",
              "divergent(s) : " + ", ".join(ecarts))
    else:
        noter("PASS", "C : ce qui est distribue est la source, a l octet",
              f"{len(ATTENDUS)} fichier(s), 0 ecart d empreinte")


# ---------------------------------------------------------------------------
# D. Le CLI ne reinterprete aucun verdict.
# ---------------------------------------------------------------------------


def _cli(arguments: list[str]) -> tuple[int, str]:
    acheve = subprocess.run(  # noqa: S603
        [sys.executable, "-B", "-m", "neomundi_evidence.cli", *arguments],
        cwd=str(_cli.depart), capture_output=True,
    )
    return acheve.returncode, acheve.stdout.decode("utf-8", errors="replace")


def epreuve_d_codes_et_egalite(embarque) -> None:
    if embarque is None:
        noter("NOT TESTED", "D : le CLI transmet verdict ET code, verbatim",
              "ni `_verifier/` dans l arbre ni roue dans dist/")
        return
    depart = embarque.parent.parent
    valide = SOURCE / VALIDE
    altere = SOURCE / ALTERE
    if not valide.is_file() or not altere.is_file():
        noter("NOT TESTED", "D : le CLI transmet le code du verificateur",
              "le corpus de conformite est absent de cet arbre")
        return

    _cli.depart = depart
    situations = [
        ("artefact valide", ["verify", str(valide)], 0),
        ("artefact altere", ["verify", str(altere)], 1),
        ("strict sans entrees rejouees", ["verify", str(valide), "--strict"], 2),
        ("fichier absent", ["verify", str(RACINE / "n-existe-pas.zip")], 4),
    ]
    for intitule, arguments, attendu in situations:
        code, _ = _cli(arguments)
        if code != attendu:
            noter("FAIL", f"D : code de sortie -- {intitule}",
                  f"{code} au lieu de {attendu}")
        else:
            noter("PASS", f"D : code de sortie -- {intitule}", f"code {attendu}")

    # L EPREUVE FORTE : le CLI et un appel DIRECT doivent rendre le meme
    # code ET les memes lignes de controle. Si le front-end reinterpretait
    # quoi que ce soit, cette egalite casserait.
    outil = embarque / "verify.py"
    direct = subprocess.run(  # noqa: S603
        [sys.executable, "-B", str(outil), str(altere), "--lang", "fr"],
        cwd=str(outil.parent), capture_output=True,
    )
    code_cli, sortie_cli = _cli(["verify", str(altere), "--lang", "fr"])
    lignes_directes = [l for l in direct.stdout.decode("utf-8", "replace").splitlines()
                       if l.startswith("[") or l.startswith("BILAN")]
    lignes_cli = [l for l in sortie_cli.splitlines()
                  if l.startswith("[") or l.startswith("BILAN")]
    if direct.returncode != code_cli:
        noter("FAIL", "D : le CLI transmet le code du verificateur",
              f"direct {direct.returncode}, par le CLI {code_cli}")
    elif lignes_directes != lignes_cli:
        noter("FAIL", "D : le CLI transmet les lignes du verificateur",
              f"{len(lignes_cli)} ligne(s) par le CLI pour "
              f"{len(lignes_directes)} en direct")
    else:
        noter("PASS", "D : le CLI transmet verdict ET code, verbatim",
              f"{len(lignes_directes)} ligne(s) identiques, code "
              f"{direct.returncode} identique")


# ---------------------------------------------------------------------------
# E. Rien de prive ne part dans la roue.
# ---------------------------------------------------------------------------


def epreuve_e_aucun_fichier_prive() -> None:
    roues = sorted((RACINE / "dist").glob("*.whl")) if (RACINE / "dist").is_dir() else []
    if not roues:
        noter("NOT TESTED", "E : la roue ne porte aucun fichier prive",
              "aucune roue dans dist/ : construire une fois pour eprouver")
        return
    import zipfile

    INTERDITS = ("gateway.py", "engine.py", "conformance/", "verifier-rs",
                 "spec/", "trust/trust-store.json", "references/")
    for roue in roues:
        with zipfile.ZipFile(roue) as z:
            noms = z.namelist()
            fautifs = [n for n in noms
                       for motif in INTERDITS if motif in n]
            octets = sum(z.getinfo(n).file_size for n in noms)
        if fautifs:
            noter("FAIL", "E : la roue ne porte aucun fichier prive",
                  f"{roue.name} : " + ", ".join(sorted(set(fautifs))[:3]))
        else:
            noter("PASS", "E : la roue ne porte que le verificateur",
                  f"{roue.name} : {len(noms)} entree(s), {octets // 1024} ko decompresses")


def main() -> int:
    epreuve_a_pas_de_duplication()
    epreuve_b_declarations_concordantes()
    embarque, garde = _embarque()
    try:
        epreuve_c_identite_a_l_octet(embarque)
        epreuve_d_codes_et_egalite(embarque)
    finally:
        if garde is not None:
            garde.cleanup()
    epreuve_e_aucun_fichier_prive()

    reussis = sum(1 for e, _, _ in BILAN if e == "PASS")
    echoues = sum(1 for e, _, _ in BILAN if e == "FAIL")
    non_eprouves = sum(1 for e, _, _ in BILAN if e == "NOT TESTED")
    print(f"\nBILAN : {reussis} PASS, {echoues} FAIL, {non_eprouves} NOT TESTED")
    if non_eprouves:
        print("NOT TESTED n est pas une reussite : construire le paquet une fois")
        print("(`python -m build`) rend ces lignes eprouvables.")
    return 1 if echoues else 0


if __name__ == "__main__":
    sys.exit(main())
