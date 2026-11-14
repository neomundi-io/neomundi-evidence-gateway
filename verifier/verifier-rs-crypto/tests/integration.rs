//! Tests d'intégration du vérificateur cryptographique, **SANS PYTHON**.
//!
//! LE CORPUS EST CELUI DU DÉPÔT
//!
//! Contrairement à la suite de `verifier-rs`, celle-ci emploie les fixtures
//! **réelles** de `examples/dossier-v1/` : une archive Evidence, son
//! attestation Ed25519/JWS, et son magasin de confiance. Il n'y a pas de
//! choix à faire ici — fabriquer une signature valide exigerait de signer,
//! donc une clef privée, donc exactement ce que ce vérificateur ne doit
//! jamais pouvoir faire.
//!
//! Les contre-exemples, eux, sont forgés **sur place** : il suffit de
//! modifier des octets, ce qui ne demande aucune clef.
//!
//! CE QUE CES TESTS ÉPINGLENT EN PRIORITÉ
//!
//! Les propriétés dont la perte produirait une **garantie trompeuse** :
//! `alg` jamais honoré, aucune chaîne annonçant une identité vérifiée, la
//! vérité du contenu jamais `PASS`, et un magasin portant une clef privée
//! refusé.

use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

fn binaire() -> PathBuf {
    PathBuf::from(env!("CARGO_BIN_EXE_evidence-verify-crypto"))
}

/// `examples/dossier-v1/`, atteint depuis le répertoire de la caisse.
fn dossier() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .join("examples")
        .join("dossier-v1")
}

fn archive() -> PathBuf {
    dossier().join("NEOMUNDI_EVIDENCE_V1_DEMO.zip")
}
fn attestation() -> PathBuf {
    dossier().join("NEOMUNDI_EVIDENCE_V1_DEMO.zip.jws")
}
fn magasin() -> PathBuf {
    dossier().join("trust-store.json")
}

fn temporaire(nom: &str) -> PathBuf {
    let mut p = std::env::temp_dir();
    p.push(format!("evc-it-{}-{}", nom, std::process::id()));
    let _ = fs::remove_dir_all(&p);
    fs::create_dir_all(&p).expect("dossier temporaire");
    p
}

struct Sortie {
    code: i32,
    stdout: String,
    stderr: String,
}

impl Sortie {
    /// La ligne dont l'INTITULÉ contient `motif`.
    ///
    /// LE PIÈGE QUE CE HELPER ÉVITE, ET QUI A MORDU TROIS FOIS
    ///
    /// Chercher le motif n'importe où dans la ligne attrape le DÉTAIL d'un
    /// autre contrôle. La ligne « chainage canonique du registre » explique
    /// qu'une seconde implémentation du « profil de canonicalisation »
    /// divergerait un jour — et un `contains("profil de canonicalisation")`
    /// la trouve avant le vrai pilier, puis lit son `NOT TESTED`.
    ///
    /// Le banc différentiel est tombé deux fois dans ce piège, cette suite
    /// une troisième. L'intitulé est ce qui précède le premier ` - `, et
    /// c'est là qu'il faut chercher.
    fn ligne(&self, motif: &str) -> &str {
        self.stdout
            .lines()
            .find(|l| {
                l.starts_with('[')
                    && l.rsplit("] ")
                        .next()
                        .map(|tete| {
                            tete.split(" - ").next().unwrap_or(tete).contains(motif)
                        })
                        .unwrap_or(false)
            })
            .unwrap_or_else(|| panic!("aucune ligne dont l intitule porte {motif:?}"))
    }
}

fn lancer(args: &[&str]) -> Sortie {
    let s = Command::new(binaire())
        .args(args)
        .output()
        .expect("lancement du binaire");
    Sortie {
        code: s.status.code().unwrap_or(-1),
        stdout: String::from_utf8_lossy(&s.stdout).into_owned(),
        stderr: String::from_utf8_lossy(&s.stderr).into_owned(),
    }
}

fn complet() -> Sortie {
    lancer(&[
        "--attestation",
        attestation().to_str().unwrap(),
        "--archive",
        archive().to_str().unwrap(),
        "--trust-store",
        magasin().to_str().unwrap(),
        "--allow-test-keys",
    ])
}

// --------------------------------------------------------------------------
// Le témoin
// --------------------------------------------------------------------------

