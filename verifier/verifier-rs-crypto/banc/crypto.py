#!/usr/bin/env python3
"""Banc différentiel des ATTESTATIONS — Python contre Rust.

CE QUE CE BANC MESURE
---------------------
Pour chaque cas : le niveau dérivé, l'état des cinq piliers, le code de
sortie, et la présence d'un rapport. Les deux vérificateurs sont lancés sur
LES MÊMES octets.

LES ATTENTES NE VIENNENT PAS DE PYTHON
--------------------------------------
La mission l'exige : *« Ne pas utiliser Python pour produire les verdicts
attendus de Rust. »* Chaque cas porte donc :

  - l'ATTENTE côté Rust, écrite d'avance ;
  - la RÈGLE DE RÉFÉRENCE qui la justifie — RFC 7515/8032, le contrat publié,
    ou un fait cryptographique élémentaire.

Pour le cas témoin, l'attente vient de `examples/dossier-v1/attendu.json`,
qui est la source de vérité du dépôt et qui est ANTÉRIEURE à ce banc.

LES CLEFS SONT GÉNÉRÉES ICI, ET JETÉES
--------------------------------------
Aucune clef réelle de pilote n'intervient. Les clefs de ce banc sont
fabriquées à l'exécution, servent à forger les contre-exemples, et meurent
avec le processus. La clef de démonstration du dépôt porte déjà
`status: test` et n'accorde aucune attestation sans `--allow-test-keys`.

Le SIGNATAIRE est Python (`cryptography`), parce qu'il faut bien produire
des signatures valides pour éprouver qu'elles sont acceptées. Le
VÉRIFICATEUR Rust, lui, ne sait pas signer : sa dépendance est déclarée
`default-features = false`, ce qui retire la génération de clefs.

Hors ligne. Aucun accès à la production.
"""
from __future__ import annotations

import argparse
import base64
import copy
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
DOSSIER = RACINE / "examples" / "dossier-v1"

try:
    from cryptography.hazmat.primitives.asymmetric import ed25519
except ImportError:
    print("`cryptography` est requis pour FORGER les contre-exemples de ce "
          "banc (le verificateur Rust, lui, n en a pas besoin).",
          file=sys.stderr)
    raise SystemExit(2)


def b64u(o: bytes) -> str:
    return base64.urlsafe_b64encode(o).rstrip(b"=").decode("ascii")


