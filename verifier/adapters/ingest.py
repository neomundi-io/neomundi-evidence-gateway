# -*- coding: utf-8 -*-
"""Ingere un paquet d execution fourni par un tiers. N EXECUTE RIEN.

    python adapters/ingest.py <dossier|paquet.zip> \\
        --out rapport.json [--md rapport.md] \\
        [--trust-store <magasin.json>] [--strict] [--lang fr|en]

CE QUE CE PROGRAMME COMBLE
--------------------------

`verify.py` ne sait lire qu une archive DEJA au format Evidence : il exige un
`manifest.json` et des membres connus. Confronte au dossier reel recu le
30 octobre -- 22 fichiers, 21 empreintes declarees, 21 concordantes -- il a
refuse, et ce refus etait JUSTE : ce paquet n est pas une archive Evidence.

Rien ne convertissait donc une collecte brute en objet exploitable. Un pilote
pouvait nous tendre ses fichiers et s arreter la. C est ce chainon, et rien
de plus.

LA SEULE REGLE QUI COMPTE
-------------------------

**Une declaration non verifiee ne devient jamais un fait atteste.** Chaque
ligne du rapport porte donc sa nature :

  CONTROLE        nous l avons recalcule. Empreintes, tailles, structure,
                  signatures. C est le seul registre ou nous engageons
                  quelque chose.
  DECLARE         la parole du soumetteur, conservee VERBATIM. Identite,
                  modele, conditions d execution. Nous la transportons,
                  nous ne la cautionnons pas.
  NON DEMONTRABLE aucun controle ne pourrait l etablir depuis ce paquet.
                  Ce n est pas un manque de zele : c est une propriete du
                  materiau.

Un champ dont le chemin ne resout pas est **absent**, jamais `null` -- meme
discipline que pour un signal non mesure.

DEUX CONTRATS, ET UNE SEULE DIFFERENCE
--------------------------------------

`neomundi.evidence.submission/1` et `/2` sont tous deux acceptes. `/2`
differe en UN point : `execution.model_declared` peut y etre **nul**, et
seulement motive -- `not_applicable` quand aucun modele d IA n est
intervenu, `unavailable` quand un modele est intervenu et que son identite
n a pas pu etre etablie. Sans ces deux motifs, declarer une execution
deterministe obligeait a **inventer** un identifiant de modele.

Un paquet `/1` au modele nul reste refuse, exactement comme avant : la
version du contrat est ce qui separe les deux lectures. Voir
`controle_execution`.

CE QU IL NE FAIT PAS, PAR CONSTRUCTION
--------------------------------------

Il n execute aucun code venu du paquet, ne suit aucun lien symbolique,
n ecrit jamais dans le paquet soumis, et n a besoin d AUCUNE cle privee.
Il ne verifie pas les signatures lui-meme : il appelle
`verify_attestation.py`, le MEME verificateur qu un auditeur, et rapporte
son verdict tel quel. Aucun second moteur de signature n existe ici.

Le magasin de confiance vient de l OPERATEUR, jamais du paquet : un paquet
ne doit pas porter sa propre reponse a la question de savoir si son
signataire est digne de confiance.

Bibliotheque standard seule.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
import zipfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

try:
    import i18n
except ImportError:  # pragma: no cover - chemin de degradation
    class i18n:  # type: ignore[no-redef]
        FR = "fr"
        EN = "en"

        @staticmethod
        def traduire(texte: str, langue: str) -> str:
            return texte

        @staticmethod
        def traduire_format(format_fr: str, langue: str) -> str:
            return format_fr


SCHEMA_SOUMISSION = "neomundi.evidence.submission/1"
SCHEMA_SOUMISSION_V2 = "neomundi.evidence.submission/2"

#: Les deux contrats acceptes, et ils ne disent pas la meme chose. `/1` exige
#: un `model_declared` non vide ; `/2` admet qu il soit nul, et seulement
#: motive. Un manifeste `/1` au modele nul reste donc refuse, exactement
#: comme avant : la VERSION est ce qui separe les deux lectures, et c est
#: pour cela qu une nouvelle a ete emise au lieu d elargir la premiere.
#: Elargir `/1` aurait rendu valides, sous un identifiant inchange, des
#: documents qu il refusait -- deux contrats pour une seule reference.
SCHEMAS_SOUMISSION = (SCHEMA_SOUMISSION, SCHEMA_SOUMISSION_V2)

SCHEMA_RAPPORT = "neomundi.evidence.ingestion-report/1"
MANIFESTE = "submission.json"

#: Les deux seuls motifs d absence de modele, et ils ne se remplacent pas.
#:
#:   not_applicable  AUCUN modele d IA n est intervenu -- execution
#:                   deterministe, regles en code, table figee. Il n y a
#:                   rien a nommer.
#:   unavailable     un modele d IA EST intervenu, et son identite n a pas
#:                   pu etre etablie. Il y a quelque chose a nommer, et on
#:                   ne le connait pas.
#:
#: Les confondre est la facon dont une execution intracable finit classee
#: comme deterministe. Aucun des deux ne vaut une identite : rien n est
#: substitue a un modele absent, jamais.
MOTIFS_ABSENCE_MODELE = ("not_applicable", "unavailable")

#: Les champs que chaque contrat definit pour `execution`. Un champ hors de
#: cette liste est RAPPORTE et non controle -- meme discipline que pour un
#: fichier non declare : le taire laisserait croire qu il a ete couvert.
CHAMPS_EXECUTION_V1 = frozenset({
    "kind_declared", "model_declared", "provider_declared",
    "executed_at_declared", "parameters_declared", "notes_declared",
})
CHAMPS_EXECUTION_V2 = CHAMPS_EXECUTION_V1 | {
    "model_absence_reason_declared", "model_absence_note_declared",
}

#: Memes listes, pour `pilot` et `provenance_declared`. Les deux objets
#: portent `additionalProperties: false` dans les deux contrats, et un champ
#: en surplus y etait avale sans un mot -- alors que `execution` le NOMMAIT
#: depuis le debut. L asymetrie n etait pas une politique, c etait un oubli.
CHAMPS_PILOTE = frozenset({
    "name_declared", "reference_declared", "contact_declared",
})
CHAMPS_PROVENANCE = frozenset({
    "code_reference_declared", "environment_declared", "evaluator_declared",
    "notes_declared",
})
#: Et les champs d un artefact. Meme objet ferme, meme politique : un champ
#: en surplus est NOMME, jamais avale. Le taire ici aurait laisse la seule
#: incoherence que le reste de ce correctif supprime.
CHAMPS_ARTEFACT = frozenset({
    "path", "sha256", "bytes", "role", "media_type",
})

#: Les quatre natures d execution du contrat, et c est une enumeration
#: FERMEE. `other` existe precisement pour le cas ou aucune des trois
#: premieres ne convient : il n y a donc aucun besoin legitime d une
#: cinquieme valeur, et une valeur inconnue n est pas un paquet a completer,
#: c est un paquet a corriger.
#:
#: Les deux contrats publient la MEME enumeration. L appliquer n est donc
#: pas un durcissement de `/1` : c est la mise en oeuvre de ce que `/1`
#: declarait deja. Voir `tests/test_contrat_v2_schema.py`, qui epingle cette
#: constante aux deux schemas publies.
NATURES_EXECUTION = ("single_call", "batch", "replay", "other")

#: Ce que le soumetteur dit qu un fichier EST. Declare -- l ingestion ne
#: lit pas l interieur d un artefact pour confirmer son role -- mais
#: OBLIGATOIRE : `artifacts.items.required` le range au meme rang que
#: `sha256`. Un artefact sans role laisse un paquet integre et inexploitable
#: sans l ouvrir fichier par fichier, ce que l ingestion s interdit.
#:
#: Meme enumeration dans les deux contrats. Meme epinglage.
ROLES_ARTEFACT = ("prompt", "response", "recording", "transcript",
                  "measurement", "receipt", "attestation", "other")

#: `$defs.instant` des deux schemas : UTC, precision a la seconde, `Z`
#: final. Ce motif controle la FORME, et rien de plus. La VERACITE de la
#: date reste hors de portee -- aucune horloge de confiance n intervient, et
#: l ingestion ne lit JAMAIS sa propre horloge pour contredire une date
#: declaree. Le rapport continue de le dire en NON DEMONTRABLE.
#:
#: Pourquoi controler la forme malgre tout : un horodatage hors format n est
#: ni triable, ni comparable, ni analysable, et il entre verbatim dans le
#: rapport. << yesterday >> relativement a quoi ?
MOTIF_INSTANT = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}"
                           r"T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")

#: Distingue la clef ABSENTE de la clef presente a `null`. Un oubli et une
#: declaration ne sont pas la meme chose, et `dict.get` les confond.
_ABSENTE = object()

PASS, FAIL, NOT_TESTED = "PASS", "FAIL", "NOT TESTED"
CONTROLE, DECLARE, INDEMONTRABLE = "CONTROLE", "DECLARE", "NON DEMONTRABLE"

ACCEPTE, REJETE, INCOMPLET = "ACCEPTE", "REJETE", "INCOMPLET"

#: Bornes de securite. Un paquet soumis est une entree HOSTILE jusqu a
#: preuve du contraire : il peut etre malforme par accident comme par
#: dessein, et les deux cas se traitent pareil.
MAX_ARTEFACTS = 512
MAX_OCTETS_PAR_FICHIER = 64 * 1024 * 1024
MAX_OCTETS_TOTAL = 256 * 1024 * 1024
MAX_MEMBRES_ZIP = 4096

#: Un chemin de soumission est RELATIF, en barres obliques, sans remontee.
#: Les trois refus ci-dessous ne sont pas du zele : un paquet capable de
#: nommer un fichier hors de lui-meme peut faire ecrire ou lire n importe ou.
MOTIF_CHEMIN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,511}$")

_LANGUE = [i18n.FR]


def dis(*morceaux: object) -> None:
    if not morceaux:
        print()
        return
    premier = morceaux[0]
    if isinstance(premier, str):
        pose = i18n.traduire_format(premier, _LANGUE[0])
        if pose == premier:
            pose = i18n.traduire(premier, _LANGUE[0])
        premier = pose
    print(premier, *morceaux[1:])


class Bilan:
    """Trois etats, et pour chacun sa NATURE. `NOT TESTED` n est pas un `PASS`."""

    def __init__(self) -> None:
        self.lignes: list[dict] = []

    def dire(self, etat: str, nature: str, intitule: str, detail: str = "",
             requis: bool = False) -> None:
        self.lignes.append({"etat": etat, "nature": nature,
                            "intitule": intitule, "detail": detail,
                            "requis": requis})
        vu = i18n.traduire(intitule, _LANGUE[0])
        vu_detail = i18n.traduire(detail, _LANGUE[0])
        print("[%-10s] [%-15s] %s%s"
              % (etat, nature, vu, " - " + vu_detail if vu_detail else ""))

    def compte(self, etat: str) -> int:
        return sum(1 for l in self.lignes if l["etat"] == etat)

    def requis_non_demontres(self) -> list[str]:
        return [l["intitule"] for l in self.lignes
                if l["requis"] and l["etat"] != PASS]

    def verdict(self) -> str:
        """ACCEPTE, REJETE ou INCOMPLET -- et jamais autre chose.

        Un FAIL rejette. Sans FAIL, un controle REQUIS non demontre rend le
        paquet INCOMPLET : ce n est pas un refus, c est un paquet auquel il
        manque quelque chose que le soumetteur peut fournir.
        """
        if self.compte(FAIL):
            return REJETE
        if self.requis_non_demontres():
            return INCOMPLET
        return ACCEPTE


def sha256_fichier(chemin: Path) -> str:
    h = hashlib.sha256()
    with chemin.open("rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def dire_surplus(bilan: Bilan, intitule: str, objet: dict,
                 connus: frozenset[str] | set[str]) -> None:
    """Nomme les champs hors contrat d un objet. Ne refuse PAS.

    `additionalProperties: false` est la lettre du schema, et la refuser
    serait defendable. Ce depot a tranche autrement pour `execution`, et le
    motif vaut ici : un champ en surplus n invalide rien, et le refuser
    romprait un paquet que le contrat precedent acceptait. Mais le TAIRE
    laisserait croire qu il a ete lu.

    C est donc une divergence ASSUMEE avec le schema, nommee comme telle
    dans `tests/test_ingestion_robustesse.py` -- et une divergence nommee
    n est pas le defaut que cet ensemble de correctifs traite. Une
    divergence INCONNUE l etait.
    """
    surplus = [c for c in sorted(objet) if c not in connus]
    if surplus:
        bilan.dire(NOT_TESTED, CONTROLE, intitule,
                   "%d champ(s) hors du contrat declare, donc NON "
                   "controle(s) : %s" % (len(surplus), ", ".join(surplus)))


def chemin_sur(brut: object) -> tuple[bool, str]:
    """Le chemin declare est-il relatif, sans remontee, sans lettre de lecteur ?"""
    if not isinstance(brut, str) or not brut:
        return False, "chemin absent ou non textuel"
    if "\\" in brut:
        return False, "barre oblique inversee : un chemin de soumission s ecrit en `/`"
    if brut.startswith("/"):
        return False, "chemin ABSOLU"
    if re.match(r"^[A-Za-z]:", brut):
        return False, "lettre de lecteur"
    if ".." in brut.split("/"):
        return False, "segment `..` : remontee hors du paquet"
    if not MOTIF_CHEMIN.match(brut):
        return False, "caracteres hors du jeu admis"
    return True, ""


def deplier(source: Path, travail: Path, bilan: Bilan) -> Path | None:
    """Rend la racine a lire. Un `.zip` est deplie SOUS CONTROLE."""
    if source.is_dir():
        bilan.dire(PASS, CONTROLE, "forme du paquet",
                   "dossier lu sur place, aucune extraction")
        return source
    if not zipfile.is_zipfile(source):
        bilan.dire(FAIL, CONTROLE, "forme du paquet",
                   "ni dossier ni archive ZIP lisible : %s" % source.name)
        return None

    cible = travail / "deplie"
    cible.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source) as z:
        infos = z.infolist()
        if len(infos) > MAX_MEMBRES_ZIP:
            bilan.dire(FAIL, CONTROLE, "forme du paquet",
                       "%d membres, borne %d" % (len(infos), MAX_MEMBRES_ZIP))
            return None
        # La taille DECOMPRESSEE est verifiee AVANT d ecrire quoi que ce
        # soit : un paquet de quelques kilo-octets peut se deplier en
        # gigaoctets, et l apprendre pendant l extraction est trop tard.
        total = sum(i.file_size for i in infos)
        if total > MAX_OCTETS_TOTAL:
            bilan.dire(FAIL, CONTROLE, "forme du paquet",
                       "%d octets decompresses annonces, borne %d"
                       % (total, MAX_OCTETS_TOTAL))
            return None
        for i in infos:
            ok, pourquoi = chemin_sur(i.filename.rstrip("/"))
            if not ok:
                bilan.dire(FAIL, CONTROLE, "chemins du paquet",
                           "membre refuse %r : %s" % (i.filename, pourquoi))
                return None
        z.extractall(cible)
    bilan.dire(PASS, CONTROLE, "forme du paquet",
               "archive ZIP de %d membre(s), %d octets decompresses, depliee"
               % (len(infos), total))
    return cible


def controle_manifeste(racine: Path, bilan: Bilan) -> dict | None:
    chemin = racine / MANIFESTE
    if not chemin.is_file():
        bilan.dire(FAIL, CONTROLE, "manifeste de soumission",
                   "`%s` absent a la racine du paquet" % MANIFESTE)
        return None
    try:
        # Sur des OCTETS : un BOM UTF-8 est detecte tout seul. Quinze des
        # vingt-deux fichiers du dossier reel du 30 octobre en portaient un.
        doc = json.loads(chemin.read_bytes())
    except (ValueError, OSError) as erreur:
        bilan.dire(FAIL, CONTROLE, "manifeste de soumission",
                   "`%s` illisible : %s" % (MANIFESTE, type(erreur).__name__))
        return None
    if not isinstance(doc, dict):
        bilan.dire(FAIL, CONTROLE, "manifeste de soumission",
                   "le manifeste n est pas un objet JSON")
        return None
    if doc.get("schema") not in SCHEMAS_SOUMISSION:
        bilan.dire(FAIL, CONTROLE, "schema du manifeste",
                   "attendu l un de %s, declare %r"
                   % (" ou ".join(SCHEMAS_SOUMISSION), doc.get("schema")))
        return None
    bilan.dire(PASS, CONTROLE, "manifeste de soumission",
               "%s, %d octets" % (doc.get("schema"), chemin.stat().st_size))
    return doc


def valeurs_non_encodables(valeur: object, chemin: str = "$") -> list[str]:
    """Les chemins des chaines qui ne peuvent PAS s ecrire en UTF-8.

    POURQUOI CE CONTROLE EXISTE
    ---------------------------

    `json.loads` accepte une demi-paire de substitution UTF-16 ecrite en
    echappement : six caracteres ASCII, barre oblique inverse puis `ud800`,
    donnent un `str` Python portant U+D800. Le
    FICHIER est de l UTF-8 parfaitement valide -- il contient six caracteres
    ASCII -- mais la VALEUR DECODEE n est pas de l Unicode valide, et
    `.encode("utf-8")` la refuse.

    Consequence mesuree AVANT ce controle : l ingestion imprimait
    `VERDICT : ACCEPTE`, puis levait `UnicodeEncodeError` en ecrivant son
    rapport, et sortait en 1 SANS RAPPORT. Trois sorties contradictoires du
    meme passage : un lecteur humain lisait << accepte >>, un script lisait
    << rejete >>, et il n y avait aucun rapport pour arbitrer. Six
    caracteres dans un champ declare suffisaient a le provoquer.

    C est une GARDE NOMMEE, au sens de la distinction que pose le filet de
    `main()` : elle dit OU est la faute, donc ce qu un soumetteur peut
    corriger. Le filet, lui, ne nomme rien et ne sert qu a garantir qu un
    rapport existe toujours.

    CE QUE CE CONTROLE NE TRANCHE PAS
    ---------------------------------

    La RFC 8259 §8.2 reconnait que sa grammaire autorise des chaines qui ne
    representent pas de l Unicode, et declare un tel texte NON INTEROPERABLE
    -- sans l interdire. `json` de Python l accepte, le verificateur Rust le
    refuse. Cette divergence est une ambiguite de contrat de la meme famille
    que les clefs en double, et elle n est PAS arbitree ici.

    Ce controle ne porte donc pas sur la validite du manifeste au regard de
    la RFC : il porte sur un fait verifiable et borne -- cette valeur ne peut
    pas etre portee verbatim dans le rapport. Or le contrat OBLIGE a la
    conserver verbatim. Un paquet qui rend cette obligation impossible a
    tenir est refuse, et la raison est dite.
    """
    mauvais: list[str] = []
    if isinstance(valeur, str):
        try:
            valeur.encode("utf-8")
        except UnicodeEncodeError:
            mauvais.append(chemin)
        return mauvais
    if isinstance(valeur, dict):
        for cle, sous in valeur.items():
            if isinstance(cle, str):
                try:
                    cle.encode("utf-8")
                except UnicodeEncodeError:
                    mauvais.append("%s.<nom de membre>" % chemin)
            mauvais += valeurs_non_encodables(sous, "%s.%s" % (chemin, cle))
        return mauvais
    if isinstance(valeur, list):
        for index, sous in enumerate(valeur):
            mauvais += valeurs_non_encodables(sous, "%s[%d]" % (chemin, index))
    return mauvais


def controle_encodabilite(doc: dict, bilan: Bilan) -> list[str]:
    """Le manifeste peut-il etre reporte verbatim ? Voir la docstring ci-dessus.

    Rend les chemins fautifs, pour que le rapport puisse les ECARTER
    deliberement au lieu de laisser son ecriture echouer. Le filet de
    `main()` resterait capable de rattraper l echec, mais une trace de pile
    emise a chaque fois pour une condition NOMMEE et TRAITEE apprendrait a
    ignorer les traces de pile.
    """
    mauvais = valeurs_non_encodables(doc)
    if mauvais:
        bilan.dire(FAIL, CONTROLE, "declarations reportables verbatim",
                   "%d valeur(s) ne peuvent pas s ecrire en UTF-8 et ne "
                   "peuvent donc pas etre conservees verbatim dans le "
                   "rapport : %s. Cause habituelle : une demi-paire de "
                   "substitution UTF-16 dans une chaine. Le "
                   "contrat exige la conservation verbatim ; un paquet qui "
                   "la rend impossible est refuse."
                   % (len(mauvais), ", ".join(mauvais[:5])))
    else:
        bilan.dire(PASS, CONTROLE, "declarations reportables verbatim",
                   "toutes les chaines du manifeste s ecrivent en UTF-8")
    return mauvais


def ecrire_rapports_de_secours(arguments, rapport: dict) -> None:
    """Seconde tentative d ecriture, en ASCII pur.

    `ensure_ascii=True` echappe tout en sequences ASCII, y compris une
    demi-paire de substitution : les octets produits sont alors de l ASCII,
    donc ecrivables. Le rapport reste lisible par `json.loads`.

    Elle est appelee SEULEMENT apres un echec, et apres que les declarations
    verbatim ont ete remplacees par la mention de leur omission : un rapport
    ampute qui le DIT vaut mieux qu aucun rapport.
    """
    if arguments.out:
        arguments.out.parent.mkdir(parents=True, exist_ok=True)
        arguments.out.write_bytes(
            (json.dumps(rapport, ensure_ascii=True, indent=2) + "\n")
            .encode("ascii"))
    if arguments.md:
        arguments.md.parent.mkdir(parents=True, exist_ok=True)
        arguments.md.write_bytes(
            rendre_markdown(rapport).encode("utf-8", "replace"))


def controle_champs(doc: dict, bilan: Bilan) -> None:
    requis = ["submission_id", "submitted_at_declared", "pilot",
              "execution", "artifacts"]
    manquants = [c for c in requis if c not in doc]
    if manquants:
        bilan.dire(FAIL, CONTROLE, "champs obligatoires",
                   "absents : %s" % ", ".join(manquants))
    else:
        bilan.dire(PASS, CONTROLE, "champs obligatoires",
                   "les %d champs du contrat sont presents" % len(requis))

    ident = doc.get("submission_id")
    if not isinstance(ident, str) or not re.match(r"^[a-z0-9][a-z0-9-]{2,63}$", ident):
        bilan.dire(FAIL, CONTROLE, "identifiant de soumission",
                   "non conforme a `^[a-z0-9][a-z0-9-]{2,63}$` : %r" % ident)
    else:
        bilan.dire(PASS, CONTROLE, "identifiant de soumission", ident)

    # La FORME de la date, et elle seule. Le contrat la range dans
    # `required` et la contraint par `$defs.instant` ; rien ici ne pretend
    # qu elle soit vraie. La ligne NON DEMONTRABLE sur la date reste emise
    # par `controle_provenance`, et elle dit le reste.
    #
    # Silencieux quand la forme est bonne : la valeur figure deja dans
    # `declared_verbatim.submitted_at_declared`, et emettre une ligne de
    # plus aurait change les decomptes de TOUT paquet valide -- y compris
    # ceux deja ingeres. Le choix est documente, et son revers assume : un
    # rapport ACCEPTE ne nomme pas ce controle-la.
    quand = doc.get("submitted_at_declared", _ABSENTE)
    if quand is not _ABSENTE and (not isinstance(quand, str)
                                  or not MOTIF_INSTANT.match(quand)):
        bilan.dire(FAIL, CONTROLE, "date declaree",
                   "`submitted_at_declared` = %r : le contrat exige UTC a la "
                   "seconde, avec `Z` final. Sa VERACITE reste hors de "
                   "portee ; sa FORME, non." % (quand,))

    # `X or {}` ne protege pas d une liste NON VIDE : elle est vraie, et
    # `.get` n existe pas dessus. La garde est un `isinstance`, exactement
    # comme pour `execution` dans `controle_execution` -- l asymetrie entre
    # les deux etait le defaut, pas l intention.
    pilote = doc.get("pilot")
    if pilote is None:
        pilote = {}
    if not isinstance(pilote, dict):
        bilan.dire(FAIL, CONTROLE, "identite du soumetteur",
                   "`pilot` n est pas un objet JSON")
    else:
        dire_surplus(bilan, "champs de pilote hors contrat", pilote,
                     CHAMPS_PILOTE)
        nom = pilote.get("name_declared")
        if not isinstance(nom, str) or not nom.strip():
            bilan.dire(FAIL, CONTROLE, "identite du soumetteur",
                       "`pilot.name_declared` absent ou vide")
        else:
            # DECLARE, et c est tout ce que cela peut etre : rien dans un
            # fichier n etablit qui l a ecrit.
            bilan.dire(NOT_TESTED, DECLARE, "identite du soumetteur",
                       "%r -- declaree, et non verifiee. Aucun controle sur "
                       "un paquet ne peut etablir qui l a produit." % nom)

    controle_execution(doc, bilan)


def controle_execution(doc: dict, bilan: Bilan) -> None:
    """Les conditions d execution, et le seul cas ou le modele peut etre nul.

    DEUX ABSENCES QUI NE SE DISENT PAS PAREIL
    -----------------------------------------

    Jusqu au contrat `/2`, `model_declared` devait porter un identifiant non
    vide. Deux executions reelles ne pouvaient donc pas etre declarees sans
    mentir :

      * une execution DETERMINISTE, ou aucun modele d IA n intervient. Il n y
        a aucune identite a declarer -- `not_applicable` ;
      * une execution ou un modele EST intervenu, et dont l identite n a pas
        pu etre etablie -- `unavailable`.

    Le soumetteur n avait que deux issues : inventer un identifiant, ou ne
    rien soumettre. La premiere est exactement ce que tout ce depot interdit.

    CE QUE LE MOTIF NE FAIT PAS
    ---------------------------

    Il n atteste rien. Motif et note sont de nature DECLARE, comme le modele
    lui-meme : l ingestion les transporte VERBATIM et n en controle aucun.
    Un motif n est donc pas une derogation -- il ne fait tomber aucun autre
    controle, et il ne vaut jamais une identite.

    LES TROIS REFUS, ET POURQUOI CHACUN
    -----------------------------------

      * nul SANS motif -- indiscernable d un oubli. Rien dans le paquet ne
        dirait laquelle des deux situations c est ;
      * motif SANS note non vide -- le motif dit laquelle des deux situations
        c est, la note dit ce qui s est passe. Un motif seul est une
        etiquette, et une etiquette ne se soupese pas ;
      * un modele nomme ET un motif d absence -- une contradiction. Une des
        deux affirmations est fausse, et rien ici ne dit laquelle.
    """
    version = doc.get("schema")
    exe = doc.get("execution")
    if not isinstance(exe, dict):
        bilan.dire(FAIL, CONTROLE, "conditions d execution",
                   "`execution` n est pas un objet JSON")
        return

    # Deux fautes, et elles ne se lisent pas pareil : une clef ABSENTE est
    # un oubli, une valeur hors enumeration est une erreur. Le test de
    # vacuite d avant attrapait la premiere et laissait passer la seconde --
    # toute chaine non vide satisfaisait `not exe.get(...)`.
    nature = exe.get("kind_declared", _ABSENTE)
    if nature is _ABSENTE or nature is None:
        bilan.dire(FAIL, CONTROLE, "conditions d execution",
                   "`execution.kind_declared` absent")
        return
    if nature not in NATURES_EXECUTION:
        # Pas de `return` : un paquet dont la nature est fausse a tout de
        # meme une declaration de modele a rapporter, et le soumetteur gagne
        # a tout apprendre d un seul coup. Meme discipline qu au cas 29 --
        # un controle qui echoue n en fait pas tomber un autre.
        bilan.dire(FAIL, CONTROLE, "conditions d execution",
                   "`execution.kind_declared` = %r, hors des %d natures du "
                   "contrat : %s"
                   % (nature, len(NATURES_EXECUTION),
                      ", ".join(NATURES_EXECUTION)))

    connus = (CHAMPS_EXECUTION_V2 if version == SCHEMA_SOUMISSION_V2
              else CHAMPS_EXECUTION_V1)
    surplus = [c for c in sorted(exe) if c not in connus]
    if surplus:
        # Pas un FAIL : un champ en surplus n invalide rien, et le refuser
        # romprait un paquet que le contrat precedent acceptait. Mais le
        # taire laisserait croire qu il a ete lu.
        bilan.dire(NOT_TESTED, CONTROLE, "champs d execution hors contrat",
                   "%d champ(s) hors du contrat declare, donc NON "
                   "controle(s) : %s" % (len(surplus), ", ".join(surplus)))

    modele = exe.get("model_declared", _ABSENTE)
    motif = exe.get("model_absence_reason_declared")
    note = exe.get("model_absence_note_declared")

    # La clef absente reste un oubli, dans les deux contrats. C est ce qui
    # rend l absence EXPLICITE possible : si omettre la clef valait `null`,
    # un oubli se lirait comme une declaration.
    if modele is _ABSENTE:
        bilan.dire(FAIL, CONTROLE, "conditions d execution",
                   "`execution.model_declared` absent")
        return

    # CE QUE << NOMME >> VEUT DIRE N EST PAS LE MEME DANS LES DEUX CONTRATS.
    #
    # `/2` exige un caractere non blanc, et son schema le publie
    # (`pattern: \S`) : une suite d espaces satisfait `minLength: 1` et ne
    # nomme rien. `/1` ne publie que `minLength: 1`, et son validateur
    # acceptait donc un identifiant tout en blancs. Y appliquer la regle
    # stricte refuserait un paquet que le contrat publie declare valide --
    # un durcissement retroactif, decide par nous et par personne d autre.
    # La laxite de `/1` est donc CONSERVEE, et nommee ici.
    if version == SCHEMA_SOUMISSION_V2:
        nomme = isinstance(modele, str) and bool(modele.strip())
    else:
        nomme = isinstance(modele, str) and bool(modele)

    if nomme:
        if version == SCHEMA_SOUMISSION_V2 and not (motif is None and note is None):
            bilan.dire(FAIL, CONTROLE, "conditions d execution",
                       "un modele est nomme ET un motif d absence est declare "
                       "(%r) : une des deux affirmations est fausse, et rien "
                       "dans ce paquet ne dit laquelle" % (motif,))
            return
        bilan.dire(NOT_TESTED, DECLARE, "conditions d execution",
                   "modele %r, nature %r, fournisseur %r -- declares. Ce "
                   "paquet ne porte rien qui permette de les confronter."
                   % (modele, exe.get("kind_declared"),
                      exe.get("provider_declared")))
        return

    if modele is None:
        if version != SCHEMA_SOUMISSION_V2:
            bilan.dire(FAIL, CONTROLE, "conditions d execution",
                       "`execution.model_declared` est nul, et le contrat "
                       "declare ne l admet pas. Le declarer nul exige le "
                       "contrat %s, et un motif." % SCHEMA_SOUMISSION_V2)
            return
        if motif not in MOTIFS_ABSENCE_MODELE:
            # Les deux motifs sont deux arguments du format, et non un
            # seul deja joint : un argument traverse la traduction
            # VERBATIM, et un << ou >> joint ici ressortirait en francais
            # dans la sortie anglaise.
            bilan.dire(FAIL, CONTROLE, "conditions d execution",
                       "`execution.model_declared` est nul et le motif vaut "
                       "%r : attendu `%s` ou `%s`. Une absence sans motif "
                       "reconnu ne se distingue pas d un oubli."
                       % ((motif,) + MOTIFS_ABSENCE_MODELE))
            return
        if not isinstance(note, str) or not note.strip():
            bilan.dire(FAIL, CONTROLE, "conditions d execution",
                       "motif `%s` declare et note absente, vide ou non "
                       "textuelle (%r) : le motif dit laquelle des deux "
                       "situations c est, la note dit ce qui s est passe."
                       % (motif, note))
            return
        if motif == "not_applicable":
            bilan.dire(NOT_TESTED, DECLARE, "conditions d execution",
                       "aucun modele declare, motif `not_applicable` : le "
                       "soumetteur declare qu AUCUN modele d IA n est "
                       "intervenu. Nature %r, note %r -- declarees, et non "
                       "controlees." % (exe.get("kind_declared"), note))
        else:
            bilan.dire(NOT_TESTED, DECLARE, "conditions d execution",
                       "aucun modele declare, motif `unavailable` : un modele "
                       "d IA est intervenu et son identite n a pas pu etre "
                       "etablie. Elle reste INCONNUE, et rien ne lui est "
                       "substitue. Nature %r, note %r -- declarees, et non "
                       "controlees." % (exe.get("kind_declared"), note))
        return

    bilan.dire(FAIL, CONTROLE, "conditions d execution",
               "`execution.model_declared` n est ni un identifiant non vide ni "
               "nul : %r" % (modele,))


def controle_artefacts(racine: Path, doc: dict, bilan: Bilan) -> list[dict]:
    """Le SEUL registre ou ce programme etablit quelque chose."""
    artefacts = doc.get("artifacts")
    if not isinstance(artefacts, list) or not artefacts:
        bilan.dire(FAIL, CONTROLE, "artefacts declares",
                   "aucun artefact declare")
        return []
    if len(artefacts) > MAX_ARTEFACTS:
        bilan.dire(FAIL, CONTROLE, "artefacts declares",
                   "%d artefacts, borne %d" % (len(artefacts), MAX_ARTEFACTS))
        return []

    resultats: list[dict] = []
    total = 0
    concordants = absents = discordants = refuses = 0
    #: `role` est DECLARE et OBLIGATOIRE a la fois -- le contrat le range
    #: dans `artifacts.items.required`, et precise qu une ingestion ne lit
    #: pas l interieur d un fichier pour le confirmer. Les deux tiennent :
    #: on exige qu il soit la, on ne juge pas s il est juste.
    sans_role: list[str] = []
    role_hors_enum: list[str] = []
    champs_surplus: set[str] = set()

    for a in artefacts:
        brut = a.get("path") if isinstance(a, dict) else None
        if isinstance(a, dict):
            role = a.get("role", _ABSENTE)
            etiquette = brut if isinstance(brut, str) and brut else "?"
            if role is _ABSENTE:
                sans_role.append(etiquette)
            elif role not in ROLES_ARTEFACT:
                role_hors_enum.append("%s -> %r" % (etiquette, role))
            champs_surplus |= {c for c in a if c not in CHAMPS_ARTEFACT}
        ok, pourquoi = chemin_sur(brut)
        if not ok:
            refuses += 1
            resultats.append({"path": brut, "etat": "chemin_refuse",
                              "pourquoi": pourquoi})
            continue
        cible = racine / brut
        # Resolution puis confinement : le motif de chemin ne suffit pas,
        # un lien symbolique passe le motif et sort du paquet.
        try:
            resolu = cible.resolve()
            dedans = resolu == racine.resolve() or racine.resolve() in resolu.parents
        except OSError:
            dedans = False
        if cible.is_symlink() or not dedans:
            refuses += 1
            resultats.append({"path": brut, "etat": "chemin_refuse",
                              "pourquoi": "lien symbolique ou cible hors du paquet"})
            continue
        if not cible.is_file():
            absents += 1
            resultats.append({"path": brut, "etat": "absent"})
            continue
        taille = cible.stat().st_size
        if taille > MAX_OCTETS_PAR_FICHIER:
            refuses += 1
            resultats.append({"path": brut, "etat": "trop_volumineux",
                              "bytes": taille})
            continue
        total += taille
        if total > MAX_OCTETS_TOTAL:
            bilan.dire(FAIL, CONTROLE, "volume du paquet",
                       "au-dela de %d octets au total" % MAX_OCTETS_TOTAL)
            return resultats
        reel = sha256_fichier(cible)
        annonce = a.get("sha256")
        octets_annonces = a.get("bytes")
        if reel == annonce and taille == octets_annonces:
            concordants += 1
            resultats.append({"path": brut, "etat": "concordant",
                              "sha256": reel, "bytes": taille,
                              "role_declared": a.get("role")})
        else:
            discordants += 1
            resultats.append({"path": brut, "etat": "discordant",
                              "sha256_recalcule": reel,
                              "sha256_declare": annonce,
                              "bytes_reels": taille,
                              "bytes_declares": octets_annonces})

    detail = ("%d concordant(s), %d discordant(s), %d absent(s), %d refuse(s), "
              "%d octets recalcules" % (concordants, discordants, absents,
                                        refuses, total))
    if discordants or refuses:
        bilan.dire(FAIL, CONTROLE, "empreintes des artefacts declares", detail)
    elif absents:
        # Un artefact annonce et non fourni n est pas une fraude : c est un
        # paquet incomplet, et le soumetteur peut le completer.
        bilan.dire(NOT_TESTED, CONTROLE, "empreintes des artefacts declares",
                   detail, requis=True)
    else:
        bilan.dire(PASS, CONTROLE, "empreintes des artefacts declares", detail)

    # Emis seulement quand quelque chose manque. Un paquet conforme ne gagne
    # pas de ligne, et son rapport est donc inchange -- y compris ses
    # decomptes. Les deux listes sont rendues ENTIERES jusqu a six noms :
    # un soumetteur qui a oublie `role` l a souvent oublie partout, et lui
    # rendre un seul chemin lui coute un aller-retour par artefact.
    #
    # Ni l un ni l autre ne court-circuite le recalcul d empreintes :
    # le registre des octets reste complet meme quand une declaration
    # manque.
    if sans_role:
        bilan.dire(FAIL, CONTROLE, "role des artefacts",
                   "%d artefact(s) sans `role`, champ obligatoire du "
                   "contrat : %s" % (len(sans_role), ", ".join(sans_role[:6])))
    if role_hors_enum:
        bilan.dire(FAIL, CONTROLE, "role des artefacts",
                   "%d role(s) hors des %d valeurs du contrat (%s) : %s"
                   % (len(role_hors_enum), len(ROLES_ARTEFACT),
                      ", ".join(ROLES_ARTEFACT),
                      ", ".join(role_hors_enum[:6])))
    # Les champs en surplus des artefacts, NOMMES comme ceux d `execution`,
    # de `pilot` et de `provenance_declared`. Les noms sont agreges : vingt
    # artefacts portant le meme champ invente sont un seul renseignement.
    if champs_surplus:
        bilan.dire(NOT_TESTED, CONTROLE, "champs d artefact hors contrat",
                   "%d champ(s) hors du contrat declare, donc NON "
                   "controle(s) : %s"
                   % (len(champs_surplus), ", ".join(sorted(champs_surplus))))
    return resultats


def controle_fichiers_non_declares(racine: Path, doc: dict,
                                   bilan: Bilan) -> list[str]:
    # Deuxieme lecture de `artifacts`, et elle a besoin de sa PROPRE garde :
    # celle de `controle_artefacts` ne protege que cette fonction-la. Une
    # garde posee a un endroit ne couvre pas les autres lectures du meme
    # champ -- c est ce qui faisait planter ici un `artifacts` numerique
    # pourtant deja refuse plus haut.
    bruts = doc.get("artifacts")
    declares = {a.get("path") for a in (bruts if isinstance(bruts, list) else [])
                if isinstance(a, dict)}
    declares.add(MANIFESTE)
    atts_bruts = doc.get("attestations")
    for att in (atts_bruts if isinstance(atts_bruts, list) else []):
        if isinstance(att, dict):
            declares.add(att.get("jws_path"))
            declares.add(att.get("subject_path"))
    presents = []
    for p in sorted(racine.rglob("*")):
        if p.is_file():
            presents.append(p.relative_to(racine).as_posix())
    surplus = [n for n in presents if n not in declares]
    if surplus:
        # Pas un FAIL : un fichier en surplus n invalide rien. Mais le taire
        # laisserait croire que le paquet a ete couvert en entier.
        bilan.dire(NOT_TESTED, CONTROLE, "fichiers non declares",
                   "%d fichier(s) present(s) et non declare(s), donc NON "
                   "controle(s) : %s" % (len(surplus), ", ".join(surplus[:6])))
    else:
        bilan.dire(PASS, CONTROLE, "fichiers non declares",
                   "aucun : les %d fichier(s) du paquet sont tous declares"
                   % len(presents))
    return surplus


def controle_attestations(racine: Path, doc: dict, magasin: Path | None,
                          bilan: Bilan) -> list[dict]:
    bruts = doc.get("attestations", _ABSENTE)
    if bruts is not _ABSENTE and not isinstance(bruts, list):
        bilan.dire(FAIL, CONTROLE, "signatures existantes",
                   "`attestations` = %r : le contrat attend un tableau, et "
                   "n en declarer aucune se fait en OMETTANT la clef ou avec "
                   "un tableau vide." % (bruts,))
        return []
    atts = [] if bruts is _ABSENTE else bruts
    if not atts:
        bilan.dire(NOT_TESTED, CONTROLE, "signatures existantes",
                   "le paquet ne declare aucune attestation. Son niveau ne "
                   "depassera donc pas `reference_verifiable`.")
        return []
    if magasin is None:
        bilan.dire(NOT_TESTED, CONTROLE, "signatures existantes",
                   "%d attestation(s) declaree(s), et aucun magasin de "
                   "confiance fourni. Le fournir avec --trust-store : jamais "
                   "celui du paquet." % len(atts), requis=True)
        return []

    resultats = []
    echecs = 0
    for att in atts:
        # Une entree qui n est pas un objet est REFUSEE, pas traversee :
        # `att.get` sur une chaine levait une exception et emportait le
        # rapport entier.
        if not isinstance(att, dict):
            echecs += 1
            resultats.append({"jws_path": None,
                              "etat": "entree_non_objet"})
            continue
        jws = att.get("jws_path")
        sujet = att.get("subject_path")
        bons = all(chemin_sur(c)[0] for c in (jws, sujet))
        if not bons or not (racine / jws).is_file() or not (racine / sujet).is_file():
            echecs += 1
            resultats.append({"jws_path": jws, "etat": "fichier_absent_ou_refuse"})
            continue
        # UN SEUL verificateur de signature existe dans ce depot. On
        # l appelle, on ne le refait pas : deux moteurs qui divergent ne
        # prouvent rien, et celui-ci est celui qu un auditeur emploie.
        fini = subprocess.run(
            [sys.executable, str(RACINE / "verify_attestation.py"),
             str(racine / jws), "--archive", str(racine / sujet),
             "--trust-store", str(magasin)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        sortie = (fini.stdout or "") + (fini.stderr or "")
        bilan_ligne = next((l for l in sortie.splitlines()
                            if l.startswith("BILAN")), "")
        niveau = next((l for l in sortie.splitlines()
                       if l.startswith("Niveau")), "")
        resultats.append({"jws_path": jws, "subject_path": sujet,
                          "exit": fini.returncode, "bilan": bilan_ligne,
                          "niveau": niveau})
        if fini.returncode != 0:
            echecs += 1

    detail = "; ".join("%s -> exit %s %s" % (r.get("jws_path"), r.get("exit"),
                                             r.get("bilan", ""))
                       for r in resultats)[:400]
    if echecs:
        bilan.dire(FAIL, CONTROLE, "signatures existantes", detail)
    else:
        bilan.dire(PASS, CONTROLE, "signatures existantes", detail)
    return resultats


def controle_provenance(doc: dict, bilan: Bilan) -> None:
    # Meme garde que pour `pilot`, et pour la meme raison : une liste non
    # vide est vraie, donc `or {}` ne la remplace pas, et `.get` n existe
    # pas dessus.
    # UNE CLEF ABSENTE N EST PAS UNE CLEF A `null`, et c est la discipline
    # que ce depot applique partout ailleurs : << un champ dont le chemin ne
    # resout pas est ABSENT, jamais `null` >>. Le schema la grave --
    # `provenance_declared` est `type: object` et n est PAS dans `required`,
    # donc dire << aucune provenance >> se fait en OMETTANT la clef. Un
    # `null` explicite est une declaration, et le contrat n en declare
    # aucune de cette forme.
    prov = doc.get("provenance_declared", _ABSENTE)
    if prov is not _ABSENTE and not isinstance(prov, dict):
        # Une forme hors contrat est NOMMEE et refusee. Elle ne se lit pas
        # comme une provenance absente : l une est un manque, l autre une
        # faute, et les confondre effacerait la faute.
        bilan.dire(FAIL, CONTROLE, "provenance de l execution",
                   "`provenance_declared` = %r : le contrat attend un objet, "
                   "et dire qu il n y en a pas se fait en OMETTANT la clef. "
                   "Une clef absente est un manque ; une clef a `null` est "
                   "une declaration, et le contrat n en declare aucune de "
                   "cette forme." % (prov,))
    else:
        prov = {} if prov is _ABSENTE else prov
        dire_surplus(bilan, "champs de provenance hors contrat", prov,
                     CHAMPS_PROVENANCE)
        champs = ("code_reference_declared", "environment_declared",
                  "evaluator_declared")
        renseignes = [c for c in champs if prov.get(c)]
        absents = [c for c in champs if not prov.get(c)]
        if renseignes:
            bilan.dire(NOT_TESTED, DECLARE, "provenance de l execution",
                       "renseignee : %s ; absente : %s. Declaree et non "
                       "verifiable depuis ce paquet."
                       % (", ".join(renseignes),
                          ", ".join(absents) or "aucune"))
        else:
            bilan.dire(NOT_TESTED, INDEMONTRABLE, "provenance de l execution",
                       "aucun champ de provenance declare. Toute affirmation "
                       "sur l environnement ou l instrument de cette "
                       "execution est donc `not_demonstrable`.")

    bilan.dire(NOT_TESTED, INDEMONTRABLE, "que l execution ait eu lieu",
               "hors de portee d une ingestion. Nous recalculons des "
               "empreintes de FICHIERS ; qu ils proviennent de l execution "
               "annoncee est une declaration, et le restera.")

    limites = doc.get("limits_declared", _ABSENTE)
    if limites is not _ABSENTE and not isinstance(limites, list):
        bilan.dire(FAIL, CONTROLE, "limites annoncees par le soumetteur",
                   "`limits_declared` = %r : le contrat attend un tableau, "
                   "et n annoncer aucune limite se fait en OMETTANT la clef "
                   "ou avec un tableau vide." % (limites,))
    elif limites is not _ABSENTE and limites:
        bilan.dire(NOT_TESTED, DECLARE, "limites annoncees par le soumetteur",
                   "%d limite(s), conservee(s) verbatim : %s"
                   % (len(limites), " | ".join(str(l) for l in limites)[:240]))


def rendre_markdown(rapport: dict) -> str:
    l = ["# Rapport d ingestion NeoMundi Evidence", "",
         "- Paquet : `%s`" % rapport["package"],
         "- Soumission : `%s`" % rapport.get("submission_id"),
         "- Verdict : **%s**" % rapport["verdict"],
         "- Decomptes : %d PASS, %d FAIL, %d NOT TESTED"
         % (rapport["counts"]["pass"], rapport["counts"]["fail"],
            rapport["counts"]["not_tested"]),
         "", "## Lignes de controle", "",
         "| Etat | Nature | Controle | Detail |", "|---|---|---|---|"]
    for ligne in rapport["lines"]:
        l.append("| %s | %s | %s | %s |"
                 % (ligne["etat"], ligne["nature"], ligne["intitule"],
                    ligne["detail"].replace("|", "/")[:200]))
    l += ["", "## Ce que ce rapport n etablit pas", ""]
    for x in rapport["does_not_establish"]:
        l.append("- %s" % x)
    return "\n".join(l) + "\n"


def main() -> int:
    analyseur = argparse.ArgumentParser(
        description="Ingere un paquet d execution tiers. N execute rien, et "
                    "n a besoin d aucune cle privee.")
    analyseur.add_argument("paquet", type=Path,
                           help="dossier ou archive ZIP de soumission")
    analyseur.add_argument("--out", type=Path, default=None,
                           help="rapport JSON, lisible par machine")
    analyseur.add_argument("--md", type=Path, default=None,
                           help="rapport Markdown, lisible par un humain")
    analyseur.add_argument("--trust-store", type=Path, default=None,
                           help="magasin de confiance de l OPERATEUR, pour "
                                "verifier les attestations declarees. Jamais "
                                "celui porte par le paquet")
    analyseur.add_argument("--strict", action="store_true",
                           help="sortir 2 sur un paquet INCOMPLET")
    analyseur.add_argument("--lang", choices=("fr", "en"), default="fr",
                           help="langue de la PROSE. Ne change aucun verdict")
    arguments = analyseur.parse_args()
    _LANGUE[0] = arguments.lang

    bilan = Bilan()
    dis("paquet : %s" % arguments.paquet)
    dis()

    travail = Path(tempfile.mkdtemp(prefix="evidence-ingest-"))
    try:
        racine = deplier(arguments.paquet, travail, bilan)
        doc: dict = {}
        non_encodables: list[str] = []
        artefacts: list[dict] = []
        surplus: list[str] = []
        atts: list[dict] = []
        if racine is not None:
            lu = controle_manifeste(racine, bilan)
            if lu is not None:
                doc = lu
                # LE FILET, et il ne remplace aucune garde.
                #
                # Les gardes locales nomment la faute -- << `pilot` n est pas
                # un objet JSON >> -- et c est ce qu un soumetteur peut
                # corriger. Ce filet-ci ne nomme rien : il garantit
                # seulement qu AUCUNE forme de manifeste ne fasse sortir cet
                # outil SANS RAPPORT. Un ingesteur dont le produit est une
                # decision ecrite doit toujours en produire une ; une trace
                # de pile dit ou le programme s est casse, et non ce qu il
                # reprochait au paquet.
                #
                # Il ne rend JAMAIS `ACCEPTE` : un FAIL est pose, donc le
                # verdict est REJETE. Et il n AVALE PAS le diagnostic -- la
                # trace complete part sur stderr, parce qu une erreur de
                # programmation doit rester reparable par un mainteneur.
                # Masquer un defaut interne sous un refus generique
                # supprimerait le defaut du champ de vision, pas le defaut.
                try:
                    # EN PREMIER : si une valeur ne peut pas etre reportee,
                    # tout ce qui suit la ferait entrer dans le rapport.
                    non_encodables = controle_encodabilite(doc, bilan)
                    controle_champs(doc, bilan)
                    artefacts = controle_artefacts(racine, doc, bilan)
                    surplus = controle_fichiers_non_declares(racine, doc,
                                                             bilan)
                    atts = controle_attestations(racine, doc,
                                                 arguments.trust_store, bilan)
                    controle_provenance(doc, bilan)
                except Exception as erreur:            # noqa: BLE001
                    traceback.print_exc()
                    bilan.dire(FAIL, CONTROLE, "lecture du manifeste",
                               "le manifeste a une forme que l ingestion n a "
                               "pas su lire : %s. Le paquet est REFUSE, et "
                               "ce rapport dit pourquoi : un plantage sans "
                               "rapport ne serait pas une decision. La trace "
                               "complete est sur stderr."
                               % type(erreur).__name__)

        verdict = bilan.verdict()
        rapport = {
            "schema": SCHEMA_RAPPORT,
            "package": str(arguments.paquet),
            "submission_id": doc.get("submission_id"),
            "submission_schema": doc.get("schema"),
            "verdict": verdict,
            "counts": {"pass": bilan.compte(PASS), "fail": bilan.compte(FAIL),
                       "not_tested": bilan.compte(NOT_TESTED)},
            "required_not_demonstrated": bilan.requis_non_demontres(),
            "lines": bilan.lignes,
            "artifacts": artefacts,
            "undeclared_files": surplus,
            "attestations": atts,
            # Les declarations verbatim sont ECARTEES, deliberement, quand
            # au moins une ne peut pas s ecrire en UTF-8 : le contrat oblige
            # a les conserver verbatim, et un paquet qui rend cette
            # obligation impossible a tenir est deja REFUSE par
            # `controle_encodabilite`. Les ecarter ici evite de faire
            # dependre l existence du rapport du filet de recuperation.
            "declared_verbatim": {
                "_omitted": (
                    "les declarations verbatim ne figurent pas dans ce "
                    "rapport : %d de leurs valeurs ne peuvent pas s ecrire "
                    "en UTF-8 (%s). Le manifeste d origine les porte, "
                    "intactes ; ce rapport ne peut pas les reproduire sans "
                    "les alterer, et il ne les altere pas."
                    % (len(non_encodables), ", ".join(non_encodables[:5])))
            } if non_encodables else {
                "pilot": doc.get("pilot"),
                "execution": doc.get("execution"),
                "provenance_declared": doc.get("provenance_declared"),
                "limits_declared": doc.get("limits_declared"),
                "submitted_at_declared": doc.get("submitted_at_declared"),
            },
            "does_not_establish": [
                "Que l execution declaree ait eu lieu. Nous recalculons des "
                "empreintes de fichiers, pas des faits.",
                "Qui a produit ce paquet. L identite du soumetteur est "
                "declaree, et aucun controle sur des fichiers ne l etablit.",
                "Que les artefacts fournis soient ceux de l execution "
                "annoncee. Leur concordance d empreinte etablit qu ils n ont "
                "pas bouge depuis que le manifeste a ete ecrit, rien de plus.",
                "La date. `submitted_at_declared` est declaree ; aucune "
                "horloge de confiance n intervient.",
                "Qu un modele ait ou non pris part a l execution. Lorsque "
                "`model_declared` est nul, le motif et la note sont la parole "
                "du soumetteur : rien dans un paquet ne distingue une "
                "execution deterministe d une execution dont l identite du "
                "modele a ete perdue.",
                "Le sens des champs du soumetteur. Decider qu un de ses "
                "champs correspond a l un des notres est une affirmation sur "
                "deux definitions : voir `adapters/reconcile.py`, qui exige "
                "une table de correspondance DECLAREE.",
            ],
        }

        # ---- LE RAPPORT EST ECRIT AVANT QUE LE VERDICT NE SOIT ANNONCE --
        #
        # LA REGLE, ET POURQUOI L ORDRE COMPTE
        #
        # Un verdict n est imprime que si le rapport structure a ete ecrit.
        # L ordre inverse -- annoncer puis ecrire -- laissait une fenetre ou
        # les deux pouvaient se contredire, et elle s est ouverte : un
        # manifeste portant une demi-paire de substitution faisait imprimer
        # `VERDICT : ACCEPTE`, puis echouer l ecriture, puis sortir en 1 SANS
        # RAPPORT. Trois sorties contradictoires du meme passage : un lecteur
        # humain lisait << accepte >>, un script lisait << rejete >>, et il n y
        # avait aucun rapport pour arbitrer.
        #
        # `controle_encodabilite` ferme la seule cause ATTEIGNABLE de cet
        # echec -- une chaine que `.encode("utf-8")` refuse. Ce filet-ci est
        # la pour les causes qu on n a pas prevues : il ne nomme rien, il
        # garantit seulement qu un rapport existe et que le verdict annonce
        # est celui du rapport ecrit.
        #
        # Il ne rend JAMAIS `ACCEPTE` : un FAIL est pose, donc le verdict
        # devient REJETE, et il est RECALCULE avant d etre annonce. Et il
        # n avale pas le diagnostic : la trace part sur stderr, parce qu une
        # erreur de programmation doit rester reparable par un mainteneur.
        #
        # AUCUN CODE DE SORTIE N EST AJOUTE. Un code << echec technique >>
        # distinct serait plus expressif, et le verificateur Rust en a un (3).
        # L introduire ici changerait la surface publique de `ingest.py` ; la
        # proposition est documentee et le comportement existant conserve.
        # Voir `COMPLETUDE_RUST_EVIDENCE/02_CORRECTION_VERDICT_PYTHON.md`.
        def ecrire_rapports(r: dict) -> None:
            if arguments.out:
                arguments.out.parent.mkdir(parents=True, exist_ok=True)
                arguments.out.write_bytes(
                    (json.dumps(r, ensure_ascii=False, indent=2) + "\n")
                    .encode("utf-8"))
            if arguments.md:
                arguments.md.parent.mkdir(parents=True, exist_ok=True)
                arguments.md.write_bytes(rendre_markdown(r).encode("utf-8"))

        try:
            ecrire_rapports(rapport)
        except Exception as erreur:                    # noqa: BLE001
            traceback.print_exc()
            bilan.dire(FAIL, CONTROLE, "rapport structure ecrit",
                       "le rapport n a pas pu etre ecrit : %s. Le paquet est "
                       "REFUSE, parce qu une ingestion dont le produit est une "
                       "decision ecrite doit toujours en produire une. La "
                       "trace complete est sur stderr."
                       % type(erreur).__name__)
            verdict = bilan.verdict()
            rapport["verdict"] = verdict
            rapport["counts"] = {"pass": bilan.compte(PASS),
                                 "fail": bilan.compte(FAIL),
                                 "not_tested": bilan.compte(NOT_TESTED)}
            rapport["lines"] = bilan.lignes
            # Seconde tentative, en ASCII pur et SANS les declarations
            # verbatim : si ce sont elles qui ont fait echouer l ecriture, un
            # rapport AMPUTE et qui le DIT vaut mieux qu aucun rapport.
            rapport["declared_verbatim"] = {
                "_omitted": "les declarations verbatim ont ete retirees de ce "
                            "rapport : leur serialisation a echoue. Le "
                            "manifeste d origine les porte, intactes ; ce "
                            "rapport ne peut pas les reproduire."
            }
            try:
                ecrire_rapports_de_secours(arguments, rapport)
            except Exception:                          # noqa: BLE001
                traceback.print_exc()
                print("ERREUR : aucun rapport n a pu etre ecrit. Le code de "
                      "sortie 1 dit un REFUS, et c est ce qu il faut lire : "
                      "cet outil n a produit AUCUNE decision exploitable.",
                      file=sys.stderr)
        dis()
        dis("BILAN : %d PASS, %d FAIL, %d NOT TESTED"
            % (bilan.compte(PASS), bilan.compte(FAIL), bilan.compte(NOT_TESTED)))
        dis("VERDICT : %s" % verdict)
        if verdict == REJETE:
            dis()
            dis("Le paquet est REJETE : au moins un controle a echoue. Les "
                "lignes FAIL ci-dessus disent lesquelles.")
        elif verdict == INCOMPLET:
            dis()
            dis("Le paquet est INCOMPLET, et ce n est pas un refus : il "
                "manque quelque chose que le soumetteur peut fournir.")
            for x in bilan.requis_non_demontres():
                dis("  - %s" % x)
        else:
            dis()
            dis("Le paquet est ACCEPTE : sa structure et les empreintes qu il "
                "declare sont controlees. Les lignes DECLARE restent la "
                "parole du soumetteur, et les NON DEMONTRABLE le resteront.")

        if arguments.out:
            dis("rapport JSON : %s" % arguments.out)
        if arguments.md:
            dis("rapport Markdown : %s" % arguments.md)

        if verdict == REJETE:
            return 1
        if verdict == INCOMPLET and arguments.strict:
            return 2
        return 0
    finally:
        shutil.rmtree(travail, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
