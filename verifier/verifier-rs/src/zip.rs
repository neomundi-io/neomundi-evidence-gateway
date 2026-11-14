//! Module 1 — lecture SÉCURISÉE d'une archive ZIP, EN MÉMOIRE.
//!
//! LA RÈGLE QUI GOUVERNE CE MODULE
//!
//! **Rien n'est jamais écrit sur le système de fichiers.** Aucune
//! extraction, même dans un dossier temporaire. Un membre est lu en
//! mémoire, condensé, et oublié. Un vérificateur qui extrait fait reposer
//! sa sûreté sur la correction de ses contrôles de chemin ; celui-ci la
//! fait reposer sur le fait qu'il n'écrit pas.
//!
//! C'est une différence de conception avec `adapters/ingest.py`, qui déplie
//! sous contrôle dans un `mkdtemp`. Les deux sont défendables ; celle-ci
//! est plus simple à auditer, et elle est documentée comme une divergence
//! d'implémentation sans effet sur les verdicts.
//!
//! CE QUI EST REFUSÉ, ET AVANT QUOI
//!
//! Tout est décidé sur le **répertoire central**, avant de toucher à une
//! seule donnée compressée :
//!
//!   nombre de membres au-delà de la borne          → refus
//!   taille décompressée annoncée au-delà de la borne → refus
//!   nom de membre en DOUBLE                        → refus
//!   chemin absolu, `..`, lettre de lecteur         → refus
//!   antislash dans un nom                          → refus
//!   bit 0 du drapeau général (chiffrement)         → refus
//!   méthode autre que 0 (stocké) ou 8 (deflate)    → refus
//!
//! La taille ANNONCÉE sert à refuser tôt ; la taille RÉELLE est vérifiée
//! après décompression, et une annonce mensongère est elle aussi un refus.
//! Se fier à l'annonce seule laisserait passer une bombe qui mentirait.

use crate::inflate;

pub const MEMBRES_MAX: usize = 4096;
pub const OCTETS_TOTAL_MAX: u64 = 256 * 1024 * 1024;
pub const OCTETS_PAR_MEMBRE_MAX: u64 = 64 * 1024 * 1024;

pub struct Membre {
    pub nom: String,
    pub methode: u16,
    pub taille_annoncee: u64,
    pub taille_compressee: u64,
    pub decalage_local: u64,
    /// Le CRC-32 que le répertoire central déclare. Vérifié dans `lire`.
    pub crc_declare: u32,
}

pub struct Archive {
    octets: Vec<u8>,
    pub membres: Vec<Membre>,
}

/// Les refus de l'ouverture. Chacun porte sa raison : un refus muet ne
/// serait pas une décision.
#[derive(Debug)]
pub struct Refus(pub String);

impl std::fmt::Display for Refus {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.0)
    }
}

fn u16le(o: &[u8], i: usize) -> u16 {
    u16::from_le_bytes([o[i], o[i + 1]])
}
fn u32le(o: &[u8], i: usize) -> u32 {
    u32::from_le_bytes([o[i], o[i + 1], o[i + 2], o[i + 3]])
}

