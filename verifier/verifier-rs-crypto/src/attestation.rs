//! Les attestations `neomundi.evidence.attestation/1`.
//!
//! QUATRE GARANTIES QUI NE SE CONFONDENT JAMAIS
//!
//! La mission l'impose, et le rapport les distingue ligne par ligne :
//!
//!   1. **VALIDITÉ CRYPTOGRAPHIQUE** — la clef examinée a signé ces octets.
//!      Mathématique, vérifiable, et c'est tout ce qu'elle dit.
//!   2. **CONFIANCE DANS LA CLEF** — une politique explicite autorise cette
//!      clef pour cet usage, à cette date. Une signature parfaitement valide
//!      d'une clef compromise reste une signature valide, et n'est **pas**
//!      une attestation.
//!   3. **IDENTITÉ DU SIGNATAIRE** — une identité a été reliée à la clef
//!      selon une procédure documentée. Ce vérificateur lit cette
//!      déclaration ; il ne la refait pas, et ne peut pas la refaire.
//!   4. **VÉRACITÉ DE L'ÉVÉNEMENT** — non démontrée par une signature, et
//!      **jamais** rendue `PASS`.
//!
//! La chaîne `identite_verifiee` n'apparaît nulle part dans ce module, et
//! un test l'exige sur la sortie du binaire : afficher « identité vérifiée »
//! quand on a seulement vérifié une signature serait la garantie trompeuse
//! la plus facile à produire.
//!
//! L'ALGORITHME EST IMPOSÉ, JAMAIS LU POUR CHOISIR
//!
//! `alg` est confronté à `EdDSA` et ne sert qu'à cela. C'est la parade à la
//! famille d'attaques « algorithm confusion » : un en-tête annonçant `none`
//! ou `HS256` est refusé, et jamais honoré. Le code de vérification ne
//! comporte **aucun branchement** sur la valeur de `alg`.
//!
//! LES CINQ PILIERS
//!
//! `cryptographically_attested` n'est dérivé que si les cinq sont `PASS`
//! **et** qu'aucune ligne n'est `FAIL`. Un seul `NOT TESTED` parmi eux
//! suffit à ne dériver aucun niveau — et non un niveau dégradé, qui se
//! lirait comme un succès partiel.

use crate::bilan::{Bilan, Etat, Raison};
use crate::bilan_ext::BilanAttestation;
use crate::json::Valeur;
use crate::jws::Jws;
use crate::magasin::{EntreeCle, Magasin};
use crate::profil;

pub const SCHEMA_ATTESTATION: &str = "neomundi.evidence.attestation/1";
pub const ALG_IMPOSE: &str = "EdDSA";
pub const COURBE_IMPOSEE: &str = "Ed25519";
pub const NIVEAU_ATTESTE: &str = "cryptographically_attested";

pub const PILIER_PROFIL: &str = "profil de canonicalisation";
pub const PILIER_ENTETE: &str = "en-tete : algorithme impose";
pub const PILIER_SIGNATURE: &str = "signature cryptographique";
pub const PILIER_CONFIANCE: &str = "identite de confiance";
pub const PILIER_CONCORDANCE: &str = "concordance avec l archive";

pub const PILIERS: [&str; 5] = [
    PILIER_PROFIL,
    PILIER_ENTETE,
    PILIER_SIGNATURE,
    PILIER_CONFIANCE,
    PILIER_CONCORDANCE,
];

fn texte<'a>(o: &'a std::collections::BTreeMap<String, Valeur>, c: &str) -> Option<&'a str> {
    o.get(c).and_then(|v| v.comme_texte())
}

fn objet<'a>(
    o: &'a std::collections::BTreeMap<String, Valeur>,
    c: &str,
) -> Option<&'a std::collections::BTreeMap<String, Valeur>> {
    match o.get(c) {
        Some(Valeur::Objet(m)) => Some(m),
        _ => None,
    }
}

fn sha256_bien_forme(s: &str) -> bool {
    s.len() == 64
        && s.bytes()
            .all(|c| c.is_ascii_digit() || (b'a'..=b'f').contains(&c))
}

