//! Analyseur JSON strict (RFC 8259), écrit ici et non emprunté.
//!
//! POURQUOI L'ÉCRIRE, ET CE QUE CELA RÉVÈLE
//!
//! Un analyseur emprunté impose ses politiques sans les déclarer. Or deux
//! d'entre elles décident de verdicts, et la mission demande explicitement
//! de les traiter : les **clefs en double** et la **forme des nombres**.
//!
//! Écrire l'analyseur permet de les rendre EXPLICITES et de les comparer à
//! celles de Python. C'est là que se trouvent les divergences de protocole
//! les plus intéressantes, et un analyseur tiers les aurait cachées.
//!
//! LES POLITIQUES, DÉCLARÉES
//!
//! **Clef en double** → REFUS. `{"a":1,"a":2}` est rejeté.
//! La RFC 8259 §4 dit que les noms « SHOULD be unique » et laisse le
//! comportement indéfini sinon. `json` de Python garde la DERNIÈRE
//! silencieusement. Un manifeste portant deux fois `sha256` aurait donc
//! deux lectures possibles, et un vérificateur qui en choisit une sans le
//! dire décide à la place du contrat. **Divergence connue et documentée**,
//! voir `04_MATRICE_PYTHON_RUST.md`.
//!
//! **Nombres** → conservés VERBATIM, en texte, et jamais convertis en
//! flottant. `bytes: 1e3`, `bytes: 1000.0` et `bytes: 1000` sont trois
//! écritures distinctes ; seule la forme entière est acceptée là où le
//! contrat déclare `type: integer`. Convertir d'abord en `f64` ferait
//! perdre la distinction, et au-delà de 2^53 la valeur elle-même.
//!
//! **Pas de virgule traînante**, pas de commentaire, pas de `NaN`, pas
//! d'`Infinity`, pas de nombre hexadécimal : la RFC n'en a aucun, et les
//! accepter élargirait le contrat en silence.
//!
//! **UTF-8 strict**, avec une exception nommée : un BOM UTF-8 en tête est
//! retiré POUR L'ANALYSE. Les octets d'origine restent intacts et c'est sur
//! eux que l'empreinte est calculée — un BOM est banal (PowerShell en met
//! un), et refuser un fichier valide pour cette raison accuserait le
//! partenaire à notre place.
//!
//! **Profondeur bornée** à 64. Un document profond de 100 000 niveaux fait
//! déborder la pile de tout analyseur récursif ; la borne est lue AVANT de
//! descendre.

use std::collections::BTreeMap;
use std::fmt;

pub const PROFONDEUR_MAX: usize = 64;

/// Nombre maximal de VALEURS dans un document, bornes comprises.
///
/// POURQUOI, ET CE QUI A ÉTÉ MESURÉ
///
/// La profondeur était bornée, la LARGEUR ne l'était pas. Un manifeste de
/// 22 Mo composé de feuilles numériques faisait culminer la mémoire à
/// **711 Mio** : l'arbre d'analyse coûte une trentaine d'octets par feuille
/// de deux octets, soit une amplification mesurée d'un facteur ~33. Avec un
/// manifeste de 64 Mio, le même calcul dépasse deux gigaoctets, et
/// `panic = "abort"` fait alors sortir le processus en 134 -- hors du
/// contrat {0, 1, 2, 3}.
///
/// Borner les NŒUDS plutôt que les octets d'entrée borne directement la
/// chose coûteuse, sans dépendre du rapport entre les deux.
///
/// Un manifeste réel en porte quelques dizaines. Un million laisse quatre
/// ordres de grandeur de marge et plafonne l'arbre à une trentaine de
/// mégaoctets. `COMPORTEMENT CHOISI ICI`, non contractuel : `AMBIGUITE-3`.
pub const NOEUDS_MAX: usize = 1_000_000;

