# -*- coding: utf-8 -*-
"""Les cinq situations que ce gateway doit distinguer, et deux gardes.

  1. artefact valide                 -> completed, verdict du moteur, code 0
  2. artefact altere                 -> completed, verdict du moteur, code 1
  3. artefact non verifiable         -> completed, mais garantie requise non
                                        demontree -- code 2, et le dire
  4. erreur d entree ou de schema    -> rejected, code 4, aucun moteur lance
  5. moteur indisponible             -> engine_unavailable, code 3

Les cas 1 a 3 exigent un moteur. Les cas 4 et 5 n en exigent AUCUN, et c est
une propriete utile : la moitie du contrat de ce gateway s eprouve sans
jamais disposer du moteur -- donc y compris quand le moteur est prive.

Emploi :
    python tests/test_gateway.py                 # cas 4 et 5 seulement
    EVIDENCE_ENGINE_HOME=<racine> python tests/test_gateway.py

Bibliotheque standard seule. `jsonschema` est employee si elle est
installee ; son absence rend NOT TESTED, jamais PASS.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import gateway  # noqa: E402

CONTRAT_REPONSE = RACINE / "contracts" / "gateway-response-v1.json"
CONTRAT_REQUETE = RACINE / "contracts" / "gateway-request-v1.json"

BILAN: list[tuple[str, str, str]] = []


def noter(etat: str, intitule: str, detail: str = "") -> None:
    BILAN.append((etat, intitule, detail))
    print(f"[{etat:10}] {intitule}" + (f" - {detail}" if detail else ""))


def _validateur():
    """Rend un validateur draft-2020-12, ou None si `jsonschema` est absente."""
    try:
        import jsonschema  # type: ignore
    except ImportError:
        return None
    return jsonschema


def valider_enveloppe(charge: dict, contrat: Path, intitule: str) -> None:
    js = _validateur()
    schema = json.loads(contrat.read_text(encoding="utf-8"))
    if js is None:
        # Controle structurel de repli. Il ne remplace pas la validation :
        # il verifie les champs obligatoires et les valeurs `const`, et le
        # dit.
        manquants = [c for c in schema.get("required", []) if c not in charge]
        if manquants:
            noter("FAIL", intitule, "champs obligatoires absents : " + ", ".join(manquants))
            return
        noter(
            "NOT TESTED",
            intitule,
            "`jsonschema` absente : seuls les champs obligatoires ont ete "
            "confrontes, pas le contrat draft-2020-12. `pip install jsonschema`",
        )
        return
    try:
        js.validate(instance=charge, schema=schema)
    except js.ValidationError as exc:  # type: ignore[attr-defined]
        noter("FAIL", intitule, f"{exc.message} (chemin {list(exc.absolute_path)})")
        return
    noter("PASS", intitule, "conforme a " + schema["$id"])


def _traiter(charge: dict, racine_artefacts: Path, moteur: str | None) -> dict:
    return gateway.traiter(charge, racine_artefacts, moteur)


def _requete(operation: str, chemin: str, **extra) -> dict:
    charge: dict = {
        "schema": gateway.CONTRAT_REQUETE,
        "operation": operation,
        "artifact": {"name": "demo", "path": chemin},
    }
    charge.update(extra)
    return charge


# ---------------------------------------------------------------------------
# Cas 4 et 5 -- sans moteur.
# ---------------------------------------------------------------------------


def cas_4_entrees_refusees(racine: Path) -> None:
    artefact = racine / "artefact.zip"
    artefact.write_bytes(b"PK\x05\x06" + b"\x00" * 18)

    attendus = [
        ("contrat de requete inconnu", {"schema": "autre/1", "operation": "verify",
                                        "artifact": {"path": "artefact.zip"}},
         "unsupported_request_schema"),
        ("operation inconnue", _requete("inspecter", "artefact.zip"), "unknown_operation"),
        ("champ non prevu", dict(_requete("verify", "artefact.zip"), inconnu=1),
         "unexpected_field"),
        ("artefact absent de la requete",
         {"schema": gateway.CONTRAT_REQUETE, "operation": "verify", "artifact": {}},
         "missing_field"),
        ("artefact introuvable", _requete("verify", "absent.zip"), "artifact_not_found"),
        ("chemin hors de la racine", _requete("verify", "../dehors.zip"),
         "path_outside_root"),
        ("attestation sans magasin de confiance",
         _requete("attestation", "artefact.zip",
                  inputs={"attestation": "artefact.zip"}),
         "missing_field"),
        ("langue non prise en charge",
         _requete("verify", "artefact.zip", options={"language": "de"}),
         "unsupported_language"),
        ("strict n est pas un booleen",
         _requete("verify", "artefact.zip", options={"strict": "oui"}),
         "field_type_invalid"),
    ]

    for intitule, charge, raison_attendue in attendus:
        reponse = _traiter(charge, racine, None)
        obtenue = (reponse["errors"] or [{}])[0].get("reason")
        if reponse["status"] != "rejected":
            noter("FAIL", f"cas 4 : {intitule}", f"statut {reponse['status']}, attendu rejected")
        elif obtenue != raison_attendue:
            noter("FAIL", f"cas 4 : {intitule}", f"raison {obtenue!r}, attendue {raison_attendue!r}")
        elif reponse["exit_code"] != gateway.CODE_REQUETE_REFUSEE:
            noter("FAIL", f"cas 4 : {intitule}", f"code {reponse['exit_code']}, attendu 4")
        elif reponse["verification_performed"]:
            noter("FAIL", f"cas 4 : {intitule}", "verification_performed est vrai sur un refus")
        elif reponse["verdict"] is not None:
            noter("FAIL", f"cas 4 : {intitule}", "un verdict est publie sur un refus")
        else:
            noter("PASS", f"cas 4 : {intitule}", raison_attendue)

    # L enveloppe de refus doit elle aussi etre conforme au contrat publie.
    reponse = _traiter(_requete("verify", "absent.zip"), racine, None)
    valider_enveloppe(reponse, CONTRAT_REPONSE, "cas 4 : enveloppe de refus conforme")


def cas_5_moteur_indisponible(racine: Path) -> None:
    artefact = racine / "artefact.zip"
    artefact.write_bytes(b"PK\x05\x06" + b"\x00" * 18)
    charge = _requete("verify", "artefact.zip")

    situations = [
        ("aucune racine declaree", "", "engine_not_declared"),
        ("racine declaree absente", str(racine / "moteur-absent"), "engine_home_absent"),
        ("racine sans point d entree", str(racine), "engine_entrypoint_missing"),
    ]
    for intitule, valeur, raison_attendue in situations:
        moteur = valeur or None
        garde = os.environ.pop(gateway.engine.VAR_MOTEUR, None)
        try:
            reponse = _traiter(charge, racine, moteur)
        finally:
            if garde is not None:
                os.environ[gateway.engine.VAR_MOTEUR] = garde
        obtenue = (reponse["errors"] or [{}])[0].get("reason")
        if reponse["status"] != "engine_unavailable":
            noter("FAIL", f"cas 5 : {intitule}", f"statut {reponse['status']}")
        elif obtenue != raison_attendue:
            noter("FAIL", f"cas 5 : {intitule}", f"raison {obtenue!r}, attendue {raison_attendue!r}")
        elif reponse["exit_code"] != gateway.CODE_MOTEUR_INDISPONIBLE:
            noter("FAIL", f"cas 5 : {intitule}", f"code {reponse['exit_code']}, attendu 3")
        elif reponse["verdict"] is not None or reponse["verification_performed"]:
            noter("FAIL", f"cas 5 : {intitule}", "un verdict survit a un moteur absent")
        else:
            noter("PASS", f"cas 5 : {intitule}", raison_attendue)

    reponse = _traiter(charge, racine, str(racine / "moteur-absent"))
    valider_enveloppe(reponse, CONTRAT_REPONSE, "cas 5 : enveloppe d indisponibilite conforme")

    # La sonde embarquee dans la reponse ne doit porter aucun chemin du poste.
    sonde = json.dumps(reponse["engine"], ensure_ascii=False)
    foyer = str(Path.home().resolve())
    if foyer and (foyer in sonde or foyer.replace("\\", "/") in sonde):
        noter("FAIL", "cas 5 : la sonde ne fuit pas le chemin du poste",
              "le repertoire personnel apparait dans la reponse")
    else:
        noter("PASS", "cas 5 : la sonde ne fuit pas le chemin du poste", "redige")


def garde_contrats_lisibles() -> None:
    for contrat in (CONTRAT_REQUETE, CONTRAT_REPONSE):
        try:
            charge = json.loads(contrat.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            noter("FAIL", f"contrat lisible : {contrat.name}", str(exc))
            continue
        if charge.get("additionalProperties") is not False:
            noter("FAIL", f"contrat ferme : {contrat.name}",
                  "`additionalProperties` doit valoir false au premier niveau")
        else:
            noter("PASS", f"contrat ferme : {contrat.name}", charge.get("$id", ""))


# ---------------------------------------------------------------------------
# Cas 1 a 3 -- avec moteur.
# ---------------------------------------------------------------------------


def _dossier_de_demonstration(moteur: Path) -> Path | None:
    dossier = moteur / "examples" / "dossier-v1"
    return dossier if (dossier / "NEOMUNDI_EVIDENCE_V1_DEMO.zip").is_file() else None


def cas_1_2_3(moteur: Path, travail: Path) -> None:
    dossier = _dossier_de_demonstration(moteur)
    if dossier is None:
        noter("NOT TESTED", "cas 1 a 3",
              "le moteur declare ne porte pas examples/dossier-v1 : aucun artefact de reference")
        return

    archive = "examples/dossier-v1/NEOMUNDI_EVIDENCE_V1_DEMO.zip"
    corpus = "examples/dossier-v1/corpus"

    # --- cas 1 : artefact valide, corpus fourni, mode strict.
    reponse = _traiter(
        _requete("verify", archive, inputs={"corpus": corpus}, options={"strict": True}),
        moteur, str(moteur),
    )
    verdict = reponse.get("verdict") or {}
    comptes = verdict.get("counts") or {}
    if reponse["status"] != "completed":
        noter("FAIL", "cas 1 : artefact valide", f"statut {reponse['status']}")
    elif reponse["exit_code"] != 0 or comptes.get("fail") != 0:
        noter("FAIL", "cas 1 : artefact valide",
              f"code {reponse['exit_code']}, FAIL={comptes.get('fail')}")
    elif verdict.get("computed_by_gateway") is not False:
        noter("FAIL", "cas 1 : artefact valide", "le gateway s attribue le verdict")
    else:
        noter("PASS", "cas 1 : artefact valide",
              f"verdict du moteur {verdict.get('value')}, PASS={comptes.get('pass')}, code 0")
    valider_enveloppe(reponse, CONTRAT_REPONSE, "cas 1 : enveloppe conforme")

    if not reponse.get("engine_report_redacted"):
        noter("FAIL", "cas 1 : chemins du poste rediges",
              "aucune redaction appliquee alors que le rapport porte des chemins")
    else:
        brut = json.dumps(reponse["engine_report"], ensure_ascii=False)
        if str(moteur.resolve()) in brut:
            noter("FAIL", "cas 1 : chemins du poste rediges", "la racine du moteur subsiste")
        else:
            noter("PASS", "cas 1 : chemins du poste rediges",
                  f"{reponse['redactions_applied']} chaine(s) reecrite(s)")

    # La reponse ENTIERE, pas seulement le rapport : une enveloppe envoyee a
    # un appelant ne doit porter aucun chemin du poste, ou qu il se trouve.
    entiere = json.dumps(reponse, ensure_ascii=False)
    foyer = str(Path.home().resolve())
    fuites = [
        variante for variante in {foyer, foyer.replace("\\", "/")}
        if variante and variante in entiere
    ]
    if fuites:
        noter("FAIL", "cas 1 : la reponse entiere ne porte aucun chemin du poste",
              "le repertoire personnel apparait dans l enveloppe")
    else:
        noter("PASS", "cas 1 : la reponse entiere ne porte aucun chemin du poste",
              "enveloppe, sonde et rapport confrontes")

    empreinte = (reponse.get("artifact") or {}).get("sha256_reported_by_engine")
    if not empreinte:
        noter("FAIL", "cas 1 : l empreinte vient du moteur", "aucune empreinte republiee")
    else:
        noter("PASS", "cas 1 : l empreinte vient du moteur", empreinte[:16] + "...")

    # --- cas 2 : artefact altere. Un membre est reecrit, rien d autre.
    altere = travail / "altere.zip"
    source = dossier / "NEOMUNDI_EVIDENCE_V1_DEMO.zip"
    with zipfile.ZipFile(source) as entree:
        noms = entree.namelist()
        cible = next((n for n in noms if n.endswith(".jsonl")), noms[-1])
        with zipfile.ZipFile(altere, "w", zipfile.ZIP_DEFLATED) as sortie:
            for nom in noms:
                donnees = entree.read(nom)
                if nom == cible:
                    donnees = donnees + b"\n"
                sortie.writestr(nom, donnees)

    reponse = _traiter(_requete("verify", altere.name), travail, str(moteur))
    verdict = reponse.get("verdict") or {}
    comptes = verdict.get("counts") or {}
    if reponse["status"] != "completed":
        noter("FAIL", "cas 2 : artefact altere", f"statut {reponse['status']}")
    elif reponse["exit_code"] != 1 or not comptes.get("fail"):
        noter("FAIL", "cas 2 : artefact altere",
              f"code {reponse['exit_code']}, FAIL={comptes.get('fail')} -- une alteration doit ECHOUER")
    else:
        noter("PASS", "cas 2 : artefact altere",
              f"membre `{cible}` reecrit -> FAIL={comptes.get('fail')}, code 1")

    # --- cas 3 : artefact non verifiable. Le corpus n est pas fourni, donc
    # l empreinte des entrees rejouees ne PEUT pas etre eprouvee. En mode
    # strict cela vaut 2 : rien n a echoue, et rien n est demontre.
    reponse = _traiter(
        _requete("verify", archive, options={"strict": True}), moteur, str(moteur)
    )
    verdict = reponse.get("verdict") or {}
    requises = verdict.get("required_not_demonstrated") or []
    if reponse["status"] != "completed":
        noter("FAIL", "cas 3 : artefact non verifiable", f"statut {reponse['status']}")
    elif reponse["exit_code"] != 2 or not requises:
        noter("FAIL", "cas 3 : artefact non verifiable",
              f"code {reponse['exit_code']}, requises={requises} -- attendu code 2 et une garantie nommee")
    else:
        noter("PASS", "cas 3 : artefact non verifiable",
              f"code 2, garantie(s) non demontree(s) : {'; '.join(requises)}")

    # --- La garantie que le gateway republie, et n invente pas : les limites
    # du moteur doivent se retrouver dans l enveloppe.
    limites_du_moteur = (reponse.get("engine_report") or {}).get("does_not_establish") or []
    republiees = [l for l in reponse["limits"] if l.startswith("engine: ")]
    if len(republiees) != len(limites_du_moteur):
        noter("FAIL", "les limites du moteur sont republiees",
              f"{len(republiees)} republiee(s) pour {len(limites_du_moteur)} declaree(s)")
    elif not any("independence" in l for l in reponse["limits"]):
        noter("FAIL", "la limite d independance est republiee", "absente de l enveloppe")
    else:
        noter("PASS", "les limites du moteur sont republiees",
              f"{len(republiees)} limite(s) du moteur + les 2 limites propres au gateway")

    # --- cas 3 bis : attestation sur cle de TEST. Sans --allow-test-keys le
    # moteur ECHOUE, et c est le comportement correct : une cle de test
    # n accorde aucune attestation. Avec le drapeau, la reponse doit porter
    # la trace de cette decision.
    jws = "examples/dossier-v1/NEOMUNDI_EVIDENCE_V1_DEMO.zip.jws"
    magasin = "examples/dossier-v1/trust-store.json"
    sans = _traiter(
        _requete("attestation", archive,
                 inputs={"attestation": jws, "trust_store": magasin}),
        moteur, str(moteur),
    )
    comptes = ((sans.get("verdict") or {}).get("counts")) or {}
    if sans["exit_code"] != 1 or not comptes.get("fail"):
        noter("FAIL", "cas 3bis : cle de test refusee par defaut",
              f"code {sans['exit_code']}, FAIL={comptes.get('fail')}")
    else:
        noter("PASS", "cas 3bis : cle de test refusee par defaut",
              "une cle `test` n accorde aucune attestation -- code 1")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="nm-gw-test-") as temporaire:
        travail = Path(temporaire)
        racine_cas_4 = travail / "cas4"
        racine_cas_4.mkdir()
        garde_contrats_lisibles()
        cas_4_entrees_refusees(racine_cas_4)
        cas_5_moteur_indisponible(racine_cas_4)

        moteur = gateway.engine.racine_du_moteur(None)
        if moteur is None or not (moteur / "verify.py").is_file():
            noter("NOT TESTED", "cas 1 a 3",
                  f"aucun moteur atteignable : poser {gateway.engine.VAR_MOTEUR}")
        else:
            cas_1_2_3(moteur, travail)

    reussis = sum(1 for e, _, _ in BILAN if e == "PASS")
    echoues = sum(1 for e, _, _ in BILAN if e == "FAIL")
    non_eprouves = sum(1 for e, _, _ in BILAN if e == "NOT TESTED")
    print(f"\nBILAN : {reussis} PASS, {echoues} FAIL, {non_eprouves} NOT TESTED")
    if non_eprouves:
        print("NOT TESTED n est pas une reussite : la ligne dit ce qui manque.")
    return 1 if echoues else 0


if __name__ == "__main__":
    sys.exit(main())
