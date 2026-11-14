//! Régressions de la consolidation : un test par défaut DÉMONTRÉ.
//!
//! CE QUI DISTINGUE CETTE SUITE DE `integration.rs`
//!
//! `integration.rs` éprouve les propriétés voulues du vérificateur.
//! Celle-ci épingle des défauts qui ONT EXISTÉ, chacun trouvé par une
//! mesure, chacun accompagné du reproducteur qui l'a trouvé. Un test ici
//! qui redevient vert sans raison annonce un retour en arrière.
//!
//! LE FORGEUR DE ZIP EST ÉCRIT ICI
//!
//! Les propriétés examinées sont précisément celles qu'aucune bibliothèque
//! n'accepte de produire : répertoire central mensonger, en-tête local
//! contradictoire, CRC faux, `nb_total` sous-déclaré. Il faut donc écrire
//! les octets à la main. Et cela garde la suite **sans Python**, comme le
//! reste.
//!
//! LES CONDENSÉS SONT DES VECTEURS PUBLIÉS
//!
//! `PROMPT` = `b"abc"`, dont le condensé est celui de FIPS 180-4 annexe
//! B.1. Aucun test ici ne fait confiance au module qu'il éprouve pour
//! savoir ce qu'il doit obtenir.

use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

const PROMPT: &[u8] = b"abc";
/// FIPS 180-4, annexe B.1.
const PROMPT_SHA: &str =
    "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad";

fn binaire() -> PathBuf {
    PathBuf::from(env!("CARGO_BIN_EXE_evidence-verify-rs"))
}

fn temporaire(nom: &str) -> PathBuf {
    let mut p = std::env::temp_dir();
    p.push(format!("evr-reg-{}-{}", nom, std::process::id()));
    let _ = fs::remove_dir_all(&p);
    fs::create_dir_all(&p).expect("dossier temporaire");
    p
}

fn manifeste(artefacts: &str) -> String {
    format!(
        r#"{{
  "schema": "neomundi.evidence.submission/2",
  "submission_id": "fixture-regression",
  "submitted_at_declared": "2026-11-11T12:00:00Z",
  "pilot": {{"name_declared": "fixture Rust"}},
  "execution": {{
    "kind_declared": "replay",
    "model_declared": null,
    "model_absence_reason_declared": "not_applicable",
    "model_absence_note_declared": "Fixture : aucun modele n intervient."
  }},
  "artifacts": [{artefacts}]
}}
"#
    )
}

fn manifeste_valide() -> String {
    manifeste(&format!(
        r#"{{"path": "artefacts/prompt.txt", "sha256": "{PROMPT_SHA}", "bytes": {}, "role": "prompt"}}"#,
        PROMPT.len()
    ))
}

struct Sortie {
    code: i32,
    stdout: String,
    stderr: String,
    rapport: Option<String>,
}

fn lancer(paquet: &Path) -> Sortie {
    let rapport = paquet.parent().unwrap().join(format!(
        "{}-r.json",
        paquet.file_name().unwrap().to_string_lossy()
    ));
    let _ = fs::remove_file(&rapport);
    let s = Command::new(binaire())
        .arg(paquet)
        .arg("--json")
        .arg(&rapport)
        .output()
        .expect("lancement");
    Sortie {
        code: s.status.code().unwrap_or(-1),
        stdout: String::from_utf8_lossy(&s.stdout).into_owned(),
        stderr: String::from_utf8_lossy(&s.stderr).into_owned(),
        rapport: fs::read_to_string(&rapport).ok(),
    }
}

// --------------------------------------------------------------------------
// Forgeur de ZIP : le minimum pour mentir sur ce qu'on veut
// --------------------------------------------------------------------------