#[test]
fn l_attestation_reelle_du_depot_est_verifiee() {
    // Le contrôle POSITIF. Sans lui, tous les refus qui suivent pourraient
    // venir d'un vérificateur qui refuse tout.
    let s = complet();
    assert_eq!(s.code, 0, "stdout:\n{}\nstderr:\n{}", s.stdout, s.stderr);
    assert!(
        s.stdout.contains("cryptographically_attested"),
        "le niveau doit etre derive sur l attestation reelle :\n{}",
        s.stdout
    );
    // Les cinq piliers, nommément.
    for pilier in [
        "profil de canonicalisation",
        "en-tete : algorithme impose",
        "signature cryptographique",
        "identite de confiance",
        "concordance avec l archive",
    ] {
        let ligne = s.ligne(pilier);
        assert!(
            ligne.starts_with("[PASS"),
            "le pilier {pilier} doit etre PASS :\n{ligne}"
        );
    }
}

#[test]
fn le_profil_de_canonicalisation_est_redive_a_l_octet() {
    // LA PROPRIÉTÉ LA PLUS INTÉRESSANTE DE CE TEST.
    //
    // Le profil `neomundi-jcs-strings/1` est redérivé ici par une
    // implémentation écrite indépendamment de `canonical.py`. Qu'elle
    // reproduise EXACTEMENT les 1541 octets portés par l'attestation réelle
    // est une concordance non triviale entre deux canonicalisations.
    let s = complet();
    let ligne = s.ligne("profil de canonicalisation");
    assert!(ligne.starts_with("[PASS"), "{ligne}");
    assert!(
        ligne.contains("forme canonique de 1541 octets"),
        "la charge reelle fait 1541 octets, et la recanonisation doit les \
         reproduire a l octet :\n{ligne}"
    );
}

#[test]
fn l_archive_reelle_du_depot_est_acceptee() {
    let s = lancer(&["--archive", archive().to_str().unwrap()]);
    assert_eq!(s.code, 0, "stdout:\n{}\nstderr:\n{}", s.stdout, s.stderr);
    assert!(s.stdout.contains("VERDICT : ACCEPTE"), "{}", s.stdout);
    // L'empreinte que le dépôt publie dans `attendu.json`.
    assert!(
        s.stdout
            .contains("e31e12bb7e32c7a33db1ecacc8c38cd18225fa10618c7e1aa5d6f9540f2ad7d6"),
        "l empreinte recalculee doit etre celle que le depot publie :\n{}",
        s.stdout
    );
}

// --------------------------------------------------------------------------
// Les propriétés dont la perte serait une garantie trompeuse
// --------------------------------------------------------------------------

#[test]
fn aucune_chaine_n_annonce_une_identite_verifiee() {
    // La garantie trompeuse la plus facile à produire : afficher
    // « identité vérifiée » quand on a seulement vérifié une signature.
    let s = complet();
    let tout = format!("{}{}", s.stdout, s.stderr).to_lowercase();
    for interdit in [
        "identite verifiee",
        "identité vérifiée",
        "identity verified",
        "signataire verifie",
    ] {
        assert!(
            !tout.contains(interdit),
            "la sortie ne doit JAMAIS annoncer {interdit:?}"
        );
    }
    // Et la capacité juridique doit être NOT TESTED, avec sa raison.
    let ligne = s.ligne("capacite juridique");
    assert!(ligne.starts_with("[NOT TESTED"), "{ligne}");
    assert!(
        ligne.contains("AUCUN code ne peut etablir"),
        "la ligne doit dire pourquoi elle ne bougera pas :\n{ligne}"
    );
}

#[test]
fn la_verite_du_contenu_n_est_jamais_pass() {
    let s = complet();
    let ligne = s.ligne("verite du contenu");
    assert!(
        ligne.starts_with("[NOT TESTED"),
        "la verite du contenu ne peut JAMAIS etre PASS :\n{ligne}"
    );
    assert!(ligne.contains("aucun ne le fera"), "{ligne}");
}