#[derive(Debug, Clone, PartialEq)]
pub enum Valeur {
    Nul,
    Bool(bool),
    /// Le texte EXACT du nombre, tel qu'il est écrit dans le document.
    /// Jamais converti : voir l'en-tête du module.
    Nombre(String),
    Texte(String),
    Tableau(Vec<Valeur>),
    /// `BTreeMap` et non `HashMap` : l'ordre de parcours est déterminé, donc
    /// un message d'erreur qui énumère des clefs est reproductible.
    Objet(BTreeMap<String, Valeur>),
}

#[derive(Debug, Clone)]
pub struct Erreur {
    pub message: String,
    pub position: usize,
}

impl fmt::Display for Erreur {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{} (octet {})", self.message, self.position)
    }
}

impl Valeur {
    // Le verificateur filtre les valeurs par motif (`Valeur::Objet(o) =>`) :
    // cet accesseur ne sert qu'aux essais, et le compilateur a raison de le
    // signaler hors essais. On le dit, on ne le masque pas.
    #[cfg_attr(not(test), allow(dead_code))]
    pub fn comme_objet(&self) -> Option<&BTreeMap<String, Valeur>> {
        match self {
            Valeur::Objet(o) => Some(o),
            _ => None,
        }
    }
    pub fn comme_texte(&self) -> Option<&str> {
        match self {
            Valeur::Texte(s) => Some(s),
            _ => None,
        }
    }
    /// Le nombre, SI et seulement si il est écrit comme un entier : pas de
    /// point, pas d'exposant, pas de zéro de tête. `type: integer` du
    /// contrat ne dit pas « une valeur entière », il dit « un entier ».
    pub fn comme_entier(&self) -> Option<i64> {
        match self {
            Valeur::Nombre(t) => {
                if t.contains('.') || t.contains('e') || t.contains('E') {
                    None
                } else {
                    t.parse::<i64>().ok()
                }
            }
            _ => None,
        }
    }
    /// Le nom du type, pour les messages. Jamais « null » pour un absent :
    /// une clef absente et une clef à `null` ne sont pas la même chose, et
    /// cette distinction se joue chez l'appelant, pas ici.
    pub fn nom_du_type(&self) -> &'static str {
        match self {
            Valeur::Nul => "null",
            Valeur::Bool(_) => "booleen",
            Valeur::Nombre(_) => "nombre",
            Valeur::Texte(_) => "chaine",
            Valeur::Tableau(_) => "tableau",
            Valeur::Objet(_) => "objet",
        }
    }
}

struct Analyseur<'a> {
    o: &'a [u8],
    i: usize,
    /// Valeurs déjà construites. Voir `NOEUDS_MAX`.
    noeuds: usize,
}

/// Analyse des OCTETS. Jamais une chaîne déjà décodée : un
/// `from_utf8_lossy` en amont remplacerait silencieusement un octet
/// invalide par U+FFFD, et le document ne serait plus celui qui a été
/// transmis.
pub fn analyser(octets: &[u8]) -> Result<Valeur, Erreur> {
    // Le BOM UTF-8 est retiré POUR L'ANALYSE seulement.
    let utiles = if octets.starts_with(&[0xEF, 0xBB, 0xBF]) {
        &octets[3..]
    } else {
        octets
    };
    let mut a = Analyseur { o: utiles, i: 0, noeuds: 0 };
    a.blancs();
    let v = a.valeur(0)?;
    a.blancs();
    if a.i != a.o.len() {
        return Err(a.err("des octets suivent la valeur de tete"));
    }
    Ok(v)
}

impl<'a> Analyseur<'a> {
    fn err(&self, m: &str) -> Erreur {
        Erreur { message: m.to_string(), position: self.i }
    }

    fn blancs(&mut self) {
        // Les QUATRE blancs de la RFC 8259, et pas un de plus. Ni tabulation
        // verticale, ni saut de page, ni espace insécable.
        while self.i < self.o.len()
            && matches!(self.o[self.i], b' ' | b'\t' | b'\n' | b'\r')
        {
            self.i += 1;
        }
    }

