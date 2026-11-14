//! Le magasin de confiance `neomundi.evidence.trust-store/1`.
//!
//! D'OÙ IL VIENT, ET POURQUOI C'EST LA QUESTION CENTRALE
//!
//! **Le magasin vient de l'OPÉRATEUR, jamais du paquet vérifié.** Un paquet
//! ne doit pas porter sa propre réponse à la question de savoir si son
//! signataire est digne de confiance : ce serait laisser l'attaquant écrire
//! la politique qui le juge.
//!
//! LA CONFRONTATION DE L'EMPREINTE, ET CE QU'ELLE PARE
//!
//! Sans elle, le magasin et l'archive arrivent par la MÊME route, et qui
//! contrôle cette route contrôle les deux. `--store-digest`, obtenue par un
//! AUTRE canal, oblige un faussaire à compromettre les deux. Un magasin non
//! confronté n'est pas faux : il est **non confronté**, et la ligne le dit.
//!
//! UN MAGASIN DE CONFIANCE NE PORTE QUE DU PUBLIC
//!
//! Trouver un champ de clef privée (`d`, `private`, `private_key`) est une
//! **divulgation**, pas une variante : le magasin est refusé, et le refus
//! nomme la clef concernée. Ce vérificateur ne sait pas signer et ne doit
//! même pas pouvoir rencontrer de quoi le faire.
//!
//! UNE POLITIQUE NON COMPRISE EST REFUSÉE, PAS INTERPRÉTÉE
//!
//! `verification_policy.policy_id` doit valoir `neomundi-evidence-policy/1`.
//! Un magasin dont la politique est inconnue n'est pas lu « au mieux » : il
//! est refusé. Interpréter une politique qu'on ne comprend pas serait
//! décider à la place de celui qui l'a écrite.

use crate::json::Valeur;
use std::collections::BTreeMap;

pub const SCHEMA_MAGASIN: &str = "neomundi.evidence.trust-store/1";
pub const POLITIQUE: &str = "neomundi-evidence-policy/1";

/// Les champs qui, dans une entrée de clef, trahissent du matériel privé.
const CHAMPS_PRIVES: [&str; 3] = ["d", "private", "private_key"];

#[derive(Debug)]
pub struct Refus(pub String);

impl std::fmt::Display for Refus {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.0)
    }
}

pub struct EntreeCle {
    pub kid: String,
    pub crv: Option<String>,
    pub alg: Option<String>,
    pub x: Option<String>,
    pub statut: Option<String>,
    pub signer_identity: Option<String>,
    pub valid_from: Option<String>,
    pub valid_until: Option<String>,
    pub revocation_genre: Option<String>,
    pub revocation_date: Option<String>,
    pub revocation_motif: Option<String>,
}

pub struct Identite {
    pub identity_id: String,
    pub legal_name: Option<String>,
    pub legal_capacity: Option<String>,
    pub superseded_by: Option<String>,
}

pub struct Magasin {
    pub store_id: Option<String>,
    pub store_version: Option<String>,
    pub cles: Vec<EntreeCle>,
    pub identites: Vec<Identite>,
    pub algorithmes_acceptes: Vec<String>,
    pub courbes_acceptees: Vec<String>,
}

fn txt(o: &BTreeMap<String, Valeur>, c: &str) -> Option<String> {
    o.get(c).and_then(|v| v.comme_texte()).map(str::to_string)
}

fn liste_txt(o: &BTreeMap<String, Valeur>, c: &str) -> Vec<String> {
    match o.get(c) {
        Some(Valeur::Tableau(t)) => t
            .iter()
            .filter_map(|v| v.comme_texte())
            .map(str::to_string)
            .collect(),
        _ => Vec::new(),
    }
}