// --------------------------------------------------------------------------
// 1. La forme, avant tout calcul cryptographique
// --------------------------------------------------------------------------

/// Rend la charge décodée si sa forme est conforme, sinon pose un `FAIL`.
pub fn controle_forme<'a>(
    b: &mut Bilan,
    charge: &'a Valeur,
) -> Option<&'a std::collections::BTreeMap<String, Valeur>> {
    let Valeur::Objet(a) = charge else {
        b.controle(
            Etat::Fail,
            "forme de l attestation",
            "la charge n est pas un objet JSON",
        );
        return None;
    };
    if texte(a, "schema") != Some(SCHEMA_ATTESTATION) {
        b.controle(
            Etat::Fail,
            "schema d attestation reconnu",
            &format!(
                "schema {:?} inconnu ; attendu {SCHEMA_ATTESTATION:?}",
                texte(a, "schema").unwrap_or("<absent>")
            ),
        );
        return None;
    }

    let mut problemes: Vec<String> = Vec::new();
    for c in [
        "canonicalization",
        "attestation_id",
        "attestation_kind",
        "subject_kind",
        "attested_at_declared",
        "key_id",
    ] {
        if texte(a, c).is_none() {
            problemes.push(format!("{c} absent ou non textuel"));
        }
    }
    if objet(a, "subject").is_none() {
        problemes.push("subject absent ou non objet".into());
    }
    if objet(a, "identities").is_none() {
        problemes.push("identities absent ou non objet".into());
    }
    let genre = texte(a, "attestation_kind").unwrap_or("");
    if genre != "contemporaneous" && genre != "retrospective" {
        problemes.push(format!("attestation_kind {genre:?} hors du contrat"));
    }

    if let Some(s) = objet(a, "subject") {
        for c in [
            "bundle_sha256",
            "bundle_name",
            "export_schema",
            "observation_count",
        ] {
            if texte(s, c).is_none() {
                problemes.push(format!("subject.{c} absent ou non textuel"));
            }
        }
        if let Some(e) = texte(s, "bundle_sha256") {
            if !sha256_bien_forme(e) {
                problemes.push("subject.bundle_sha256 n est pas un SHA-256".into());
            }
        }
        if let Some(n) = texte(s, "observation_count") {
            if n.is_empty() || !n.bytes().all(|c| c.is_ascii_digit()) {
                problemes
                    .push("subject.observation_count doit etre un entier en chaine".into());
            }
        }
        // Une attestation rétrospective sans date de gel ne peut pas dire
        // ce qu'elle atteste.
        if genre == "retrospective" && texte(s, "subject_frozen_at_declared").is_none() {
            problemes.push(
                "attestation retrospective sans subject_frozen_at_declared : la date \
                 de gel du corpus doit etre conservee"
                    .into(),
            );
        }
    }

    if let Some(i) = objet(a, "identities") {
        for role in [
            "signer",
            "technical_operator",
            "measurement_author",
            "key_custodian",
            "trust_authority",
        ] {
            if !i.contains_key(role) {
                problemes.push(format!("identities.{role} absent"));
            }
        }
        for role in [
            "signer",
            "technical_operator",
            "measurement_author",
            "key_custodian",
        ] {
            if i.contains_key(role) && texte(i, role).is_none() {
                problemes.push(format!(
                    "identities.{role} doit etre un identity_id textuel"
                ));
            }
        }
    }

    if !problemes.is_empty() {
        let n = problemes.len();
        problemes.truncate(5);
        b.controle(
            Etat::Fail,
            "forme de l attestation",
            &format!("{} probleme(s) : {}", n, problemes.join(" ; ")),
        );
        return None;
    }
    b.controle(
        Etat::Pass,
        "forme de l attestation",
        &format!(
            "{}, cle {}",
            genre,
            texte(a, "key_id").unwrap_or("?")
        ),
    );
    Some(a)
}

// --------------------------------------------------------------------------
// 2. Le profil — SÉPARÉ de la signature
// --------------------------------------------------------------------------

