# -*- coding: utf-8 -*-
"""NeoMundi Evidence Gateway -- interface d entree/sortie stable du moteur.

CE QUE CE PROGRAMME FAIT

  1. il valide une requete contre son propre contrat d enveloppe ;
  2. il localise le moteur Evidence et lance le point d entree demande ;
  3. il republie le rapport du moteur, chemins locaux redige, dans une
     enveloppe de reponse versionnee ;
  4. il nomme les deux etats que le moteur ne peut pas exprimer :
     requete refusee, et moteur indisponible.

CE QUE CE PROGRAMME NE FAIT PAS

  il ne verifie rien. Il ne lit aucune archive, ne calcule aucune empreinte,
  ne compare aucun manifeste, ne derive aucun verdict. Le verdict republie
  est celui du moteur, et la reponse le dit a chaque fois
  (`verdict.computed_by_gateway: false`).

  Cette abstention est la propriete centrale du produit : une passerelle qui
  reimplementerait la verification serait un second verificateur, avec ses
  propres divergences. `tests/test_no_verification_logic.py` echoue si une
  primitive de verification apparait dans ce fichier.

CODES DE SORTIE -- lire `docs/INTERFACE.md`, section « Codes de sortie ».

  0  le moteur a tourne, aucun controle n a echoue
  1  le moteur a tourne, au moins un controle a ECHOUE
  2  le moteur a tourne, mode strict, une garantie requise n est pas demontree
  3  AUCUNE verification n a eu lieu -- moteur indisponible
  4  AUCUNE verification n a eu lieu -- requete refusee

  0, 1 et 2 sont ceux du moteur, transmis sans traduction. 3 et 4 sont
  propres au gateway, et c est pour cela qu ils existent : sans eux, un
  consommateur confondrait « rien n a echoue » avec « rien n a tourne ».

Bibliotheque standard seule.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import engine

VERSION_DU_GATEWAY = "0.1.0"

CONTRAT_REQUETE = "neomundi.evidence.gateway.request/1"
CONTRAT_REPONSE = "neomundi.evidence.gateway.response/1"

#: Operations exposees, et le point d entree du moteur derriere chacune.
OPERATIONS = ("verify", "attestation")

#: Codes de sortie du gateway qui ne viennent PAS du moteur.
CODE_MOTEUR_INDISPONIBLE = 3
CODE_REQUETE_REFUSEE = 4

#: Champs acceptes au premier niveau d une requete. La discipline est celle
#: des contrats Evidence : ce qui n est pas prevu est refuse, pas ignore.
CHAMPS_REQUETE = {"schema", "operation", "artifact", "inputs", "options", "request_id"}
CHAMPS_ARTEFACT = {"name", "path"}
CHAMPS_ENTREES = {"corpus", "attestation", "trust_store", "allow_test_keys"}
CHAMPS_OPTIONS = {"strict", "language"}

#: Limite que ce gateway ajoute, et qui ne figure dans aucun rapport du
#: moteur. Elle est republiee dans CHAQUE reponse.
LIMITE_D_INDEPENDANCE = (
    "independence: this gateway and the engine it invokes run under the same "
    "operator unless the operator states otherwise. A report produced here is "
    "a verification performed by that operator, not an independent "
    "third-party verification."
)
LIMITE_DE_PASSERELLE = (
    "gateway scope: this gateway performs no verification of its own. Every "
    "control line, count and verdict in `engine_report` was produced by the "
    "Evidence engine; the gateway republishes them and redacts local paths."
)


class RequeteRefusee(Exception):
    """La requete n est pas recevable. AUCUNE verification n a eu lieu."""

    def __init__(self, raison: str, detail: str, champ: str | None = None) -> None:
        super().__init__(detail)
        self.raison = raison
        self.detail = detail
        self.champ = champ


# ---------------------------------------------------------------------------
# Validation de l enveloppe. C est la SEULE validation que fait le gateway,
# et elle porte sur sa propre requete -- jamais sur un artefact.
# ---------------------------------------------------------------------------


def _exiger_objet(valeur: object, champ: str) -> dict:
    if valeur is None:
        return {}
    if not isinstance(valeur, dict):
        raise RequeteRefusee(
            "field_type_invalid", f"`{champ}` doit etre un objet JSON", champ
        )
    return valeur


def _refuser_champs_inattendus(objet: dict, permis: set[str], prefixe: str) -> None:
    surplus = sorted(set(objet) - permis)
    if surplus:
        raise RequeteRefusee(
            "unexpected_field",
            f"champ(s) non prevu(s) sous `{prefixe}` : " + ", ".join(surplus),
            prefixe,
        )


def _resoudre_dans(racine: Path, valeur: str, champ: str) -> Path:
    """Resout un chemin de requete sous `racine`, et refuse toute evasion.

    Un appelant ne doit pas pouvoir designer un fichier hors du territoire
    que l operateur lui a ouvert. Le controle est fait sur les chemins
    RESOLUS, parce qu un `..` ou un lien symbolique ne se voit pas sur la
    chaine de caracteres.
    """
    candidat = Path(valeur)
    if candidat.is_absolute():
        resolu = candidat.resolve()
    else:
        resolu = (racine / candidat).resolve()
    racine_resolue = racine.resolve()
    try:
        resolu.relative_to(racine_resolue)
    except ValueError as exc:
        raise RequeteRefusee(
            "path_outside_root",
            f"`{champ}` sort de la racine d artefacts autorisee ({racine_resolue})",
            champ,
        ) from exc
    return resolu


def valider_requete(charge: object, racine_artefacts: Path) -> dict:
    """Valide une requete et rend sa forme normalisee.

    Leve RequeteRefusee, qui devient un code de sortie 4 et une reponse
    `status: rejected`. Aucun moteur n est lance avant que cette fonction
    ait rendu la main.
    """
    if not isinstance(charge, dict):
        raise RequeteRefusee(
            "request_not_an_object", "la requete n est pas un objet JSON"
        )

    _refuser_champs_inattendus(charge, CHAMPS_REQUETE, "<racine>")

    declare = charge.get("schema")
    if declare != CONTRAT_REQUETE:
        raise RequeteRefusee(
            "unsupported_request_schema",
            f"`schema` attendu {CONTRAT_REQUETE!r}, recu {declare!r}",
            "schema",
        )

    operation = charge.get("operation")
    if operation not in OPERATIONS:
        raise RequeteRefusee(
            "unknown_operation",
            f"`operation` doit valoir l une de {', '.join(OPERATIONS)} -- recu {operation!r}",
            "operation",
        )

    artefact = _exiger_objet(charge.get("artifact"), "artifact")
    _refuser_champs_inattendus(artefact, CHAMPS_ARTEFACT, "artifact")
    chemin_declare = artefact.get("path")
    if not isinstance(chemin_declare, str) or not chemin_declare.strip():
        raise RequeteRefusee(
            "missing_field",
            "`artifact.path` est obligatoire et doit etre une chaine non vide",
            "artifact.path",
        )
    chemin = _resoudre_dans(racine_artefacts, chemin_declare, "artifact.path")
    if not chemin.is_file():
        raise RequeteRefusee(
            "artifact_not_found",
            "`artifact.path` ne designe aucun fichier lisible",
            "artifact.path",
        )

    nom = artefact.get("name")
    if nom is not None and not isinstance(nom, str):
        raise RequeteRefusee(
            "field_type_invalid", "`artifact.name` doit etre une chaine", "artifact.name"
        )

    entrees = _exiger_objet(charge.get("inputs"), "inputs")
    _refuser_champs_inattendus(entrees, CHAMPS_ENTREES, "inputs")
    options = _exiger_objet(charge.get("options"), "options")
    _refuser_champs_inattendus(options, CHAMPS_OPTIONS, "options")

    strict = options.get("strict", False)
    if not isinstance(strict, bool):
        raise RequeteRefusee(
            "field_type_invalid", "`options.strict` doit etre un booleen", "options.strict"
        )
    langue = options.get("language", "fr")
    if langue not in ("fr", "en"):
        raise RequeteRefusee(
            "unsupported_language",
            "`options.language` accepte `fr` ou `en`",
            "options.language",
        )

    permis_test = entrees.get("allow_test_keys", False)
    if not isinstance(permis_test, bool):
        raise RequeteRefusee(
            "field_type_invalid",
            "`inputs.allow_test_keys` doit etre un booleen",
            "inputs.allow_test_keys",
        )

    resolus: dict[str, Path] = {}
    for champ in ("corpus", "attestation", "trust_store"):
        valeur = entrees.get(champ)
        if valeur is None:
            continue
        if not isinstance(valeur, str) or not valeur.strip():
            raise RequeteRefusee(
                "field_type_invalid",
                f"`inputs.{champ}` doit etre une chaine non vide",
                f"inputs.{champ}",
            )
        resolu = _resoudre_dans(racine_artefacts, valeur, f"inputs.{champ}")
        if not resolu.exists():
            raise RequeteRefusee(
                "input_not_found",
                f"`inputs.{champ}` ne designe aucun chemin lisible",
                f"inputs.{champ}",
            )
        resolus[champ] = resolu

    if operation == "attestation":
        for obligatoire in ("attestation", "trust_store"):
            if obligatoire not in resolus:
                raise RequeteRefusee(
                    "missing_field",
                    f"l operation `attestation` exige `inputs.{obligatoire}`. "
                    "Sans magasin de confiance, aucune identite n est etablie "
                    "et le moteur ne rendrait qu un NOT TESTED.",
                    f"inputs.{obligatoire}",
                )

    identifiant = charge.get("request_id")
    if identifiant is not None and not isinstance(identifiant, str):
        raise RequeteRefusee(
            "field_type_invalid", "`request_id` doit etre une chaine", "request_id"
        )

    return {
        "operation": operation,
        "artefact": chemin,
        "nom": nom or chemin.name,
        "entrees": resolus,
        "strict": strict,
        "langue": langue,
        "allow_test_keys": permis_test,
        "request_id": identifiant,
    }


# ---------------------------------------------------------------------------
# Redaction. Ce n est pas de la verification : c est retirer d un rapport les
# chemins de la machine qui l a produit.
# ---------------------------------------------------------------------------


def construire_redactions(racine_moteur: Path, racine_artefacts: Path) -> list[tuple[str, str]]:
    """Rend les couples (motif, jeton) a appliquer au rapport du moteur.

    Les chemins sont rendus dans leurs deux ecritures (`/` et `\\`), parce
    qu un rapport produit sous Windows porte des antislashs et que le meme
    rapport lu sous Linux n en porte pas.
    """
    couples: list[tuple[str, str]] = []
    for racine, jeton in (
        (racine_moteur, "<engine>"),
        (racine_artefacts, "<artifacts>"),
        (Path.home(), "<home>"),
    ):
        try:
            texte = str(racine.resolve())
        except OSError:
            continue
        if not texte:
            continue
        for variante in {texte, texte.replace("\\", "/"), texte.replace("/", "\\")}:
            couples.append((variante, jeton))
    # Les motifs les plus longs d abord : `<engine>` est souvent sous `<home>`,
    # et rediger `<home>` en premier rendrait `<home>/...` au lieu de `<engine>`.
    couples.sort(key=lambda c: len(c[0]), reverse=True)
    return couples


def rediger_sonde(etat: dict, racine_moteur: str | None, racine_artefacts: Path) -> dict:
    """Redige la sonde du moteur AVANT de l embarquer dans une reponse.

    La sonde porte le chemin de l interpreteur et la racine du moteur. Sur
    un poste, ce chemin contient le nom du compte : une reponse envoyee a un
    appelant n a pas a le lui apprendre. Le moteur Evidence se garde de la
    meme fuite dans ses propres rapports.
    """
    racine = engine.racine_du_moteur(racine_moteur)
    couples = construire_redactions(racine or Path.home(), racine_artefacts)
    compteur = [0]
    redige = rediger(etat, couples, compteur)
    assert isinstance(redige, dict)
    return redige


def rediger(valeur: object, couples: list[tuple[str, str]], compteur: list[int]) -> object:
    """Applique les redactions a toutes les CHAINES d une charge JSON.

    Les cles ne sont jamais touchees, et une empreinte ne peut pas l etre :
    elle ne contient aucun separateur de chemin.
    """
    if isinstance(valeur, str):
        sortie = valeur
        for motif, jeton in couples:
            if motif and motif in sortie:
                sortie = sortie.replace(motif, jeton)
        if sortie != valeur:
            compteur[0] += 1
        return sortie
    if isinstance(valeur, dict):
        return {cle: rediger(v, couples, compteur) for cle, v in valeur.items()}
    if isinstance(valeur, list):
        return [rediger(v, couples, compteur) for v in valeur]
    return valeur


# ---------------------------------------------------------------------------
# Enveloppes de reponse.
# ---------------------------------------------------------------------------


def _rediger_texte(texte: str, couples: list[tuple[str, str]] | None) -> str:
    """Redige un message destine a l appelant ET a la sortie d erreur.

    Un detail d erreur porte volontiers un chemin absolu -- « la racine
    declaree n est pas un repertoire lisible : <un chemin absolu> ». Ce chemin
    nomme le poste ; il n a pas a sortir d ici. Le rapport du moteur est
    redige par `rediger` ; les messages du gateway le sont par celle-ci.
    """
    compteur = [0]
    sortie = rediger(texte, couples or construire_redactions(Path.home(), Path.cwd()), compteur)
    return sortie if isinstance(sortie, str) else texte


def _enveloppe(operation: str | None, identifiant: str | None, statut: str) -> dict:
    return {
        "schema": CONTRAT_REPONSE,
        "gateway": {
            "name": "neomundi-evidence-gateway",
            "version": VERSION_DU_GATEWAY,
            "performs_verification": False,
        },
        "operation": operation,
        "request_id": identifiant,
        "status": statut,
        "verification_performed": False,
        "engine": None,
        "verdict": None,
        "engine_report": None,
        "engine_report_redacted": False,
        "limits": [LIMITE_DE_PASSERELLE, LIMITE_D_INDEPENDANCE],
        "errors": [],
        "exit_code": None,
    }


def reponse_refusee(
    exc: RequeteRefusee,
    operation: str | None,
    identifiant: str | None,
    couples: list[tuple[str, str]] | None = None,
) -> dict:
    reponse = _enveloppe(operation, identifiant, "rejected")
    detail = _rediger_texte(exc.detail, couples)
    reponse["errors"] = [
        {"reason": exc.raison, "field": exc.champ, "detail": detail}
    ]
    reponse["limits"] = reponse["limits"] + [
        "no verification took place: the request was refused before the engine was invoked."
    ]
    reponse["exit_code"] = CODE_REQUETE_REFUSEE
    return reponse


def reponse_moteur_indisponible(
    exc: engine.MoteurIndisponible,
    operation: str | None,
    identifiant: str | None,
    etat: dict | None,
    couples: list[tuple[str, str]] | None = None,
) -> dict:
    reponse = _enveloppe(operation, identifiant, "engine_unavailable")
    reponse["engine"] = {"available": False, "probe": etat}
    reponse["errors"] = [
        {"reason": exc.raison, "field": None, "detail": _rediger_texte(exc.detail, couples)}
    ]
    reponse["limits"] = reponse["limits"] + [
        "no verification took place: the engine could not be reached. An "
        "unreachable engine is not a passing verification, and exit code 3 "
        "exists so that no consumer can read it as one."
    ]
    reponse["exit_code"] = CODE_MOTEUR_INDISPONIBLE
    return reponse


def reponse_achevee(
    operation: str,
    identifiant: str | None,
    nom_artefact: str,
    execution: dict,
    rapport: dict,
    etat_moteur: dict,
    couples: list[tuple[str, str]],
) -> dict:
    compteur = [0]
    rapport_redige = rediger(rapport, couples, compteur)
    assert isinstance(rapport_redige, dict)

    reponse = _enveloppe(operation, identifiant, "completed")
    reponse["verification_performed"] = True
    reponse["engine"] = {
        "available": True,
        "entrypoint": execution["commande"][0],
        "exit_code": execution["code_de_sortie"],
        "report_schema": rapport.get("schema"),
        "conformance_corpus_declared": etat_moteur.get("corpus_de_conformite_declare"),
        "revision_declared": etat_moteur.get("revision_declaree"),
        "revision_is_declared_not_verified": True,
    }
    reponse["verdict"] = {
        "source": "evidence-engine",
        "computed_by_gateway": False,
        "value": rapport.get("verdict"),
        "counts": rapport.get("counts"),
        "strict": rapport.get("strict"),
        "required_not_demonstrated": rapport.get("required_not_demonstrated"),
        "engine_exit_code": execution["code_de_sortie"],
    }
    reponse["artifact"] = {
        "name": nom_artefact,
        "sha256_reported_by_engine": rapport.get("archive_sha256"),
    }
    reponse["engine_report"] = rapport_redige
    reponse["engine_report_redacted"] = compteur[0] > 0
    reponse["redactions_applied"] = compteur[0]

    limites = list(reponse["limits"])
    for ligne in rapport.get("does_not_establish") or []:
        if isinstance(ligne, str):
            limites.append("engine: " + ligne)
    reponse["limits"] = limites
    reponse["exit_code"] = execution["code_de_sortie"]
    return reponse


# ---------------------------------------------------------------------------
# Traitement d une requete.
# ---------------------------------------------------------------------------


def _arguments_du_moteur(requete: dict, rapport: Path) -> list[str]:
    """Construit la ligne de commande du moteur depuis une requete validee."""
    artefact = str(requete["artefact"])
    entrees = requete["entrees"]
    if requete["operation"] == "verify":
        arguments = [artefact]
        if "corpus" in entrees:
            arguments += ["--corpus", str(entrees["corpus"])]
    else:
        arguments = [str(entrees["attestation"]), "--archive", artefact]
        arguments += ["--trust-store", str(entrees["trust_store"])]
        if requete["allow_test_keys"]:
            arguments.append("--allow-test-keys")
    arguments += ["--lang", requete["langue"], "--json", str(rapport)]
    if requete["strict"]:
        arguments.append("--strict")
    return arguments


def traiter(charge: object, racine_artefacts: Path, racine_moteur: str | None) -> dict:
    """Traite une requete de bout en bout et rend l enveloppe de reponse.

    Ne leve pas : tout echec devient un statut et un code de sortie.
    """
    operation_annoncee = None
    identifiant_annonce = None
    if isinstance(charge, dict):
        valeur = charge.get("operation")
        operation_annoncee = valeur if isinstance(valeur, str) else None
        valeur = charge.get("request_id")
        identifiant_annonce = valeur if isinstance(valeur, str) else None

    try:
        requete = valider_requete(charge, racine_artefacts)
    except RequeteRefusee as exc:
        return reponse_refusee(
            exc,
            operation_annoncee,
            identifiant_annonce,
            construire_redactions(
                engine.racine_du_moteur(racine_moteur) or Path.home(), racine_artefacts
            ),
        )

    try:
        racine, etat = engine.exiger(requete["operation"], racine_moteur)
    except engine.MoteurIndisponible as exc:
        return reponse_moteur_indisponible(
            exc,
            requete["operation"],
            requete["request_id"],
            rediger_sonde(engine.sonder(racine_moteur), racine_moteur, racine_artefacts),
            construire_redactions(
                engine.racine_du_moteur(racine_moteur) or Path.home(), racine_artefacts
            ),
        )

    with tempfile.TemporaryDirectory(prefix="nm-gateway-") as temporaire:
        chemin_rapport = Path(temporaire) / "engine-report.json"
        arguments = _arguments_du_moteur(requete, chemin_rapport)
        try:
            execution = engine.invoquer(racine, requete["operation"], arguments)
            rapport = engine.lire_rapport(chemin_rapport)
        except engine.MoteurIndisponible as exc:
            return reponse_moteur_indisponible(
                exc,
                requete["operation"],
                requete["request_id"],
                rediger_sonde(etat, racine_moteur, racine_artefacts),
                construire_redactions(racine, racine_artefacts),
            )
        couples = construire_redactions(racine, racine_artefacts)
        return reponse_achevee(
            requete["operation"],
            requete["request_id"],
            requete["nom"],
            execution,
            rapport,
            etat,
            couples,
        )


# ---------------------------------------------------------------------------
# Interface en ligne de commande.
# ---------------------------------------------------------------------------


def _ecrire(reponse: dict, sortie: str | None) -> None:
    texte = json.dumps(reponse, indent=2, ensure_ascii=False, sort_keys=False)
    if sortie:
        Path(sortie).write_bytes((texte + "\n").encode("utf-8"))
        print(f"reponse ecrite : {sortie}")
    else:
        print(texte)


def _resume(reponse: dict) -> None:
    """Une ligne lisible par un humain, sur la sortie d erreur."""
    statut = reponse["status"]
    code = reponse["exit_code"]
    if statut == "completed":
        verdict = reponse["verdict"] or {}
        comptes = verdict.get("counts") or {}
        print(
            f"[gateway] {statut} -- verdict du MOTEUR : {verdict.get('value')} "
            f"(PASS={comptes.get('pass')} FAIL={comptes.get('fail')} "
            f"NOT TESTED={comptes.get('not_tested')}) code={code}",
            file=sys.stderr,
        )
    else:
        detail = (reponse["errors"] or [{}])[0].get("detail", "")
        print(
            f"[gateway] {statut} -- AUCUNE verification n a eu lieu. code={code} : {detail}",
            file=sys.stderr,
        )


def _racine_artefacts(valeur: str | None) -> Path:
    return Path(valeur).expanduser().resolve() if valeur else Path.cwd().resolve()


def commande_submit(args: argparse.Namespace) -> int:
    chemin = Path(args.request)
    if not chemin.is_file():
        print(f"requete introuvable : {chemin}", file=sys.stderr)
        return CODE_REQUETE_REFUSEE
    try:
        charge = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        reponse = reponse_refusee(
            RequeteRefusee("request_unreadable", f"requete illisible : {exc}"), None, None
        )
        _ecrire(reponse, args.out)
        _resume(reponse)
        return CODE_REQUETE_REFUSEE
    reponse = traiter(charge, _racine_artefacts(args.artifact_root), args.engine_home)
    _ecrire(reponse, args.out)
    _resume(reponse)
    return int(reponse["exit_code"])


def _soumettre_direct(charge: dict, args: argparse.Namespace) -> int:
    reponse = traiter(charge, _racine_artefacts(args.artifact_root), args.engine_home)
    _ecrire(reponse, args.out)
    _resume(reponse)
    return int(reponse["exit_code"])


def commande_verify(args: argparse.Namespace) -> int:
    entrees: dict = {}
    if args.corpus:
        entrees["corpus"] = args.corpus
    charge = {
        "schema": CONTRAT_REQUETE,
        "operation": "verify",
        "artifact": {"name": args.name or Path(args.artifact).name, "path": args.artifact},
        "inputs": entrees,
        "options": {"strict": bool(args.strict), "language": args.lang},
    }
    return _soumettre_direct(charge, args)


def commande_attest(args: argparse.Namespace) -> int:
    entrees = {
        "attestation": args.attestation,
        "trust_store": args.trust_store,
        "allow_test_keys": bool(args.allow_test_keys),
    }
    charge = {
        "schema": CONTRAT_REQUETE,
        "operation": "attestation",
        "artifact": {"name": args.name or Path(args.artifact).name, "path": args.artifact},
        "inputs": entrees,
        "options": {"strict": bool(args.strict), "language": args.lang},
    }
    return _soumettre_direct(charge, args)


def commande_engine(args: argparse.Namespace) -> int:
    etat = engine.sonder(args.engine_home)
    redige = rediger_sonde(etat, args.engine_home, Path.cwd().resolve())
    print(json.dumps(redige, indent=2, ensure_ascii=False))
    return 0 if etat["disponible"] else CODE_MOTEUR_INDISPONIBLE


def commande_contracts(args: argparse.Namespace) -> int:
    racine = Path(__file__).resolve().parent
    propres = []
    for fichier in sorted((racine / "contracts").glob("*.json")):
        try:
            charge = json.loads(fichier.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        propres.append({"file": f"contracts/{fichier.name}", "id": charge.get("$id")})

    etat = engine.sonder(args.engine_home)
    schemas_du_moteur: list[str] = []
    racine_moteur = engine.racine_du_moteur(args.engine_home)
    if etat["disponible"] and racine_moteur is not None:
        for fichier in sorted((racine_moteur / "schemas").glob("*.json")):
            schemas_du_moteur.append(f"schemas/{fichier.name}")

    print(
        json.dumps(
            {
                "gateway_envelopes": propres,
                "engine_report_contracts": [
                    "neomundi.evidence.verification-report/1",
                    "neomundi.evidence.attestation-report/1",
                ],
                "engine_schemas_present": schemas_du_moteur,
                "note": (
                    "The report contracts above are emitted by the engine and "
                    "documented in its docs/INTEGRATION.md. They are NOT "
                    "published as JSON Schemas by the engine; the gateway "
                    "republishes their payload verbatim and does not redefine "
                    "them."
                ),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


def construire_analyseur() -> argparse.ArgumentParser:
    analyseur = argparse.ArgumentParser(
        prog="gateway.py",
        description=(
            "Interface d entree/sortie du moteur NeoMundi Evidence. "
            "Ne verifie rien par elle-meme."
        ),
    )
    analyseur.add_argument("--version", action="version", version=VERSION_DU_GATEWAY)
    sous = analyseur.add_subparsers(dest="commande", required=True)

    def communs(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--engine-home",
            default=None,
            help=f"racine du moteur Evidence (sinon ${engine.VAR_MOTEUR})",
        )
        p.add_argument(
            "--artifact-root",
            default=None,
            help="racine sous laquelle les chemins de la requete doivent rester (defaut : repertoire courant)",
        )
        p.add_argument("--out", default=None, help="ecrire la reponse JSON dans ce fichier")

    p = sous.add_parser("submit", help="soumettre une requete JSON (interface stable)")
    p.add_argument("request", help="fichier de requete au contrat gateway.request/1")
    communs(p)
    p.set_defaults(fonction=commande_submit)

    p = sous.add_parser("verify", help="raccourci : verifier un artefact")
    p.add_argument("artifact")
    p.add_argument("--corpus", default=None)
    p.add_argument("--strict", action="store_true")
    p.add_argument("--name", default=None, help="nom logique de l artefact dans la reponse")
    p.add_argument("--lang", default="fr", choices=("fr", "en"))
    communs(p)
    p.set_defaults(fonction=commande_verify)

    p = sous.add_parser("attest", help="raccourci : verifier une attestation detachee")
    p.add_argument("attestation")
    p.add_argument("--artifact", required=True)
    p.add_argument("--trust-store", required=True)
    p.add_argument("--allow-test-keys", action="store_true")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--name", default=None)
    p.add_argument("--lang", default="fr", choices=("fr", "en"))
    communs(p)
    p.set_defaults(fonction=commande_attest)

    p = sous.add_parser("engine", help="sonder la disponibilite du moteur")
    p.add_argument("--engine-home", default=None)
    p.set_defaults(fonction=commande_engine)

    p = sous.add_parser("contracts", help="lister les contrats d enveloppe et de rapport")
    p.add_argument("--engine-home", default=None)
    p.set_defaults(fonction=commande_contracts)

    return analyseur


def main(argv: list[str] | None = None) -> int:
    args = construire_analyseur().parse_args(argv)
    return int(args.fonction(args))


if __name__ == "__main__":
    sys.exit(main())
