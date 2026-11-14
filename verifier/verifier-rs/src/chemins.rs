//! Règles de chemin d'un paquet de soumission.
//!
//! LE TEXTE NORMATIF
//!
//! `schemas/evidence-submission-v2.json`, `artifacts.items.properties.path` :
//!
//! > RELATIVE path inside the submission, with forward slashes. Absolute
//! > paths, drive letters, `..` segments and symbolic links are REFUSED --
//! > a submission must not be able to name a file outside itself.
//! > `minLength: 1`, `maxLength: 512`
//!
//! Le schéma **n'a pas de `pattern`** sur ce champ : l'interdiction est
//! écrite dans la **description**, en prose. Un validateur JSON Schema
//! générique accepte donc `../../etc/passwd`, et c'est le CODE qui doit le
//! refuser. C'est une **ambiguïté du contrat**, relevée comme telle dans
//! `01_BASELINE_ET_CONTRAT.md`, et les deux implémentations la traitent de
//! la même manière — par choix, non par accident.
//!
//! LE MOTIF DE L'IMPLÉMENTATION PYTHON
//!
//! `adapters/ingest.py` applique `^[A-Za-z0-9][A-Za-z0-9._/-]{0,511}$` en
//! plus des quatre refus nommés. Ce motif est un **COMPORTEMENT OBSERVÉ**,
//! pas une règle publiée : le schéma ne le mentionne pas. Il est reproduit
//! ici pour que les deux vérificateurs concordent, et cette reproduction
//! est déclarée — voir la note `AMBIGUITE-1` du document de baseline.
//!
//! Conséquence assumée : un chemin parfaitement légitime selon le schéma,
//! par exemple `artefacts/réponse.txt`, est refusé par les DEUX
//! vérificateurs. C'est une restriction du code, non du contrat.

/// Longueur maximale, celle du schéma.
pub const LONGUEUR_MAX: usize = 512;

/// Le chemin est-il sûr ? Rend `Err(raison)` sinon.
///
/// Les raisons sont les mêmes que celles de `ingest.py::chemin_sur`, dans
/// le même ordre : un auditeur qui compare les deux rapports doit retrouver
/// le même motif de refus, pas un équivalent.
pub fn chemin_sur(brut: &str) -> Result<(), String> {
    if brut.is_empty() {
        return Err("chemin absent ou non textuel".into());
    }
    if brut.contains('\\') {
        return Err(
            "barre oblique inversee : un chemin de soumission s ecrit en `/`".into(),
        );
    }
    if brut.starts_with('/') {
        return Err("chemin ABSOLU".into());
    }
    // Lettre de lecteur : une lettre ASCII suivie de `:`.
    let mut c = brut.chars();
    if let (Some(a), Some(b)) = (c.next(), c.next()) {
        if a.is_ascii_alphabetic() && b == ':' {
            return Err("lettre de lecteur".into());
        }
    }
    if brut.split('/').any(|s| s == "..") {
        return Err("segment `..` : remontee hors du paquet".into());
    }
    if !motif_admis(brut) {
        return Err("caracteres hors du jeu admis".into());
    }
    Ok(())
}

/// `^[A-Za-z0-9][A-Za-z0-9._/-]{0,511}$`, appliqué sans moteur d'expressions
/// régulières — il n'y en a pas dans la bibliothèque standard de Rust, et en
/// importer un pour six lignes serait une dépendance de trop.
fn motif_admis(s: &str) -> bool {
    if s.len() > LONGUEUR_MAX {
        return false;
    }
    let o = s.as_bytes();
    let Some(&premier) = o.first() else {
        return false;
    };
    if !premier.is_ascii_alphanumeric() {
        return false;
    }
    o[1..].iter().all(|&c| {
        c.is_ascii_alphanumeric() || c == b'.' || c == b'_' || c == b'/' || c == b'-'
    })
}

/// Un membre d'archive est-il lisible comme chemin de paquet ?
///
/// Appliqué à TOUS les membres d'un ZIP, y compris ceux que le manifeste ne
/// déclare pas : un membre dangereux ne doit pas pouvoir entrer, même s'il
/// n'est jamais nommé. Les entrées de dossier (`a/b/`) sont admises et
/// ignorées ensuite.
pub fn membre_sur(nom: &str) -> Result<(), String> {
    if nom.ends_with('/') {
        let sans = nom.trim_end_matches('/');
        if sans.is_empty() {
            return Err("entree de dossier sans nom".into());
        }
        return chemin_sur(sans);
    }
    chemin_sur(nom)
}