pub fn controle_profil(b: &mut Bilan, charge: &[u8]) {
    let (conforme, explication) = profil::est_conforme(charge);
    b.controle_requis(
        if conforme { Etat::Pass } else { Etat::Fail },
        PILIER_PROFIL,
        &format!("{} -- {}", profil::PROFIL, explication),
    );
}

// --------------------------------------------------------------------------
// 3. L'en-tête — l'algorithme est IMPOSÉ
// --------------------------------------------------------------------------

pub fn controle_entete(b: &mut Bilan, entete: &Valeur, key_id: &str) {
    let Valeur::Objet(h) = entete else {
        b.controle_requis(
            Etat::Fail,
            PILIER_ENTETE,
            "l en-tete JWS n est pas un objet JSON",
        );
        return;
    };
    let mut problemes: Vec<String> = Vec::new();
    let alg = texte(h, "alg").unwrap_or("<absent>");
    if alg != ALG_IMPOSE {
        problemes.push(format!(
            "alg {alg:?} refuse ; seul {ALG_IMPOSE:?} est accepte. Aucun \
             branchement de ce programme ne depend de cette valeur : elle est \
             CONFRONTEE, jamais honoree"
        ));
    }
    let kid = texte(h, "kid").unwrap_or("<absent>");
    if kid != key_id {
        problemes.push(format!(
            "kid de l en-tete ({kid:?}) different de key_id de la charge \
             ({key_id:?})"
        ));
    }
    if problemes.is_empty() {
        b.controle_requis(
            Etat::Pass,
            PILIER_ENTETE,
            &format!("{ALG_IMPOSE}, kid {key_id}"),
        );
    } else {
        b.controle_requis(Etat::Fail, PILIER_ENTETE, &problemes.join(" ; "));
    }
}

// --------------------------------------------------------------------------
// 4. La signature — VALIDITÉ CRYPTOGRAPHIQUE, et rien d'autre
// --------------------------------------------------------------------------

pub fn controle_signature(b: &mut Bilan, cle: &EntreeCle, jws: &Jws) {
    if cle.crv.as_deref() != Some(COURBE_IMPOSEE) || cle.alg.as_deref() != Some(ALG_IMPOSE) {
        b.controle_requis(
            Etat::Fail,
            PILIER_SIGNATURE,
            &format!(
                "la cle declare crv={:?} alg={:?} ; attendu {COURBE_IMPOSEE}/{ALG_IMPOSE}",
                cle.crv.as_deref().unwrap_or("<absent>"),
                cle.alg.as_deref().unwrap_or("<absent>")
            ),
        );
        return;
    }
    let Some(x) = cle.x.as_deref() else {
        b.controle_requis(
            Etat::Fail,
            PILIER_SIGNATURE,
            "la cle ne porte aucun champ `x`",
        );
        return;
    };
    let brut = match crate::jws::deb64u(x) {
        Ok(v) => v,
        Err(e) => {
            b.controle_requis(
                Etat::Fail,
                PILIER_SIGNATURE,
                &format!("cle publique illisible : {e}"),
            );
            return;
        }
    };
    if brut.len() != 32 {
        b.controle_requis(
            Etat::Fail,
            PILIER_SIGNATURE,
            &format!(
                "une cle publique Ed25519 fait 32 octets ; recu {}",
                brut.len()
            ),
        );
        return;
    }
    if jws.signature.len() != 64 {
        b.controle_requis(
            Etat::Fail,
            PILIER_SIGNATURE,
            &format!(
                "une signature Ed25519 fait 64 octets ; recu {}",
                jws.signature.len()
            ),
        );
        return;
    }
    let mut k = [0u8; 32];
    k.copy_from_slice(&brut);
    let mut s = [0u8; 64];
    s.copy_from_slice(&jws.signature);

    let vk = match ed25519_dalek::VerifyingKey::from_bytes(&k) {
        Ok(v) => v,
        Err(e) => {
            b.controle_requis(
                Etat::Fail,
                PILIER_SIGNATURE,
                &format!("cle publique Ed25519 invalide : {e}"),
            );
            return;
        }
    };
    let sig = ed25519_dalek::Signature::from_bytes(&s);
    // `verify_strict`, et non `verify` : il refuse les points d'ordre faible
    // et les composantes non canoniques. La variante permissive laisserait
    // deux signatures distinctes valider le même message, ce qui romprait
    // l'unicité qu'une attestation doit avoir.
    match vk.verify_strict(&jws.octets_signes, &sig) {
        Ok(()) => b.controle_requis(
            Etat::Pass,
            PILIER_SIGNATURE,
            &format!(
                "{ALG_IMPOSE}/{COURBE_IMPOSEE}, cle {}, {} octets signes. \
                 Ceci etablit que CETTE cle a signe CES octets -- et rien de \
                 plus : ni que la cle soit de confiance, ni qui la detient, \
                 ni que son contenu soit vrai",
                cle.kid,
                jws.octets_signes.len()
            ),
        ),
        Err(_) => b.controle_requis(
            Etat::Fail,
            PILIER_SIGNATURE,
            &format!(
                "la cle {} n a pas signe ces octets (verification stricte)",
                cle.kid
            ),
        ),
    }
}

