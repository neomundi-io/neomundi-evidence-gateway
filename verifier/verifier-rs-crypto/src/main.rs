//! `evidence-verify-crypto` — attestations Ed25519/JWS et archives Evidence.
//!
//!   evidence-verify-crypto --archive A.zip
//!   evidence-verify-crypto --attestation A.zip.jws --archive A.zip \
//!       --trust-store magasin.json [--store-digest <sha256>] \
//!       [--allow-test-keys] [--json r.json]
//!
//! CE QUE CE PROGRAMME EST
//!
//! Le second vérificateur, pour deux périmètres que
//! `evidence-verify-rs` ne couvre pas : les attestations détachées et le
//! format d'archive Evidence. Il ne connaît que du matériel **public**, il
//! n'écrit rien hors du `--json` demandé, et **aucun chemin de code ne peut
//! y atteindre une clef privée** — il n'y a pas de signataire ici, et le
//! magasin de confiance est refusé s'il porte un champ de clef privée.
//!
//! CE QU'IL NE FAIT PAS
//!
//! Il n'appelle ni Python, ni l'API NeoMundi, ni Station. Il n'ouvre aucune
//! socket. Il ne modifie jamais les preuves qu'on lui soumet : rien n'est
//! extrait, rien n'est réécrit.
//!
//! LES CODES DE SORTIE
//!
//!   0  ACCEPTE, ou INCOMPLET sans `--strict`
//!   1  REJETE
//!   2  INCOMPLET avec `--strict`
//!   3  erreur d'exécution — JAMAIS un verdict
//!
//! Le `3` est le même que celui de `evidence-verify-rs` : une erreur d'outil
//! (fichier introuvable, option inconnue) ne doit pas se lire comme un
//! jugement sur la preuve. Les verdicts vont sur **stdout**, les erreurs
//! d'exécution sur **stderr**.

#[path = "../../verifier-rs/src/bilan.rs"]
mod bilan;
// `chemins::membre_sur` et `json::Valeur::nom_du_type` ne servent pas a
// cette caisse-ci. Les deux sont employes par `verifier-rs`, qui partage
// LES MEMES fichiers : les signaler ici serait signaler du code vivant
// ailleurs. `allow` est donc pose sur le module, avec sa raison.
#[allow(dead_code)]
#[path = "../../verifier-rs/src/chemins.rs"]
mod chemins;
#[path = "../../verifier-rs/src/inflate.rs"]
mod inflate;
#[allow(dead_code)]
#[path = "../../verifier-rs/src/json.rs"]
mod json;
#[path = "../../verifier-rs/src/sha256.rs"]
mod sha256;
#[path = "../../verifier-rs/src/zip.rs"]
mod zip;

mod archive;
mod attestation;
mod bilan_ext;
mod jws;
mod magasin;
mod profil;

use bilan::{Bilan, Etat, Raison, Verdict};
use bilan_ext::BilanAttestation;
use json::echapper;
use sha256::{en_hex, Sha256};
use std::path::{Path, PathBuf};

const NOM: &str = "evidence-verify-crypto";
const VERSION: &str = env!("CARGO_PKG_VERSION");
const SCHEMA_RAPPORT: &str = "neomundi.evidence.crypto-report-rs/1";
const CODE_ERREUR_EXECUTION: i32 = 3;

/// Borne de taille d'un fichier lu, sur ses MÉTADONNÉES, avant lecture.
/// Même raison que dans le cœur : sans elle, un fichier de plusieurs
/// gigaoctets ferait échouer l'allocation, et `panic = "abort"` rendrait un
/// code hors du contrat {0, 1, 2, 3}.
const FICHIER_OCTETS_MAX: u64 = 320 * 1024 * 1024;

struct ErreurExecution(String);

fn lire_fichier(p: &Path, quoi: &str) -> Result<Vec<u8>, ErreurExecution> {
    match std::fs::metadata(p) {
        Ok(m) if m.len() > FICHIER_OCTETS_MAX => {
            return Err(ErreurExecution(format!(
                "{quoi} : {} octets, borne {FICHIER_OCTETS_MAX}. Refuse AVANT lecture.",
                m.len()
            )))
        }
        Ok(_) => {}
        Err(e) => return Err(ErreurExecution(format!("{quoi} illisible : {e}"))),
    }
    std::fs::read(p).map_err(|e| ErreurExecution(format!("{quoi} illisible : {e}")))
}