pub fn charger(octets: &[u8]) -> Result<Magasin, Refus> {
    let v = crate::json::analyser(octets)
        .map_err(|e| Refus(format!("le magasin n est pas du JSON lisible : {e}")))?;
    let Valeur::Objet(m) = v else {
        return Err(Refus("le magasin n est pas un objet JSON".into()));
    };
    if txt(&m, "schema").as_deref() != Some(SCHEMA_MAGASIN) {
        return Err(Refus(format!(
            "magasin de schema {:?} inconnu ; attendu {SCHEMA_MAGASIN:?}",
            txt(&m, "schema").unwrap_or_else(|| "<absent>".into())
        )));
    }
    let Some(Valeur::Objet(pol)) = m.get("verification_policy") else {
        return Err(Refus(
            "magasin sans `verification_policy` : une politique absente n est \
             pas une politique permissive"
                .into(),
        ));
    };
    if txt(pol, "policy_id").as_deref() != Some(POLITIQUE) {
        return Err(Refus(format!(
            "politique de verification {:?} inconnue ; attendu {POLITIQUE:?}. \
             Un magasin dont la politique n est pas comprise est REFUSE, pas \
             interprete.",
            txt(pol, "policy_id").unwrap_or_else(|| "<absente>".into())
        )));
    }

    let Some(Valeur::Tableau(brutes)) = m.get("keys") else {
        return Err(Refus("magasin sans tableau `keys`".into()));
    };
    if brutes.is_empty() {
        return Err(Refus("magasin sans aucune cle".into()));
    }
    let mut cles: Vec<EntreeCle> = Vec::with_capacity(brutes.len());
    for e in brutes {
        let Valeur::Objet(k) = e else {
            return Err(Refus("entree de cle malformee : pas un objet".into()));
        };
        let Some(kid) = txt(k, "kid") else {
            return Err(Refus("entree de cle sans `kid` textuel".into()));
        };
        // UN KID NE SE REUTILISE PAS. Deux entrées de même kid rendraient
        // la résolution ambiguë, et c'est exactement la forme d'ambiguïté
        // que ce dépôt refuse partout.
        if cles.iter().any(|c| c.kid == kid) {
            return Err(Refus(format!(
                "kid {kid:?} en double dans le magasin : un kid ne se reutilise pas"
            )));
        }
        for prive in CHAMPS_PRIVES {
            if k.contains_key(prive) {
                return Err(Refus(format!(
                    "le magasin contient un champ de cle PRIVEE (`{prive}`) pour \
                     {kid:?} : REFUS. Un magasin de confiance ne porte que du \
                     materiel public, et ce verificateur ne doit meme pas \
                     pouvoir rencontrer de quoi signer."
                )));
            }
        }
        let (rg, rd, rm) = match k.get("revocation") {
            Some(Valeur::Objet(r)) => (
                txt(r, "kind"),
                txt(r, "at_declared"),
                txt(r, "reason"),
            ),
            _ => (None, None, None),
        };
        cles.push(EntreeCle {
            kid,
            crv: txt(k, "crv"),
            alg: txt(k, "alg"),
            x: txt(k, "x"),
            statut: txt(k, "status"),
            signer_identity: txt(k, "signer_identity"),
            valid_from: txt(k, "valid_from_declared"),
            valid_until: txt(k, "valid_until_declared"),
            revocation_genre: rg,
            revocation_date: rd,
            revocation_motif: rm,
        });
    }

    let mut identites = Vec::new();
    if let Some(Valeur::Tableau(ids)) = m.get("identities") {
        for e in ids {
            if let Valeur::Objet(i) = e {
                if let Some(id) = txt(i, "identity_id") {
                    identites.push(Identite {
                        identity_id: id,
                        legal_name: txt(i, "legal_name"),
                        legal_capacity: txt(i, "legal_capacity_to_attest"),
                        superseded_by: txt(i, "superseded_by"),
                    });
                }
            }
        }
    }

    Ok(Magasin {
        store_id: txt(&m, "store_id"),
        store_version: m
            .get("store_version")
            .map(|v| match v {
                Valeur::Nombre(n) => n.clone(),
                Valeur::Texte(s) => s.clone(),
                _ => "?".into(),
            }),
        cles,
        identites,
        algorithmes_acceptes: liste_txt(pol, "accepted_algorithms"),
        courbes_acceptees: liste_txt(pol, "accepted_curves"),
    })
}

impl Magasin {
    pub fn trouver(&self, kid: &str) -> Option<&EntreeCle> {
        self.cles.iter().find(|c| c.kid == kid)
    }

    /// La politique du magasin autorise-t-elle cet algorithme et cette
    /// courbe ? Une politique qui ne les liste pas n'est pas permissive.
    pub fn politique_autorise(&self, alg: &str, crv: &str) -> Result<(), String> {
        if !self.algorithmes_acceptes.iter().any(|a| a == alg) {
            return Err(format!(
                "la politique du magasin n autorise pas {alg:?} (elle liste {:?})",
                self.algorithmes_acceptes
            ));
        }
        if !self.courbes_acceptees.iter().any(|c| c == crv) {
            return Err(format!(
                "la politique du magasin n autorise pas la courbe {crv:?} \
                 (elle liste {:?})",
                self.courbes_acceptees
            ));
        }
        Ok(())
    }
}