// --------------------------------------------------------------------------
// 5. La confiance — DISTINCTE de la validité mathématique
// --------------------------------------------------------------------------

pub fn controle_confiance(
    b: &mut Bilan,
    m: &Magasin,
    cle: &EntreeCle,
    att: &std::collections::BTreeMap<String, Valeur>,
    autoriser_test: bool,
) {
    let emis = texte(att, "attested_at_declared").unwrap_or("");
    let kid = &cle.kid;

    if cle.statut.as_deref() == Some("test") && !autoriser_test {
        b.controle_requis(
            Etat::Fail,
            PILIER_CONFIANCE,
            &format!(
                "cle {kid} de statut `test` : elle n accorde aucune \
                 attestation. Relancer avec --allow-test-keys pour \
                 l accepter explicitement"
            ),
        );
        return;
    }

    // COMPROMISSION : RÉTROACTIVE, et c'est la différence avec une
    // rotation. Qui détient la clef privée peut forger n'importe quel
    // `attested_at_declared` : faire survivre les signatures antérieures
    // reviendrait à faire confiance à un horodatage que l'attaquant
    // contrôle.
    if cle.statut.as_deref() == Some("compromised")
        || cle.revocation_genre.as_deref() == Some("compromised")
    {
        b.controle_requis(
            Etat::Fail,
            PILIER_CONFIANCE,
            &format!(
                "cle {kid} COMPROMISE le {} ({}) : toutes ses signatures sont \
                 non fiables, quelle que soit leur date DECLAREE",
                cle.revocation_date.as_deref().unwrap_or("?"),
                cle.revocation_motif.as_deref().unwrap_or("sans motif")
            ),
        );
        return;
    }

    if cle.revocation_genre.as_deref() == Some("rotated") {
        if let Some(limite) = cle.revocation_date.as_deref() {
            if !emis.is_empty() && !limite.is_empty() && emis > limite {
                b.controle_requis(
                    Etat::Fail,
                    PILIER_CONFIANCE,
                    &format!(
                        "cle {kid} retiree par rotation le {limite}, \
                         attestation declaree le {emis} : posterieure a la \
                         rotation"
                    ),
                );
                return;
            }
        }
    }

    if let Some(fin) = cle.valid_until.as_deref() {
        if !emis.is_empty() && emis > fin {
            b.controle_requis(
                Etat::Fail,
                PILIER_CONFIANCE,
                &format!("cle {kid} expiree le {fin}, attestation declaree le {emis}"),
            );
            return;
        }
    }
    if let Some(debut) = cle.valid_from.as_deref() {
        if !emis.is_empty() && emis < debut {
            b.controle_requis(
                Etat::Fail,
                PILIER_CONFIANCE,
                &format!(
                    "attestation declaree le {emis}, anterieure a la validite \
                     de la cle {kid} ({debut})"
                ),
            );
            return;
        }
    }

    let signataire_att = objet(att, "identities").and_then(|i| texte(i, "signer"));
    if cle.signer_identity.as_deref() != signataire_att {
        b.controle_requis(
            Etat::Fail,
            PILIER_CONFIANCE,
            &format!(
                "l attestation se dit signee par {:?}, le magasin rattache la \
                 cle {kid} a {:?}",
                signataire_att.unwrap_or("<absent>"),
                cle.signer_identity.as_deref().unwrap_or("<absent>")
            ),
        );
        return;
    }
    let Some(sig_att) = signataire_att else {
        b.controle_requis(
            Etat::Fail,
            PILIER_CONFIANCE,
            "l attestation ne nomme aucun signataire",
        );
        return;
    };
    let Some(identite) = m.identites.iter().find(|i| i.identity_id == sig_att) else {
        b.controle_requis(
            Etat::Fail,
            PILIER_CONFIANCE,
            &format!(
                "signataire {sig_att:?} inconnu du registre d identites du magasin"
            ),
        );
        return;
    };

    let mut detail = format!(
        "cle {kid} {}, signataire {sig_att} ({}). Ceci etablit qu une \
         POLITIQUE autorise cette cle a cette date -- pas que l identite ait \
         ete juridiquement verifiee",
        cle.statut.as_deref().unwrap_or("?"),
        identite.legal_name.as_deref().unwrap_or("?")
    );
    if let Some(succ) = identite.superseded_by.as_deref() {
        // Une succession est ADDITIVE : elle n'invalide rien.
        detail.push_str(&format!(
            " ; identite remplacee depuis par {succ}, sans effet sur cette \
             attestation"
        ));
    }
    b.controle_requis(Etat::Pass, PILIER_CONFIANCE, &detail);
}

