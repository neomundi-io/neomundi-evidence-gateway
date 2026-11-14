//! JWS compact, base64url, et les octets effectivement signés.
//!
//! CE QUI EST SIGNÉ, ET POURQUOI C'EST LA SEULE CHOSE QUI COMPTE
//!
//! Les octets signés sont `ASCII(entete_b64url) || "." || ASCII(charge_b64url)`,
//! **verbatim, tels qu'ils figurent dans le fichier**. Aucune
//! canonicalisation n'intervient dans la vérification : ni ici, ni dans
//! `verify_attestation.py`, qui le dit explicitement —
//!
//!   « Il n'intervient **jamais** dans la vérification d'une signature. Le
//!     vérificateur signe-vérifie les octets portés verbatim par le JWS. »
//!     (`canonical.py`)
//!
//! C'est une propriété précieuse : elle rend la vérification INDÉPENDANTE
//! du profil de canonicalisation. Une divergence de canonicalisation entre
//! deux implémentations ne peut donc pas invalider une signature valide —
//! la classe de bug la plus pernicieuse de ce genre de dispositif.
//!
//! Le profil est vérifié SÉPARÉMENT, et son échec n'est pas un échec de
//! signature. Voir `profil.rs`.
//!
//! BASE64URL, ÉCRIT ICI
//!
//! Le décodage base64url est une dizaine de lignes et n'est pas une
//! primitive cryptographique : l'écrire n'expose à rien, et évite une
//! dépendance de plus. Ed25519, lui, n'est PAS écrit ici — voir
//! `Cargo.toml`.
//!
//! LE BOURRAGE EST REFUSÉ
//!
//! La RFC 7515 §2 impose base64url **sans** bourrage. Un segment portant
//! des `=` est refusé : l'accepter laisserait deux écritures pour un même
//! jeton, donc deux fichiers distincts qui se vérifient tous deux — exactement
//! l'ambiguïté que ce dépôt écarte partout ailleurs.

/// Refus de lecture. Jamais une panique, jamais un verdict de signature.
#[derive(Debug)]
pub struct Illisible(pub String);

impl std::fmt::Display for Illisible {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.0)
    }
}

const ALPHABET: &[u8; 64] =
    b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";

fn valeur(c: u8) -> Option<u32> {
    ALPHABET.iter().position(|&x| x == c).map(|p| p as u32)
}

/// Décode un segment base64url **sans bourrage**, en refusant tout le reste.
pub fn deb64u(s: &str) -> Result<Vec<u8>, Illisible> {
    if s.is_empty() {
        return Err(Illisible("segment base64url vide".into()));
    }
    if s.contains('=') {
        return Err(Illisible(
            "segment base64url avec bourrage `=` : la RFC 7515 §2 l interdit, \
             et l accepter laisserait deux ecritures pour un meme jeton"
                .into(),
        ));
    }
    if s.contains('+') || s.contains('/') {
        return Err(Illisible(
            "segment en base64 STANDARD (`+` ou `/`) : la RFC 7515 impose \
             base64url (`-` et `_`)"
                .into(),
        ));
    }
    // Une longueur de 1 modulo 4 ne code aucun octet entier.
    if s.len() % 4 == 1 {
        return Err(Illisible(format!(
            "segment base64url de longueur {} : impossible, {} modulo 4 ne \
             code aucun octet entier",
            s.len(),
            s.len() % 4
        )));
    }
    let mut bits: u32 = 0;
    let mut n: u32 = 0;
    let mut out = Vec::with_capacity(s.len() * 3 / 4 + 1);
    for c in s.bytes() {
        let Some(v) = valeur(c) else {
            return Err(Illisible(format!(
                "caractere 0x{c:02x} hors de l alphabet base64url"
            )));
        };
        bits = (bits << 6) | v;
        n += 6;
        if n >= 8 {
            n -= 8;
            out.push((bits >> n) as u8);
        }
    }
    // Les bits de queue doivent être nuls : sinon deux écritures distinctes
    // décodent vers les mêmes octets, et le jeton n'a plus une seule forme.
    if n > 0 && (bits & ((1 << n) - 1)) != 0 {
        return Err(Illisible(
            "bits de queue non nuls : ce segment n est pas la seule ecriture \
             base64url de ses octets"
                .into(),
        ));
    }
    Ok(out)
}

/// Un JWS compact, découpé et décodé.
pub struct Jws {
    /// Les octets EXACTEMENT signés : `entete_b64 . charge_b64`, en ASCII.
    pub octets_signes: Vec<u8>,
    pub entete: Vec<u8>,
    pub charge: Vec<u8>,
    pub signature: Vec<u8>,
}

/// Borne de taille du jeton. Non contractuelle : une attestation réelle
/// pèse ~2 Kio, et celle du dossier de démonstration 2 211 octets.
pub const JETON_OCTETS_MAX: usize = 1024 * 1024;

pub fn lire(octets: &[u8]) -> Result<Jws, Illisible> {
    if octets.len() > JETON_OCTETS_MAX {
        return Err(Illisible(format!(
            "jeton de {} octets, borne {JETON_OCTETS_MAX}",
            octets.len()
        )));
    }
    // ASCII STRICT. La RFC 7515 §3.1 ne décrit qu'un jeton ASCII, et un
    // octet non-ASCII dans un segment ne peut pas en faire partie.
    if let Some(mauvais) = octets.iter().find(|&&c| c > 0x7F) {
        return Err(Illisible(format!(
            "octet non-ASCII 0x{mauvais:02x} dans le jeton : un JWS compact \
             est de l ASCII"
        )));
    }
    let texte = std::str::from_utf8(octets)
        .map_err(|_| Illisible("jeton non textuel".into()))?
        .trim();
    let parties: Vec<&str> = texte.split('.').collect();
    if parties.len() != 3 || parties.iter().any(|p| p.is_empty()) {
        return Err(Illisible(format!(
            "un JWS compact a exactement trois segments non vides ; recu {}",
            parties.len()
        )));
    }
    let entete = deb64u(parties[0]).map_err(|e| Illisible(format!("en-tete : {e}")))?;
    let charge = deb64u(parties[1]).map_err(|e| Illisible(format!("charge : {e}")))?;
    let signature =
        deb64u(parties[2]).map_err(|e| Illisible(format!("signature : {e}")))?;
    let octets_signes = format!("{}.{}", parties[0], parties[1]).into_bytes();
    Ok(Jws {
        octets_signes,
        entete,
        charge,
        signature,
    })
}
