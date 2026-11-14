//! `evidence-verify-rs` — second vérificateur indépendant d'un paquet de
//! soumission NeoMundi Evidence. **N'EXÉCUTE RIEN.**
//!
//! ```text
//! evidence-verify-rs <dossier|paquet.zip> [--json rapport.json] [--md rapport.md]
//! ```
//!
//! CE QU'IL EST
//!
//! Une seconde implémentation, écrite en Rust, des contrôles que
//! `adapters/ingest.py` applique aux contrats
//! `neomundi.evidence.submission/1` et `/2`. Deux implémentations
//! indépendantes qui concordent valent mieux qu'une seule qui affirme ;
//! deux qui divergent signalent une ambiguïté du protocole, et c'est une
//! information, pas un incident.
//!
//! CE DONT IL NE DÉPEND PAS
//!
//! Ni de Python, ni de l'API NeoMundi, ni de Station, ni du réseau, ni
//! d'aucun secret. **Aucune caisse tierce** : SHA-256, l'analyse JSON, la
//! lecture ZIP et l'inflation DEFLATE sont écrites dans ce dépôt. Il ne lit
//! jamais un rapport Python, et n'emploie aucune conclusion Python comme
//! oracle.
//!
//! CE QU'IL N'ÉTABLIT PAS
//!
//! Que l'exécution déclarée ait eu lieu. Qui a produit le paquet. La
//! véracité d'une date. La validité d'une signature — il n'en vérifie
//! aucune, et le déclare `NOT TESTED` avec sa raison plutôt que de rendre
//! un verdict trompeur.
//!
//! CODES DE SORTIE
//!
//!   0  ACCEPTE, ou INCOMPLET sans `--strict`
//!   1  REJETE
//!   2  INCOMPLET avec `--strict`
//!   3  erreur d'EXÉCUTION du programme -- à ne pas confondre avec un
//!      verdict de vérification. Python n'a pas ce code : voir la
//!      divergence D-1 de `04_MATRICE_PYTHON_RUST.md`.

mod bilan;
mod chemins;
mod essais;
mod contrat;
mod inflate;
mod json;
mod sha256;
mod verifier;
mod zip;

use bilan::{Etat, Verdict};
use contrat as c;
use std::io::Write;
use std::path::PathBuf;

const CODE_ERREUR_EXECUTION: i32 = 3;

struct Options {
    paquet: PathBuf,
    json: Option<PathBuf>,
    md: Option<PathBuf>,
    strict: bool,
}

fn usage() -> String {
    format!(
        "{} {}\n\n\
         Emploi : evidence-verify-rs <dossier|paquet.zip> [options]\n\n\
         Options :\n\
         \x20 --json <fichier>   rapport JSON, lisible par machine\n\
         \x20 --md <fichier>     rapport Markdown, lisible par un auditeur\n\
         \x20 --strict           sortir 2 sur un paquet INCOMPLET\n\
         \x20 --version          la version, et rien d autre\n\
         \x20 --help             ce texte\n\n\
         Aucune dependance, aucun reseau, aucun secret, aucune ecriture dans\n\
         le paquet soumis.",
        c::NOM_VERIFICATEUR,
        c::VERSION_VERIFICATEUR
    )
}

fn lire_options() -> Result<Options, String> {
    let mut args = std::env::args().skip(1);
    let mut paquet: Option<PathBuf> = None;
    let mut json = None;
    let mut md = None;
    let mut strict = false;
    while let Some(a) = args.next() {
        match a.as_str() {
            "--help" | "-h" => {
                println!("{}", usage());
                std::process::exit(0);
            }
            "--version" => {
                println!("{} {}", c::NOM_VERIFICATEUR, c::VERSION_VERIFICATEUR);
                std::process::exit(0);
            }
            "--strict" => strict = true,
            "--json" => {
                json = Some(PathBuf::from(
                    args.next().ok_or("--json attend un chemin")?,
                ))
            }
            "--md" => {
                md = Some(PathBuf::from(args.next().ok_or("--md attend un chemin")?))
            }
            autre if autre.starts_with("--") => {
                // Une option inconnue est REFUSÉE, jamais ignorée : l'ignorer
                // ferait croire qu'elle a été prise en compte.
                return Err(format!("option inconnue : {autre}"));
            }
            autre => {
                if paquet.is_some() {
                    return Err("un seul paquet a la fois".into());
                }
                paquet = Some(PathBuf::from(autre));
            }
        }
    }
    Ok(Options {
        paquet: paquet.ok_or("aucun paquet donne")?,
        json,
        md,
        strict,
    })
}