/// CRC-32 de la norme ZIP. Écrit ici pour que le test ne dépende PAS de la
/// fonction du vérificateur : un test qui emprunterait son CRC au module
/// éprouvé ne prouverait que la cohérence du module avec lui-même.
fn crc32(d: &[u8]) -> u32 {
    let mut c = 0xFFFF_FFFFu32;
    for &o in d {
        c ^= o as u32;
        for _ in 0..8 {
            c = if c & 1 != 0 { 0xEDB8_8320 ^ (c >> 1) } else { c >> 1 };
        }
    }
    c ^ 0xFFFF_FFFF
}

struct Mensonge {
    /// `nb_total` écrit dans l'EOCD, si on veut qu'il mente.
    nb_total: Option<u16>,
    /// `taille_rc` écrite dans l'EOCD.
    taille_rc: Option<u32>,
    /// Le nom à écrire dans l'EN-TÊTE LOCAL, au lieu du vrai.
    nom_local: Option<(&'static str, &'static str)>,
    /// Fausser le CRC déclaré.
    crc_faux: bool,
    /// Octets glissés entre le répertoire central et l'EOCD.
    entre_rc_et_eocd: usize,
}

impl Default for Mensonge {
    fn default() -> Self {
        Mensonge {
            nb_total: None,
            taille_rc: None,
            nom_local: None,
            crc_faux: false,
            entre_rc_et_eocd: 0,
        }
    }
}

fn u16o(v: u16) -> [u8; 2] {
    v.to_le_bytes()
}
fn u32o(v: u32) -> [u8; 4] {
    v.to_le_bytes()
}

/// Forge un ZIP STOCKÉ (méthode 0) à partir de `membres`, en appliquant
/// `m`. Méthode 0 seulement : le mensonge porte sur la STRUCTURE, pas sur
/// la compression, et un bloc stocké garde le test lisible.
fn forger(membres: &[(&str, Vec<u8>)], m: &Mensonge) -> Vec<u8> {
    let mut o: Vec<u8> = Vec::new();
    let mut entrees: Vec<(String, u32, usize, usize)> = Vec::new();
    for (nom, donnees) in membres {
        let crc = if m.crc_faux {
            crc32(donnees) ^ 0xFFFF_FFFF
        } else {
            crc32(donnees)
        };
        let nom_ecrit = match m.nom_local {
            Some((cible, remplacant)) if cible == *nom => remplacant,
            _ => nom,
        };
        let decalage = o.len();
        o.extend_from_slice(&u32o(0x0403_4b50));
        o.extend_from_slice(&u16o(20));
        o.extend_from_slice(&u16o(0));
        o.extend_from_slice(&u16o(0)); // méthode 0
        o.extend_from_slice(&u16o(0));
        o.extend_from_slice(&u16o(0));
        o.extend_from_slice(&u32o(crc));
        o.extend_from_slice(&u32o(donnees.len() as u32));
        o.extend_from_slice(&u32o(donnees.len() as u32));
        o.extend_from_slice(&u16o(nom_ecrit.len() as u16));
        o.extend_from_slice(&u16o(0));
        o.extend_from_slice(nom_ecrit.as_bytes());
        o.extend_from_slice(donnees);
        entrees.push((nom.to_string(), crc, donnees.len(), decalage));
    }
    let depart_rc = o.len();
    let mut rc: Vec<u8> = Vec::new();
    for (nom, crc, n, decalage) in &entrees {
        rc.extend_from_slice(&u32o(0x0201_4b50));
        rc.extend_from_slice(&u16o(20));
        rc.extend_from_slice(&u16o(20));
        rc.extend_from_slice(&u16o(0));
        rc.extend_from_slice(&u16o(0));
        rc.extend_from_slice(&u16o(0));
        rc.extend_from_slice(&u16o(0));
        rc.extend_from_slice(&u32o(*crc));
        rc.extend_from_slice(&u32o(*n as u32));
        rc.extend_from_slice(&u32o(*n as u32));
        rc.extend_from_slice(&u16o(nom.len() as u16));
        rc.extend_from_slice(&u16o(0));
        rc.extend_from_slice(&u16o(0));
        rc.extend_from_slice(&u16o(0));
        rc.extend_from_slice(&u16o(0));
        rc.extend_from_slice(&u32o(0));
        rc.extend_from_slice(&u32o(*decalage as u32));
        rc.extend_from_slice(nom.as_bytes());
    }
    let taille_rc_vraie = rc.len();
    o.extend_from_slice(&rc);
    o.extend(std::iter::repeat_n(0u8, m.entre_rc_et_eocd));

    let n = m.nb_total.unwrap_or(entrees.len() as u16);
    let t = m.taille_rc.unwrap_or(taille_rc_vraie as u32);
    o.extend_from_slice(&u32o(0x0605_4b50));
    o.extend_from_slice(&u16o(0));
    o.extend_from_slice(&u16o(0));
    o.extend_from_slice(&u16o(n));
    o.extend_from_slice(&u16o(n));
    o.extend_from_slice(&u32o(t));
    o.extend_from_slice(&u32o(depart_rc as u32));
    o.extend_from_slice(&u16o(0));
    o
}