fn sha(octets: &[u8]) -> String {
    let mut h = Sha256::new();
    h.alimenter(octets);
    en_hex(&h.terminer())
}

// --------------------------------------------------------------------------

struct Options {
    attestation: Option<PathBuf>,
    archive: Option<PathBuf>,
    magasin: Option<PathBuf>,
    empreinte_magasin: Option<String>,
    autoriser_test: bool,
    strict: bool,
    json: Option<PathBuf>,
}

fn aide() -> &'static str {
    "emploi :
  evidence-verify-crypto --archive <A.zip>
  evidence-verify-crypto --attestation <A.zip.jws> [--archive <A.zip>]
                         [--trust-store <magasin.json>]
                         [--store-digest <sha256>] [--allow-test-keys]
                         [--json <rapport.json>] [--strict]

  --archive <f>        archive Evidence a verifier (format station.export.*)
  --attestation <f>    attestation detachee au format JWS compact
  --trust-store <f>    magasin de confiance de l OPERATEUR, jamais du paquet
  --store-digest <h>   empreinte du magasin, obtenue par un AUTRE canal
  --allow-test-keys    accepter explicitement une cle de statut `test`
  --json <f>           rapport lisible par machine
  --strict             INCOMPLET sort en code 2 ; le VERDICT ne change pas
  --version, --help

codes de sortie : 0 accepte/incomplet · 1 rejete · 2 incomplet+strict
                  3 erreur d execution (jamais un verdict)
"
}

fn analyser_arguments() -> Result<Options, ErreurExecution> {
    let mut o = Options {
        attestation: None,
        archive: None,
        magasin: None,
        empreinte_magasin: None,
        autoriser_test: false,
        strict: false,
        json: None,
    };
    let args: Vec<String> = std::env::args().skip(1).collect();
    let mut i = 0;
    while i < args.len() {
        let a = args[i].as_str();
        let mut valeur = |nom: &str| -> Result<String, ErreurExecution> {
            if i + 1 >= args.len() {
                return Err(ErreurExecution(format!("{nom} attend une valeur")));
            }
            i += 1;
            Ok(args[i].clone())
        };
        match a {
            "--help" | "-h" => {
                print!("{}", aide());
                std::process::exit(0);
            }
            "--version" => {
                println!("{NOM} {VERSION}");
                std::process::exit(0);
            }
            "--attestation" => o.attestation = Some(PathBuf::from(valeur("--attestation")?)),
            "--archive" => o.archive = Some(PathBuf::from(valeur("--archive")?)),
            "--trust-store" => o.magasin = Some(PathBuf::from(valeur("--trust-store")?)),
            "--store-digest" => o.empreinte_magasin = Some(valeur("--store-digest")?),
            "--json" => o.json = Some(PathBuf::from(valeur("--json")?)),
            "--allow-test-keys" => o.autoriser_test = true,
            "--strict" => o.strict = true,
            autre => {
                // Une option inconnue est une ERREUR, jamais ignoree : un
                // `--trust-stroe` mal tape ne doit pas produire un verdict
                // calcule sans magasin.
                return Err(ErreurExecution(format!(
                    "option inconnue : {autre}\n\n{}",
                    aide()
                )));
            }
        }
        i += 1;
    }
    if o.attestation.is_none() && o.archive.is_none() {
        return Err(ErreurExecution(format!(
            "rien a verifier : fournir --archive, --attestation, ou les deux\n\n{}",
            aide()
        )));
    }
    Ok(o)
}

// --------------------------------------------------------------------------