fn main() {
    let o = match lire_options() {
        Ok(o) => o,
        Err(e) => {
            eprintln!("{e}\n\n{}", usage());
            std::process::exit(CODE_ERREUR_EXECUTION);
        }
    };

    let r = match verifier::verifier(&o.paquet) {
        Ok(r) => r,
        Err(e) => {
            // ERREUR D'EXÉCUTION, et non verdict de vérification. La
            // distinction est portée par le code de sortie ET par le canal :
            // un verdict va sur stdout, une erreur de programme sur stderr.
            eprintln!("erreur d execution : {e}");
            std::process::exit(CODE_ERREUR_EXECUTION);
        }
    };

    // L'invariant central, vérifié à l'exécution : aucune ligne DECLARE ne
    // porte PASS. S'il tombe, le rapport présenterait une déclaration comme
    // un fait, et il vaut mieux ne rien rendre.
    if let Err(e) = r.bilan.invariant_declare() {
        eprintln!("erreur d execution : {e}");
        std::process::exit(CODE_ERREUR_EXECUTION);
    }

    let verdict = r.bilan.verdict();
    println!("paquet : {}\n", r.paquet);
    for l in &r.bilan.lignes {
        let detail = if l.detail.is_empty() {
            String::new()
        } else {
            format!(" - {}", l.detail)
        };
        println!("[{:<10}] [{:<15}] {}{}", l.etat.texte(), l.nature.texte(), l.intitule, detail);
    }
    println!(
        "\nSOMMAIRE : {} PASS, {} FAIL, {} NOT TESTED",
        r.bilan.compte(Etat::Pass),
        r.bilan.compte(Etat::Fail),
        r.bilan.compte(Etat::NonTeste)
    );
    println!("VERDICT : {}", verdict.texte());
    match verdict {
        Verdict::Rejete => println!(
            "\nLe paquet est REJETE : au moins un controle a echoue. Les lignes \
             FAIL ci-dessus disent lesquelles."
        ),
        Verdict::Incomplet => {
            println!(
                "\nLe paquet est INCOMPLET, et ce n est pas un refus : il manque \
                 quelque chose que le soumetteur peut fournir."
            );
            for x in r.bilan.requis_non_demontres() {
                println!("  - {x}");
            }
        }
        Verdict::Accepte => println!(
            "\nLe paquet est ACCEPTE : sa structure et les empreintes qu il \
             declare sont controlees. Les lignes DECLARE restent la parole du \
             soumetteur, et les NON DEMONTRABLE le resteront."
        ),
    }

    if let Some(p) = &o.json {
        if let Err(e) = ecrire(p, rapport_json(&r, verdict).as_bytes()) {
            eprintln!("erreur d execution : rapport JSON non ecrit : {e}");
            std::process::exit(CODE_ERREUR_EXECUTION);
        }
        println!("rapport JSON : {}", p.display());
    }
    if let Some(p) = &o.md {
        if let Err(e) = ecrire(p, rapport_md(&r, verdict).as_bytes()) {
            eprintln!("erreur d execution : rapport Markdown non ecrit : {e}");
            std::process::exit(CODE_ERREUR_EXECUTION);
        }
        println!("rapport Markdown : {}", p.display());
    }

    std::process::exit(match verdict {
        Verdict::Rejete => 1,
        Verdict::Incomplet if o.strict => 2,
        _ => 0,
    });
}

fn ecrire(p: &std::path::Path, octets: &[u8]) -> std::io::Result<()> {
    if let Some(parent) = p.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)?;
        }
    }
    let mut f = std::fs::File::create(p)?;
    f.write_all(octets)
}

fn ser(v: &json::Valeur) -> String {
    match v {
        json::Valeur::Nul => "null".into(),
        json::Valeur::Bool(b) => b.to_string(),
        // Le nombre ressort TEL QU'IL ÉTAIT ÉCRIT. Le reconvertir depuis un
        // flottant changerait `1000` en `1000.0`, et au-delà de 2^53
        // changerait la valeur.
        json::Valeur::Nombre(n) => n.clone(),
        json::Valeur::Texte(s) => json::echapper(s),
        json::Valeur::Tableau(t) => {
            let v: Vec<String> = t.iter().map(ser).collect();
            format!("[{}]", v.join(", "))
        }
        json::Valeur::Objet(o) => {
            let v: Vec<String> = o
                .iter()
                .map(|(k, x)| format!("{}: {}", json::echapper(k), ser(x)))
                .collect();
            format!("{{{}}}", v.join(", "))
        }
    }
}