fn membres_valides() -> Vec<(&'static str, Vec<u8>)> {
    vec![
        ("submission.json", manifeste_valide().into_bytes()),
        ("artefacts/prompt.txt", PROMPT.to_vec()),
    ]
}

fn zip_forge(nom: &str, membres: &[(&str, Vec<u8>)], m: &Mensonge) -> PathBuf {
    let d = temporaire(nom);
    let f = d.join("paquet.zip");
    fs::write(&f, forger(membres, m)).unwrap();
    f
}

// --------------------------------------------------------------------------
// Témoin : le forgeur produit bien une archive acceptable
// --------------------------------------------------------------------------

#[test]
fn temoin_le_forgeur_produit_une_archive_acceptee() {
    // Sans ce témoin, tous les tests suivants pourraient passer parce que
    // le forgeur est cassé, et non parce que le contrôle fonctionne.
    let f = zip_forge("temoin", &membres_valides(), &Mensonge::default());
    let s = lancer(&f);
    assert_eq!(s.code, 0, "stdout:\n{}\nstderr:\n{}", s.stdout, s.stderr);
    assert!(s.stdout.contains("VERDICT : ACCEPTE"), "{}", s.stdout);
}

// --------------------------------------------------------------------------
// Z-1 — le CRC-32 est vérifié
// --------------------------------------------------------------------------

#[test]
fn crc32_faux_est_refuse() {
    // DÉFAUT CORRIGÉ : le CRC n'était pas lu. Le vérificateur rendait
    // `ACCEPTE` sur une archive que `unzip` et `zipfile` refusent tous
    // deux -- la définition même d'une garantie trompeuse.
    let f = zip_forge(
        "crc",
        &membres_valides(),
        &Mensonge { crc_faux: true, ..Default::default() },
    );
    let s = lancer(&f);
    assert_eq!(s.code, 1, "stdout:\n{}", s.stdout);
    assert!(s.stdout.contains("VERDICT : REJETE"), "{}", s.stdout);
    assert!(
        s.stdout.contains("CRC-32"),
        "le refus doit NOMMER le CRC, sinon un auditeur cherche ailleurs :\n{}",
        s.stdout
    );
}

#[test]
fn crc32_suit_les_vecteurs_publies() {
    // Trois valeurs publiées, recalculées par le CRC écrit DANS CE TEST.
    // Elles valident le forgeur ; le CRC du vérificateur est validé par le
    // test précédent, qui compare les deux implémentations indirectement.
    assert_eq!(crc32(b""), 0x0000_0000);
    assert_eq!(crc32(b"a"), 0xE8B7_BE43);
    assert_eq!(crc32(b"123456789"), 0xCBF4_3926);
    assert_eq!(crc32(b"The quick brown fox jumps over the lazy dog"), 0x414F_A339);
}

// --------------------------------------------------------------------------
// Z-2 — le nom de l'en-tête local doit être celui du répertoire central
// --------------------------------------------------------------------------