fn verifier(o: &Options, b: &mut Bilan) -> Result<Sortie, ErreurExecution> {
    let mut s = Sortie::default();

    // ---- l'archive -------------------------------------------------------
    if let Some(chemin) = &o.archive {
        let octets = lire_fichier(chemin, "l archive")?;
        println!("Archive     : {}", chemin.display());
        let r = archive::verifier(&octets, b);
        println!("empreinte   : {}", r.empreinte_archive);
        s.empreinte_archive = Some(r.empreinte_archive);
        s.schema_archive = r.schema;
        s.membres = r.membres;
        s.empreintes_membres = r.empreintes_membres;
    }

    // ---- l'attestation ---------------------------------------------------
    if let Some(chemin) = &o.attestation {
        let octets = lire_fichier(chemin, "l attestation")?;
        println!("Attestation : {}", chemin.display());
        println!("empreinte   : {}", sha(&octets));
        s.empreinte_attestation = Some(sha(&octets));

        let jeton = match jws::lire(&octets) {
            Ok(j) => j,
            Err(e) => {
                b.controle(Etat::Fail, "attestation lisible", &e.0);
                return Ok(s);
            }
        };
        b.controle(
            Etat::Pass,
            "attestation lisible",
            &format!(
                "JWS compact, 3 segments, {} octets signes",
                jeton.octets_signes.len()
            ),
        );

        let entete = match json::analyser(&jeton.entete) {
            Ok(v) => v,
            Err(e) => {
                b.controle(
                    Etat::Fail,
                    "attestation lisible",
                    &format!("en-tete JWS illisible : {e}"),
                );
                return Ok(s);
            }
        };
        let charge = match json::analyser(&jeton.charge) {
            Ok(v) => v,
            Err(e) => {
                b.controle(
                    Etat::Fail,
                    "attestation lisible",
                    &format!("charge illisible : {e}"),
                );
                return Ok(s);
            }
        };

        let Some(att) = attestation::controle_forme(b, &charge) else {
            return Ok(s);
        };
        let key_id = att
            .get("key_id")
            .and_then(|v| v.comme_texte())
            .unwrap_or("")
            .to_string();
        s.key_id = Some(key_id.clone());

        // Le profil, SEPARE de la signature.
        attestation::controle_profil(b, &jeton.charge);
        attestation::controle_entete(b, &entete, &key_id);

        match &o.magasin {
            None => {
                b.pilier_non_teste(
                    attestation::PILIER_SIGNATURE,
                    Raison::NonApplicable,
                    &format!(
                        "aucun magasin de confiance fourni : la cle {key_id} n est \
                         pas resoluble. La fournir avec --trust-store <fichier>"
                    ),
                );
                b.pilier_non_teste(
                    attestation::PILIER_CONFIANCE,
                    Raison::NonApplicable,
                    "sans magasin, aucune confiance n est etablie -- et aucune \
                     n est niee",
                );
            }
            Some(chemin_m) => {
                let octets_m = lire_fichier(chemin_m, "le magasin de confiance")?;
                let empreinte_m = sha(&octets_m);
                s.empreinte_magasin = Some(empreinte_m.clone());
                match magasin::charger(&octets_m) {
                    Err(e) => {
                        b.controle(Etat::Fail, "magasin de confiance lisible", &e.0);
                    }
                    Ok(m) => {
                        b.controle(
                            Etat::Pass,
                            "magasin de confiance lisible",
                            &format!(
                                "{} v{}, politique {}, {} cle(s), {} identite(s)",
                                m.store_id.as_deref().unwrap_or("?"),
                                m.store_version.as_deref().unwrap_or("?"),
                                magasin::POLITIQUE,
                                m.cles.len(),
                                m.identites.len()
                            ),
                        );

                        // LA CONFRONTATION PAR UN SECOND CANAL.
                        match o.empreinte_magasin.as_deref() {
                            None => b.pilier_non_teste(
                                "empreinte du magasin confrontee",
                                Raison::NonApplicable,
                                "aucune empreinte fournie. La fournir avec \
                                 --store-digest <sha256>, obtenue par un AUTRE \
                                 canal que celui qui a fourni le magasin. Sans \
                                 cela, le magasin et l archive arrivent par la \
                                 MEME route, et qui controle cette route \
                                 controle les deux. Un magasin non confronte n est \
                                 pas faux : il est non confronte.",
                            ),
                            Some(attendue) => {
                                let attendue = attendue.trim().to_ascii_lowercase();
                                if attendue == empreinte_m {
                                    b.controle_requis(
                                        Etat::Pass,
                                        "empreinte du magasin confrontee",
                                        &format!(
                                            "les octets du magasin se hachent sur \
                                             l empreinte annoncee par un second \
                                             canal ({}...). Un faussaire devrait \
                                             compromettre les DEUX",
                                            &empreinte_m[..16]
                                        ),
                                    );
                                } else {
                                    b.controle_requis(
                                        Etat::Fail,
                                        "empreinte du magasin confrontee",
                                        &format!(
                                            "le magasin fourni se hache sur {}..., \
                                             le second canal annonce {}... : ce n est \
                                             pas le meme magasin. Ne pas s en servir",
                                            &empreinte_m[..16],
                                            &attendue[..attendue.len().min(16)]
                                        ),
                                    );
                                }
                            }
                        }

                        match m.trouver(&key_id) {
                            None => {
                                // INCONNUE n'est pas FAUSSE.
                                b.pilier_non_teste(
                                    attestation::PILIER_SIGNATURE,
                                    Raison::NonApplicable,
                                    &format!(
                                        "cle {key_id} inconnue de ce magasin ({} cle(s) \
                                         connue(s)). La signature est peut-etre \
                                         valide ; rien ici ne permet de le dire",
                                        m.cles.len()
                                    ),
                                );
                                b.pilier_non_teste(
                                    attestation::PILIER_CONFIANCE,
                                    Raison::NonApplicable,
                                    "cle inconnue : aucune confiance n est etablie, \
                                     et aucune n est niee",
                                );
                            }
                            Some(cle) => {
                                // La politique du magasin AVANT le calcul.
                                if let Err(pourquoi) = m.politique_autorise(
                                    attestation::ALG_IMPOSE,
                                    attestation::COURBE_IMPOSEE,
                                ) {
                                    b.controle(
                                        Etat::Fail,
                                        "politique du magasin compatible",
                                        &pourquoi,
                                    );
                                } else {
                                    b.controle(
                                        Etat::Pass,
                                        "politique du magasin compatible",
                                        &format!(
                                            "{} et {} figurent dans la politique du \
                                             magasin",
                                            attestation::ALG_IMPOSE,
                                            attestation::COURBE_IMPOSEE
                                        ),
                                    );
                                }
                                attestation::controle_signature(b, cle, &jeton);
                                attestation::controle_confiance(
                                    b,
                                    &m,
                                    cle,
                                    att,
                                    o.autoriser_test,
                                );
                                attestation::controle_capacite_juridique(b, &m, att);
                                attestation::controle_identites(b, &m, att);
                                s.signataire = cle.signer_identity.clone();
                            }
                        }
                    }
                }
            }
        }

        let archive_pour_concordance = s.empreinte_archive.as_deref().map(|e| {
            (
                o.archive
                    .as_deref()
                    .and_then(|p| p.file_name())
                    .map(|n| n.to_string_lossy().into_owned())
                    .unwrap_or_else(|| "l archive".into()),
                e.to_string(),
            )
        });
        attestation::controle_concordance(
            b,
            att,
            archive_pour_concordance
                .as_ref()
                .map(|(n, e)| (n.as_str(), e.as_str())),
            &s.empreintes_membres,
        );
        attestation::controle_nature(b, att);
        attestation::controle_horodatage(b, att);
        attestation::controle_ancrage(b, att);
        attestation::controle_verite(b);

        s.niveau = attestation::niveau_derive(b).map(str::to_string);
    }

    Ok(s)
}