fn opt_txt(v: &Option<String>) -> String {
    match v {
        Some(s) => json::echapper(s),
        None => "null".into(),
    }
}

fn rapport_json(r: &verifier::Resultat, verdict: Verdict) -> String {
    let mut s = String::new();
    s.push_str("{\n");
    s.push_str(&format!("  \"schema\": {},\n", json::echapper(c::SCHEMA_RAPPORT)));
    s.push_str(&format!(
        "  \"verifier\": {{\"name\": {}, \"version\": {}, \"language\": \"rust\", \
         \"dependencies\": []}},\n",
        json::echapper(c::NOM_VERIFICATEUR),
        json::echapper(c::VERSION_VERIFICATEUR)
    ));
    s.push_str(&format!("  \"package\": {},\n", json::echapper(&r.paquet)));
    s.push_str(&format!(
        "  \"submission_id\": {},\n",
        opt_txt(&r.submission_id)
    ));
    s.push_str(&format!(
        "  \"submission_schema\": {},\n",
        opt_txt(&r.submission_schema)
    ));
    s.push_str(&format!("  \"verdict\": {},\n", json::echapper(verdict.texte())));
    s.push_str(&format!(
        "  \"counts\": {{\"pass\": {}, \"fail\": {}, \"not_tested\": {}}},\n",
        r.bilan.compte(Etat::Pass),
        r.bilan.compte(Etat::Fail),
        r.bilan.compte(Etat::NonTeste)
    ));
    let requis: Vec<String> = r
        .bilan
        .requis_non_demontres()
        .iter()
        .map(|x| json::echapper(x))
        .collect();
    s.push_str(&format!(
        "  \"required_not_demonstrated\": [{}],\n",
        requis.join(", ")
    ));
    s.push_str(&format!("  \"lines\": {},\n", r.bilan.lignes_json()));

    s.push_str("  \"artifacts\": [");
    for (i, a) in r.artefacts.iter().enumerate() {
        if i > 0 {
            s.push(',');
        }
        s.push_str("\n    {");
        s.push_str(&format!("\"path\": {}, ", json::echapper(&a.chemin)));
        s.push_str(&format!("\"etat\": {}, ", json::echapper(&a.etat)));
        s.push_str(&format!(
            "\"sha256_recomputed\": {}, ",
            opt_txt(&a.sha256_recalcule)
        ));
        s.push_str(&format!(
            "\"sha256_declared\": {}, ",
            opt_txt(&a.sha256_declare)
        ));
        s.push_str(&format!(
            "\"bytes_observed\": {}, ",
            a.octets_reels.map(|x| x.to_string()).unwrap_or("null".into())
        ));
        s.push_str(&format!(
            "\"bytes_declared\": {}, ",
            a.octets_declares.map(|x| x.to_string()).unwrap_or("null".into())
        ));
        s.push_str(&format!("\"role_declared\": {}, ", opt_txt(&a.role_declare)));
        s.push_str(&format!("\"why\": {}", opt_txt(&a.pourquoi)));
        s.push('}');
    }
    s.push_str("\n  ],\n");

    let nd: Vec<String> = r
        .fichiers_non_declares
        .iter()
        .map(|x| json::echapper(x))
        .collect();
    s.push_str(&format!("  \"undeclared_files\": [{}],\n", nd.join(", ")));

    s.push_str("  \"declared_verbatim\": {");
    for (i, (k, v)) in r.declare_verbatim.iter().enumerate() {
        if i > 0 {
            s.push(',');
        }
        s.push_str(&format!("\n    {}: {}", json::echapper(k), ser(v)));
    }
    s.push_str("\n  },\n");

    s.push_str("  \"does_not_establish\": [\n");
    for (i, x) in [
        "Que l execution declaree ait eu lieu. Nous recalculons des empreintes \
         de fichiers, pas des faits.",
        "Qui a produit ce paquet. L identite du soumetteur est declaree, et \
         aucun controle sur des fichiers ne l etablit.",
        "Que les artefacts fournis soient ceux de l execution annoncee. Leur \
         concordance d empreinte etablit qu ils n ont pas bouge depuis que le \
         manifeste a ete ecrit, rien de plus.",
        "La date. `submitted_at_declared` est declaree ; aucune horloge de \
         confiance n intervient, et ce verificateur ne lit jamais la sienne.",
        "Qu une signature soit valide. CE VERIFICATEUR N EN VERIFIE AUCUNE : \
         une signature valide ne dirait pas par qui, et le contrat de \
         soumission ne publie aucune politique de confiance.",
        "Qu un modele ait ou non pris part a l execution. Lorsque \
         `model_declared` est nul, le motif et la note sont la parole du \
         soumetteur.",
    ]
    .iter()
    .enumerate()
    {
        if i > 0 {
            s.push_str(",\n");
        }
        s.push_str(&format!("    {}", json::echapper(x)));
    }
    s.push_str("\n  ]\n}\n");
    s
}

