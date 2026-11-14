//! Outil d'essai : expose `sha256` et `inflate` sur l'entrée standard, pour
//! les comparer à `hashlib` et `zlib`.
//!
//! POURQUOI UN `examples/` ET PAS UN SECOND BINAIRE
//!
//! Un exemple Cargo n'est PAS construit par `cargo build --release` : le
//! binaire livré ne change pas d'un octet du fait de ce fichier. Il est en
//! revanche compilé par `cargo test`, donc il ne peut pas pourrir sans que
//! la suite le dise.
//!
//! POURQUOI IL EXISTE
//!
//! `hashlib` et `zlib` sont des références INDÉPENDANTES de ce dépôt : elles
//! ne partagent pas une ligne avec ce vérificateur. Les comparer exige
//! d'atteindre les primitives, que la ligne de commande n'expose pas -- et
//! c'est tant mieux : un vérificateur de preuve n'a pas à offrir un mode
//! « condense ces octets ».
//!
//! `#[path]` réutilise les MÊMES fichiers que le binaire. Il n'y a pas de
//! copie à faire dériver.
//!
//! Emploi :
//!   banc_primitives sha256  0        < octets   -> condensé hexadécimal
//!   banc_primitives inflate <borne>  < flux     -> condensé de la sortie
//!
//! Le mode `inflate` rend le CONDENSÉ de la sortie, non la sortie : un
//! condensé se compare sans transporter 64 Mio sur un tuyau.

#[path = "../src/inflate.rs"]
mod inflate;
#[path = "../src/sha256.rs"]
mod sha256;

use std::io::Read;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 2 {
        eprintln!("emploi : banc_primitives <sha256|inflate> [borne] < octets");
        std::process::exit(2);
    }
    let mut entree = Vec::new();
    if std::io::stdin().read_to_end(&mut entree).is_err() {
        eprintln!("entree illisible");
        std::process::exit(2);
    }
    let borne: usize = args
        .get(2)
        .and_then(|s| s.parse().ok())
        .unwrap_or(64 * 1024 * 1024);

    match args[1].as_str() {
        "sha256" => {
            let mut h = sha256::Sha256::new();
            h.alimenter(&entree);
            println!("{}", sha256::en_hex(&h.terminer()));
        }
        "inflate" => match inflate::inflate(&entree, borne.max(1)) {
            Ok(sortie) => {
                let mut h = sha256::Sha256::new();
                h.alimenter(&sortie);
                println!("{}", sha256::en_hex(&h.terminer()));
            }
            Err(e) => {
                eprintln!("{e}");
                std::process::exit(1);
            }
        },
        autre => {
            eprintln!("mode inconnu : {autre}");
            std::process::exit(2);
        }
    }
}