#[derive(Default)]
struct Sortie {
    empreinte_archive: Option<String>,
    schema_archive: Option<String>,
    membres: Vec<String>,
    empreintes_membres: std::collections::BTreeMap<String, String>,
    empreinte_attestation: Option<String>,
    empreinte_magasin: Option<String>,
    key_id: Option<String>,
    signataire: Option<String>,
    niveau: Option<String>,
}

fn rapport_json(b: &Bilan, s: &Sortie, verdict: Verdict) -> String {
    let opt = |v: &Option<String>| match v {
        Some(x) => echapper(x),
        None => "null".to_string(),
    };
    format!(
        "{{\n  \"schema\": {},\n  \"verifier\": {{\"name\": {}, \"version\": {}, \
         \"language\": \"rust\", \"dependencies\": [\"ed25519-dalek\"]}},\n  \
         \"verdict\": {},\n  \"attested_level\": {},\n  \"counts\": {{\"pass\": {}, \
         \"fail\": {}, \"not_tested\": {}}},\n  \"required_not_demonstrated\": [{}],\n  \
         \"archive\": {{\"sha256\": {}, \"export_schema\": {}, \"members\": [{}]}},\n  \
         \"attestation\": {{\"sha256\": {}, \"key_id\": {}, \"signer_identity_declared\": {}}},\n  \
         \"trust_store\": {{\"sha256\": {}}},\n  \"lines\": {},\n  \
         \"does_not_establish\": [{}]\n}}\n",
        echapper(SCHEMA_RAPPORT),
        echapper(NOM),
        echapper(VERSION),
        echapper(verdict.texte()),
        opt(&s.niveau),
        b.compte(Etat::Pass),
        b.compte(Etat::Fail),
        b.compte(Etat::NonTeste),
        b.requis_non_demontres()
            .iter()
            .map(|x| echapper(x))
            .collect::<Vec<_>>()
            .join(", "),
        opt(&s.empreinte_archive),
        opt(&s.schema_archive),
        s.membres
            .iter()
            .map(|m| echapper(m))
            .collect::<Vec<_>>()
            .join(", "),
        opt(&s.empreinte_attestation),
        opt(&s.key_id),
        opt(&s.signataire),
        opt(&s.empreinte_magasin),
        b.lignes_json(),
        [
            "Que le contenu atteste soit vrai. Une signature etablit qu une clef \
             s est engagee sur des octets, pas que ces octets disent vrai.",
            "L identite JURIDIQUE du signataire. Le magasin la DECLARE ; aucun \
             code ne la verifie, et ce verificateur n affiche jamais `identite \
             verifiee`.",
            "La date. `attested_at_declared` est declaree par le signataire, qui \
             detient la clef privee : il peut y ecrire n importe quelle date.",
            "La completude de l export. Une chaine d integrite entiere ne dit rien \
             de ce qui n a pas ete exporte.",
            "Le chainage canonique du registre d origine. Le recalculer ici serait \
             une seconde implementation du meme profil, et deux implementations \
             divergeraient un jour sur un cas rare."
        ]
        .map(echapper)
        .join(", ")
    )
}

