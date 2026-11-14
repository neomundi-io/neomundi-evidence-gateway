//! SHA-256, d'après FIPS 180-4. Écrit ici, et non emprunté.
//!
//! POURQUOI L'ÉCRIRE
//!
//! Un second vérificateur indépendant qui emprunterait sa primitive de
//! condensation à une caisse tierce déplacerait la confiance vers un tiers
//! que l'auditeur n'a pas choisi. SHA-256 tient en une page, sa
//! spécification est publique et figée depuis 2001, et ses vecteurs d'essai
//! sont publiés. Il n'y a aucune raison de l'importer.
//!
//! CE QUI L'ÉPROUVE
//!
//! Les vecteurs de FIPS 180-4 et du NIST CAVP, dans `tests/sha256.rs` :
//! chaîne vide, « abc », le bloc de 56 octets qui force un second bloc de
//! bourrage, le million de « a », et des entrées de 0 à 200 octets
//! comparées à une seconde voie de calcul.
//!
//! CE QU'IL N'EST PAS
//!
//! Il n'est pas protégé contre les attaques par canal auxiliaire, et il n'a
//! pas à l'être : il condense des fichiers publics, jamais un secret. Aucune
//! clé ne traverse ce module.

const K: [u32; 64] = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1,
    0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
    0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
    0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
    0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
    0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
    0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
];

const H0: [u32; 8] = [
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c,
    0x1f83d9ab, 0x5be0cd19,
];

/// État de condensation. Alimenté par morceaux : un artefact de 64 Mio ne
/// doit jamais être tenu entier en mémoire pour être condensé.
pub struct Sha256 {
    h: [u32; 8],
    tampon: [u8; 64],
    rempli: usize,
    /// Longueur TOTALE en octets. Le bourrage de FIPS 180-4 s'engage sur
    /// elle en bits, sur 64 bits big-endian.
    octets: u64,
}

impl Default for Sha256 {
    fn default() -> Self {
        Self::new()
    }
}

impl Sha256 {
    pub fn new() -> Self {
        Sha256 { h: H0, tampon: [0u8; 64], rempli: 0, octets: 0 }
    }

    pub fn alimenter(&mut self, mut entree: &[u8]) {
        self.octets = self.octets.wrapping_add(entree.len() as u64);
        // Compléter d'abord le tampon partiel, s'il y en a un.
        if self.rempli > 0 {
            let manque = 64 - self.rempli;
            let pris = manque.min(entree.len());
            self.tampon[self.rempli..self.rempli + pris]
                .copy_from_slice(&entree[..pris]);
            self.rempli += pris;
            entree = &entree[pris..];
            if self.rempli == 64 {
                let bloc = self.tampon;
                self.comprimer(&bloc);
                self.rempli = 0;
            }
        }
        // Puis les blocs pleins, sans recopie.
        while entree.len() >= 64 {
            let (bloc, reste) = entree.split_at(64);
            let mut fixe = [0u8; 64];
            fixe.copy_from_slice(bloc);
            self.comprimer(&fixe);
            entree = reste;
        }
        // Le résidu attend le prochain appel.
        if !entree.is_empty() {
            self.tampon[..entree.len()].copy_from_slice(entree);
            self.rempli = entree.len();
        }
    }