    fn valeur(&mut self, profondeur: usize) -> Result<Valeur, Erreur> {
        if profondeur > PROFONDEUR_MAX {
            return Err(self.err(&format!(
                "profondeur superieure a {PROFONDEUR_MAX} : refuse avant de descendre"
            )));
        }
        // La borne est lue AVANT de construire la valeur, comme celle de
        // profondeur : un refus après coup aurait déjà payé la mémoire.
        self.noeuds += 1;
        if self.noeuds > NOEUDS_MAX {
            return Err(self.err(&format!(
                "plus de {NOEUDS_MAX} valeurs dans le document : refuse.                  L arbre d analyse coute une trentaine d octets par valeur,                  et un manifeste de soumission en porte quelques dizaines"
            )));
        }
        let Some(&c) = self.o.get(self.i) else {
            return Err(self.err("fin de document inattendue"));
        };
        match c {
            b'{' => self.objet(profondeur),
            b'[' => self.tableau(profondeur),
            b'"' => Ok(Valeur::Texte(self.chaine()?)),
            b't' => self.litteral(b"true", Valeur::Bool(true)),
            b'f' => self.litteral(b"false", Valeur::Bool(false)),
            b'n' => self.litteral(b"null", Valeur::Nul),
            b'-' | b'0'..=b'9' => self.nombre(),
            _ => Err(self.err(&format!("octet inattendu 0x{c:02x}"))),
        }
    }

    fn litteral(&mut self, mot: &[u8], v: Valeur) -> Result<Valeur, Erreur> {
        if self.o[self.i..].starts_with(mot) {
            self.i += mot.len();
            Ok(v)
        } else {
            Err(self.err("litteral inconnu"))
        }
    }

    fn objet(&mut self, profondeur: usize) -> Result<Valeur, Erreur> {
        self.i += 1; // '{'
        let mut m: BTreeMap<String, Valeur> = BTreeMap::new();
        self.blancs();
        if self.o.get(self.i) == Some(&b'}') {
            self.i += 1;
            return Ok(Valeur::Objet(m));
        }
        loop {
            self.blancs();
            if self.o.get(self.i) != Some(&b'"') {
                return Err(self.err("nom de membre attendu, entre guillemets"));
            }
            let depart = self.i;
            let nom = self.chaine()?;
            self.blancs();
            if self.o.get(self.i) != Some(&b':') {
                return Err(self.err("`:` attendu apres le nom de membre"));
            }
            self.i += 1;
            self.blancs();
            let v = self.valeur(profondeur + 1)?;
            // CLEF EN DOUBLE -> REFUS. Voir l'en-tete du module : la RFC
            // laisse le comportement indefini, Python garde la derniere
            // SILENCIEUSEMENT, et un manifeste a deux `sha256` aurait alors
            // deux lectures. Nous refusons plutot que de choisir.
            if m.contains_key(&nom) {
                return Err(Erreur {
                    message: format!(
                        "nom de membre en DOUBLE : {nom:?}. La RFC 8259 laisse \
                         ce cas indefini ; nous refusons plutot que de choisir \
                         l une des deux valeurs en silence."
                    ),
                    position: depart,
                });
            }
            m.insert(nom, v);
            self.blancs();
            match self.o.get(self.i) {
                Some(&b',') => {
                    self.i += 1;
                    self.blancs();
                    // Pas de virgule trainante : la RFC n en a pas.
                    if self.o.get(self.i) == Some(&b'}') {
                        return Err(self.err("virgule trainante dans un objet"));
                    }
                }
                Some(&b'}') => {
                    self.i += 1;
                    return Ok(Valeur::Objet(m));
                }
                _ => return Err(self.err("`,` ou `}` attendu")),
            }
        }
    }

    fn tableau(&mut self, profondeur: usize) -> Result<Valeur, Erreur> {
        self.i += 1; // '['
        let mut t = Vec::new();
        self.blancs();
        if self.o.get(self.i) == Some(&b']') {
            self.i += 1;
            return Ok(Valeur::Tableau(t));
        }
        loop {
            self.blancs();
            t.push(self.valeur(profondeur + 1)?);
            self.blancs();
            match self.o.get(self.i) {
                Some(&b',') => {
                    self.i += 1;
                    self.blancs();
                    if self.o.get(self.i) == Some(&b']') {
                        return Err(self.err("virgule trainante dans un tableau"));
                    }
                }
                Some(&b']') => {
                    self.i += 1;
                    return Ok(Valeur::Tableau(t));
                }
                _ => return Err(self.err("`,` ou `]` attendu")),
            }
        }
    }

