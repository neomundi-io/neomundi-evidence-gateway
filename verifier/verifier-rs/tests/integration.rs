//! Tests d'intégration : le binaire, de bout en bout, **SANS PYTHON**.
//!
//! POURQUOI LES FIXTURES SONT CONSTRUITES ICI
//!
//! Elles pourraient venir de `tests/make_submission.py`. Elles n'en
//! viennent pas, et c'est le point : la mission exige que le vérificateur
//! Rust fonctionne **sans Python**. Une suite d'intégration qui appellerait
//! un script Python pour fabriquer ses entrées ne prouverait pas cette
//! indépendance — elle la contredirait.
//!
//! Les fixtures sont donc écrites en Rust, à la main, dans un dossier
//! temporaire. Le banc comparatif, lui, emploie les profils du dépôt : c'est
//! son rôle, et il est un témoin, pas le vérificateur.
//!
//! CE QUE CETTE SUITE ÉPROUVE
//!
//! Le binaire compilé : ses verdicts, ses codes de sortie, son rapport
//! JSON, et le fait qu'il n'écrit rien dans le paquet soumis.

use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

/// Le binaire sous test. `CARGO_BIN_EXE_<nom>` est posé par Cargo.
fn binaire() -> PathBuf {
    PathBuf::from(env!("CARGO_BIN_EXE_evidence-verify-rs"))
}

fn temporaire(nom: &str) -> PathBuf {
    let mut p = std::env::temp_dir();
    p.push(format!("evr-it-{}-{}", nom, std::process::id()));
    let _ = fs::remove_dir_all(&p);
    fs::create_dir_all(&p).expect("dossier temporaire");
    p
}

/// SHA-256 d'une tranche, calculé par un chemin INDÉPENDANT de celui du
/// vérificateur : `sha256sum` n'est pas disponible partout, donc on relit
/// la valeur depuis des constantes publiées. Pour les fixtures, les
/// condensés sont ceux de FIPS 180-4 ou de chaînes dont le condensé est
/// donné en clair ici.
const PROMPT: &[u8] = b"abc";
/// FIPS 180-4, annexe B.1.
const PROMPT_SHA: &str =
    "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad";
const VIDE_SHA: &str =
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";

