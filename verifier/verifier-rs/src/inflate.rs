//! DEFLATE (RFC 1951), décompression seule. Écrit ici, et non emprunté.
//!
//! POURQUOI
//!
//! C'est la seule pièce de ce vérificateur qui aurait un argument sérieux
//! pour être empruntée. Elle est écrite ici pour la même raison que le
//! reste : un vérificateur indépendant doit être lisible de bout en bout,
//! et une chaîne de dépendances transitives déplacerait la confiance vers
//! des tiers que l'auditeur n'a pas choisis.
//!
//! LES BORNES, ET POURQUOI ELLES SONT ICI
//!
//! La décompression est le point d'entrée des bombes : quelques kilo-octets
//! peuvent se déplier en gigaoctets. La borne de sortie est donc passée par
//! l'appelant et vérifiée **à chaque octet produit**, non à la fin. Un
//! dépassement est un refus, jamais une troncature : une sortie tronquée
//! aurait une empreinte différente, et la comparer serait pire que de
//! refuser.
//!
//! CE QU'ELLE N'EST PAS
//!
//! Elle ne compresse pas, ne gère ni zlib ni gzip (pas d'en-tête, pas
//! d'Adler-32) : un membre de ZIP est du DEFLATE nu. Elle n'est pas
//! optimisée pour la vitesse.

/// Borne dure de sécurité, en plus de celle que passe l'appelant.
pub const SORTIE_MAX_DURE: usize = 256 * 1024 * 1024;

pub fn inflate(entree: &[u8], borne_sortie: usize) -> Result<Vec<u8>, String> {
    let borne = borne_sortie.min(SORTIE_MAX_DURE);
    let mut f = Flux { o: entree, octet: 0, bit: 0 };
    let mut sortie: Vec<u8> = Vec::new();
    loop {
        let dernier = f.bits(1)? == 1;
        let genre = f.bits(2)?;
        match genre {
            0 => {
                // Bloc STOCKÉ : on s'aligne sur l'octet, puis LEN/NLEN.
                f.aligner();
                let len = f.u16_le()? as usize;
                let nlen = f.u16_le()? as usize;
                if len != (!nlen) & 0xFFFF {
                    return Err("bloc stocke : LEN et NLEN se contredisent".into());
                }
                if sortie.len() + len > borne {
                    return Err(format!(
                        "sortie decompressee au-dela de la borne de {borne} octets : refuse, \
                         et NON tronquee"
                    ));
                }
                let d = f.octet;
                if d + len > f.o.len() {
                    return Err("bloc stocke tronque".into());
                }
                sortie.extend_from_slice(&f.o[d..d + len]);
                f.octet = d + len;
            }
            1 => {
                let (lit, dist) = arbres_fixes()?;
                f.bloc(&lit, &dist, &mut sortie, borne)?;
            }
            2 => {
                let (lit, dist) = f.arbres_dynamiques()?;
                f.bloc(&lit, &dist, &mut sortie, borne)?;
            }
            _ => return Err("genre de bloc DEFLATE reserve (3)".into()),
        }
        if dernier {
            return Ok(sortie);
        }
    }
}

struct Flux<'a> {
    o: &'a [u8],
    octet: usize,
    bit: u32,
}

/// Un arbre de Huffman canonique, en table plate : pour chaque longueur,
/// le premier code et l'indice du premier symbole.
struct Huffman {
    /// `compte[l]` = nombre de codes de longueur `l`.
    compte: [u16; 16],
    /// Symboles triés par (longueur, valeur).
    symboles: Vec<u16>,
}