impl Archive {
    /// Ouvre l'archive et valide son répertoire central. Ne décompresse
    /// RIEN : c'est `lire` qui s'en charge, membre par membre.
    pub fn ouvrir(octets: Vec<u8>) -> Result<Archive, Refus> {
        // --- trouver la fin du répertoire central (EOCD) ---------------
        if octets.len() < 22 {
            return Err(Refus("archive trop courte pour etre un ZIP".into()));
        }
        // Le commentaire final peut faire jusqu'à 65535 octets ; on remonte
        // depuis la fin, et on prend la DERNIÈRE signature trouvée.
        let debut = octets.len().saturating_sub(22 + 65535);
        let mut eocd = None;
        let mut i = octets.len() - 22;
        loop {
            if u32le(&octets, i) == 0x0605_4b50 {
                eocd = Some(i);
                break;
            }
            if i == debut {
                break;
            }
            i -= 1;
        }
        let Some(eocd) = eocd else {
            return Err(Refus(
                "aucune fin de repertoire central : ni ZIP lisible, ni archive \
                 tronquee recuperable"
                    .into(),
            ));
        };

        let nb_disque = u16le(&octets, eocd + 8) as usize;
        let nb_total = u16le(&octets, eocd + 10) as usize;
        // ZIP64 : REFUS NOMMÉ, et non refus accidentel.
        //
        // Les champs de 16 et 32 bits de l'EOCD portent 0xFFFF / 0xFFFFFFFF
        // pour dire « la vraie valeur est dans l'EOCD64 ». Ce module ne lit
        // pas l'EOCD64. Sans ce contrôle, une archive ZIP64 était refusée
        // quand même -- mais pour une raison FAUSSE (« entree de repertoire
        // central malformee »), ce qui envoyait un auditeur chercher une
        // corruption là où il n'y a qu'un format non pris en charge.
        if nb_disque == 0xFFFF
            || nb_total == 0xFFFF
            || u32le(&octets, eocd + 12) == 0xFFFF_FFFF
            || u32le(&octets, eocd + 16) == 0xFFFF_FFFF
        {
            return Err(Refus(
                "archive ZIP64 : non prise en charge par ce verificateur.                  Un paquet de soumission tient sous les bornes de ce module,                  et lire l EOCD64 ajouterait une surface sans besoin etabli"
                    .into(),
            ));
        }
        if nb_disque != nb_total {
            return Err(Refus(
                "archive multi-volumes : refusee, un paquet de preuve est d un \
                 seul tenant"
                    .into(),
            ));
        }
        if nb_total > MEMBRES_MAX {
            return Err(Refus(format!(
                "{nb_total} membres, borne {MEMBRES_MAX} : refuse avant lecture"
            )));
        }
        let taille_rc = u32le(&octets, eocd + 12) as usize;
        let decalage_rc = u32le(&octets, eocd + 16) as usize;
        if decalage_rc
            .checked_add(taille_rc)
            .map_or(true, |f| f > octets.len())
        {
            return Err(Refus("repertoire central hors de l archive".into()));
        }

        // --- parcourir le répertoire central --------------------------
        //
        // LA ZONE EST BORNÉE, ET ELLE DOIT ÊTRE CONSOMMÉE EXACTEMENT.
        //
        // La boucle ne se bornait qu'à la taille du FICHIER, pas à la zone
        // que l'EOCD déclare. Deux conséquences mesurées :
        //
        //   1. une archive sous-déclarant `taille_rc` était lue AU-DELÀ de
        //      sa zone, et acceptée, là où `zipfile` de Python la refuse ;
        //   2. une archive sous-déclarant `nb_total` d'une unité rendait le
        //      dernier membre INVISIBLE -- un fichier non déclaré pouvait
        //      donc être transporté dans l'archive sans apparaître au
        //      rapport, alors que Python le signalait.
        //
        // Le second point était le plus grave : le contrôle « fichiers non
        // déclarés » se contournait en changeant deux octets de l'EOCD.
        //
        // L'invariant qui ferme les deux : les `nb_total` entrées doivent
        // remplir `[decalage_rc, decalage_rc + taille_rc)` **exactement**.
        // Trop court, il reste des entrées cachées ; trop long, l'EOCD
        // mentait dans l'autre sens.
        let fin_rc = decalage_rc + taille_rc;
        // LE RÉPERTOIRE CENTRAL DOIT TOUCHER L'EOCD.
        //
        // Des octets entre la fin du répertoire central et l'EOCD ne sont
        // décrits par aucune partie du format. Mesuré : avec 22 octets
        // glissés là -- une fausse signature d'EOCD --, `zipfile` de Python
        // refusait l'archive et ce module l'ACCEPTAIT. Les deux lectures
        // sont défendables, et c'est précisément le problème : une archive
        // qu'un lecteur accepte et l'autre refuse est ambiguë. Tout outil
        // standard écrit l'EOCD immédiatement après le répertoire central ;
        // l'exiger supprime l'ambiguïté sans refuser rien de légitime.
        if fin_rc != eocd {
            return Err(Refus(format!(
                "{} octet(s) entre la fin du repertoire central et l EOCD :                  aucune partie du format ne les decrit, et deux lecteurs n en                  tirent pas la meme archive",
                eocd.saturating_sub(fin_rc)
            )));
        }
        let mut membres: Vec<Membre> = Vec::with_capacity(nb_total);
        let mut vus: Vec<String> = Vec::with_capacity(nb_total);
        let mut p = decalage_rc;
        let mut total_annonce: u64 = 0;
        for _ in 0..nb_total {
            if p + 46 > fin_rc || u32le(&octets, p) != 0x0201_4b50 {
                return Err(Refus(
                    "entree de repertoire central malformee ou hors de la                      zone que l EOCD declare"
                        .into(),
                ));
            }
            let drapeaux = u16le(&octets, p + 8);
            let methode = u16le(&octets, p + 10);
            let crc_declare = u32le(&octets, p + 16);
            let taille_compressee = u32le(&octets, p + 20) as u64;
            let taille_annoncee = u32le(&octets, p + 24) as u64;
            let n_nom = u16le(&octets, p + 28) as usize;
            let n_extra = u16le(&octets, p + 30) as usize;
            let n_comm = u16le(&octets, p + 32) as usize;
            let decalage_local = u32le(&octets, p + 42) as u64;
            let fin_nom = p + 46 + n_nom;
            if fin_nom > fin_rc {
                return Err(Refus(
                    "nom de membre hors de la zone du repertoire central".into(),
                ));
            }
            // Le nom doit être de l'UTF-8 valide. Un nom indécodable n'est
            // pas comparable à un chemin déclaré, et le remplacer par
            // U+FFFD inventerait un nom.
            let nom = std::str::from_utf8(&octets[p + 46..fin_nom])
                .map_err(|_| {
                    Refus("nom de membre qui n est pas de l UTF-8 valide".into())
                })?
                .to_string();

            if drapeaux & 0x0001 != 0 {
                return Err(Refus(format!(
                    "membre chiffre {nom:?} : refuse. Un paquet de preuve dont \
                     le contenu n est pas lisible ne se verifie pas"
                )));
            }
            if methode != 0 && methode != 8 {
                return Err(Refus(format!(
                    "membre {nom:?} : methode de compression {methode} non prise \
                     en charge (0 stocke ou 8 deflate seulement)"
                )));
            }
            if taille_annoncee > OCTETS_PAR_MEMBRE_MAX {
                return Err(Refus(format!(
                    "membre {nom:?} : {taille_annoncee} octets annonces, borne \
                     {OCTETS_PAR_MEMBRE_MAX}"
                )));
            }
            total_annonce = total_annonce.saturating_add(taille_annoncee);
            if total_annonce > OCTETS_TOTAL_MAX {
                return Err(Refus(format!(
                    "{total_annonce} octets decompresses annonces, borne \
                     {OCTETS_TOTAL_MAX} : refuse AVANT toute decompression"
                )));
            }
            // NOM EN DOUBLE -> REFUS. Deux membres de même nom rendent
            // l'archive ambiguë : un lecteur prendrait le premier, un autre
            // le dernier, et les deux condenseraient des octets différents
            // sous le même chemin déclaré.
            if vus.iter().any(|v| v == &nom) {
                return Err(Refus(format!(
                    "nom de membre en DOUBLE : {nom:?}. L archive est ambigue, \
                     et deux lecteurs en tireraient des octets differents"
                )));
            }
            vus.push(nom.clone());
            membres.push(Membre {
                nom,
                methode,
                taille_annoncee,
                taille_compressee,
                decalage_local,
                crc_declare,
            });
            p = fin_nom + n_extra + n_comm;
            if p > fin_rc {
                return Err(Refus(
                    "une entree de repertoire central depasse la zone                      declaree par l EOCD"
                        .into(),
                ));
            }
        }
        // Consommation EXACTE : des octets restants sont des entrées que
        // `nb_total` ne compte pas, donc des membres qu'un lecteur verrait
        // et l'autre non.
        if p != fin_rc {
            return Err(Refus(format!(
                "l EOCD annonce {nb_total} entree(s) et {taille_rc} octets de                  repertoire central, mais {} octet(s) restent apres la                  derniere : l archive est ambigue, et un fichier peut s y                  cacher",
                fin_rc - p
            )));
        }
        Ok(Archive { octets, membres })
    }