fn manifeste_v2(artefacts: &str) -> String {
    format!(
        r#"{{
  "schema": "neomundi.evidence.submission/2",
  "submission_id": "fixture-rust-001",
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

fn paquet_valide(nom: &str) -> PathBuf {
    let d = temporaire(nom);
    fs::create_dir_all(d.join("artefacts")).unwrap();
    fs::write(d.join("artefacts/prompt.txt"), PROMPT).unwrap();
    let a = format!(
        r#"{{"path": "artefacts/prompt.txt", "sha256": "{PROMPT_SHA}", "bytes": {}, "role": "prompt"}}"#,
        PROMPT.len()
    );
    fs::write(d.join("submission.json"), manifeste_v2(&a)).unwrap();
    d
}

struct Sortie {
    code: i32,
    stdout: String,
    stderr: String,
    rapport: Option<String>,
}

fn lancer(paquet: &Path, extra: &[&str]) -> Sortie {
    let rapport = paquet.parent().unwrap().join(format!(
        "{}-rapport.json",
        paquet.file_name().unwrap().to_string_lossy()
    ));
    let _ = fs::remove_file(&rapport);
    let mut cmd = Command::new(binaire());
    cmd.arg(paquet).arg("--json").arg(&rapport);
    for e in extra {
        cmd.arg(e);
    }
    let s = cmd.output().expect("lancement du binaire");
    Sortie {
        code: s.status.code().unwrap_or(-1),
        stdout: String::from_utf8_lossy(&s.stdout).into_owned(),
        stderr: String::from_utf8_lossy(&s.stderr).into_owned(),
        rapport: fs::read_to_string(&rapport).ok(),
    }
}

/// Extraction minimale d'un champ texte du rapport, sans analyseur : les
/// tests ne doivent pas dépendre du module qu'ils éprouvent.
fn champ(rapport: &str, clef: &str) -> Option<String> {
    let motif = format!("\"{clef}\": \"");
    let i = rapport.find(&motif)? + motif.len();
    let reste = &rapport[i..];
    let j = reste.find('"')?;
    Some(reste[..j].to_string())
}

#[test]
fn paquet_valide_est_accepte() {
    let d = paquet_valide("valide");
    let s = lancer(&d, &[]);
    assert_eq!(s.code, 0, "stdout:\n{}\nstderr:\n{}", s.stdout, s.stderr);
    assert!(s.stdout.contains("VERDICT : ACCEPTE"), "{}", s.stdout);
    let r = s.rapport.expect("rapport JSON ecrit");
    assert_eq!(champ(&r, "verdict").as_deref(), Some("ACCEPTE"));
    assert_eq!(
        champ(&r, "submission_schema").as_deref(),
        Some("neomundi.evidence.submission/2")
    );
    // L'empreinte publiée est celle que NOUS recalculons.
    assert!(r.contains(PROMPT_SHA), "le condense recalcule doit figurer");
    // Le vérificateur ne se déclare jamais dépendant.
    assert!(r.contains("\"dependencies\": []"));
    assert!(r.contains("\"language\": \"rust\""));
}

#[test]
fn empreinte_fausse_est_rejetee() {
    let d = temporaire("empreinte-fausse");
    fs::create_dir_all(d.join("artefacts")).unwrap();
    fs::write(d.join("artefacts/prompt.txt"), PROMPT).unwrap();
    let a = format!(
        r#"{{"path": "artefacts/prompt.txt", "sha256": "{}", "bytes": {}, "role": "prompt"}}"#,
        "0".repeat(64),
        PROMPT.len()
    );
    fs::write(d.join("submission.json"), manifeste_v2(&a)).unwrap();
    let s = lancer(&d, &[]);
    assert_eq!(s.code, 1);
    assert!(s.stdout.contains("VERDICT : REJETE"));
    // Les DEUX valeurs sont conservées : la déclarée et la recalculée.
    let r = s.rapport.unwrap();
    assert!(r.contains(PROMPT_SHA) && r.contains(&"0".repeat(64)));
}

#[test]
fn taille_fausse_est_rejetee() {
    let d = temporaire("taille-fausse");
    fs::create_dir_all(d.join("artefacts")).unwrap();
    fs::write(d.join("artefacts/prompt.txt"), PROMPT).unwrap();
    let a = format!(
        r#"{{"path": "artefacts/prompt.txt", "sha256": "{PROMPT_SHA}", "bytes": 99999, "role": "prompt"}}"#
    );
    fs::write(d.join("submission.json"), manifeste_v2(&a)).unwrap();
    assert_eq!(lancer(&d, &[]).code, 1);
}

#[test]
fn artefact_absent_rend_incomplet_et_non_refus() {
    // Un artefact annoncé et non fourni n'est pas une fraude : c'est un
    // paquet que le soumetteur peut compléter. Code 0 sans `--strict`,
    // code 2 avec.
    let d = temporaire("artefact-absent");
    fs::create_dir_all(d.join("artefacts")).unwrap();
    let a = format!(
        r#"{{"path": "artefacts/absent.txt", "sha256": "{VIDE_SHA}", "bytes": 0, "role": "other"}}"#
    );
    fs::write(d.join("submission.json"), manifeste_v2(&a)).unwrap();
    let s = lancer(&d, &[]);
    assert_eq!(s.code, 0, "{}", s.stdout);
    assert!(s.stdout.contains("VERDICT : INCOMPLET"), "{}", s.stdout);
    let s2 = lancer(&d, &["--strict"]);
    assert_eq!(s2.code, 2, "--strict doit sortir 2 sur INCOMPLET");
    assert!(s2.stdout.contains("VERDICT : INCOMPLET"), "le verdict ne change PAS");
}

#[test]
fn artefact_vide_est_accepte() {
    let d = temporaire("artefact-vide");
    fs::create_dir_all(d.join("artefacts")).unwrap();
    fs::write(d.join("artefacts/vide.txt"), b"").unwrap();
    let a = format!(
        r#"{{"path": "artefacts/vide.txt", "sha256": "{VIDE_SHA}", "bytes": 0, "role": "other"}}"#
    );
    fs::write(d.join("submission.json"), manifeste_v2(&a)).unwrap();
    let s = lancer(&d, &[]);
    assert_eq!(s.code, 0, "{}", s.stdout);
    assert!(s.stdout.contains("ACCEPTE"));
}

#[test]
fn version_inconnue_est_rejetee() {
    let d = paquet_valide("version-inconnue");
    let m = fs::read_to_string(d.join("submission.json")).unwrap();
    fs::write(
        d.join("submission.json"),
        m.replace("submission/2", "submission/99"),
    )
    .unwrap();
    let s = lancer(&d, &[]);
    assert_eq!(s.code, 1);
    assert!(s.stdout.contains("schema du manifeste"), "{}", s.stdout);
}

#[test]
fn manifeste_absent_est_rejete() {
    let d = temporaire("sans-manifeste");
    fs::write(d.join("autre.txt"), b"x").unwrap();
    let s = lancer(&d, &[]);
    assert_eq!(s.code, 1);
    assert!(s.stdout.contains("manifeste de soumission"));
}

#[test]
fn chemins_dangereux_sont_rejetes() {
    for (nom, chemin) in [
        ("abs", "/etc/passwd"),
        ("remontee", "../../etc/passwd"),
        ("lecteur", "C:/x"),
        ("antislash", "a\\b"),
    ] {
        let d = temporaire(&format!("dangereux-{nom}"));
        let a = format!(
            r#"{{"path": "{}", "sha256": "{VIDE_SHA}", "bytes": 0, "role": "other"}}"#,
            chemin.replace('\\', "\\\\")
        );
        fs::write(d.join("submission.json"), manifeste_v2(&a)).unwrap();
        let s = lancer(&d, &[]);
        assert_eq!(s.code, 1, "{nom} devrait etre refuse : {}", s.stdout);
    }
}

#[test]
fn clef_en_double_est_rejetee_et_le_dit() {
    // LA divergence déclarée avec Python. Le refus doit NOMMER la cause :
    // un auditeur qui compare les deux rapports doit pouvoir constater que
    // la différence est une politique, pas un accident.
    let d = temporaire("clef-double");
    fs::create_dir_all(d.join("artefacts")).unwrap();
    fs::write(d.join("artefacts/prompt.txt"), PROMPT).unwrap();
    let a = format!(
        r#"{{"path": "artefacts/prompt.txt", "sha256": "{PROMPT_SHA}", "bytes": {}, "role": "prompt"}}"#,
        PROMPT.len()
    );
    let m = manifeste_v2(&a).replace(
        r#""submission_id": "fixture-rust-001","#,
        r#""submission_id": "premier","submission_id": "fixture-rust-001","#,
    );
    fs::write(d.join("submission.json"), m).unwrap();
    let s = lancer(&d, &[]);
    assert_eq!(s.code, 1);
    assert!(
        s.stdout.contains("DOUBLE"),
        "le refus doit nommer la clef en double : {}",
        s.stdout
    );
}

#[test]
fn bom_est_tolere() {
    let d = paquet_valide("bom");
    let m = fs::read(d.join("submission.json")).unwrap();
    let mut avec = vec![0xEF, 0xBB, 0xBF];
    avec.extend_from_slice(&m);
    fs::write(d.join("submission.json"), avec).unwrap();
    let s = lancer(&d, &[]);
    assert_eq!(s.code, 0, "un BOM est banal : {}", s.stdout);
}

#[test]
fn le_paquet_soumis_n_est_pas_modifie() {
    // La propriété la plus simple à perdre, et la plus grave : un
    // vérificateur qui écrit dans le paquet qu'il vérifie en altère la
    // preuve.
    let d = paquet_valide("intact");
    let avant: Vec<(PathBuf, Vec<u8>)> = fs::read_dir(d.join("artefacts"))
        .unwrap()
        .flatten()
        .map(|e| (e.path(), fs::read(e.path()).unwrap()))
        .collect();
    let manifeste_avant = fs::read(d.join("submission.json")).unwrap();
    lancer(&d, &[]);
    for (p, octets) in avant {
        assert_eq!(fs::read(&p).unwrap(), octets, "{p:?} a ete modifie");
    }
    assert_eq!(fs::read(d.join("submission.json")).unwrap(), manifeste_avant);
}

#[test]
fn option_inconnue_est_refusee_non_ignoree() {
    let d = paquet_valide("option");
    let s = Command::new(binaire())
        .arg(&d)
        .arg("--inconnue")
        .output()
        .unwrap();
    assert_eq!(s.status.code(), Some(3), "une option inconnue sort en 3");
}

#[test]
fn erreur_d_execution_distingue_du_verdict() {
    // Un paquet inexistant est une erreur d'EXÉCUTION (code 3, sur stderr),
    // et non un verdict de vérification (codes 0, 1, 2, sur stdout).
    let s = Command::new(binaire())
        .arg("/chemin/qui/n/existe/pas/du/tout")
        .output()
        .unwrap();
    assert_eq!(s.status.code(), Some(3));
    let err = String::from_utf8_lossy(&s.stderr);
    assert!(err.contains("erreur d execution"), "{err}");
    assert!(String::from_utf8_lossy(&s.stdout).is_empty(),
            "aucun verdict ne doit sortir sur stdout");
}

#[test]
fn la_version_est_publiee() {
    let s = Command::new(binaire()).arg("--version").output().unwrap();
    assert_eq!(s.status.code(), Some(0));
    let t = String::from_utf8_lossy(&s.stdout);
    assert!(t.contains("evidence-verify-rs"), "{t}");
    assert!(t.contains(env!("CARGO_PKG_VERSION")), "{t}");
}

#[test]
fn signature_declaree_rend_non_teste_et_jamais_valide() {
    // Le point le plus important du module 5 : une attestation DÉCLARÉE ne
    // doit jamais produire un verdict de validité. Elle rend le paquet
    // INCOMPLET -- il manque une vérification que ce vérificateur ne sait
    // pas faire -- et le rapport dit pourquoi.
    let d = paquet_valide("attestation");
    let m = fs::read_to_string(d.join("submission.json")).unwrap();
    let m = m.replace(
        "\n  \"artifacts\"",
        "\n  \"attestations\": [{\"jws_path\": \"a.jws\", \"subject_path\": \"b.zip\"}],\n  \"artifacts\"",
    );
    fs::write(d.join("submission.json"), m).unwrap();
    let s = lancer(&d, &[]);
    assert!(s.stdout.contains("VERDICT : INCOMPLET"), "{}", s.stdout);
    assert!(
        s.stdout.contains("NE VERIFIE") || s.stdout.contains("NON TESTE"),
        "le rapport doit DIRE qu aucune signature n est verifiee : {}",
        s.stdout
    );
    let r = s.rapport.unwrap();
    assert!(r.contains("hors_portee_de_ce_verificateur"));
    // Et jamais le mot qui ferait croire à une validation.
    assert!(!r.contains("signature_valide"));
}

#[test]
fn aucune_ligne_declare_ne_porte_pass() {
    // L'invariant central, vérifié sur la sortie du binaire : une
    // déclaration ne devient jamais un fait attesté.
    let d = paquet_valide("invariant");
    let s = lancer(&d, &[]);
    for ligne in s.stdout.lines() {
        if ligne.contains("[DECLARE") {
            assert!(
                !ligne.contains("[PASS"),
                "une ligne DECLARE porte PASS : {ligne}"
            );
        }
    }
}