    fn chaine(&mut self) -> Result<String, Erreur> {
        self.i += 1; // '"'
        let mut sortie = String::new();
        loop {
            let Some(&c) = self.o.get(self.i) else {
                return Err(self.err("chaine non terminee"));
            };
            match c {
                b'"' => {
                    self.i += 1;
                    return Ok(sortie);
                }
                b'\\' => {
                    self.i += 1;
                    let Some(&e) = self.o.get(self.i) else {
                        return Err(self.err("echappement non termine"));
                    };
                    self.i += 1;
                    match e {
                        b'"' => sortie.push('"'),
                        b'\\' => sortie.push('\\'),
                        b'/' => sortie.push('/'),
                        b'b' => sortie.push('\u{0008}'),
                        b'f' => sortie.push('\u{000C}'),
                        b'n' => sortie.push('\n'),
                        b'r' => sortie.push('\r'),
                        b't' => sortie.push('\t'),
                        b'u' => {
                            let haut = self.hex4()?;
                            // Les paires de substitution UTF-16 sont
                            // assemblees ; une moitie seule est REFUSEE.
                            // L accepter produirait une chaine qui n est pas
                            // de l Unicode valide, et deux implementations la
                            // rendraient differemment.
                            if (0xD800..0xDC00).contains(&haut) {
                                if self.o.get(self.i) != Some(&b'\\')
                                    || self.o.get(self.i + 1) != Some(&b'u')
                                {
                                    return Err(self.err(
                                        "demi-paire de substitution UTF-16 sans \
                                         sa seconde moitie",
                                    ));
                                }
                                self.i += 2;
                                let bas = self.hex4()?;
                                if !(0xDC00..0xE000).contains(&bas) {
                                    return Err(self.err(
                                        "seconde moitie de paire de substitution \
                                         hors plage",
                                    ));
                                }
                                let p = 0x10000
                                    + (((haut - 0xD800) as u32) << 10)
                                    + (bas - 0xDC00) as u32;
                                sortie.push(
                                    char::from_u32(p)
                                        .ok_or_else(|| self.err("point de code invalide"))?,
                                );
                            } else if (0xDC00..0xE000).contains(&haut) {
                                return Err(self.err(
                                    "seconde moitie de paire de substitution \
                                     rencontree seule",
                                ));
                            } else {
                                sortie.push(
                                    char::from_u32(haut as u32)
                                        .ok_or_else(|| self.err("point de code invalide"))?,
                                );
                            }
                        }
                        _ => return Err(self.err("echappement inconnu")),
                    }
                }
                // Les caracteres de controle U+0000 a U+001F doivent etre
                // echappes (RFC 8259 §7). Les accepter bruts elargirait le
                // contrat.
                0x00..=0x1F => {
                    return Err(self.err(&format!(
                        "caractere de controle 0x{c:02x} non echappe dans une chaine"
                    )))
                }
                _ => {
                    // UTF-8 STRICT. Un octet invalide est un refus, jamais un
                    // U+FFFD : le document ne serait plus celui qui a ete
                    // transmis.
                    let largeur = match c {
                        0x00..=0x7F => 1,
                        0xC2..=0xDF => 2,
                        0xE0..=0xEF => 3,
                        0xF0..=0xF4 => 4,
                        _ => return Err(self.err("octet UTF-8 de tete invalide")),
                    };
                    let fin = self.i + largeur;
                    if fin > self.o.len() {
                        return Err(self.err("sequence UTF-8 tronquee"));
                    }
                    let s = std::str::from_utf8(&self.o[self.i..fin])
                        .map_err(|_| self.err("sequence UTF-8 invalide"))?;
                    sortie.push_str(s);
                    self.i = fin;
                }
            }
        }
    }

