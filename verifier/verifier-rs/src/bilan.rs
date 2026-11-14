//! Module 6 — le registre des contrôles, et le verdict qu'il produit.
//!
//! LES TROIS NATURES, ET POURQUOI ELLES NE SE MÉLANGENT PAS
//!
//!   CONTROLE         nous l'avons recalculé. Empreintes, tailles,
//!                    structure. C'est le seul registre où ce programme
//!                    engage quelque chose.
//!   DECLARE          la parole du soumetteur, conservée VERBATIM. Nous la
//!                    transportons, nous ne la cautionnons pas.
//!   NON DEMONTRABLE  aucun contrôle ne pourrait l'établir depuis ce
//!                    paquet. Ce n'est pas un manque de zèle : c'est une
//!                    propriété du matériau.
//!
//! **Une ligne de nature `DECLARE` ne peut JAMAIS porter `PASS`.** C'est
//! l'invariant qui empêche une déclaration de devenir un fait attesté, et
//! il est vérifié par le banc comparatif, pas seulement écrit ici.
//!
//! LES TROIS ÉTATS, ET CE QU'ILS NE SONT PAS
//!
//!   PASS        recalculé, et conforme
//!   FAIL        recalculé, et non conforme
//!   NOT TESTED  non recalculé, avec sa raison
//!
//! `NOT TESTED` recouvre trois situations que la mission demande de ne pas
//! confondre, et le champ `raison_non_teste` les sépare :
//!
//!   NonApplicable   le contrôle n'a pas d'objet ici (aucune attestation
//!                   déclarée, donc rien à vérifier)
//!   HorsPortee      le contrôle a un objet, et ce vérificateur ne sait
//!                   pas le faire (vérification de signature)
//!   Declaration     ce n'est pas un contrôle : c'est une parole rapportée
//!
//! Un contrôle ÉCHOUÉ est un `FAIL`, jamais un `NOT TESTED` : les
//! confondre transformerait un refus en abstention.

use crate::json::echapper;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Etat {
    Pass,
    Fail,
    NonTeste,
}

impl Etat {
    pub fn texte(self) -> &'static str {
        match self {
            Etat::Pass => "PASS",
            Etat::Fail => "FAIL",
            Etat::NonTeste => "NOT TESTED",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Nature {
    Controle,
    Declare,
    NonDemontrable,
}

impl Nature {
    pub fn texte(self) -> &'static str {
        match self {
            Nature::Controle => "CONTROLE",
            Nature::Declare => "DECLARE",
            Nature::NonDemontrable => "NON DEMONTRABLE",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Raison {
    /// Le contrôle n'a pas d'objet dans ce paquet.
    NonApplicable,
    /// Le contrôle a un objet, et ce vérificateur ne sait pas le faire.
    HorsPortee,
    /// Ce n'est pas un contrôle : une parole rapportée.
    Declaration,
}

impl Raison {
    pub fn texte(self) -> &'static str {
        match self {
            Raison::NonApplicable => "non_applicable",
            Raison::HorsPortee => "hors_portee_de_ce_verificateur",
            Raison::Declaration => "declaration_rapportee",
        }
    }
}

#[derive(Debug, Clone)]
pub struct Ligne {
    pub etat: Etat,
    pub nature: Nature,
    pub intitule: String,
    pub detail: String,
    /// Présent si et seulement si `etat == NonTeste`.
    pub raison: Option<Raison>,
    /// Un contrôle REQUIS non démontré rend le paquet INCOMPLET.
    pub requis: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Verdict {
    Accepte,
    Rejete,
    Incomplet,
}

impl Verdict {
    pub fn texte(self) -> &'static str {
        match self {
            Verdict::Accepte => "ACCEPTE",
            Verdict::Rejete => "REJETE",
            Verdict::Incomplet => "INCOMPLET",
        }
    }
}

#[derive(Default)]
pub struct Bilan {
    pub lignes: Vec<Ligne>,
}

impl Bilan {
    pub fn new() -> Self {
        Bilan { lignes: Vec::new() }
    }

    pub fn controle(&mut self, etat: Etat, intitule: &str, detail: &str) {
        debug_assert!(
            etat != Etat::NonTeste,
            "un CONTROLE non teste doit passer par `non_teste`, avec sa raison"
        );
        self.lignes.push(Ligne {
            etat,
            nature: Nature::Controle,
            intitule: intitule.into(),
            detail: detail.into(),
            raison: None,
            requis: false,
        });
    }

    pub fn non_teste(
        &mut self,
        nature: Nature,
        intitule: &str,
        detail: &str,
        raison: Raison,
        requis: bool,
    ) {
        self.lignes.push(Ligne {
            etat: Etat::NonTeste,
            nature,
            intitule: intitule.into(),
            detail: detail.into(),
            raison: Some(raison),
            requis,
        });
    }

    pub fn compte(&self, etat: Etat) -> usize {
        self.lignes.iter().filter(|l| l.etat == etat).count()
    }

    pub fn requis_non_demontres(&self) -> Vec<&str> {
        self.lignes
            .iter()
            .filter(|l| l.requis && l.etat != Etat::Pass)
            .map(|l| l.intitule.as_str())
            .collect()
    }

    /// `ACCEPTE`, `REJETE` ou `INCOMPLET` -- et jamais autre chose.
    ///
    /// Un `FAIL` rejette. Sans `FAIL`, un contrôle REQUIS non démontré rend
    /// le paquet `INCOMPLET` : ce n'est pas un refus, c'est un paquet
    /// auquel il manque quelque chose que le soumetteur peut fournir.
    pub fn verdict(&self) -> Verdict {
        if self.compte(Etat::Fail) > 0 {
            Verdict::Rejete
        } else if !self.requis_non_demontres().is_empty() {
            Verdict::Incomplet
        } else {
            Verdict::Accepte
        }
    }

    /// L'invariant central : aucune ligne `DECLARE` ne porte `PASS`.
    ///
    /// Vérifié à l'exécution et non seulement par un test : si cet
    /// invariant tombe, le rapport présente une déclaration comme un fait,
    /// et c'est la seule faute que ce produit ne doit jamais commettre.
    pub fn invariant_declare(&self) -> Result<(), String> {
        for l in &self.lignes {
            if l.nature == Nature::Declare && l.etat == Etat::Pass {
                return Err(format!(
                    "INVARIANT ROMPU : la ligne {:?} est de nature DECLARE et \
                     porte PASS. Une declaration ne devient jamais un fait \
                     atteste.",
                    l.intitule
                ));
            }
        }
        Ok(())
    }

    pub fn lignes_json(&self) -> String {
        let mut s = String::from("[");
        for (i, l) in self.lignes.iter().enumerate() {
            if i > 0 {
                s.push(',');
            }
            s.push_str("\n    {");
            s.push_str(&format!("\"etat\": {}, ", echapper(l.etat.texte())));
            s.push_str(&format!("\"nature\": {}, ", echapper(l.nature.texte())));
            s.push_str(&format!("\"intitule\": {}, ", echapper(&l.intitule)));
            s.push_str(&format!("\"detail\": {}, ", echapper(&l.detail)));
            match l.raison {
                Some(r) => s.push_str(&format!(
                    "\"raison_non_teste\": {}, ",
                    echapper(r.texte())
                )),
                None => s.push_str("\"raison_non_teste\": null, "),
            }
            s.push_str(&format!("\"requis\": {}", l.requis));
            s.push('}');
        }
        s.push_str("\n  ]");
        s
    }
}