// --------------------------------------------------------------------------
// 6. La capacité juridique et les identités — DÉCLARÉES, jamais vérifiées
// --------------------------------------------------------------------------

/// Ce que chaque valeur déclarée veut dire, mot pour mot. La distinction
/// entre une identité DÉCLARÉE et une identité juridiquement VÉRIFIÉE se
/// perd dès qu'on laisse le lecteur déduire le sens d'un mot-clef : elle est
/// donc écrite.
pub fn sens_de_la_capacite(v: &str) -> &'static str {
    match v {
        "experimental" => {
            "l entite est NOMMEE et a decide d attester dans un cadre \
             scientifique et non commercial ; AUCUNE verification de ses \
             pouvoirs n a ete faite. Identite DECLAREE, non juridiquement \
             VERIFIEE : ceci n est pas une certification juridique."
        }
        "unverified" => {
            "aucune verification des pouvoirs, et aucune decision documentee \
             non plus. Identite DECLAREE seulement."
        }
        "verified" => {
            "des pouvoirs ont ete verifies HORS de ce code, et ce champ n en \
             est que la declaration. Le verificateur ne refait pas ce \
             controle, et ne peut pas le refaire."
        }
        "disputed" => {
            "la capacite est CONTESTEE. Lire l attestation comme engageante \
             serait abusif."
        }
        "not_applicable" => "ce role ne s engage sur rien ; la question ne se pose pas.",
        _ => "valeur hors du vocabulaire du contrat : non interpretee.",
    }
}

pub fn controle_capacite_juridique(
    b: &mut Bilan,
    m: &Magasin,
    att: &std::collections::BTreeMap<String, Valeur>,
) {
    let signataire = objet(att, "identities")
        .and_then(|i| texte(i, "signer"))
        .unwrap_or("");
    let capacite = m
        .identites
        .iter()
        .find(|i| i.identity_id == signataire)
        .and_then(|i| i.legal_capacity.as_deref())
        .unwrap_or("<non declaree>");
    // TOUJOURS `NOT TESTED`, et c'est définitif : aucun code ne peut établir
    // la capacité juridique d'une entité.
    b.hors_portee(
        "capacite juridique du signataire",
        Raison::HorsPortee,
        &format!(
            "declaree `{capacite}` -- {} AUCUN code ne peut etablir cette \
             capacite ; ce verificateur rapporte la declaration du magasin, \
             et ne la verifie pas.",
            sens_de_la_capacite(capacite)
        ),
    );
}