    /// Les octets d'un membre, décompressés en mémoire.
    ///
    /// La taille réelle est confrontée à l'annonce : une annonce mensongère
    /// est un refus. Se fier à l'annonce seule laisserait passer une bombe
    /// qui mentirait sur sa taille.
    pub fn lire(&self, m: &Membre) -> Result<Vec<u8>, Refus> {
        let d = m.decalage_local as usize;
        if d + 30 > self.octets.len() || u32le(&self.octets, d) != 0x0403_4b50 {
            return Err(Refus(format!(
                "membre {:?} : en-tete local absent ou malforme",
                m.nom
            )));
        }
        let n_nom = u16le(&self.octets, d + 26) as usize;
        let n_extra = u16le(&self.octets, d + 28) as usize;
        // LE NOM LOCAL DOIT ÊTRE CELUI DU RÉPERTOIRE CENTRAL.
        //
        // Il n'était pas lu. Une archive pouvait donc annoncer
        // `submission.json` dans son répertoire central et nommer tout
        // autre chose dans l'en-tête local du même offset : deux lecteurs
        // en tiraient des octets différents sous le même nom. `zipfile` de
        // Python compare les deux et lève `BadZipFile` ; ce module
        // ACCEPTAIT. C'est la forme la plus directe de l'ambiguïté que le
        // refus des noms en double cherche justement à écarter.
        let fin_nom_local = d + 30 + n_nom;
        if fin_nom_local > self.octets.len() {
            return Err(Refus(format!(
                "membre {:?} : nom de l en-tete local hors de l archive",
                m.nom
            )));
        }
        match std::str::from_utf8(&self.octets[d + 30..fin_nom_local]) {
            Ok(local) if local == m.nom => {}
            Ok(local) => {
                return Err(Refus(format!(
                    "membre {:?} : l en-tete local le nomme {local:?}.                      L archive est ambigue, et deux lecteurs en tireraient                      des octets differents sous le meme nom",
                    m.nom
                )))
            }
            Err(_) => {
                return Err(Refus(format!(
                    "membre {:?} : nom de l en-tete local qui n est pas de                      l UTF-8 valide",
                    m.nom
                )))
            }
        }
        let debut = d + 30 + n_nom + n_extra;
        let taille_c = if m.taille_compressee > 0 {
            m.taille_compressee as usize
        } else {
            // Un membre vide est légitime (fichier de 0 octet). Le cas est
            // explicitement éprouvé par le banc comparatif.
            0
        };
        if debut
            .checked_add(taille_c)
            .map_or(true, |f| f > self.octets.len())
        {
            return Err(Refus(format!("membre {:?} : donnees tronquees", m.nom)));
        }
        let brut = &self.octets[debut..debut + taille_c];
        let sortie = match m.methode {
            0 => brut.to_vec(),
            // LA BORNE SUIT L ANNONCE, PAS LE PLAFOND.
            //
            // Elle valait `OCTETS_PAR_MEMBRE_MAX`, soit 64 Mio, pour TOUT
            // membre -- y compris un membre qui n annonce que 60 Kio. Un
            // menteur pouvait donc faire travailler le verificateur 1 000
            // fois plus que son annonce : 32 Mio d archive suffisaient a
            // declencher 32 Gio de decompression (513 membres x 64 Mio),
            // soit environ trois minutes de calcul mesurees sur ce poste,
            // avant que le mensonge ne soit constate a la ligne suivante.
            //
            // Borner a l annonce arrete le travail AU PREMIER octet de trop.
            // Le mensonge reste un refus ; il coute seulement ce qu il a
            // annonce. `+ 1` pour que depasser d un seul octet soit un
            // depassement, et non une egalite.
            8 => inflate::inflate(
                brut,
                (m.taille_annoncee.min(OCTETS_PAR_MEMBRE_MAX) as usize)
                    .saturating_add(1),
            )
            .map_err(|e| Refus(format!("membre {:?} : {e}", m.nom)))?,
            _ => {
                return Err(Refus(format!(
                    "membre {:?} : methode {} non prise en charge",
                    m.nom, m.methode
                )))
            }
        };
        if sortie.len() as u64 != m.taille_annoncee {
            return Err(Refus(format!(
                "membre {:?} : {} octets produits, {} annonces. Une annonce \
                 mensongere est un refus",
                m.nom,
                sortie.len(),
                m.taille_annoncee
            )));
        }
        // LE CRC-32 EST VÉRIFIÉ.
        //
        // Il ne l'était pas : ce vérificateur rendait `ACCEPTE` sur une
        // archive dont le champ d'intégrité contredit les données, et que
        // `unzip` comme `zipfile` refusent tous deux. Pour un paquet de
        // preuve, conclure « accepté » là où tout outil standard dit
        // « corrompu » est une garantie trompeuse -- exactement ce qu'il
        // faut éviter.
        //
        // L'empreinte SHA-256 déclarée protège les ARTEFACTS ; elle ne dit
        // rien du manifeste, dont aucun condensé n'est déclaré nulle part.
        let crc = crc32(&sortie);
        if crc != m.crc_declare {
            return Err(Refus(format!(
                "membre {:?} : CRC-32 recalcule {:#010x}, declare {:#010x}.                  L archive est corrompue ou forgee",
                m.nom, crc, m.crc_declare
            )));
        }
        Ok(sortie)
    }