impl Huffman {
    /// `tolerer_incomplet` suit la règle de `zlib` (`inflate_table`) :
    ///
    ///   - **sur-souscrit** → refus, toujours ;
    ///   - **incomplet** → refus, SAUF pour les arbres littéral/longueur et
    ///     distance qui ne portent qu'**un seul code, ou aucun** -- le cas
    ///     légitime d'un bloc sans retour arrière, que `zlib` produit.
    ///
    /// L'arbre des LONGUEURS DE CODE, lui, n'a pas droit à cette tolérance,
    /// exactement comme `type == CODES` chez `zlib`.
    ///
    /// POURQUOI CE CONTRÔLE A ÉTÉ AJOUTÉ, ET CE QU'IL CORRIGE
    ///
    /// Il manquait. Le commentaire annonçait « sur-souscrit **ou
    /// incomplet** », le code ne testait que `reste < 0`. Une campagne de
    /// 50 000 flux mutés a trouvé quatre flux que `zlib` refuse
    /// (« invalid distances set ») et que ce module ACCEPTAIT, en produisant
    /// des octets qu'aucun décodeur standard ne produit. Pour un
    /// vérificateur de preuve, c'était le mauvais sens : il aurait condensé
    /// une sortie que lui seul sait calculer.
    fn depuis_longueurs(longueurs: &[u8], tolerer_incomplet: bool)
        -> Result<Huffman, String>
    {
        let mut compte = [0u16; 16];
        for &l in longueurs {
            if l as usize > 15 {
                return Err("longueur de code Huffman superieure a 15".into());
            }
            compte[l as usize] += 1;
        }
        compte[0] = 0;
        let nb_codes: u32 = compte[1..].iter().map(|&c| c as u32).sum();
        let mut reste: i32 = 1;
        for l in 1..16 {
            reste <<= 1;
            reste -= compte[l] as i32;
            if reste < 0 {
                return Err("arbre Huffman sur-souscrit".into());
            }
        }
        if reste > 0 && !(tolerer_incomplet && nb_codes <= 1) {
            return Err(format!(
                "arbre Huffman INCOMPLET : {nb_codes} code(s), {reste}                  motif(s) de bits sans symbole. Un decodeur tolerant                  produirait des octets qu un autre ne produit pas"
            ));
        }
        let mut offsets = [0u16; 16];
        for l in 1..15 {
            offsets[l + 1] = offsets[l] + compte[l];
        }
        let mut symboles = vec![0u16; longueurs.len()];
        for (s, &l) in longueurs.iter().enumerate() {
            if l != 0 {
                symboles[offsets[l as usize] as usize] = s as u16;
                offsets[l as usize] += 1;
            }
        }
        Ok(Huffman { compte, symboles })
    }
}

/// Les arbres du bloc de type 1, figés par la RFC 1951 §3.2.6.
///
/// LES 32 CODES DE DISTANCE, ET NON 30
///
/// La RFC décrit 30 codes de distance de 5 bits et précise que les codes 30
/// et 31 « n'apparaîtront jamais ». Trente codes de 5 bits forment un arbre
/// formellement INCOMPLET : déclaré ainsi, il serait désormais refusé par le
/// contrôle de complétude. `zlib` construit la même table avec 32 entrées,
/// ce qui la rend complète, et refuse les symboles 30 et 31 au décodage.
/// C'est ce que fait ce module : 32 ici, et `ds >= 30` refusé dans `bloc`.
///
/// Rend un `Result` : un `expect` dans un vérificateur est une panique en
/// attente, même quand elle est inatteignable par construction.
fn arbres_fixes() -> Result<(Huffman, Huffman), String> {
    let mut l = vec![8u8; 288];
    for x in l.iter_mut().take(256).skip(144) {
        *x = 9;
    }
    for x in l.iter_mut().take(280).skip(256) {
        *x = 7;
    }
    let lit = Huffman::depuis_longueurs(&l, false)?;
    let dist = Huffman::depuis_longueurs(&[5u8; 32], false)?;
    Ok((lit, dist))
}

const LONGUEURS_BASE: [u16; 29] = [
    3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59,
    67, 83, 99, 115, 131, 163, 195, 227, 258,
];
const LONGUEURS_EXTRA: [u8; 29] = [
    0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5,
    5, 5, 5, 0,
];
const DISTANCES_BASE: [u16; 30] = [
    1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513,
    769, 1025, 1537, 2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577,
];
const DISTANCES_EXTRA: [u8; 30] = [
    0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10,
    11, 11, 12, 12, 13, 13,
];

impl<'a> Flux<'a> {
    fn bits(&mut self, n: u32) -> Result<u32, String> {
        let mut v = 0u32;
        for k in 0..n {
            if self.octet >= self.o.len() {
                return Err("flux DEFLATE tronque".into());
            }
            let b = (self.o[self.octet] >> self.bit) & 1;
            v |= (b as u32) << k;
            self.bit += 1;
            if self.bit == 8 {
                self.bit = 0;
                self.octet += 1;
            }
        }
        Ok(v)
    }

    fn aligner(&mut self) {
        if self.bit != 0 {
            self.bit = 0;
            self.octet += 1;
        }
    }

    fn u16_le(&mut self) -> Result<u16, String> {
        if self.octet + 2 > self.o.len() {
            return Err("flux DEFLATE tronque (u16)".into());
        }
        let v = u16::from_le_bytes([self.o[self.octet], self.o[self.octet + 1]]);
        self.octet += 2;
        Ok(v)
    }