    fn hex4(&mut self) -> Result<u16, Erreur> {
        if self.i + 4 > self.o.len() {
            return Err(self.err("echappement \\u tronque"));
        }
        let mut v: u16 = 0;
        for k in 0..4 {
            let c = self.o[self.i + k];
            let n = match c {
                b'0'..=b'9' => c - b'0',
                b'a'..=b'f' => c - b'a' + 10,
                b'A'..=b'F' => c - b'A' + 10,
                _ => return Err(self.err("chiffre hexadecimal attendu")),
            };
            v = v * 16 + n as u16;
        }
        self.i += 4;
        Ok(v)
    }

    /// La grammaire des nombres de la RFC 8259, appliquee a la lettre.
    /// Le TEXTE est conserve ; aucune conversion n a lieu ici.
    fn nombre(&mut self) -> Result<Valeur, Erreur> {
        let depart = self.i;
        if self.o.get(self.i) == Some(&b'-') {
            self.i += 1;
        }
        // Partie entiere : soit un seul `0`, soit 1-9 suivi de chiffres.
        // `01` est REFUSE par la RFC, et l accepter diviserait les lectures.
        match self.o.get(self.i) {
            Some(&b'0') => {
                self.i += 1;
                if matches!(self.o.get(self.i), Some(b'0'..=b'9')) {
                    return Err(self.err("zero de tete non admis par la RFC 8259"));
                }
            }
            Some(&c) if c.is_ascii_digit() => {
                while matches!(self.o.get(self.i), Some(b'0'..=b'9')) {
                    self.i += 1;
                }
            }
            _ => return Err(self.err("chiffre attendu")),
        }
        if self.o.get(self.i) == Some(&b'.') {
            self.i += 1;
            if !matches!(self.o.get(self.i), Some(b'0'..=b'9')) {
                return Err(self.err("chiffre attendu apres le point decimal"));
            }
            while matches!(self.o.get(self.i), Some(b'0'..=b'9')) {
                self.i += 1;
            }
        }
        if matches!(self.o.get(self.i), Some(b'e') | Some(b'E')) {
            self.i += 1;
            if matches!(self.o.get(self.i), Some(b'+') | Some(b'-')) {
                self.i += 1;
            }
            if !matches!(self.o.get(self.i), Some(b'0'..=b'9')) {
                return Err(self.err("chiffre attendu dans l exposant"));
            }
            while matches!(self.o.get(self.i), Some(b'0'..=b'9')) {
                self.i += 1;
            }
        }
        // `from_utf8` sans perte : la tranche ne contient que des octets
        // ASCII, par construction de la grammaire ci-dessus.
        let texte = std::str::from_utf8(&self.o[depart..self.i])
            .map_err(|_| self.err("nombre non textuel"))?
            .to_string();
        Ok(Valeur::Nombre(texte))
    }
}

// --------------------------------------------------------------------------
// Écriture JSON, pour le rapport. Déterministe : clefs triées, aucun
// flottant, aucune dépendance.
// --------------------------------------------------------------------------

/// Échappe une chaîne selon la RFC 8259. Les non-ASCII sortent tels quels
/// en UTF-8 -- le rapport est un document UTF-8, et échapper en `\u` le
/// rendrait illisible pour un auditeur.
pub fn echapper(s: &str) -> String {
    let mut o = String::with_capacity(s.len() + 2);
    o.push('"');
    for c in s.chars() {
        match c {
            '"' => o.push_str("\\\""),
            '\\' => o.push_str("\\\\"),
            '\n' => o.push_str("\\n"),
            '\r' => o.push_str("\\r"),
            '\t' => o.push_str("\\t"),
            '\u{0008}' => o.push_str("\\b"),
            '\u{000C}' => o.push_str("\\f"),
            c if (c as u32) < 0x20 => {
                o.push_str(&format!("\\u{:04x}", c as u32))
            }
            c => o.push(c),
        }
    }
    o.push('"');
    o
}