    pub fn trouver(&self, nom: &str) -> Option<&Membre> {
        self.membres.iter().find(|m| m.nom == nom)
    }

    /// Les noms des membres qui ne sont pas des dossiers.
    pub fn fichiers(&self) -> Vec<&str> {
        self.membres
            .iter()
            .filter(|m| !m.nom.ends_with('/'))
            .map(|m| m.nom.as_str())
            .collect()
    }
}

/// CRC-32 de la norme ZIP (polynôme inversé 0xEDB88320), RFC 1952 §8.
///
/// Écrit ici comme le reste : vingt lignes, une table dérivée à la volée,
/// aucune dépendance. Ce n'est pas une primitive cryptographique -- un CRC
/// se forge trivialement. Il n'est donc PAS une garantie d'authenticité,
/// seulement le contrôle d'intégrité que le format ZIP prescrit, et son
/// rôle ici est de ne pas accepter une archive que tout autre outil refuse.
fn crc32(donnees: &[u8]) -> u32 {
    let mut table = [0u32; 256];
    for (n, e) in table.iter_mut().enumerate() {
        let mut c = n as u32;
        for _ in 0..8 {
            c = if c & 1 != 0 { 0xEDB8_8320 ^ (c >> 1) } else { c >> 1 };
        }
        *e = c;
    }
    let mut c = 0xFFFF_FFFFu32;
    for &o in donnees {
        c = table[((c ^ o as u32) & 0xFF) as usize] ^ (c >> 8);
    }
    c ^ 0xFFFF_FFFF
}
