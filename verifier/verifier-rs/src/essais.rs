//! Tests unitaires des primitives écrites ici : SHA-256, JSON, DEFLATE,
//! chemins, et les règles de forme du contrat.
//!
//! POURQUOI ILS SONT DANS LA CAISSE
//!
//! Ces tests éprouvent des fonctions privées et des invariants internes.
//! Les mettre dans `tests/` imposerait de rendre publique une surface qui
//! n'a pas à l'être. Les tests d'intégration — paquets complets, verdicts,
//! comparaison avec Python — sont ailleurs : `tests/integration.rs` et le
//! banc comparatif.
//!
//! LES VECTEURS
//!
//! Ceux de SHA-256 viennent de FIPS 180-4 (annexes B.1 et B.3) et du NIST
//! CAVP. Ils sont recopiés ici en clair : un vecteur qu'on ne peut pas lire
//! dans le fichier de test ne prouve rien à un auditeur.

#![cfg(test)]

use crate::chemins;
use crate::contrat as c;
use crate::inflate;
use crate::json::{self, Valeur};
use crate::sha256::{self, Sha256};

// ======================================================================
// SHA-256 -- vecteurs publiés
// ======================================================================

#[test]
fn sha256_chaine_vide() {
    // FIPS 180-4 : le condensé de la chaîne vide.
    assert_eq!(
        sha256::hex(b""),
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    );
}

#[test]
fn sha256_abc() {
    // FIPS 180-4, annexe B.1.
    assert_eq!(
        sha256::hex(b"abc"),
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    );
}