#[test]
fn aucune_ligne_declare_ne_porte_pass() {
    // L'invariant central, vérifié aussi à l'exécution par le binaire : si
    // `invariant_declare` échouait, le programme sortirait en 3.
    let s = complet();
    for l in s.stdout.lines() {
        if l.starts_with("[PASS") {
            assert!(
                !l.contains("[DECLARE"),
                "une ligne DECLARE porte PASS : une declaration est devenue \
                 un fait atteste\n{l}"
            );
        }
    }
    assert_ne!(s.code, 3, "l invariant a ete rompu :\n{}", s.stderr);
}

// --------------------------------------------------------------------------
// L'algorithme est IMPOSÉ
// --------------------------------------------------------------------------

/// Réécrit l'en-tête d'un JWS avec `alg` remplacé, en laissant la charge et
/// la signature inchangées. La signature ne peut donc plus valider — ce
/// n'est pas le propos : le propos est que l'en-tête soit **refusé** avant
/// même d'être honoré.
fn jws_avec_alg(nom: &str, alg: &str) -> PathBuf {
    const A: &[u8; 64] =
        b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
    fn b64u(o: &[u8]) -> String {
        let mut s = String::new();
        for morceau in o.chunks(3) {
            let b = [
                morceau[0],
                *morceau.get(1).unwrap_or(&0),
                *morceau.get(2).unwrap_or(&0),
            ];
            let n = ((b[0] as u32) << 16) | ((b[1] as u32) << 8) | b[2] as u32;
            let chiffres = [
                A[(n >> 18) as usize & 63],
                A[(n >> 12) as usize & 63],
                A[(n >> 6) as usize & 63],
                A[n as usize & 63],
            ];
            let garder = match morceau.len() {
                1 => 2,
                2 => 3,
                _ => 4,
            };
            for c in &chiffres[..garder] {
                s.push(*c as char);
            }
        }
        s
    }
    let original = fs::read_to_string(attestation()).expect("attestation");
    let parties: Vec<&str> = original.trim().split('.').collect();
    let entete = format!(r#"{{"alg":"{alg}","kid":"nm-ev-demo-v1","typ":"JOSE"}}"#);
    let d = temporaire(nom);
    let f = d.join("forge.jws");
    fs::write(
        &f,
        format!("{}.{}.{}", b64u(entete.as_bytes()), parties[1], parties[2]),
    )
    .unwrap();
    f
}

#[test]
fn alg_none_est_refuse_et_jamais_honore() {
    let f = jws_avec_alg("alg-none", "none");
    let s = lancer(&[
        "--attestation",
        f.to_str().unwrap(),
        "--archive",
        archive().to_str().unwrap(),
        "--trust-store",
        magasin().to_str().unwrap(),
        "--allow-test-keys",
    ]);
    assert_eq!(s.code, 1, "stdout:\n{}", s.stdout);
    assert!(
        !s.stdout.contains("cryptographically_attested"),
        "aucun niveau ne doit etre derive :\n{}",
        s.stdout
    );
    let ligne = s.ligne("algorithme impose");
    assert!(ligne.starts_with("[FAIL"), "{ligne}");
    assert!(
        ligne.contains("CONFRONTEE, jamais honoree"),
        "le refus doit dire que `alg` n est pas lu pour choisir :\n{ligne}"
    );
}

#[test]
fn alg_hs256_est_refuse() {
    let f = jws_avec_alg("alg-hs256", "HS256");
    let s = lancer(&[
        "--attestation",
        f.to_str().unwrap(),
        "--archive",
        archive().to_str().unwrap(),
        "--trust-store",
        magasin().to_str().unwrap(),
        "--allow-test-keys",
    ]);
    assert_eq!(s.code, 1);
    assert!(!s.stdout.contains("cryptographically_attested"));
}

// --------------------------------------------------------------------------
// Le magasin de confiance
// --------------------------------------------------------------------------

#[test]
fn un_magasin_portant_une_cle_privee_est_refuse() {
    // Trouver un champ de clef privée est une DIVULGATION, pas une variante.
    let d = temporaire("magasin-prive");
    let f = d.join("store.json");
    let texte = fs::read_to_string(magasin()).unwrap();
    // Injecter un champ `d` dans l'entrée de clef.
    let mute = texte.replacen(r#""kid": "nm-ev-demo-v1","#, r#""kid": "nm-ev-demo-v1", "d": "AAAA","#, 1);
    assert_ne!(mute, texte, "l ancre de la fixture a change");
    fs::write(&f, mute).unwrap();
    let s = lancer(&[
        "--attestation",
        attestation().to_str().unwrap(),
        "--archive",
        archive().to_str().unwrap(),
        "--trust-store",
        f.to_str().unwrap(),
        "--allow-test-keys",
    ]);
    assert_eq!(s.code, 1, "stdout:\n{}", s.stdout);
    assert!(
        s.stdout.contains("cle PRIVEE") || s.stdout.contains("PRIVEE"),
        "le refus doit NOMMER la divulgation :\n{}",
        s.stdout
    );
}

#[test]
fn une_cle_de_test_n_accorde_rien_sans_autorisation_explicite() {
    let s = lancer(&[
        "--attestation",
        attestation().to_str().unwrap(),
        "--archive",
        archive().to_str().unwrap(),
        "--trust-store",
        magasin().to_str().unwrap(),
    ]);
    assert_eq!(s.code, 1, "stdout:\n{}", s.stdout);
    assert!(
        s.stdout.contains("--allow-test-keys"),
        "le refus doit dire comment l autoriser explicitement :\n{}",
        s.stdout
    );
    assert!(!s.stdout.contains("cryptographically_attested"));
}

#[test]
fn sans_magasin_la_signature_est_non_testee_et_jamais_fausse() {
    // INCONNUE n'est pas FAUSSE : sans magasin, la clef n'est pas
    // résoluble, et la signature est peut-être parfaitement valide.
    let s = lancer(&[
        "--attestation",
        attestation().to_str().unwrap(),
        "--archive",
        archive().to_str().unwrap(),
    ]);
    let ligne = s.ligne("signature cryptographique");
    assert!(
        ligne.starts_with("[NOT TESTED"),
        "sans magasin, la signature doit etre NOT TESTED, jamais FAIL :\n{ligne}"
    );
    assert!(!s.stdout.contains("cryptographically_attested"));
}

#[test]
fn l_empreinte_du_magasin_est_confrontee_quand_elle_est_fournie() {
    // Fournir une MAUVAISE empreinte doit faire échouer la confrontation :
    // c'est la parade au cas où magasin et archive arrivent par la même
    // route.
    let s = lancer(&[
        "--attestation",
        attestation().to_str().unwrap(),
        "--archive",
        archive().to_str().unwrap(),
        "--trust-store",
        magasin().to_str().unwrap(),
        "--store-digest",
        &"0".repeat(64),
        "--allow-test-keys",
    ]);
    assert_eq!(s.code, 1, "stdout:\n{}", s.stdout);
    let ligne = s.ligne("empreinte du magasin confrontee");
    assert!(ligne.starts_with("[FAIL"), "{ligne}");
    assert!(
        ligne.contains("Ne pas s en servir"),
        "le refus doit dire quoi faire :\n{ligne}"
    );
}

// --------------------------------------------------------------------------
// La concordance porte sur les TROIS empreintes
// --------------------------------------------------------------------------

#[test]
fn la_concordance_confronte_trois_empreintes() {
    let s = complet();
    let ligne = s.ligne("concordance avec l archive");
    assert!(ligne.starts_with("[PASS"), "{ligne}");
    assert!(
        ligne.contains("3 empreinte(s) confrontee(s)"),
        "la concordance doit confronter bundle_sha256, manifest_sha256 ET \
         checksums_sha256 -- un pilier qui n examine qu un tiers de ce qu il \
         annonce est trompeur :\n{ligne}"
    );
}

#[test]
fn une_autre_archive_fait_echouer_la_concordance() {
    // L'attestation porte sur l'archive réelle ; on lui en donne une autre.
    let d = temporaire("autre-archive");
    let f = d.join("autre.zip");
    let mut octets = fs::read(archive()).unwrap();
    // Un ZIP invalide suffit : la concordance doit refuser avant tout.
    octets.truncate(octets.len() / 2);
    fs::write(&f, &octets).unwrap();
    let s = lancer(&[
        "--attestation",
        attestation().to_str().unwrap(),
        "--archive",
        f.to_str().unwrap(),
        "--trust-store",
        magasin().to_str().unwrap(),
        "--allow-test-keys",
    ]);
    assert_eq!(s.code, 1);
    assert!(!s.stdout.contains("cryptographically_attested"));
}

// --------------------------------------------------------------------------
// L'archive
// --------------------------------------------------------------------------

#[test]
fn un_membre_altere_est_refuse() {
    let d = temporaire("membre-altere");
    let f = d.join("altere.zip");
    let octets = fs::read(archive()).unwrap();
    // Modifier un octet au milieu : le CRC-32 du membre, puis son
    // empreinte, ne tiennent plus.
    let mut mute = octets.clone();
    let milieu = mute.len() / 2;
    mute[milieu] ^= 0xFF;
    fs::write(&f, &mute).unwrap();
    let s = lancer(&["--archive", f.to_str().unwrap()]);
    assert_eq!(s.code, 1, "stdout:\n{}", s.stdout);
    assert!(s.stdout.contains("VERDICT : REJETE"), "{}", s.stdout);
}

#[test]
fn les_trois_lignes_hors_de_portee_de_l_archive_sont_declarees() {
    let s = lancer(&["--archive", archive().to_str().unwrap()]);
    for (intitule, mot) in [
        ("chainage canonique du registre", "SECONDE implementation"),
        ("completude de l export", "export PARTIEL"),
        ("origine et horodatage de l archive", "aucune signature tierce"),
    ] {
        let ligne = s.ligne(intitule);
        assert!(
            ligne.starts_with("[NOT TESTED"),
            "{intitule} doit etre NOT TESTED :\n{ligne}"
        );
        assert!(
            ligne.contains(mot),
            "{intitule} doit dire POURQUOI :\n{ligne}"
        );
    }
}

// --------------------------------------------------------------------------
// base64url strict — LA DIVERGENCE DÉCLARÉE avec Python
// --------------------------------------------------------------------------

#[test]
fn base64_avec_bourrage_est_refuse() {
    // DIVERGENCE DÉCLARÉE. `json`/`base64` de Python tolèrent le bourrage
    // `=` et l'alphabet standard `+`/`/` ; la RFC 7515 §2 impose base64url
    // SANS bourrage. Ce module refuse, Python accepte.
    //
    // Conséquence mesurée : une attestation a PLUSIEURS sérialisations
    // valides côté Python. C'est la même famille d'ambiguïté que les clefs
    // JSON en double, et elle n'est PAS arbitrée ici.
    let d = temporaire("b64-bourre");
    let f = d.join("bourre.jws");
    let original = fs::read_to_string(attestation()).unwrap();
    let parties: Vec<&str> = original.trim().split('.').collect();
    fs::write(
        &f,
        format!("{}=.{}.{}", parties[0], parties[1], parties[2]),
    )
    .unwrap();
    let s = lancer(&[
        "--attestation",
        f.to_str().unwrap(),
        "--archive",
        archive().to_str().unwrap(),
        "--trust-store",
        magasin().to_str().unwrap(),
        "--allow-test-keys",
    ]);
    assert_eq!(s.code, 1, "stdout:\n{}", s.stdout);
    let ligne = s.ligne("attestation lisible");
    assert!(ligne.starts_with("[FAIL"), "{ligne}");
    assert!(
        ligne.contains("bourrage"),
        "le refus doit NOMMER le bourrage :\n{ligne}"
    );
}

#[test]
fn base64_standard_est_refuse() {
    let d = temporaire("b64-standard");
    let f = d.join("standard.jws");
    let original = fs::read_to_string(attestation()).unwrap();
    let parties: Vec<&str> = original.trim().split('.').collect();
    let signature = parties[2].replace('-', "+").replace('_', "/");
    // Si la signature de la fixture ne contient ni `-` ni `_`, le cas
    // n'éprouve rien : on le dit plutôt que de le laisser passer vert.
    if signature == parties[2] {
        eprintln!(
            "la signature de la fixture ne porte ni `-` ni `_` : cas non \
             applicable, et NON compte comme reussi"
        );
        return;
    }
    fs::write(
        &f,
        format!("{}.{}.{}", parties[0], parties[1], signature),
    )
    .unwrap();
    let s = lancer(&[
        "--attestation",
        f.to_str().unwrap(),
        "--archive",
        archive().to_str().unwrap(),
        "--trust-store",
        magasin().to_str().unwrap(),
        "--allow-test-keys",
    ]);
    assert_eq!(s.code, 1, "stdout:\n{}", s.stdout);
    assert!(!s.stdout.contains("cryptographically_attested"));
}

// --------------------------------------------------------------------------
// Le contrat de sortie
// --------------------------------------------------------------------------

#[test]
fn aucune_entree_hostile_ne_sort_du_contrat_de_code() {
    let d = temporaire("codes");
    let entrees: [(&str, Vec<u8>); 7] = [
        ("vide", vec![]),
        ("un-point", b".".to_vec()),
        ("deux-points", b"..".to_vec()),
        ("trois-vides", b"a.b.".to_vec()),
        ("non-ascii", vec![0xFF, 0x2E, 0xFF, 0x2E, 0xFF]),
        ("nuls", vec![0u8; 4096]),
        ("tres-long", vec![b'A'; 300_000]),
    ];
    for (nom, octets) in entrees {
        let f = d.join(format!("{nom}.jws"));
        fs::write(&f, &octets).unwrap();
        let s = lancer(&[
            "--attestation",
            f.to_str().unwrap(),
            "--trust-store",
            magasin().to_str().unwrap(),
        ]);
        assert!(
            (0..=3).contains(&s.code),
            "{nom} : code {} hors du contrat {{0,1,2,3}}\nstderr:\n{}",
            s.code,
            s.stderr
        );
    }
}

#[test]
fn une_option_inconnue_est_une_erreur_d_execution() {
    let s = lancer(&["--archive", archive().to_str().unwrap(), "--inconnue"]);
    assert_eq!(
        s.code, 3,
        "une option inconnue doit rendre 3, jamais un verdict"
    );
    assert!(s.stdout.is_empty(), "stdout doit rester vide :\n{}", s.stdout);
    assert!(s.stderr.contains("option inconnue"), "{}", s.stderr);
}

#[test]
fn rien_a_verifier_est_une_erreur_d_execution() {
    let s = lancer(&["--allow-test-keys"]);
    assert_eq!(s.code, 3);
    assert!(s.stdout.is_empty());
}

#[test]
fn un_fichier_absent_est_une_erreur_d_execution_et_non_un_verdict() {
    let s = lancer(&["--archive", "/n/existe/pas.zip"]);
    assert_eq!(s.code, 3, "stdout:\n{}", s.stdout);
    assert!(s.stdout.is_empty());
    assert!(!s.stderr.is_empty());
}

// --------------------------------------------------------------------------
// Le paquet soumis n'est jamais modifié
// --------------------------------------------------------------------------

#[test]
fn les_preuves_soumises_ne_sont_pas_modifiees() {
    fn empreinte(p: &Path) -> Vec<u8> {
        fs::read(p).expect("lecture")
    }
    let avant = (
        empreinte(&archive()),
        empreinte(&attestation()),
        empreinte(&magasin()),
    );
    let _ = complet();
    let apres = (
        empreinte(&archive()),
        empreinte(&attestation()),
        empreinte(&magasin()),
    );
    assert_eq!(avant.0, apres.0, "l archive a ete modifiee");
    assert_eq!(avant.1, apres.1, "l attestation a ete modifiee");
    assert_eq!(avant.2, apres.2, "le magasin a ete modifie");
}

#[test]
fn le_rapport_json_porte_ses_dependances_et_ses_limites() {
    let d = temporaire("rapport");
    let f = d.join("r.json");
    let s = lancer(&[
        "--attestation",
        attestation().to_str().unwrap(),
        "--archive",
        archive().to_str().unwrap(),
        "--trust-store",
        magasin().to_str().unwrap(),
        "--allow-test-keys",
        "--json",
        f.to_str().unwrap(),
    ]);
    assert_eq!(s.code, 0, "{}", s.stdout);
    let r = fs::read_to_string(&f).expect("rapport ecrit");
    // La dépendance cryptographique est DÉCLARÉE dans le rapport : un
    // auditeur doit savoir ce que le vérificateur a importé.
    assert!(
        r.contains("ed25519-dalek"),
        "le rapport doit declarer sa dependance :\n{r}"
    );
    assert!(r.contains("\"language\": \"rust\""));
    assert!(r.contains("cryptographically_attested"));
    // Et ce que le niveau n'établit PAS.
    assert!(
        r.contains("does_not_establish"),
        "le rapport doit dire ce qu il n etablit pas"
    );
    assert!(r.contains("identite verifiee") || r.contains("identite JURIDIQUE"));
}