    /// Décodage canonique, bit à bit, du plus significatif au moins.
    fn symbole(&mut self, h: &Huffman) -> Result<u16, String> {
        let mut code: i32 = 0;
        let mut premier: i32 = 0;
        let mut indice: i32 = 0;
        for l in 1..16 {
            code |= self.bits(1)? as i32;
            let compte = h.compte[l] as i32;
            if code - premier < compte {
                let i = (indice + (code - premier)) as usize;
                return h
                    .symboles
                    .get(i)
                    .copied()
                    .ok_or_else(|| "symbole Huffman hors table".to_string());
            }
            indice += compte;
            premier = (premier + compte) << 1;
            code <<= 1;
        }
        Err("code Huffman de plus de 15 bits".into())
    }

    fn arbres_dynamiques(&mut self) -> Result<(Huffman, Huffman), String> {
        let hlit = self.bits(5)? as usize + 257;
        let hdist = self.bits(5)? as usize + 1;
        let hclen = self.bits(4)? as usize + 4;
        const ORDRE: [usize; 19] = [
            16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15,
        ];
        let mut lc = [0u8; 19];
        for k in 0..hclen {
            lc[ORDRE[k]] = self.bits(3)? as u8;
        }
        // L arbre des LONGUEURS DE CODE n a pas droit a la tolerance :
        // c est `type == CODES` chez `zlib`.
        let arbre_lc = Huffman::depuis_longueurs(&lc, false)?;
        let mut longueurs = vec![0u8; hlit + hdist];
        let mut i = 0usize;
        while i < longueurs.len() {
            let s = self.symbole(&arbre_lc)?;
            match s {
                0..=15 => {
                    longueurs[i] = s as u8;
                    i += 1;
                }
                16 => {
                    if i == 0 {
                        return Err("repetition 16 sans longueur precedente".into());
                    }
                    let prec = longueurs[i - 1];
                    let n = 3 + self.bits(2)? as usize;
                    if i + n > longueurs.len() {
                        return Err("repetition de longueurs hors table".into());
                    }
                    for _ in 0..n {
                        longueurs[i] = prec;
                        i += 1;
                    }
                }
                17 => {
                    let n = 3 + self.bits(3)? as usize;
                    if i + n > longueurs.len() {
                        return Err("repetition de zeros hors table".into());
                    }
                    i += n;
                }
                18 => {
                    let n = 11 + self.bits(7)? as usize;
                    if i + n > longueurs.len() {
                        return Err("repetition de zeros hors table".into());
                    }
                    i += n;
                }
                _ => return Err("symbole de longueur de code inconnu".into()),
            }
        }
        let lit = Huffman::depuis_longueurs(&longueurs[..hlit], true)?;
        let dist = Huffman::depuis_longueurs(&longueurs[hlit..], true)?;
        Ok((lit, dist))
    }

    fn bloc(
        &mut self,
        lit: &Huffman,
        dist: &Huffman,
        sortie: &mut Vec<u8>,
        borne: usize,
    ) -> Result<(), String> {
        loop {
            let s = self.symbole(lit)?;
            match s {
                0..=255 => {
                    // La borne est verifiee A CHAQUE octet produit, et non
                    // a la fin : c est la seule facon d arreter une bombe
                    // avant qu elle ne remplisse la memoire.
                    if sortie.len() + 1 > borne {
                        return Err(format!(
                            "sortie decompressee au-dela de la borne de {borne} octets : \
                             refuse, et NON tronquee"
                        ));
                    }
                    sortie.push(s as u8);
                }
                256 => return Ok(()),
                257..=285 => {
                    let k = (s - 257) as usize;
                    let longueur = LONGUEURS_BASE[k] as usize
                        + self.bits(LONGUEURS_EXTRA[k] as u32)? as usize;
                    let ds = self.symbole(dist)? as usize;
                    if ds >= 30 {
                        return Err("symbole de distance reserve".into());
                    }
                    let distance = DISTANCES_BASE[ds] as usize
                        + self.bits(DISTANCES_EXTRA[ds] as u32)? as usize;
                    if distance == 0 || distance > sortie.len() {
                        return Err(
                            "distance de retour hors de la fenetre deja produite".into()
                        );
                    }
                    if sortie.len() + longueur > borne {
                        return Err(format!(
                            "sortie decompressee au-dela de la borne de {borne} octets : \
                             refuse, et NON tronquee"
                        ));
                    }
                    let depart = sortie.len() - distance;
                    for n in 0..longueur {
                        let o = sortie[depart + n];
                        sortie.push(o);
                    }
                }
                _ => return Err("symbole litteral/longueur inconnu".into()),
            }
        }
    }
}