#[test]
fn sha256_448_bits() {
    // FIPS 180-4, annexe B.2 : 56 octets. C'est LE cas qui force un second
    // bloc de bourrage -- 56 + 1 > 56, donc la longueur ne tient plus.
    assert_eq!(
        sha256::hex(b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"),
        "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1"
    );
}

#[test]
fn sha256_exactement_un_bloc() {
    // 64 octets : le message remplit un bloc entier, et tout le bourrage
    // part dans un second.
    let m = [b'a'; 64];
    assert_eq!(
        sha256::hex(&m),
        "ffe054fe7ae0cb6dc65c3af9b61d5209f439851db43d0ba5997337df154668eb"
    );
}

#[test]
fn sha256_frontieres_de_bourrage() {
    // Les longueurs 55, 56, 57, 63, 64, 65 encadrent les deux frontières
    // du bourrage. Condensés obtenus par la spécification, et stables.
    let attendus: [(usize, &str); 3] = [
        (55, "9f4390f8d30c2dd92ec9f095b65e2b9ae9b0a925a5258e241c9f1e910f734318"),
        (56, "b35439a4ac6f0948b6d6f9e3c6af0f5f590ce20f1bde7090ef7970686ec6738a"),
        (57, "f13b2d724659eb3bf47f2dd6af1accc87b81f09f59f2b75e5c0bed6589dfe8c6"),
    ];
    for (n, attendu) in attendus {
        let m = vec![b'a'; n];
        assert_eq!(sha256::hex(&m), attendu, "longueur {n}");
    }
}

#[test]
fn sha256_million_de_a() {
    // FIPS 180-4, annexe B.3. Alimenté par morceaux de 1000 octets : c'est
    // aussi ce qui éprouve la reprise du tampon partiel.
    let mut h = Sha256::new();
    let bloc = [b'a'; 1000];
    for _ in 0..1000 {
        h.alimenter(&bloc);
    }
    assert_eq!(
        sha256::en_hex(&h.terminer()),
        "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0"
    );
}

#[test]
fn sha256_alimentation_par_morceaux_equivaut_a_un_coup() {
    // La propriété qui compte pour un fichier de 64 Mio : la découpe ne
    // change pas le condensé, quelle que soit la taille des morceaux.
    let message: Vec<u8> = (0..=255u8).cycle().take(1000).collect();
    let un_coup = sha256::hex(&message);
    for taille in [1usize, 3, 7, 63, 64, 65, 127, 128, 999] {
        let mut h = Sha256::new();
        for bout in message.chunks(taille) {
            h.alimenter(bout);
        }
        assert_eq!(
            sha256::en_hex(&h.terminer()),
            un_coup,
            "morceaux de {taille} octets"
        );
    }
}

// ======================================================================
// JSON -- les politiques, éprouvées
// ======================================================================

#[test]
fn json_clef_en_double_est_refusee() {
    // LA politique qui diverge de Python, et la raison d'écrire cet
    // analyseur. `json` de Python garde la dernière, en silence.
    let e = json::analyser(br#"{"a": 1, "a": 2}"#).unwrap_err();
    assert!(e.message.contains("DOUBLE"), "{}", e.message);
}

#[test]
fn json_nombres_conserves_verbatim() {
    let v = json::analyser(br#"{"a": 1000, "b": 1e3, "c": 1000.0}"#).unwrap();
    let o = v.comme_objet().unwrap();
    assert_eq!(o["a"], Valeur::Nombre("1000".into()));
    assert_eq!(o["b"], Valeur::Nombre("1e3".into()));
    assert_eq!(o["c"], Valeur::Nombre("1000.0".into()));
    // Et seule la forme ENTIÈRE est un entier : `type: integer` du contrat
    // ne dit pas « une valeur entière ».
    assert_eq!(o["a"].comme_entier(), Some(1000));
    assert_eq!(o["b"].comme_entier(), None);
    assert_eq!(o["c"].comme_entier(), None);
}

#[test]
fn json_grand_entier_ne_perd_pas_de_precision() {
    // 2^53 + 1 : un `f64` l'arrondirait, et la taille déclarée serait
    // fausse sans que personne ne le voie.
    let v = json::analyser(br#"{"bytes": 9007199254740993}"#).unwrap();
    assert_eq!(
        v.comme_objet().unwrap()["bytes"].comme_entier(),
        Some(9007199254740993)
    );
}

#[test]
fn json_refus_de_la_grammaire_elargie() {
    for (entree, quoi) in [
        (&br#"{"a": 1,}"#[..], "virgule trainante en objet"),
        (&br#"[1, 2,]"#[..], "virgule trainante en tableau"),
        (&br#"{"a": 01}"#[..], "zero de tete"),
        (&br#"{"a": NaN}"#[..], "NaN"),
        (&br#"{"a": Infinity}"#[..], "Infinity"),
        (&br#"{"a": .5}"#[..], "point sans partie entiere"),
        (&br#"{"a": 1.}"#[..], "point sans decimale"),
        (&br#"{"a": 0x10}"#[..], "hexadecimal"),
        (&br#"{"a": 1} // note"#[..], "commentaire"),
        (&br#"{'a': 1}"#[..], "guillemets simples"),
        (&br#"{"a": 1}{"b": 2}"#[..], "deux documents"),
        (&br#""#[..], "document vide"),
    ] {
        assert!(
            json::analyser(entree).is_err(),
            "accepte a tort : {quoi}"
        );
    }
}

#[test]
fn json_utf8_strict_et_bom_tolere() {
    // Un BOM en tête est retiré POUR L'ANALYSE : un fichier valide ne doit
    // pas être refusé pour cette raison.
    assert!(json::analyser(b"\xEF\xBB\xBF{\"a\": 1}").is_ok());
    // Un octet invalide est un REFUS, jamais un U+FFFD : le document ne
    // serait plus celui qui a été transmis.
    assert!(json::analyser(b"{\"a\": \"\xFF\"}").is_err());
    // Une demi-paire de substitution seule est refusée.
    assert!(json::analyser(br#"{"a": "\ud800"}"#).is_err());
    assert!(json::analyser(br#"{"a": "\udc00"}"#).is_err());
    // Une paire complète est assemblée.
    let v = json::analyser(br#"{"a": "\ud83d\ude00"}"#).unwrap();
    assert_eq!(v.comme_objet().unwrap()["a"].comme_texte(), Some("😀"));
}

#[test]
fn json_controle_non_echappe_refuse() {
    // RFC 8259 §7 : U+0000..U+001F doivent être échappés.
    assert!(json::analyser(b"{\"a\": \"x\ny\"}").is_err());
    assert!(json::analyser(br#"{"a": "x\ny"}"#).is_ok());
}

#[test]
fn json_profondeur_bornee() {
    // Une récursion non bornée fait déborder la pile. La borne est lue
    // AVANT de descendre.
    let profond = format!("{}1{}", "[".repeat(5000), "]".repeat(5000));
    let e = json::analyser(profond.as_bytes()).unwrap_err();
    assert!(e.message.contains("profondeur"), "{}", e.message);
}

// ======================================================================
// DEFLATE
// ======================================================================

#[test]
fn inflate_bloc_stocke() {
    // Un bloc stocké : dernier=1, genre=00, alignement, LEN/NLEN, données.
    let mut f = vec![0x01, 0x03, 0x00, 0xFC, 0xFF];
    f.extend_from_slice(b"abc");
    assert_eq!(inflate::inflate(&f, 1024).unwrap(), b"abc");
}

#[test]
fn inflate_refuse_len_nlen_incoherents() {
    let f = vec![0x01, 0x03, 0x00, 0x00, 0x00, b'a', b'b', b'c'];
    assert!(inflate::inflate(&f, 1024).is_err());
}

#[test]
fn inflate_refuse_genre_reserve() {
    // Genre 3 est réservé par la RFC 1951.
    assert!(inflate::inflate(&[0x07], 1024).is_err());
}

#[test]
fn inflate_borne_de_sortie_refuse_sans_tronquer() {
    // 1000 octets stockés, borne à 10 : refus, et non troncature. Une
    // sortie tronquée aurait une autre empreinte, et la comparer serait
    // pire que de refuser.
    let mut f = vec![0x01, 0xE8, 0x03, 0x17, 0xFC];
    f.extend_from_slice(&[b'a'; 1000]);
    let e = inflate::inflate(&f, 10).unwrap_err();
    assert!(e.contains("borne") && e.contains("NON tronquee"), "{e}");
}

#[test]
fn inflate_refuse_flux_tronque() {
    assert!(inflate::inflate(&[0x01, 0x10, 0x00], 1024).is_err());
    assert!(inflate::inflate(&[], 1024).is_err());
}

#[test]
fn inflate_refuse_un_arbre_de_distance_incomplet() {
    // RÉGRESSION. `depuis_longueurs` ne testait que la sur-souscription.
    // Le commentaire annonçait « sur-souscrit **ou incomplet** » ; le code
    // ne faisait que la moitié. Une campagne de 50 000 flux mutés a trouvé
    // quatre flux que `zlib` refuse avec « invalid distances set » et que
    // ce module ACCEPTAIT, en produisant des octets qu'aucun décodeur
    // standard ne produit.
    //
    // Ces quatre flux sont conservés ici en clair. Ce sont les
    // reproducteurs, pas des cas inventés après coup.
    const TROUVES: [&str; 4] = [
        "edc13101000000c2a0f54f6d0a3fa4b6a4a3dba0",
        "edc13101000000c2a0f54f6d0a3fb00000000080b701",
        "edc13101000000c2a0f54f6d0a3fa40000000080b701",
        "edc13101000000c2a0f54f6d0a3f740000000080b701",
    ];
    for hex in TROUVES {
        let flux: Vec<u8> = (0..hex.len() / 2)
            .map(|k| u8::from_str_radix(&hex[k * 2..k * 2 + 2], 16).unwrap())
            .collect();
        let r = inflate::inflate(&flux, 1 << 20);
        let e = r.unwrap_err();
        assert!(
            e.contains("INCOMPLET"),
            "le flux {hex} doit etre refuse POUR son arbre incomplet,              et non par accident : {e}"
        );
    }
}

#[test]
fn inflate_tolere_l_arbre_a_un_seul_code_que_zlib_produit() {
    // L'AUTRE MOITIÉ DU CONTRÔLE, et la raison pour laquelle il n'est pas
    // un simple « refuse tout arbre incomplet ».
    //
    // `zlib` produit légitimement un arbre de distance à UN seul code --
    // voire aucun -- quand un bloc n'emploie qu'une distance de retour, ou
    // aucune. Refuser cela refuserait des archives parfaitement valides.
    // La règle suit donc celle de `inflate_table` de `zlib` : incomplet
    // admis pour les arbres littéral/longueur et distance s'ils portent au
    // plus UN code, refusé pour l'arbre des longueurs de code.
    //
    // Les deux flux ci-dessous sont produits par `zlib` niveau 9 sur des
    // entrées qui n'emploient qu'une distance. Si le contrôle de complétude
    // devenait trop strict, ce test rougirait AVANT qu'une archive réelle
    // ne soit refusée en production.
    //
    //   zlib.compressobj(9, zlib.DEFLATED, -15) sur b"a" * 300
    const UNE_SEULE_DISTANCE: &str = "4b4c1c05c40200";
    //   la meme chose sur b"ab" * 300
    const UNE_SEULE_DISTANCE_2: &str = "4b4c4a1c85a390ea1000";
    for (hex, attendu_len) in [(UNE_SEULE_DISTANCE, 300usize), (UNE_SEULE_DISTANCE_2, 600)] {
        let flux: Vec<u8> = (0..hex.len() / 2)
            .map(|k| u8::from_str_radix(&hex[k * 2..k * 2 + 2], 16).unwrap())
            .collect();
        let sortie = inflate::inflate(&flux, 1 << 20)
            .unwrap_or_else(|e| panic!("flux zlib legitime REFUSE : {e}"));
        assert_eq!(sortie.len(), attendu_len);
    }
}

#[test]
fn inflate_refuse_un_arbre_sur_souscrit() {
    // L'autre côté de la même porte, déjà couvert avant la consolidation
    // mais sans test nommé.
    //
    // Bloc dynamique dont l'arbre des longueurs de code déclare plus de
    // codes qu'un arbre de 3 bits n'en porte.
    let flux = [0x05u8, 0xC0, 0x81, 0x00, 0x00, 0x00, 0x00, 0x00, 0x90, 0xFF,
                0x6B, 0x01];
    assert!(inflate::inflate(&flux, 1 << 20).is_err());
}

// ======================================================================
// Bornes de largeur du JSON
// ======================================================================

#[test]
fn json_largeur_bornee() {
    // RÉGRESSION. La PROFONDEUR était bornée, la LARGEUR non : 22 Mo de
    // feuilles numériques faisaient culminer la mémoire à 711 Mio, soit
    // une amplification mesurée d'un facteur ~33.
    let sous = format!("[{}]", vec!["1"; 1000].join(","));
    assert!(json::analyser(sous.as_bytes()).is_ok());

    // Une valeur de plus que la borne, tableau compris.
    let trop = format!(
        "[{}]",
        vec!["1"; json::NOEUDS_MAX].join(",")
    );
    let e = json::analyser(trop.as_bytes()).unwrap_err();
    assert!(
        e.message.contains("valeurs dans le document"),
        "{}",
        e.message
    );
}

// ======================================================================
// Chemins
// ======================================================================

#[test]
fn chemins_les_quatre_refus_du_contrat() {
    for (mauvais, attendu) in [
        ("/etc/passwd", "ABSOLU"),
        ("../../etc/passwd", "`..`"),
        ("C:/x", "lecteur"),
        ("a\\b", "inversee"),
        ("", "absent"),
    ] {
        let e = chemins::chemin_sur(mauvais).unwrap_err();
        assert!(e.contains(attendu), "{mauvais} -> {e}");
    }
}

#[test]
fn chemins_admis() {
    for bon in [
        "submission.json",
        "artefacts/prompt.txt",
        "a/b/c/d.json",
        "a-b_c.1/x.txt",
    ] {
        assert!(chemins::chemin_sur(bon).is_ok(), "{bon}");
    }
}

#[test]
fn chemins_un_point_simple_est_admis_mais_pas_un_double() {
    // `.` n'est pas dans la liste des refus du contrat, et le motif
    // l'admet. C'est une bizarrerie du motif Python, reproduite à
    // l'identique pour que les deux vérificateurs concordent -- et
    // signalée comme telle dans la baseline.
    assert!(chemins::chemin_sur("a/./b").is_ok());
    assert!(chemins::chemin_sur("a/../b").is_err());
}

#[test]
fn chemins_longueur_bornee() {
    let long = format!("a{}", "b".repeat(512));
    assert!(chemins::chemin_sur(&long).is_err());
}

// ======================================================================
// Formes du contrat
// ======================================================================

#[test]
fn forme_sha256_minuscules_seulement() {
    assert!(c::sha256_bien_forme(&"a".repeat(64)));
    // MAJUSCULES refusées : le contrat publie `^[0-9a-f]{64}$`.
    assert!(!c::sha256_bien_forme(&"A".repeat(64)));
    assert!(!c::sha256_bien_forme(&"a".repeat(63)));
    assert!(!c::sha256_bien_forme(&"a".repeat(65)));
    assert!(!c::sha256_bien_forme("zz"));
}

#[test]
fn forme_instant_utc_a_la_seconde() {
    assert!(c::instant_bien_forme("2026-11-10T21:17:51Z"));
    for mauvais in [
        "yesterday",
        "2026-11-10",
        "2026-11-10T21:17:51",
        "2026-11-10T21:17:51+01:00",
        "2026-11-10T21:17:51.123Z",
        "2026-11-10t21:17:51z",
        " 2026-11-10T21:17:51Z",
        "",
    ] {
        assert!(!c::instant_bien_forme(mauvais), "{mauvais}");
    }
}

#[test]
fn forme_identifiant_de_soumission() {
    assert!(c::identifiant_bien_forme("ogs-neomundi-b3-v2-candidate-001"));
    assert!(c::identifiant_bien_forme("abc"));
    for mauvais in ["ab", "Abc", "a_b", "a b", "-ab", ""] {
        assert!(!c::identifiant_bien_forme(mauvais), "{mauvais}");
    }
}

#[test]
fn forme_non_blanc() {
    assert!(c::porte_un_non_blanc("x"));
    assert!(!c::porte_un_non_blanc(""));
    assert!(!c::porte_un_non_blanc("   "));
    assert!(!c::porte_un_non_blanc("\t\n "));
}

#[test]
fn champs_execution_selon_la_version() {
    assert_eq!(c::champs_execution(c::SCHEMA_V1).len(), 6);
    assert_eq!(c::champs_execution(c::SCHEMA_V2).len(), 8);
}