def deb64u(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def canonise(valeur) -> bytes:
    """Le profil `neomundi-jcs-strings/1`, tel que `canonical.py` le publie."""
    return json.dumps(valeur, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


# --------------------------------------------------------------------------
# Forge
# --------------------------------------------------------------------------


class Cle:
    """Une clef de test, generee a l execution et jetee avec le processus.

    `graine` permet de DERIVER la clef au lieu de la tirer au hasard. Elle
    n est employee que par `forger_jws_a_encodage_discriminant`, pour la
    raison expliquee dans sa docstring. Par defaut, le comportement est
    inchange : une clef fraiche, jetee avec le processus.

    Une graine ecrite ici n est PAS un secret : elle ne sert qu a forger des
    contre-exemples locaux, et aucune attestation du depot n est signee avec.
    """

    def __init__(self, kid: str, *, graine: bytes | None = None):
        self.kid = kid
        if graine is None:
            self._priv = ed25519.Ed25519PrivateKey.generate()
        else:
            self._priv = ed25519.Ed25519PrivateKey.from_private_bytes(graine)
        self.x = b64u(self._priv.public_key().public_bytes_raw())

    def signer(self, octets: bytes) -> bytes:
        return self._priv.sign(octets)


def forger_jws(cle: Cle, charge: dict, *, alg: str = "EdDSA",
               kid_entete: str | None = None,
               signature_fausse: bool = False,
               charge_apres_signature: dict | None = None,
               canoniser: bool = True) -> str:
    """Forge un JWS compact. Chaque parametre nomme la propriete qu on fait
    mentir."""
    entete = {"alg": alg, "kid": kid_entete or cle.kid, "typ": "JOSE"}
    e = b64u(canonise(entete) if canoniser else json.dumps(entete).encode())
    octets_charge = canonise(charge) if canoniser else json.dumps(charge).encode()
    c = b64u(octets_charge)
    sig = cle.signer(f"{e}.{c}".encode("ascii"))
    if signature_fausse:
        mute = bytearray(sig)
        mute[0] ^= 0xFF
        sig = bytes(mute)
    if charge_apres_signature is not None:
        # LA CHARGE EST REMPLACEE APRES LA SIGNATURE : les octets signes ne
        # sont plus ceux qui voyagent.
        c = b64u(canonise(charge_apres_signature))
    return f"{e}.{c}.{b64u(sig)}"


#: Prefixe des graines deterministes employees par
#: `forger_jws_a_encodage_discriminant`. Fixe, donc le banc rend le meme
#: jeton a chaque execution sur une fixture donnee.
GRAINE_B64 = b"neomundi-evidence/banc-crypto/encodage-base64/"

#: Borne de la recherche de graine. 64 essais laissent une probabilite
#: d echec de (62/64)^(86*64) -- indistinguable de zero. La borne existe
#: pour qu une boucle ne puisse pas tourner indefiniment, pas parce qu on
#: s attend a l atteindre.
GRAINES_MAX = 64


def forger_jws_a_encodage_discriminant(charge: dict, kid: str
                                       ) -> tuple[Cle, str]:
    """Un JWS valide dont la REECRITURE en base64 standard ALTERE le jeton.

    POURQUOI CETTE FONCTION EXISTE
    ------------------------------

    Le cas `b64-standard` eprouve la RFC 7515 §2 : le segment de signature
    doit etre en base64**url**, pas en base64 standard. Il construisait sa
    variante ainsi :

        s.replace("-", "+").replace("_", "/")

    Or `-` et `_` n apparaissent dans un base64url que lorsqu un sextet vaut
    62 ou 63. Une signature Ed25519 fait 64 octets, soit **86** caracteres
    base64url ; la probabilite qu aucun ne vaille 62 ou 63 est
    (62/64)^86 ~ 6,5 %. Dans ce cas le remplacement est une **operation
    nulle** : le jeton forge est IDENTIQUE au jeton valide, les deux
    verificateurs l acceptent -- a juste titre -- et l attente `aucun`
    devient fausse.

    La clef etant tiree au hasard a chaque execution, le banc echouait donc
    une fois sur quinze environ, SANS qu aucune regression n ait eu lieu.
    Mesure du 2026-11-12 : **13 573 / 200 000** tirages, soit **6,787 %**
    (theorie 6,519 %). Et un banc qui echoue sans raison lisible apprend a
    relancer plutot qu a lire -- c est ainsi qu une vraie regression finit
    par etre rejouee jusqu a passer.

    CE QUE CETTE FONCTION GARANTIT, ET CE QU ELLE NE GARANTIT PAS
    -------------------------------------------------------------

    Elle **garantit** que la mutation eprouvee n est jamais une operation
    nulle : le jeton rendu porte au moins un `-` ou un `_` dans sa
    signature. L appelant le reverifie par une assertion, donc une
    regression de cette fonction ne peut pas passer en silence.

    Elle **n ajoute aucune laxite** : le jeton rendu est une signature
    PLEINEMENT VALIDE sur une charge conforme. Seul son ENCODAGE sera
    ensuite rendu fautif. Le comportement cryptographique des
    verificateurs n est pas touche.

    Les graines sont **deterministes** -- derivees d un prefixe fixe et d un
    compteur -- donc le jeton est le meme a chaque execution pour une
    fixture donnee. On ne fixe PAS une graine unique en dur : la charge
    signee contient l empreinte reelle de l archive de demonstration, et
    une graine choisie pour cette empreinte-la cesserait de discriminer si
    la fixture changeait. La recherche bornee, elle, suit la fixture.
    """
    import hashlib

    for essai in range(GRAINES_MAX):
        graine = hashlib.sha256(GRAINE_B64 + str(essai).encode()).digest()
        cle = Cle(kid, graine=graine)
        jws = forger_jws(cle, charge)
        if set("-_") & set(jws.split(".")[2]):
            return cle, jws
    raise RuntimeError(
        "aucune des %d graines deterministes ne produit une signature dont "
        "l ecriture base64url porte `-` ou `_`. La mutation `b64-standard` "
        "serait une operation nulle, et le cas ne mesurerait rien : le banc "
        "s arrete plutot que de rendre un faux resultat." % GRAINES_MAX)


def magasin(cles: list[Cle], *, statuts: dict | None = None,
            revocations: dict | None = None,
            algorithmes: list[str] | None = None,
            courbes: list[str] | None = None,
            avec_cle_privee: str | None = None,
            politique: str = "neomundi-evidence-policy/1",
            schema: str = "neomundi.evidence.trust-store/1") -> dict:
    statuts = statuts or {}
    revocations = revocations or {}
    entrees = []
    for k in cles:
        e = {
            "kid": k.kid, "kty": "OKP", "crv": "Ed25519", "alg": "EdDSA",
            "x": k.x,
            "status": statuts.get(k.kid, "test"),
            "signer_identity": "nm-test",
            "key_custodian_identity": "nm-test-op",
            "valid_from_declared": "2026-01-01T00:00:00Z",
            "valid_until_declared": None,
            "superseded_by": None,
            "revocation": revocations.get(k.kid),
            "notes": "cle de BANC, generee a l execution",
        }
        if avec_cle_privee == k.kid:
            e["d"] = "AAAA"          # divulgation volontaire, pour l eprouver
        entrees.append(e)
    return {
        "schema": schema,
        "store_id": "banc-crypto",
        "store_version": 1,
        "updated_at_declared": "2026-01-01T00:00:00Z",
        "store_kind": "test",
        "verification_policy": {
            "policy_id": politique,
            "accepted_algorithms": algorithmes if algorithmes is not None else ["EdDSA"],
            "accepted_curves": courbes if courbes is not None else ["Ed25519"],
            "on_unknown_key": "not_tested",
            "on_rotated_key_within_window": "trusted",
            "on_rotated_key_after_window": "untrusted",
            "on_compromised_key": "untrusted_retroactively",
            "on_expired_key": "untrusted",
            "on_test_key": "untrusted_unless_allowed",
        },
        # LE CHAMP QUI MANQUAIT. Sans `keys`, tous les magasins forges
        # etaient refuses pour << aucune cle >>, et le banc mesurait cela
        # au lieu de ce qu il croyait mesurer. Correction d instrument.
        "keys": entrees,
        "identities": [
            {"identity_id": "nm-test", "legal_name": "Banc de test",
             "kind": "machine", "jurisdiction": None,
             "registration_reference": None,
             "legal_capacity_to_attest": "not_applicable",
             "valid_from_declared": "2026-01-01T00:00:00Z",
             "superseded_by": None, "notes": "identite de BANC"},
            {"identity_id": "nm-test-op", "legal_name": "Operateur de test",
             "kind": "machine", "jurisdiction": None,
             "registration_reference": None,
             "legal_capacity_to_attest": "not_applicable",
             "valid_from_declared": "2026-01-01T00:00:00Z",
             "superseded_by": None, "notes": "identite de BANC"},
        ],
        "changes": [],
        "limits": ["Magasin de BANC : aucune cle reelle."],
    }


#: Les empreintes REELLES des deux membres que `subject` declare, remplies
#: au demarrage depuis l archive de reference.
#:
#: CORRECTION DE FIXTURE. Elles valaient `"0" * 64`, et le cas temoin
#: `sig-valide` -- qui doit etre le controle POSITIF -- echouait donc
#: legitimement sur la concordance, des deux cotes. L attente etait fausse,
#: pas le code : une attestation qui declare de fausses empreintes de membres
#: DOIT etre refusee.
EMPREINTES_MEMBRES: dict[str, str] = {}


def charge_type(empreinte: str, *, kid: str = "banc-1",
                genre: str = "contemporaneous") -> dict:
    """Une charge d attestation conforme au contrat, sur une empreinte."""
    c = {
        "attestation_id": "att-banc-0000000000000000",
        "attestation_kind": genre,
        "attested_at_declared": "2026-06-01T00:00:00Z",
        "canonicalization": "neomundi-jcs-strings/1",
        "identities": {
            "key_custodian": "nm-test-op",
            "measurement_author": "nm-test",
            "signer": "nm-test",
            "technical_operator": "nm-test-op",
            "trust_authority": None,
        },
        "key_id": kid,
        "limits": ["Attestation de BANC."],
        "schema": "neomundi.evidence.attestation/1",
        "subject": {
            "bundle_name": "banc.zip",
            "bundle_sha256": empreinte,
            "checksums_sha256": EMPREINTES_MEMBRES.get("checksums.sha256", "0" * 64),
            "export_schema": "station.export.campagne/2",
            "manifest_sha256": EMPREINTES_MEMBRES.get("manifest.json", "0" * 64),
            "observation_count": "4",
            "subject_frozen_at_declared": "2026-01-01T00:00:00Z",
        },
        "subject_kind": "evidence_bundle",
    }
    if genre == "retrospective":
        pass
    return c


# --------------------------------------------------------------------------
# Lancement
# --------------------------------------------------------------------------


def lancer(cmd, timeout=300):
    try:
        x = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout,
                           env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        return x.returncode, x.stdout or "", x.stderr or ""
    except subprocess.TimeoutExpired:
        return "DELAI", "", ""


def etats_piliers(sortie: str) -> dict:
    """L etat de chaque pilier, lu dans la sortie lisible. Les intitules sont
    les memes des deux cotes, par construction du contrat."""
    piliers = {
        "profil": "profil de canonicalisation",
        "entete": "algorithme impose",
        "signature": "signature cryptographique",
        "confiance": "identite de confiance",
        "concordance": "concordance avec l archive",
    }
    out = {}
    for court, motif in piliers.items():
        etat = None
        for ligne in sortie.splitlines():
            if not ligne.startswith("["):
                continue
            # CORRECTION D INSTRUMENT. Le critere etait << le motif apparait
            # dans la ligne >>. Il attrapait la ligne
            # << chainage canonique du registre >>, dont le DETAIL contient
            # les mots << profil de canonicalisation >>, et lisait son
            # NOT TESTED comme l etat du pilier. 51 faux desaccords de
            # piliers sur 125 venaient de la.
            #
            # Le motif doit etre cherche dans l INTITULE seul, c est-a-dire
            # entre le dernier crochet fermant et le premier << - >>.
            tete = ligne.rsplit("] ", 1)[-1]
            intitule = tete.split(" - ", 1)[0]
            if motif in intitule:
                etat = ligne[1:ligne.index("]")].strip()
                break
        out[court] = etat
    return out


def niveau_de(sortie: str) -> str | None:
    for ligne in sortie.splitlines():
        if "cryptographically_attested" in ligne:
            return "cryptographically_attested"
    return None


def mesurer(nom: str, risque: str, regle: str, attente: str,
            jws: str, mag: dict | None, travail: Path, binaire: Path,
            archive: Path | None, extra_py=(), extra_rs=()) -> dict:
    f_jws = travail / f"{nom}.jws"
    f_jws.write_text(jws, encoding="ascii")
    f_mag = None
    if mag is not None:
        f_mag = travail / f"{nom}.store.json"
        f_mag.write_bytes(json.dumps(mag, indent=2, ensure_ascii=False).encode())

    cmd_py = [sys.executable, "-B", str(RACINE / "verify_attestation.py"), str(f_jws)]
    cmd_rs = [str(binaire), "--attestation", str(f_jws)]
    if archive is not None:
        cmd_py += ["--archive", str(archive)]
        cmd_rs += ["--archive", str(archive)]
    if f_mag is not None:
        cmd_py += ["--trust-store", str(f_mag)]
        cmd_rs += ["--trust-store", str(f_mag)]
    cmd_py += ["--lang", "fr", *extra_py]
    cmd_rs += [*extra_rs]

    cp, op, _ = lancer(cmd_py)
    cr, orr, er = lancer(cmd_rs)

    pp, pr = etats_piliers(op), etats_piliers(orr)
    np_, nr = niveau_de(op), niveau_de(orr)
    conforme = (nr == (attente if attente != "aucun" else None)) if attente in (
        "cryptographically_attested", "aucun") else None

    accord_piliers = sum(1 for k in pp if pp[k] == pr[k])
    print("%-30s attendu=%-26s rust=%-26s py=%-26s piliers %d/5 %s"
          % (nom, attente, nr or "aucun", np_ or "aucun", accord_piliers,
             "" if conforme else "  <<< HORS ATTENTE"))
    desaccords = {k: (pp[k], pr[k]) for k in pp if pp[k] != pr[k]}
    if desaccords:
        print("      piliers divergents : %s" % desaccords)
    if er.strip() and cr == 3:
        print("      rust stderr : %s" % er.strip().splitlines()[0][:120])

    return {"id": nom, "risque": risque, "regle": regle, "attente": attente,
            "rust": {"niveau": nr, "code": cr, "piliers": pr},
            "python": {"niveau": np_, "code": cp, "piliers": pp},
            "conforme": bool(conforme),
            "piliers_en_accord": accord_piliers,
            "piliers_divergents": desaccords}


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

    travail = Path(os.environ.get("TMPDIR", "/tmp")) / "evc-banc"
    shutil.rmtree(travail, ignore_errors=True)
    travail.mkdir(parents=True)

    archive_reelle = DOSSIER / "NEOMUNDI_EVIDENCE_V1_DEMO.zip"
    import hashlib
    import zipfile
    emp_reelle = hashlib.sha256(archive_reelle.read_bytes()).hexdigest()
    # Les empreintes REELLES des membres que `subject` declare : sans elles,
    # le controle POSITIF du banc echouerait pour la bonne raison, et le banc
    # n aurait aucun temoin.
    with zipfile.ZipFile(archive_reelle) as z:
        for membre in ("manifest.json", "checksums.sha256"):
            EMPREINTES_MEMBRES[membre] = hashlib.sha256(z.read(membre)).hexdigest()

    k1 = Cle("banc-1")
    k2 = Cle("banc-2")
    res = []

    print("%-30s %-34s %-34s %-34s %s"
          % ("cas", "attendu (niveau)", "rust", "python", "piliers"))
    print("-" * 150)

    # ---- 1. le TEMOIN : l attestation REELLE du depot --------------------
    # Attente issue de `examples/dossier-v1/attendu.json`, source de verite
    # du depot, ANTERIEURE a ce banc.
    attendu_depot = json.loads((DOSSIER / "attendu.json").read_bytes())
    res.append(mesurer(
        "reel-dossier-v1",
        "l attestation REELLE du depot doit etre verifiee par les deux",
        "examples/dossier-v1/attendu.json : %s" % attendu_depot["attendu"]["attestation"],
        "cryptographically_attested",
        (DOSSIER / "NEOMUNDI_EVIDENCE_V1_DEMO.zip.jws").read_text("ascii"),
        json.loads((DOSSIER / "trust-store.json").read_bytes()),
        travail, binaire, archive_reelle,
        extra_py=["--allow-test-keys"], extra_rs=["--allow-test-keys"]))

    # ---- 2. signature VALIDE, forgee ici --------------------------------
    res.append(mesurer(
        "sig-valide",
        "une signature valide sur une charge conforme doit etre acceptee",
        "RFC 8032 : Ed25519 verifie sur les octets signes",
        "cryptographically_attested",
        forger_jws(k1, charge_type(emp_reelle)), magasin([k1]),
        travail, binaire, archive_reelle,
        extra_py=["--allow-test-keys"], extra_rs=["--allow-test-keys"]))

    # ---- 3. signature INVALIDE ------------------------------------------
    res.append(mesurer(
        "sig-invalide",
        "un octet de signature retourne doit faire echouer la verification",
        "RFC 8032 : une signature alteree ne verifie pas",
        "aucun",
        forger_jws(k1, charge_type(emp_reelle), signature_fausse=True),
        magasin([k1]), travail, binaire, archive_reelle,
        extra_py=["--allow-test-keys"], extra_rs=["--allow-test-keys"]))

    # ---- 4. MAUVAISE clef ------------------------------------------------
    # Signe par k2, mais l attestation et le magasin disent k1.
    jws_k2 = forger_jws(k2, charge_type(emp_reelle, kid="banc-1"),
                        kid_entete="banc-1")
    res.append(mesurer(
        "mauvaise-cle",
        "signee par une autre clef que celle que le magasin resout",
        "RFC 8032 : la clef publique de k1 ne verifie pas une signature de k2",
        "aucun", jws_k2, magasin([k1]), travail, binaire, archive_reelle,
        extra_py=["--allow-test-keys"], extra_rs=["--allow-test-keys"]))

    # ---- 5. clef INCONNUE ------------------------------------------------
    res.append(mesurer(
        "cle-inconnue",
        "clef absente du magasin : INCONNUE n est pas FAUSSE",
        "le contrat : `on_unknown_key: not_tested`",
        "aucun",
        forger_jws(k1, charge_type(emp_reelle)), magasin([k2]),
        travail, binaire, archive_reelle,
        extra_py=["--allow-test-keys"], extra_rs=["--allow-test-keys"]))

    # ---- 6. ALGORITHME non autorise -------------------------------------
    res.append(mesurer(
        "alg-none",
        "`alg: none` dans l en-tete : attaque `algorithm confusion`",
        "RFC 7515 §4.1.1 + le contrat : seul EdDSA est accepte, et `alg` est "
        "CONFRONTE, jamais honore",
        "aucun",
        forger_jws(k1, charge_type(emp_reelle), alg="none"), magasin([k1]),
        travail, binaire, archive_reelle,
        extra_py=["--allow-test-keys"], extra_rs=["--allow-test-keys"]))
    res.append(mesurer(
        "alg-hs256",
        "`alg: HS256` : meme famille d attaque, variante symetrique",
        "RFC 7515 §4.1.1 + le contrat", "aucun",
        forger_jws(k1, charge_type(emp_reelle), alg="HS256"), magasin([k1]),
        travail, binaire, archive_reelle,
        extra_py=["--allow-test-keys"], extra_rs=["--allow-test-keys"]))

    # ---- 7. en-tete INCOHERENT ------------------------------------------
    res.append(mesurer(
        "kid-incoherent",
        "le `kid` de l en-tete differe du `key_id` de la charge",
        "le contrat : les deux doivent coincider, sinon on ne sait pas quelle "
        "clef l emetteur designait",
        "aucun",
        forger_jws(k1, charge_type(emp_reelle, kid="banc-1"),
                   kid_entete="banc-2"),
        magasin([k1, k2]), travail, binaire, archive_reelle,
        extra_py=["--allow-test-keys"], extra_rs=["--allow-test-keys"]))

    # ---- 8. CHARGE modifiee APRES signature -----------------------------
    autre = charge_type(emp_reelle)
    autre["subject"]["observation_count"] = "99"
    res.append(mesurer(
        "charge-alteree-apres-signature",
        "la charge est remplacee APRES la signature : les octets signes ne "
        "sont plus ceux qui voyagent",
        "RFC 7515 §5.2 : la verification porte sur les octets portes",
        "aucun",
        forger_jws(k1, charge_type(emp_reelle), charge_apres_signature=autre),
        magasin([k1]), travail, binaire, archive_reelle,
        extra_py=["--allow-test-keys"], extra_rs=["--allow-test-keys"]))

    # ---- 9. ATTESTATION malformee ---------------------------------------
    sans_sujet = charge_type(emp_reelle)
    del sans_sujet["subject"]
    res.append(mesurer(
        "attestation-sans-sujet",
        "`subject` absent : l attestation ne dit pas sur quoi elle porte",
        "le contrat : `subject` est obligatoire", "aucun",
        forger_jws(k1, sans_sujet), magasin([k1]),
        travail, binaire, archive_reelle,
        extra_py=["--allow-test-keys"], extra_rs=["--allow-test-keys"]))

    # ---- 10. MAUVAIS encodage -------------------------------------------
    #
    # UNE SEULE GARDE COMMUNE, ET UN SEUL CAS CHANGE DE CLEF.
    #
    # `verifier_mutation_non_nulle` confronte chaque jeton mute au jeton
    # VALIDE dont il derive. Si la mutation etait une operation nulle, le cas
    # ne mesurerait rien et son attente `aucun` serait fausse -- exactement
    # le defaut corrige ici. Le banc s arrete alors, plutot que de rendre un
    # resultat qui a l air d un fait.
    def verifier_mutation_non_nulle(nom_mutation: str, valide: str,
                                    mute: str) -> str:
        if mute == valide:
            raise RuntimeError(
                "la mutation `%s` est une OPERATION NULLE : le jeton forge "
                "est identique au jeton valide. Le cas ne mesure rien, et "
                "son attente `aucun` est fausse. Le banc s arrete."
                % nom_mutation)
        return mute

    # Le BOURRAGE garde la clef `k1`, et c est deliberé : ajouter un `=`
    # ALTERE le jeton quelle que soit la signature. Ce cas n a JAMAIS ete
    # non deterministe, donc le toucher aurait deplace une mesure sans
    # raison -- mesure : son accord de piliers passait de 0/5 a 5/5 avec une
    # autre clef, parce que la longueur de l en-tete change ce que Python
    # parvient a decoder. On ne change pas ce qu on n a pas besoin de
    # changer.
    bon = forger_jws(k1, charge_type(emp_reelle))
    e, c, s = bon.split(".")
    res.append(mesurer(
        "b64-avec-bourrage",
        "segments base64url avec bourrage `=` : deux ecritures pour un jeton",
        "RFC 7515 §2 : base64url SANS bourrage",
        "aucun",
        verifier_mutation_non_nulle("b64-avec-bourrage", bon,
                                    "%s=.%s.%s" % (e, c, s)),
        magasin([k1]),
        travail, binaire, archive_reelle,
        extra_py=["--allow-test-keys"], extra_rs=["--allow-test-keys"]))

    # L ALPHABET STANDARD, lui, n altere le jeton que si la signature porte
    # `-` ou `_`. Clef DERIVEE, donc deterministe et discriminante. Voir
    # `forger_jws_a_encodage_discriminant`.
    k_b64, bon_b64 = forger_jws_a_encodage_discriminant(
        charge_type(emp_reelle, kid="banc-b64"), "banc-b64")
    e2, c2, s2 = bon_b64.split(".")
    res.append(mesurer(
        "b64-standard",
        "base64 STANDARD (`+`/`/`) au lieu de base64url",
        "RFC 7515 §2", "aucun",
        verifier_mutation_non_nulle(
            "b64-standard", bon_b64,
            "%s.%s.%s" % (e2, c2, s2.replace("-", "+").replace("_", "/"))),
        magasin([k_b64]), travail, binaire, archive_reelle,
        extra_py=["--allow-test-keys"], extra_rs=["--allow-test-keys"]))
    res.append(mesurer(
        "deux-segments",
        "un JWS a exactement trois segments", "RFC 7515 §3.1", "aucun",
        "%s.%s" % (e, c), magasin([k1]), travail, binaire, archive_reelle,
        extra_py=["--allow-test-keys"], extra_rs=["--allow-test-keys"]))

    # ---- 11. SUBSTITUTION de clef ---------------------------------------
    # Le magasin declare k1 sous le kid de k1, mais avec la cle publique de
    # k2 : une substitution dans le magasin lui-meme.
    m = magasin([k1])
    m["keys"][0]["x"] = k2.x
    res.append(mesurer(
        "substitution-de-cle",
        "le magasin porte la clef publique d un AUTRE sous le meme kid",
        "RFC 8032 : la clef substituee ne verifie pas la signature",
        "aucun",
        forger_jws(k1, charge_type(emp_reelle)), m,
        travail, binaire, archive_reelle,
        extra_py=["--allow-test-keys"], extra_rs=["--allow-test-keys"]))

    # ---- 12. clef COMPROMISE, RETROACTIVEMENT ---------------------------
    res.append(mesurer(
        "cle-compromise",
        "une clef compromise invalide TOUTES ses signatures, meme anterieures",
        "le contrat : `on_compromised_key: untrusted_retroactively`. Qui "
        "detient la clef privee peut forger n importe quelle date declaree",
        "aucun",
        forger_jws(k1, charge_type(emp_reelle)),
        magasin([k1], statuts={"banc-1": "compromised"},
                revocations={"banc-1": {"kind": "compromised",
                                        "at_declared": "2026-09-01T00:00:00Z",
                                        "reason": "banc"}}),
        travail, binaire, archive_reelle,
        extra_py=["--allow-test-keys"], extra_rs=["--allow-test-keys"]))

    # ---- 13. clef ROTEE, attestation POSTERIEURE ------------------------
    res.append(mesurer(
        "cle-rotee-posterieure",
        "attestation declaree APRES la rotation de la clef",
        "le contrat : `on_rotated_key_after_window: untrusted`", "aucun",
        forger_jws(k1, charge_type(emp_reelle)),
        magasin([k1], revocations={"banc-1": {
            "kind": "rotated", "at_declared": "2026-03-01T00:00:00Z",
            "reason": "banc"}}),
        travail, binaire, archive_reelle,
        extra_py=["--allow-test-keys"], extra_rs=["--allow-test-keys"]))

    # ---- 14. clef EXPIREE ------------------------------------------------
    m = magasin([k1])
    m["keys"][0]["valid_until_declared"] = "2026-02-01T00:00:00Z"
    res.append(mesurer(
        "cle-expiree",
        "attestation declaree apres la fin de validite de la clef",
        "le contrat : `on_expired_key: untrusted`", "aucun",
        forger_jws(k1, charge_type(emp_reelle)), m,
        travail, binaire, archive_reelle,
        extra_py=["--allow-test-keys"], extra_rs=["--allow-test-keys"]))

    # ---- 15. clef de TEST sans autorisation explicite -------------------
    res.append(mesurer(
        "cle-test-sans-autorisation",
        "une clef `test` n accorde aucune attestation sans le dire",
        "le contrat : `on_test_key: untrusted_unless_allowed`", "aucun",
        forger_jws(k1, charge_type(emp_reelle)), magasin([k1]),
        travail, binaire, archive_reelle))

    # ---- 16. SIGNATAIRE declare different de celui du magasin -----------
    ch = charge_type(emp_reelle)
    ch["identities"]["signer"] = "quelqu-un-d-autre"
    res.append(mesurer(
        "signataire-divergent",
        "l attestation se dit signee par X, le magasin rattache la clef a Y",
        "le contrat : les deux doivent coincider", "aucun",
        forger_jws(k1, ch), magasin([k1]), travail, binaire, archive_reelle,
        extra_py=["--allow-test-keys"], extra_rs=["--allow-test-keys"]))

    # ---- 17. ARCHIVE qui ne concorde pas --------------------------------
    res.append(mesurer(
        "archive-non-concordante",
        "l attestation porte sur une AUTRE archive",
        "le contrat : la concordance est l un des cinq piliers", "aucun",
        forger_jws(k1, charge_type("f" * 64)), magasin([k1]),
        travail, binaire, archive_reelle,
        extra_py=["--allow-test-keys"], extra_rs=["--allow-test-keys"]))

    # ---- 18. MAGASIN portant une clef PRIVEE ----------------------------
    res.append(mesurer(
        "magasin-avec-cle-privee",
        "un magasin de confiance ne porte que du public : un champ `d` est "
        "une DIVULGATION",
        "le contrat : refus, et le refus nomme la clef", "aucun",
        forger_jws(k1, charge_type(emp_reelle)),
        magasin([k1], avec_cle_privee="banc-1"),
        travail, binaire, archive_reelle,
        extra_py=["--allow-test-keys"], extra_rs=["--allow-test-keys"]))

    # ---- 19. POLITIQUE inconnue -----------------------------------------
    res.append(mesurer(
        "politique-inconnue",
        "un magasin dont la politique n est pas comprise est REFUSE, pas "
        "interprete",
        "le contrat : `policy_id` doit valoir neomundi-evidence-policy/1",
        "aucun",
        forger_jws(k1, charge_type(emp_reelle)),
        magasin([k1], politique="une-autre-politique/9"),
        travail, binaire, archive_reelle,
        extra_py=["--allow-test-keys"], extra_rs=["--allow-test-keys"]))

    # ---- 20. KID en DOUBLE dans le magasin ------------------------------
    m = magasin([k1])
    m["keys"].append(copy.deepcopy(m["keys"][0]))
    res.append(mesurer(
        "kid-en-double",
        "deux entrees de meme kid rendent la resolution ambigue",
        "le contrat : un kid ne se reutilise pas", "aucun",
        forger_jws(k1, charge_type(emp_reelle)), m,
        travail, binaire, archive_reelle,
        extra_py=["--allow-test-keys"], extra_rs=["--allow-test-keys"]))

    # ---- 21. CHARGE hors du profil de canonicalisation ------------------
    # Un NOMBRE dans la charge : le profil l interdit. La signature reste
    # VALIDE -- c est tout l interet de separer les deux lectures.
    ch = charge_type(emp_reelle)
    ch["subject"]["observation_count"] = 4          # entier, non chaine
    res.append(mesurer(
        "charge-hors-profil",
        "un NOMBRE dans la charge : le profil l interdit, la signature reste "
        "VALIDE. Les deux lectures doivent se separer",
        "canonical.py : nombres et booleens interdits par le profil", "aucun",
        forger_jws(k1, ch), magasin([k1]), travail, binaire, archive_reelle,
        extra_py=["--allow-test-keys"], extra_rs=["--allow-test-keys"]))

    # ---- 22. CHARGE non canonique (clefs non triees) --------------------
    bonne = charge_type(emp_reelle)
    non_triee = json.dumps(bonne, sort_keys=False, separators=(",", ":"),
                           ensure_ascii=False)
    # Reordonner pour que le tri ne soit PAS respecte.
    items = list(bonne.items())
    items.reverse()
    non_triee = "{" + ",".join(
        '%s:%s' % (json.dumps(k, ensure_ascii=False),
                   json.dumps(v, sort_keys=True, separators=(",", ":"),
                              ensure_ascii=False))
        for k, v in items) + "}"
    e2 = b64u(canonise({"alg": "EdDSA", "kid": k1.kid, "typ": "JOSE"}))
    c2 = b64u(non_triee.encode("utf-8"))
    s2 = b64u(k1.signer(f"{e2}.{c2}".encode("ascii")))
    res.append(mesurer(
        "charge-clefs-non-triees",
        "clefs non triees : hors du profil, signature VALIDE",
        "canonical.py : `sort_keys=True`", "aucun",
        f"{e2}.{c2}.{s2}", magasin([k1]), travail, binaire, archive_reelle,
        extra_py=["--allow-test-keys"], extra_rs=["--allow-test-keys"]))

    # ---- bilan -----------------------------------------------------------
    print()
    conformes = sum(1 for r in res if r["conforme"])
    accord_total = sum(r["piliers_en_accord"] for r in res)
    divergents = [r for r in res if r["piliers_divergents"]]
    niveaux_divergents = [r for r in res
                          if r["rust"]["niveau"] != r["python"]["niveau"]]
    print("cas executes                          : %d" % len(res))
    print("conformes a l attente ECRITE d avance  : %d / %d" % (conformes, len(res)))
    print("piliers en accord Python/Rust          : %d / %d"
          % (accord_total, len(res) * 5))
    print("cas ou le NIVEAU derive diverge        : %d" % len(niveaux_divergents))
    print("cas ou un PILIER diverge               : %d" % len(divergents))
    for r in niveaux_divergents:
        print("  NIVEAU : %-28s rust=%s python=%s"
              % (r["id"], r["rust"]["niveau"], r["python"]["niveau"]))
    for r in divergents:
        print("  PILIER : %-28s %s" % (r["id"], r["piliers_divergents"]))

    if a.sortie:
        Path(a.sortie).write_text(
            json.dumps({"total": len(res), "conformes": conformes,
                        "piliers_en_accord": accord_total,
                        "niveaux_divergents": [r["id"] for r in niveaux_divergents],
                        "piliers_divergents": [r["id"] for r in divergents],
                        "cas": res}, indent=2, ensure_ascii=False),
            encoding="utf-8")
        print("\nrapport machine : %s" % a.sortie)

    # LE CODE DE SORTIE NE SANCTIONNE QUE LA NON-CONFORMITE.
    #
    # Une divergence de NIVEAU n est pas un echec du banc : il en existe une,
    # declaree -- `b64-standard`, voir `03_SIGNATURES_RUST.md` §8. La faire
    # echouer ici empechait la CI d atteindre l etape qui VERIFIE que
    # l ensemble des divergences est exactement celui qu on annonce.
    #
    # C est cette etape-la qui tranche, et dans les deux sens : une
    # divergence qui APPARAIT casse la CI, une qui DISPARAIT aussi.
    return 0 if conformes == len(res) else 1


if __name__ == "__main__":
    raise SystemExit(main())