pub fn controle_identites(
    b: &mut Bilan,
    m: &Magasin,
    att: &std::collections::BTreeMap<String, Valeur>,
) {
    let Some(i) = objet(att, "identities") else {
        return;
    };
    let mut lignes: Vec<String> = Vec::new();
    let mut inconnues = 0usize;
    for role in [
        "signer",
        "technical_operator",
        "measurement_author",
        "key_custodian",
        "trust_authority",
    ] {
        let id = match i.get(role) {
            Some(Valeur::Texte(s)) => s.as_str(),
            Some(Valeur::Nul) => {
                lignes.push(format!("{role} : aucun (null)"));
                continue;
            }
            _ => {
                lignes.push(format!("{role} : absent"));
                continue;
            }
        };
        match m.identites.iter().find(|x| x.identity_id == id) {
            Some(e) => lignes.push(format!(
                "{role} : {id} ({})",
                e.legal_name.as_deref().unwrap_or("?")
            )),
            None => {
                inconnues += 1;
                lignes.push(format!("{role} : {id} -- INCONNU du magasin"));
            }
        }
    }
    // Les rôles sont des DÉCLARATIONS, et le registre d'identités les
    // résout sans les attester. La ligne reste donc `NOT TESTED`.
    b.hors_portee(
        "roles declares resolus dans le magasin",
        Raison::Declaration,
        &format!(
            "{}{}. Resoudre un identifiant dans un registre n est pas \
             verifier une identite : le registre est lui-meme declaratif.",
            lignes.join(" ; "),
            if inconnues > 0 {
                format!(" ; {inconnues} role(s) inconnu(s)")
            } else {
                String::new()
            }
        ),
    );
}

// --------------------------------------------------------------------------
// 7. La concordance avec l'archive
// --------------------------------------------------------------------------

/// LES TROIS EMPREINTES, ET NON UNE SEULE.
///
/// `subject` déclare `bundle_sha256`, `manifest_sha256` et
/// `checksums_sha256`. Une première version ne confrontait que la première,
/// et le banc différentiel l'a vu : sur une attestation dont les deux autres
/// étaient fausses, Python rendait `FAIL` et ce module `PASS`. Un pilier qui
/// n'examine qu'un tiers de ce qu'il annonce est un pilier trompeur.
///
/// `manifest_sha256` et `checksums_sha256` ne sont confrontés que si
/// l'archive a pu être lue — sinon la faute est nommée, et non passée sous
/// silence.
pub fn controle_concordance(
    b: &mut Bilan,
    att: &std::collections::BTreeMap<String, Valeur>,
    archive: Option<(&str, &str)>,
    empreintes_membres: &std::collections::BTreeMap<String, String>,
) {
    let sujet = objet(att, "subject");
    let declaree = sujet.and_then(|s| texte(s, "bundle_sha256")).unwrap_or("");
    let Some((nom, obtenue)) = archive else {
        b.pilier_non_teste(
            PILIER_CONCORDANCE,
            Raison::NonApplicable,
            &format!(
                "aucune archive fournie : l attestation declare porter sur \
                 {}..., et rien ici ne dit que c est l archive que vous \
                 tenez. La fournir avec --archive <fichier>",
                &declaree[..declaree.len().min(16)]
            ),
        );
        return;
    };

    let mut fautes: Vec<String> = Vec::new();
    if obtenue != declaree {
        fautes.push(format!(
            "bundle_sha256 : l attestation porte sur {}..., l archive fournie \
             se hache sur {}...",
            &declaree[..declaree.len().min(16)],
            &obtenue[..obtenue.len().min(16)]
        ));
    }
    // Les deux empreintes de MEMBRE, confrontees a celles recalculees depuis
    // l archive.
    let mut confrontees = 1usize;
    for (champ, membre) in [
        ("manifest_sha256", "manifest.json"),
        ("checksums_sha256", "checksums.sha256"),
    ] {
        let Some(annoncee) = sujet.and_then(|s| texte(s, champ)) else {
            continue;
        };
        match empreintes_membres.get(membre) {
            None => fautes.push(format!(
                "{champ} declare {}..., mais {membre} n a pas pu etre \
                 recalcule depuis l archive",
                &annoncee[..annoncee.len().min(16)]
            )),
            Some(reelle) => {
                confrontees += 1;
                if reelle != annoncee {
                    fautes.push(format!(
                        "{champ} : declare {}..., recalcule {}...",
                        &annoncee[..annoncee.len().min(16)],
                        &reelle[..reelle.len().min(16)]
                    ));
                }
            }
        }
    }

    if fautes.is_empty() {
        b.controle_requis(
            Etat::Pass,
            PILIER_CONCORDANCE,
            &format!(
                "{confrontees} empreinte(s) confrontee(s) : les octets de \
                 {nom} se hachent sur {}..., et les empreintes de membres \
                 declarees concordent",
                &obtenue[..obtenue.len().min(16)]
            ),
        );
    } else {
        b.controle_requis(
            Etat::Fail,
            PILIER_CONCORDANCE,
            &format!("attestation incoherente -- {}", fautes.join(" ; ")),
        );
    }
}

