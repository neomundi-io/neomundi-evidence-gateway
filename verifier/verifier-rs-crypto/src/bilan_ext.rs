//! Deux commodités sur `Bilan`, apportées par un TRAIT et non par une
//! modification de `bilan.rs`.
//!
//! POURQUOI UN TRAIT
//!
//! `bilan.rs` est le MÊME fichier que celui de `verifier-rs`, atteint par
//! `#[path]`. Y ajouter deux méthodes dont le cœur n'a pas l'usage y
//! introduirait du code mort — et le cœur compile sans un seul
//! avertissement, propriété que la consolidation précédente a établie.
//!
//! Un trait local n'ajoute rien au cœur et ne peut rien lui casser.
//!
//! CE QUE LES DEUX MÉTHODES APPORTENT
//!
//! `controle_requis` marque une ligne de contrôle comme REQUISE : les cinq
//! piliers d'une attestation le sont, et un pilier non démontré doit rendre
//! le verdict `INCOMPLET` plutôt que `ACCEPTE`. `bilan.rs` ne pose le
//! drapeau `requis` que sur les lignes `NOT TESTED`, parce que le
//! vérificateur de soumission n'a pas de contrôle requis.
//!
//! `est_passe` répond à « ce pilier précis est-il `PASS` ? », ce dont la
//! dérivation du niveau a besoin.

use crate::bilan::{Bilan, Etat, Ligne, Nature, Raison};

pub trait BilanAttestation {
    /// Un contrôle REQUIS : s'il n'est pas `PASS`, le verdict ne peut pas
    /// être `ACCEPTE`.
    fn controle_requis(&mut self, etat: Etat, intitule: &str, detail: &str);

    /// `NOT TESTED` de nature `NON DEMONTRABLE`, avec sa raison. Non requis :
    /// une ligne définitivement hors de portée ne rend pas un paquet
    /// `INCOMPLET` — il n'y a rien à compléter.
    fn hors_portee(&mut self, intitule: &str, raison: Raison, detail: &str);

    /// `NOT TESTED` sur un pilier REQUIS : il manque quelque chose que
    /// l'appelant peut fournir (un magasin, une archive).
    fn pilier_non_teste(&mut self, intitule: &str, raison: Raison, detail: &str);

    /// Cette ligne précise est-elle `PASS` ?
    fn est_passe(&self, intitule: &str) -> bool;
}

impl BilanAttestation for Bilan {
    fn controle_requis(&mut self, etat: Etat, intitule: &str, detail: &str) {
        debug_assert!(
            etat != Etat::NonTeste,
            "un controle non teste doit passer par `pilier_non_teste`, avec sa raison"
        );
        self.lignes.push(Ligne {
            etat,
            nature: Nature::Controle,
            intitule: intitule.into(),
            detail: detail.into(),
            raison: None,
            requis: true,
        });
    }

    fn hors_portee(&mut self, intitule: &str, raison: Raison, detail: &str) {
        self.non_teste(Nature::NonDemontrable, intitule, detail, raison, false);
    }

    fn pilier_non_teste(&mut self, intitule: &str, raison: Raison, detail: &str) {
        self.non_teste(Nature::Controle, intitule, detail, raison, true);
    }

    fn est_passe(&self, intitule: &str) -> bool {
        self.lignes
            .iter()
            .any(|l| l.intitule == intitule && l.etat == Etat::Pass)
    }
}
