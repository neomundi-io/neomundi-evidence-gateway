//! Conformité au profil `neomundi-jcs-strings/1`.
//!
//! CE QUE CE CONTRÔLE EST, ET CE QU'IL N'EST PAS
//!
//! Il **ne participe pas** à la vérification de la signature. Celle-ci porte
//! sur les octets verbatim du JWS (voir `jws.rs`). Ce contrôle dit autre
//! chose : *le producteur a-t-il suivi son propre profil ?* Un écart ici
//! n'invalide aucune signature — il dit qu'un document signé n'a pas la
//! forme que son émetteur s'était engagé à produire.
//!
//! Les deux lectures doivent rester séparées, et `verify_attestation.py` les
//! sépare déjà.
//!
//! LE PROFIL, TEL QUE `canonical.py` LE PUBLIE
//!
//!   1. UTF-8, sans BOM.
//!   2. clefs triées, séparateurs `,` et `:`, aucun espace.
//!   3. **nombres et booléens INTERDITS** — un décompte voyage en chaîne.
//!   4. toute clef d'objet respecte `^[a-z0-9_]+$`.
//!
//! POURQUOI CE PROFIL EST FACILE À REDÉRIVER, ET RFC 8785 NE L'EST PAS
//!
//! JCS est difficile sur trois points. Le profil en neutralise deux :
//!
//!   - **les nombres** : interdits, donc l'écriture ECMAScript — la partie
//!     la plus délicate de la RFC 8785 — ne se pose pas ;
//!   - **l'ordre des clefs** : JCS trie sur les unités de code UTF-16,
//!     Rust et Python trient sur les points de code. En restreignant les
//!     clefs à `[a-z0-9_]`, les deux ordres **coïncident** ;
//!   - **l'échappement** : hérité, et identique des deux côtés.
//!
//! Ce module peut donc redériver la forme canonique **exactement**, sans
//! implémenter la RFC 8785. Hors de ce domaine restreint, il ne le pourrait
//! pas — et c'est précisément pourquoi le domaine est restreint.
//!
//! LE CONTRÔLE, EN DEUX TEMPS
//!
//! Relire, recanoniser, comparer **octet pour octet**. Un écart n'est pas
//! approximé : il est nommé.

use crate::json::{echapper, Valeur};

pub const PROFIL: &str = "neomundi-jcs-strings/1";

fn clef_admissible(c: &str) -> bool {
    !c.is_empty()
        && c.bytes()
            .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b == b'_')
}

/// Redérive les octets canoniques d'une valeur selon le profil, ou dit
/// pourquoi la valeur en sort.
pub fn canonise(v: &Valeur) -> Result<String, String> {
    match v {
        Valeur::Nul => Ok("null".into()),
        Valeur::Bool(_) => Err(
            "booleen interdit par le profil (le porter en chaine \"true\"/\"false\")"
                .into(),
        ),
        Valeur::Nombre(t) => Err(format!(
            "nombre interdit par le profil -- le porter en chaine ({t})"
        )),
        Valeur::Texte(s) => Ok(echapper(s)),
        Valeur::Tableau(t) => {
            let mut parts = Vec::with_capacity(t.len());
            for (i, e) in t.iter().enumerate() {
                parts.push(canonise(e).map_err(|m| format!("[{i}] {m}"))?);
            }
            Ok(format!("[{}]", parts.join(",")))
        }
        Valeur::Objet(o) => {
            let mut parts = Vec::with_capacity(o.len());
            // `BTreeMap` parcourt déjà par ordre croissant de points de
            // code ; sur `[a-z0-9_]` cet ordre est celui de JCS.
            for (c, e) in o {
                if !clef_admissible(c) {
                    return Err(format!(
                        "clef {c:?} hors de ^[a-z0-9_]+$ : l ordre de tri JCS \
                         ne serait plus garanti"
                    ));
                }
                parts.push(format!(
                    "{}:{}",
                    echapper(c),
                    canonise(e).map_err(|m| format!(".{c} {m}"))?
                ));
            }
            Ok(format!("{{{}}}", parts.join(",")))
        }
    }
}

/// Ces octets sont-ils la forme canonique de leur propre contenu ?
pub fn est_conforme(octets: &[u8]) -> (bool, String) {
    if octets.starts_with(&[0xEF, 0xBB, 0xBF]) {
        return (
            false,
            "la charge porte un BOM UTF-8 : le profil l interdit".into(),
        );
    }
    let v = match crate::json::analyser(octets) {
        Ok(v) => v,
        Err(e) => return (false, format!("charge illisible : {e}")),
    };
    match canonise(&v) {
        Err(m) => (false, m),
        Ok(rejoue) => {
            if rejoue.as_bytes() == octets {
                (true, format!("forme canonique de {} octets", octets.len()))
            } else {
                (
                    false,
                    format!(
                        "les octets ne sont pas la forme canonique de leur \
                         propre contenu ({} octets portes, {} octets \
                         recanonises)",
                        octets.len(),
                        rejoue.len()
                    ),
                )
            }
        }
    }
}