#[test]
fn nom_local_divergent_est_refuse() {
    // DÉFAUT CORRIGÉ : l'en-tête local n'était pas lu. Le répertoire
    // central pouvait annoncer `submission.json` là où l'en-tête local
    // nommait autre chose : deux lecteurs en tiraient des octets
    // différents sous le même nom. `zipfile` compare, ce module non.
    let f = zip_forge(
        "nom-local",
        &membres_valides(),
        &Mensonge {
            nom_local: Some(("submission.json", "autre.json")),
            ..Default::default()
        },
    );
    let s = lancer(&f);
    assert_eq!(s.code, 1, "stdout:\n{}", s.stdout);
    assert!(
        s.stdout.contains("en-tete local") || s.stdout.contains("autre.json"),
        "le refus doit nommer la contradiction :\n{}",
        s.stdout
    );
}

// --------------------------------------------------------------------------
// Z-3 — le répertoire central doit être consommé EXACTEMENT
// --------------------------------------------------------------------------

#[test]
fn nb_total_sous_declare_ne_cache_plus_un_fichier() {
    // LE DÉFAUT LE PLUS GRAVE DE LA CAMPAGNE.
    //
    // Mesuré : une archive portant un fichier NON DÉCLARÉ, avec `nb_total`
    // diminué d'une unité, était ACCEPTÉE et le fichier n'apparaissait PAS
    // au rapport -- alors que Python le signalait. Le contrôle « fichiers
    // non déclarés » se contournait donc en changeant deux octets de
    // l'EOCD.
    let mut membres = membres_valides();
    membres.push(("artefacts/clandestin.bin", b"octets non declares".to_vec()));
    let n = membres.len() as u16;

    // D'abord : sans mensonge, le fichier clandestin EST signalé.
    let honnete = zip_forge("clandestin-vu", &membres, &Mensonge::default());
    let s = lancer(&honnete);
    assert_eq!(s.code, 0, "{}", s.stdout);
    assert!(
        s.stdout.contains("clandestin.bin"),
        "un fichier non declare doit etre NOMME :\n{}",
        s.stdout
    );

    // Puis : avec `nb_total` amputé, l'archive est REFUSÉE, et non
    // acceptée avec un rapport incomplet.
    let menteur = zip_forge(
        "clandestin-cache",
        &membres,
        &Mensonge { nb_total: Some(n - 1), ..Default::default() },
    );
    let s = lancer(&menteur);
    assert_eq!(
        s.code, 1,
        "une archive dont l EOCD mente doit etre refusee, non acceptee avec \
         un fichier invisible :\n{}",
        s.stdout
    );
    assert!(s.stdout.contains("VERDICT : REJETE"), "{}", s.stdout);
}

#[test]
fn nb_total_sur_declare_est_refuse() {
    let membres = membres_valides();
    let n = membres.len() as u16;
    let f = zip_forge(
        "nb-sur",
        &membres,
        &Mensonge { nb_total: Some(n + 2), ..Default::default() },
    );
    assert_eq!(lancer(&f).code, 1);
}

#[test]
fn taille_du_repertoire_central_sous_declaree_est_refusee() {
    // DÉFAUT CORRIGÉ : la boucle ne se bornait qu'à la taille du FICHIER.
    // Une archive sous-déclarant `taille_rc` était lue AU-DELÀ de sa zone
    // et acceptée, là où `zipfile` la refuse.
    let f = zip_forge(
        "taille-rc",
        &membres_valides(),
        &Mensonge { taille_rc: Some(46), ..Default::default() },
    );
    assert_eq!(lancer(&f).code, 1);
}

#[test]
fn octets_entre_le_repertoire_central_et_l_eocd_sont_refuses() {
    // Aucune partie du format ne les décrit. Mesuré : Python refusait, ce
    // module acceptait. Une archive qu'un lecteur accepte et l'autre
    // refuse est ambiguë, et l'ambiguïté est ce qu'on écarte.
    let f = zip_forge(
        "entre-deux",
        &membres_valides(),
        &Mensonge { entre_rc_et_eocd: 22, ..Default::default() },
    );
    assert_eq!(lancer(&f).code, 1);
}