    fn comprimer(&mut self, bloc: &[u8; 64]) {
        let mut w = [0u32; 64];
        for i in 0..16 {
            w[i] = u32::from_be_bytes([
                bloc[4 * i], bloc[4 * i + 1], bloc[4 * i + 2], bloc[4 * i + 3],
            ]);
        }
        for i in 16..64 {
            let s0 = w[i - 15].rotate_right(7)
                ^ w[i - 15].rotate_right(18)
                ^ (w[i - 15] >> 3);
            let s1 = w[i - 2].rotate_right(17)
                ^ w[i - 2].rotate_right(19)
                ^ (w[i - 2] >> 10);
            w[i] = w[i - 16]
                .wrapping_add(s0)
                .wrapping_add(w[i - 7])
                .wrapping_add(s1);
        }
        let [mut a, mut b, mut c, mut d, mut e, mut f, mut g, mut h] = self.h;
        for i in 0..64 {
            let s1 = e.rotate_right(6) ^ e.rotate_right(11) ^ e.rotate_right(25);
            let ch = (e & f) ^ ((!e) & g);
            let t1 = h
                .wrapping_add(s1)
                .wrapping_add(ch)
                .wrapping_add(K[i])
                .wrapping_add(w[i]);
            let s0 = a.rotate_right(2) ^ a.rotate_right(13) ^ a.rotate_right(22);
            let maj = (a & b) ^ (a & c) ^ (b & c);
            let t2 = s0.wrapping_add(maj);
            h = g;
            g = f;
            f = e;
            e = d.wrapping_add(t1);
            d = c;
            c = b;
            b = a;
            a = t1.wrapping_add(t2);
        }
        let ajout = [a, b, c, d, e, f, g, h];
        for i in 0..8 {
            self.h[i] = self.h[i].wrapping_add(ajout[i]);
        }
    }

    /// Clôt la condensation et rend les 32 octets du condensé.
    ///
    /// Le bourrage est posé DIRECTEMENT dans le tampon, sans repasser par
    /// `alimenter` : celui-ci incrémente le compteur d'octets, et la
    /// longueur en bits sur laquelle FIPS 180-4 s'engage est celle du
    /// message, pas celle du message plus son bourrage.
    pub fn terminer(mut self) -> [u8; 32] {
        let bits = self.octets.wrapping_mul(8);
        let n = self.rempli;
        self.tampon[n] = 0x80;
        for o in self.tampon.iter_mut().skip(n + 1) {
            *o = 0;
        }
        // Si la longueur ne tient plus dans ce bloc -- il faut 8 octets, et
        // 0x80 en occupe un -- le bloc part tel quel et la longueur va dans
        // un SECOND bloc, entièrement de bourrage. C'est précisément ce que
        // le vecteur de 56 octets éprouve.
        if n + 1 > 56 {
            let bloc = self.tampon;
            self.comprimer(&bloc);
            self.tampon = [0u8; 64];
        }
        self.tampon[56..64].copy_from_slice(&bits.to_be_bytes());
        let bloc = self.tampon;
        self.comprimer(&bloc);

        let mut sortie = [0u8; 32];
        for i in 0..8 {
            sortie[4 * i..4 * i + 4].copy_from_slice(&self.h[i].to_be_bytes());
        }
        sortie
    }
}

/// Le condensé d'une tranche, en hexadécimal minuscule -- la seule forme
/// que le contrat publie (`^[0-9a-f]{64}$`).
// Commodite d'un seul coup, utilisee par les essais seulement.
//
// RECTIFICATION. Ce commentaire affirmait que « le verificateur, lui,
// alimente par morceaux pour ne jamais charger un artefact entier en
// memoire ». C'est FAUX : `verifier.rs` lit chaque fichier en entier
// (`lire()` rend un `Vec<u8>`) puis l'alimente d'un coup. L'alimentation
// par morceaux existe et elle est eprouvee, mais le chemin de production
// ne l'emprunte pas. La memoire est bornee par `FICHIER_OCTETS_MAX` et par
// les bornes du module ZIP, non par un flux.
#[cfg_attr(not(test), allow(dead_code))]
pub fn hex(entree: &[u8]) -> String {
    let mut c = Sha256::new();
    c.alimenter(entree);
    en_hex(&c.terminer())
}

pub fn en_hex(condense: &[u8; 32]) -> String {
    const CHIFFRES: &[u8; 16] = b"0123456789abcdef";
    let mut s = String::with_capacity(64);
    for o in condense {
        s.push(CHIFFRES[(o >> 4) as usize] as char);
        s.push(CHIFFRES[(o & 0x0f) as usize] as char);
    }
    s
}