fn rapport_md(r: &verifier::Resultat, verdict: Verdict) -> String {
    let mut l = Vec::new();
    l.push("# Rapport de verification NeoMundi Evidence (Rust)".to_string());
    l.push(String::new());
    l.push(
        "> Second verificateur INDEPENDANT. Aucune dependance, aucun appel a \
         Python,"
            .into(),
    );
    l.push("> aucun service NeoMundi, aucun reseau.".into());
    l.push(String::new());
    l.push("| | |".into());
    l.push("|---|---|".into());
    // Seul le NOM du paquet figure, jamais son chemin de machine.
    let nom = std::path::Path::new(&r.paquet)
        .file_name()
        .map(|s| s.to_string_lossy().to_string())
        .unwrap_or_else(|| r.paquet.clone());
    l.push(format!("| Paquet | `{}` |", nom));
    l.push(format!(
        "| Soumission | `{}` |",
        r.submission_id.clone().unwrap_or_else(|| "aucune".into())
    ));
    l.push(format!(
        "| Contrat declare | `{}` |",
        r.submission_schema.clone().unwrap_or_else(|| "aucun".into())
    ));
    l.push(format!("| Verdict | **{}** |", verdict.texte()));
    l.push(format!(
        "| Decomptes | {} PASS, {} FAIL, {} NOT TESTED |",
        r.bilan.compte(Etat::Pass),
        r.bilan.compte(Etat::Fail),
        r.bilan.compte(Etat::NonTeste)
    ));
    l.push(format!(
        "| Verificateur | `{} {}` (rust, 0 dependance) |",
        c::NOM_VERIFICATEUR,
        c::VERSION_VERIFICATEUR
    ));
    l.push(String::new());
    l.push("## Lignes de controle".into());
    l.push(String::new());
    l.push("| Etat | Nature | Controle | Raison | Detail |".into());
    l.push("|---|---|---|---|---|".into());
    for x in &r.bilan.lignes {
        l.push(format!(
            "| {} | {} | {} | {} | {} |",
            x.etat.texte(),
            x.nature.texte(),
            x.intitule,
            x.raison.map(|r| r.texte()).unwrap_or("-"),
            x.detail.replace('|', "\\|")
        ));
    }
    l.push(String::new());
    l.push("## Artefacts".into());
    l.push(String::new());
    l.push("| Etat | Chemin | Recalcule | Declare | Octets |".into());
    l.push("|---|---|---|---|---|".into());
    for a in &r.artefacts {
        l.push(format!(
            "| {} | `{}` | `{}` | `{}` | {} |",
            a.etat,
            a.chemin,
            a.sha256_recalcule.clone().unwrap_or_else(|| "-".into()),
            a.sha256_declare.clone().unwrap_or_else(|| "-".into()),
            a.octets_reels.map(|x| x.to_string()).unwrap_or_else(|| "-".into())
        ));
    }
    l.push(String::new());
    l.push("## Ce que ce rapport n etablit PAS".into());
    l.push(String::new());
    for x in [
        "Que l execution declaree ait eu lieu.",
        "Qui a produit ce paquet.",
        "La veracite de la date declaree.",
        "**La validite d une signature : ce verificateur n en verifie aucune.**",
        "Qu un modele ait ou non pris part a l execution.",
    ] {
        l.push(format!("- {x}"));
    }
    l.push(String::new());
    l.join("\n")
}