pub fn controle_nature(b: &mut Bilan, att: &std::collections::BTreeMap<String, Valeur>) {
    let genre = texte(att, "attestation_kind").unwrap_or("?");
    let gel = objet(att, "subject")
        .and_then(|s| texte(s, "subject_frozen_at_declared"))
        .unwrap_or("non declaree");
    b.hors_portee(
        "nature de l attestation",
        Raison::Declaration,
        &format!(
            "`{genre}`, corpus gele le {gel} (declare). Une attestation \
             `retrospective` atteste un corpus GELE AVANT elle : la date de \
             gel est la parole du signataire, et aucune horloge de confiance \
             n intervient."
        ),
    );
}

pub fn controle_horodatage(b: &mut Bilan, att: &std::collections::BTreeMap<String, Valeur>) {
    let emis = texte(att, "attested_at_declared").unwrap_or("?");
    b.hors_portee(
        "horodatage independant",
        Raison::HorsPortee,
        &format!(
            "`attested_at_declared` vaut {emis}, et il est DECLARE par le \
             signataire : qui detient la cle privee peut y ecrire n importe \
             quelle date. Aucun horodatage qualifie eIDAS n est revendique."
        ),
    );
}

pub fn controle_ancrage(b: &mut Bilan, att: &std::collections::BTreeMap<String, Valeur>) {
    let ancre = objet(att, "external_anchor");
    let (genre, statut) = match ancre {
        Some(a) => (
            texte(a, "kind").unwrap_or("?"),
            texte(a, "status").unwrap_or("?"),
        ),
        None => ("aucun", "absent"),
    };
    b.hors_portee(
        "ancrage exterieur",
        Raison::HorsPortee,
        &format!(
            "`{genre}`, statut `{statut}`. Ce verificateur ne resout aucun \
             ancrage tiers, et ce champ N ELEVE AUCUN niveau."
        ),
    );
}

pub fn controle_verite(b: &mut Bilan) {
    // La ligne qui ne bougera jamais, et la raison pour laquelle elle existe.
    b.hors_portee(
        "verite du contenu atteste",
        Raison::HorsPortee,
        "une signature etablit qu une clef s est engagee sur des octets. Elle \
         n etablit PAS que ce que ces octets affirment soit vrai. Aucun \
         controle de ce programme ne peut rendre cette ligne `PASS`, et aucun \
         ne le fera.",
    );
}

// --------------------------------------------------------------------------
// 9. Le niveau dérivé
// --------------------------------------------------------------------------

/// `cryptographically_attested` seulement si les cinq piliers sont `PASS`.
///
/// Rend `None` quand un contrôle a échoué : il n'y a alors aucun niveau à
/// annoncer, et surtout pas un niveau dégradé qui se lirait comme un succès
/// partiel.
pub fn niveau_derive(b: &Bilan) -> Option<&'static str> {
    if b.compte(Etat::Fail) > 0 {
        return None;
    }
    if PILIERS.iter().all(|p| b.est_passe(p)) {
        Some(NIVEAU_ATTESTE)
    } else {
        None
    }
}