#[test]
fn marqueur_zip64_est_refuse_par_son_nom() {
    // Avant : refus quand même, mais pour une raison FAUSSE (« entree de
    // repertoire central malformee »), ce qui envoie un auditeur chercher
    // une corruption là où il n'y a qu'un format non pris en charge.
    let f = zip_forge(
        "zip64",
        &membres_valides(),
        &Mensonge { nb_total: Some(0xFFFF), ..Default::default() },
    );
    let s = lancer(&f);
    assert_eq!(s.code, 1);
    assert!(
        s.stdout.contains("ZIP64"),
        "le refus doit nommer ZIP64 :\n{}",
        s.stdout
    );
}

// --------------------------------------------------------------------------
// R-1 / R-2 — les bornes de taille sont lues AVANT la lecture
// --------------------------------------------------------------------------

#[test]
fn fichier_de_paquet_trop_gros_est_refuse_sans_etre_lu() {
    // DÉFAUT CORRIGÉ : `std::fs::read` chargeait le fichier ENTIER avant
    // toute borne. Mesuré : la mémoire de pointe suivait la taille du
    // fichier à l'unité près (256 Mio -> 264 Mio), et un fichier de
    // plusieurs gigaoctets faisait échouer l'allocation -- donc sortir en
    // 134, hors du contrat {0, 1, 2, 3}.
    //
    // Le test ne fabrique PAS 320 Mio : il vérifie que la borne existe et
    // qu'elle est annoncée. Le dépassement réel est mesuré par
    // `banc/securite.sh`, qui dispose du disque pour le faire.
    let d = temporaire("borne-paquet");
    let f = d.join("paquet.zip");
    // Un fichier creux de 400 Mio : `set_len` n'écrit pas 400 Mio sur le
    // disque, et c'est la TAILLE DÉCLARÉE que le contrôle lit.
    let fichier = fs::File::create(&f).unwrap();
    if fichier.set_len(400 * 1024 * 1024).is_err() {
        eprintln!("systeme de fichiers sans fichier creux : cas ignore");
        return;
    }
    drop(fichier);
    let s = lancer(&f);
    assert_eq!(s.code, 1, "stdout:\n{}\nstderr:\n{}", s.stdout, s.stderr);
    assert!(
        s.stdout.contains("AVANT lecture"),
        "le refus doit dire qu il precede la lecture :\n{}",
        s.stdout
    );
}

#[test]
fn fichier_trop_gros_dans_un_dossier_est_refuse_sans_etre_lu() {
    let d = temporaire("borne-dossier");
    fs::create_dir_all(d.join("artefacts")).unwrap();
    let f = fs::File::create(d.join("artefacts/gros.bin")).unwrap();
    if f.set_len(100 * 1024 * 1024).is_err() {
        eprintln!("systeme de fichiers sans fichier creux : cas ignore");
        return;
    }
    drop(f);
    let a = format!(
        r#"{{"path": "artefacts/gros.bin", "sha256": "{}", "bytes": 104857600, "role": "other"}}"#,
        "0".repeat(64)
    );
    fs::write(d.join("submission.json"), manifeste(&a)).unwrap();
    let s = lancer(&d);
    assert_eq!(s.code, 1, "{}", s.stdout);
    let r = s.rapport.expect("rapport");
    assert!(
        r.contains("refuse AVANT lecture"),
        "la raison doit figurer dans le rapport machine :\n{r}"
    );
}

// --------------------------------------------------------------------------
// J-1 — la largeur du document JSON est bornée
// --------------------------------------------------------------------------