fn main() {
    let o = match analyser_arguments() {
        Ok(o) => o,
        Err(e) => {
            eprintln!("{NOM} : {}", e.0);
            std::process::exit(CODE_ERREUR_EXECUTION);
        }
    };

    let mut b = Bilan::new();
    let s = match verifier(&o, &mut b) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("{NOM} : {}", e.0);
            std::process::exit(CODE_ERREUR_EXECUTION);
        }
    };

    // L'INVARIANT CENTRAL, verifie a l'execution : aucune ligne DECLARE ne
    // porte PASS. S'il tombe, le rapport presente une declaration comme un
    // fait, et c'est la seule faute que ce produit ne doit jamais commettre.
    if let Err(rompu) = b.invariant_declare() {
        eprintln!("{NOM} : {rompu}");
        std::process::exit(CODE_ERREUR_EXECUTION);
    }

    println!();
    for l in &b.lignes {
        println!(
            "[{:<10}] [{:<15}] {} - {}",
            l.etat.texte(),
            l.nature.texte(),
            l.intitule,
            l.detail
        );
    }

    let verdict = b.verdict();
    println!();
    println!(
        "BILAN : {} PASS, {} FAIL, {} NOT TESTED",
        b.compte(Etat::Pass),
        b.compte(Etat::Fail),
        b.compte(Etat::NonTeste)
    );
    println!("VERDICT : {}", verdict.texte());
    match &s.niveau {
        Some(n) => println!(
            "NIVEAU  : {n} -- les cinq piliers sont PASS. Ceci ne dit RIEN de la \
             veracite du contenu ni de l identite juridique du signataire."
        ),
        None => println!(
            "NIVEAU  : aucun. Un niveau degrade se lirait comme un succes partiel, \
             et il n y en a pas."
        ),
    }

    // Le rapport est ECRIT AVANT que le code de sortie ne soit rendu, et son
    // echec est un REFUS, pas un silence. Meme regle que celle posee dans
    // `adapters/ingest.py` par le chantier A.
    if let Some(chemin) = &o.json {
        let contenu = rapport_json(&b, &s, verdict);
        if let Some(parent) = chemin.parent() {
            if !parent.as_os_str().is_empty() {
                let _ = std::fs::create_dir_all(parent);
            }
        }
        if let Err(e) = std::fs::write(chemin, contenu) {
            eprintln!("{NOM} : rapport JSON non ecrit : {e}");
            std::process::exit(CODE_ERREUR_EXECUTION);
        }
        println!("rapport JSON : {}", chemin.display());
    }

    std::process::exit(match verdict {
        Verdict::Rejete => 1,
        Verdict::Incomplet if o.strict => 2,
        _ => 0,
    });
}