#[test]
fn largeur_du_document_json_est_bornee() {
    // DÉFAUT CORRIGÉ : la PROFONDEUR était bornée, la LARGEUR non. Mesuré :
    // 22 Mo de feuilles numériques faisaient culminer la mémoire à
    // 711 Mio, soit une amplification d'un facteur ~33. Après la borne de
    // nœuds, la même entrée culmine à 86 Mio.
    let d = temporaire("largeur");
    let mut doc = String::from(r#"{"schema":"neomundi.evidence.submission/2","x":["#);
    // 1 000 001 feuilles : une de plus que la borne.
    doc.reserve(2_200_000);
    for k in 0..1_000_001 {
        if k > 0 {
            doc.push(',');
        }
        doc.push('1');
    }
    doc.push_str("]}");
    fs::write(d.join("submission.json"), &doc).unwrap();
    let s = lancer(&d);
    assert_eq!(s.code, 1, "{}", s.stdout);
    assert!(
        s.stdout.contains("valeurs dans le document"),
        "le refus doit nommer la borne de valeurs :\n{}",
        s.stdout
    );
}

#[test]
fn un_manifeste_large_mais_sous_la_borne_reste_lisible() {
    // L'autre moitié du contrôle : la borne ne doit pas refuser un
    // document légitime. 100 000 feuilles, soit un dixième de la borne.
    let d = temporaire("largeur-ok");
    let mut doc = String::from(r#"{"schema":"neomundi.evidence.submission/2","x":["#);
    for k in 0..100_000 {
        if k > 0 {
            doc.push(',');
        }
        doc.push('1');
    }
    doc.push_str("]}");
    fs::write(d.join("submission.json"), &doc).unwrap();
    let s = lancer(&d);
    // Refusé pour ses CHAMPS manquants, pas pour sa largeur.
    assert_eq!(s.code, 1);
    assert!(
        !s.stdout.contains("valeurs dans le document"),
        "la borne ne doit pas se declencher ici :\n{}",
        s.stdout
    );
    assert!(
        s.stdout.contains("champs obligatoires"),
        "le refus doit porter sur le contrat, non sur la taille :\n{}",
        s.stdout
    );
}

// --------------------------------------------------------------------------
// AMBIGUÏTÉ-4 — la portée du refus des clefs en double
// --------------------------------------------------------------------------

#[test]
fn clef_en_double_est_refusee_sur_toute_sa_portee() {
    // La divergence déclarée avec Python n'était éprouvée que sur UN cas.
    // Elle est ici éprouvée sur les quatre formes qui comptent, parce que
    // la décision normative proposée porte sur les quatre :
    //
    //   - `sha256` : DEUX empreintes pour un artefact ;
    //   - `schema` : DEUX versions de contrat ;
    //   - valeurs IDENTIQUES : le doublon reste une ambiguïté d'écriture ;
    //   - objet IMBRIQUÉ : le contrôle n'est pas réservé à la racine.
    let cas: [(&str, &str); 4] = [
        (
            "double-sha256",
            r#"{"schema":"neomundi.evidence.submission/2","artifacts":[{"sha256":"aa","sha256":"bb"}]}"#,
        ),
        (
            "double-schema",
            r#"{"schema":"neomundi.evidence.submission/99","schema":"neomundi.evidence.submission/2"}"#,
        ),
        (
            "double-identique",
            r#"{"schema":"neomundi.evidence.submission/2","submission_id":"x","submission_id":"x"}"#,
        ),
        (
            "double-imbriquee",
            r#"{"schema":"neomundi.evidence.submission/2","pilot":{"name_declared":"a","name_declared":"b"}}"#,
        ),
    ];
    for (nom, doc) in cas {
        let d = temporaire(nom);
        fs::write(d.join("submission.json"), doc).unwrap();
        let s = lancer(&d);
        assert_eq!(s.code, 1, "{nom} doit etre refuse :\n{}", s.stdout);
        assert!(
            s.stdout.contains("DOUBLE"),
            "{nom} : le refus doit NOMMER le doublon, pour qu on voie que \
             c est une politique et non un accident :\n{}",
            s.stdout
        );
    }
}

#[test]
fn la_grammaire_elargie_de_python_est_refusee() {
    // SECONDE FAMILLE, trouvée pendant cette consolidation et qui n'était
    // déclarée nulle part : `json` de Python accepte `NaN`, `Infinity` et
    // `-Infinity`, que la RFC 8259 ne définit pas. Mesuré : un manifeste
    // portant `NaN` dans un champ hors contrat est ACCEPTÉ par Python et
    // refusé ici. C'est la même ambiguïté que les clefs en double, et elle
    // est désormais éprouvée au lieu d'être supposée.
    for (nom, doc) in [
        ("nan", r#"{"schema":"neomundi.evidence.submission/2","x":NaN}"#),
        ("inf", r#"{"schema":"neomundi.evidence.submission/2","x":Infinity}"#),
        ("inf-neg", r#"{"schema":"neomundi.evidence.submission/2","x":-Infinity}"#),
    ] {
        let d = temporaire(&format!("grammaire-{nom}"));
        fs::write(d.join("submission.json"), doc).unwrap();
        assert_eq!(lancer(&d).code, 1, "{nom} doit etre refuse");
    }
}

#[test]
fn demi_paire_de_substitution_est_refusee_avec_un_rapport() {
    // Python, lui, ACCEPTE `\ud800` dans une chaîne, imprime
    // « VERDICT : ACCEPTE », puis échoue en écrivant son rapport
    // (`UnicodeEncodeError`) et sort en 1. Un lecteur humain lit donc
    // « accepté » et un script lit « rejeté ». Ce test épingle que le
    // vérificateur Rust, lui, rend UN verdict et UN rapport.
    let d = temporaire("surrogate");
    fs::write(
        d.join("submission.json"),
        r#"{"schema":"neomundi.evidence.submission/2","pilot":{"name_declared":"\ud800"}}"#,
    )
    .unwrap();
    let s = lancer(&d);
    assert_eq!(s.code, 1, "{}", s.stdout);
    assert!(s.stdout.contains("VERDICT : REJETE"), "{}", s.stdout);
    assert!(
        s.rapport.is_some(),
        "un refus doit TOUJOURS laisser un rapport machine"
    );
}

// --------------------------------------------------------------------------
// Aucun code hors contrat sur donnée non fiable
// --------------------------------------------------------------------------

#[test]
fn aucune_entree_adversariale_ne_sort_du_contrat_de_code() {
    // Le contrat de sortie est {0, 1, 2, 3}. Un 101 ou un 134 serait une
    // panique ou un abandon, et un script qui lit le code conclurait
    // n'importe quoi. Ce test parcourt les formes d'entrée les plus
    // hostiles que la campagne a produites.
    let entrees: Vec<(&str, Vec<u8>)> = vec![
        ("vide", vec![]),
        ("un-octet", vec![0x50]),
        ("eocd-seul", {
            let mut v = vec![0x50, 0x4b, 0x05, 0x06];
            v.extend_from_slice(&[0u8; 18]);
            v
        }),
        ("nuls", vec![0u8; 1024]),
        ("ff", vec![0xFFu8; 1024]),
        ("zip-tronque", {
            let z = forger(&membres_valides(), &Mensonge::default());
            z[..z.len() / 2].to_vec()
        }),
        ("eocd-decalage-enorme", {
            let mut z = forger(&membres_valides(), &Mensonge::default());
            let n = z.len();
            z[n - 6..n - 2].copy_from_slice(&u32o(0xFFFF_FFFE));
            z
        }),
        ("eocd-taille-enorme", {
            let mut z = forger(&membres_valides(), &Mensonge::default());
            let n = z.len();
            z[n - 10..n - 6].copy_from_slice(&u32o(0xFFFF_FFFE));
            z
        }),
    ];
    let d = temporaire("codes");
    for (nom, octets) in entrees {
        let f = d.join(format!("{nom}.zip"));
        fs::write(&f, &octets).unwrap();
        let s = lancer(&f);
        assert!(
            (0..=3).contains(&s.code),
            "{nom} : code {} hors du contrat {{0,1,2,3}}\nstderr:\n{}",
            s.code,
            s.stderr
        );
    }
}
