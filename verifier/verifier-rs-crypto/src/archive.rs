//! Le format d'ARCHIVE Evidence — à ne pas confondre avec le conteneur ZIP
//! d'un paquet de soumission.
//!
//! LA DISTINCTION, PARCE QU'ELLE EST FACILE À PERDRE
//!
//! Un **paquet de soumission** (`neomundi.evidence.submission/1` ou `/2`)
//! est ce qu'un tiers nous tend : un `submission.json` et des artefacts dont
//! il déclare les empreintes. C'est le périmètre de `evidence-verify-rs`.
//!
//! Une **archive Evidence** (`station.export.campagne/2`, `/1`, `/3`,
//! `neomundi.evidence.med-demo/1`) est ce que NOUS exportons : un
//! `manifest.json`, un `checksums.sha256`, et des registres `.jsonl` dont les
//! enregistrements se référencent entre eux. C'est le périmètre de ce module.
//!
//! Les deux voyagent dans un ZIP, et c'est tout ce qu'elles ont en commun.
//!
//! CE QUE CE MODULE VÉRIFIE, ET CE QU'IL DÉCLARE HORS DE PORTÉE
//!
//! Il recalcule ce qui est recalculable depuis les octets de l'archive :
//! structure, empreintes des membres, couverture, décomptes du manifeste,
//! références croisées entre registres, absences déclarées. Il **déclare
//! hors de portée** ce qu'une lecture locale ne peut pas établir : le
//! chaînage canonique du registre d'origine, la complétude de l'export, et
//! l'origine comme l'horodatage de l'archive.
//!
//! LES PROTECTIONS DU CŒUR SONT CONSERVÉES, PAS RÉÉCRITES
//!
//! La lecture du ZIP passe par `zip.rs` du cœur, donc l'archive hérite sans
//! un mot de plus de tout ce que la consolidation précédente a corrigé :
//! vérification du CRC-32, comparaison des en-têtes local et central,
//! invariant de la zone du répertoire central (qui ferme la dissimulation de
//! fichier), refus des octets entre répertoire central et EOCD, refus de
//! ZIP64, validation stricte de DEFLATE, bornes de mémoire, et le fait que
//! **rien n'est jamais extrait sur le système de fichiers**.
//!
//! Aucune tolérance précédemment corrigée n'est réintroduite ici : il n'y a
//! pas de second lecteur de ZIP.

use crate::bilan::{Bilan, Etat, Raison};
use crate::bilan_ext::BilanAttestation;
use crate::json::Valeur;
use crate::sha256::{en_hex, Sha256};
use crate::zip::Archive;
use std::collections::{BTreeMap, BTreeSet};

/// Les schémas d'export reconnus, et leurs membres attendus.
///
/// Repris de `verify.py::MEMBRES_PAR_SCHEMA`. `COMPORTEMENT OBSERVÉ` : ces
/// listes ne figurent dans aucun schéma JSON publié — `evidence-manifest-v1`
/// décrit le manifeste, pas la composition de l'archive.
pub const MEMBRES_PAR_SCHEMA: [(&str, &[&str]); 4] = [
    (
        "station.export.campagne/1",
        &[
            "observations.csv",
            "observations.jsonl",
            "manifest.json",
            "rapport.md",
            "checksums.sha256",
        ],
    ),
    (
        "station.export.campagne/2",
        &[
            "observations.csv",
            "observations.jsonl",
            "measurements.jsonl",
            "reference_evaluations.jsonl",
            "replay_provenance.jsonl",
            "manifest.json",
            "rapport.md",
            "checksums.sha256",
        ],
    ),
    (
        "station.export.campagne/3",
        &[
            "observations.csv",
            "observations.jsonl",
            "measurements.jsonl",
            "measurement_coverage.jsonl",
            "reference_evaluations.jsonl",
            "replay_provenance.jsonl",
            "manifest.json",
            "rapport.md",
            "checksums.sha256",
        ],
    ),
    (
        "neomundi.evidence.med-demo/1",
        &[
            "observations.jsonl",
            "measurements.jsonl",
            "manifest.json",
            "report.md",
            "checksums.sha256",
        ],
    ),
];

/// Les registres dont les enregistrements se réfèrent aux observations, et
/// le champ du manifeste qui en annonce le décompte.
const REGISTRES_LIES: [(&str, &str); 3] = [
    ("measurements.jsonl", "mesures"),
    ("reference_evaluations.jsonl", "evaluations"),
    ("replay_provenance.jsonl", "provenances_de_rejeu"),
];

/// Borne du nombre de lignes d'un registre. Non contractuelle.
pub const LIGNES_MAX: usize = 1_000_000;

fn txt<'a>(o: &'a BTreeMap<String, Valeur>, c: &str) -> Option<&'a str> {
    o.get(c).and_then(|v| v.comme_texte())
}

fn objet<'a>(o: &'a BTreeMap<String, Valeur>, c: &str) -> Option<&'a BTreeMap<String, Valeur>> {
    match o.get(c) {
        Some(Valeur::Objet(m)) => Some(m),
        _ => None,
    }
}

fn sha(octets: &[u8]) -> String {
    let mut h = Sha256::new();
    h.alimenter(octets);
    en_hex(&h.terminer())
}

/// Un enregistrement de registre, réduit à ce dont les contrôles ont besoin.
struct Enregistrement {
    record_id: Option<String>,
    observation_ref: Option<String>,
}

/// Lit un `.jsonl` : une valeur JSON par ligne non vide.
///
/// Les lignes vides sont ignorées, comme chez Python. Une ligne illisible
/// est une faute NOMMÉE avec son numéro : « le registre est illisible » sans
/// dire où n'aide personne.
fn lire_jsonl(octets: &[u8]) -> Result<Vec<BTreeMap<String, Valeur>>, String> {
    let mut out = Vec::new();
    for (n, ligne) in octets.split(|&c| c == b'\n').enumerate() {
        let ligne = if ligne.last() == Some(&b'\r') {
            &ligne[..ligne.len() - 1]
        } else {
            ligne
        };
        if ligne.iter().all(|c| c.is_ascii_whitespace()) {
            continue;
        }
        if out.len() >= LIGNES_MAX {
            return Err(format!("plus de {LIGNES_MAX} lignes : refuse"));
        }
        match crate::json::analyser(ligne) {
            Ok(Valeur::Objet(o)) => out.push(o),
            Ok(autre) => {
                return Err(format!(
                    "ligne {} : attendu un objet JSON, lu un {}",
                    n + 1,
                    autre.nom_du_type()
                ))
            }
            Err(e) => return Err(format!("ligne {} : {e}", n + 1)),
        }
    }
    Ok(out)
}

/// Extrait `(identifiant d observation, reference a une observation)`.
///
/// LE CHAMP DE LIAISON EST `payload.observation_id`, ET RIEN D AUTRE.
///
/// CORRECTION. Une premiere version lisait l identifiant sous
/// `integrity.record_id` et cherchait la reference sous
/// `payload.observation_record_id`. Le banc differentiel a montre que ce
/// second champ **n existe pas** dans le format : il vaut `null` dans
/// l archive reelle. En alterant un champ inexistant, le banc fabriquait un
/// orphelin que Rust voyait et que Python ignorait -- une divergence
/// entierement due au champ que j avais invente.
///
/// `verify.py` emploie `payload.observation_id` des deux cotes de la
/// relation, et c est ce que les octets de l archive portent
/// effectivement. Ce module s y aligne : non pour obtenir un accord, mais
/// parce que c est le champ du modele de donnees.
///
/// `integrity.record_id` existe aussi et vaut la meme chose dans l archive
/// de reference. Il n est PAS employe ici : deux chemins vers la meme
/// relation finiraient par divergir, et c est `payload.observation_id` que
/// le verificateur de reference lit.
fn reduire(o: &BTreeMap<String, Valeur>) -> Enregistrement {
    let p = objet(o, "payload");
    let observation_id = p
        .and_then(|p| txt(p, "observation_id"))
        .map(str::to_string);
    Enregistrement {
        record_id: observation_id.clone(),
        observation_ref: observation_id,
    }
}

pub struct Rapport {
    pub schema: Option<String>,
    pub empreinte_archive: String,
    pub membres: Vec<String>,
    /// Les empreintes RECALCULEES des membres, par nom.
    ///
    /// Elles servent a la concordance d une attestation : `subject`
    /// declare `manifest_sha256` et `checksums_sha256` en plus de
    /// `bundle_sha256`, et les trois doivent etre confrontees. Sans elles,
    /// la concordance ne verifiait qu un tiers de ce qu elle annonce.
    pub empreintes_membres: BTreeMap<String, String>,
}

/// Vérifie une archive Evidence, EN MÉMOIRE, sans rien extraire.
pub fn verifier(octets_archive: &[u8], b: &mut Bilan) -> Rapport {
    let empreinte_archive = sha(octets_archive);
    let mut r = Rapport {
        schema: None,
        empreinte_archive: empreinte_archive.clone(),
        membres: Vec::new(),
        empreintes_membres: BTreeMap::new(),
    };

    // ---- 1. le ZIP, par le lecteur DURCI du cœur -------------------------
    let a = match Archive::ouvrir(octets_archive.to_vec()) {
        Ok(a) => a,
        Err(refus) => {
            b.controle(Etat::Fail, "integrite interne du ZIP", &refus.0);
            return r;
        }
    };
    let noms: Vec<String> = a.fichiers().iter().map(|s| s.to_string()).collect();
    r.membres = noms.clone();
    // LES EMPREINTES DE TOUS LES MEMBRES, et non seulement de ceux que
    // `checksums.sha256` declare.
    //
    // Il ne se declare PAS lui-meme -- c est la nature d un fichier de
    // sommes --, or une attestation declare `checksums_sha256`. Une premiere
    // version ne remplissait cette table qu au fil des lignes de
    // `checksums.sha256`, et la concordance de l attestation REELLE du depot
    // echouait donc sur un membre qu elle n avait jamais hache. Trouve par
    // le banc differentiel, sur la fixture du depot.
    for m in &a.membres {
        if m.nom.ends_with('/') {
            continue;
        }
        if let Ok(o) = a.lire(m) {
            r.empreintes_membres.insert(m.nom.clone(), sha(&o));
        }
    }
    b.controle(
        Etat::Pass,
        "integrite interne du ZIP",
        &format!(
            "{} membre(s), CRC-32 et en-tetes locaux verifies par le lecteur \
             du coeur, lus EN MEMOIRE, aucune extraction",
            noms.len()
        ),
    );

    // ---- 2. aucun membre ne sort du repertoire cible ---------------------
    let mut dangereux: Vec<String> = Vec::new();
    for n in &noms {
        if let Err(pourquoi) = crate::chemins::chemin_sur(n) {
            dangereux.push(format!("{n} ({pourquoi})"));
        }
    }
    if dangereux.is_empty() {
        b.controle(
            Etat::Pass,
            "aucun membre ne sort du repertoire cible",
            &format!("{} membre(s), tous relatifs et sans remontee", noms.len()),
        );
    } else {
        b.controle(
            Etat::Fail,
            "aucun membre ne sort du repertoire cible",
            &dangereux.join(" ; "),
        );
        return r;
    }

    // ---- 3. le manifeste -------------------------------------------------
    let Some(m_membre) = a.trouver("manifest.json") else {
        b.controle(
            Etat::Fail,
            "manifest.json present",
            "membre absent : sans manifeste, il n y a pas d archive Evidence",
        );
        return r;
    };
    let octets_m = match a.lire(m_membre) {
        Ok(o) => o,
        Err(e) => {
            b.controle(Etat::Fail, "manifest.json lisible", &e.0);
            return r;
        }
    };
    let manifeste = match crate::json::analyser(&octets_m) {
        Ok(Valeur::Objet(o)) => o,
        Ok(autre) => {
            b.controle(
                Etat::Fail,
                "manifest.json lisible",
                &format!("attendu un objet JSON, lu un {}", autre.nom_du_type()),
            );
            return r;
        }
        Err(e) => {
            b.controle(
                Etat::Fail,
                "manifest.json lisible",
                &format!("JSON illisible : {e}"),
            );
            return r;
        }
    };

    let schema = txt(&manifeste, "schema").unwrap_or("").to_string();
    let attendus = MEMBRES_PAR_SCHEMA
        .iter()
        .find(|(s, _)| *s == schema)
        .map(|(_, m)| *m);
    let Some(attendus) = attendus else {
        b.controle(
            Etat::Fail,
            "schema d export reconnu",
            &format!(
                "schema {schema:?} inconnu ; connus : {}",
                MEMBRES_PAR_SCHEMA
                    .iter()
                    .map(|(s, _)| *s)
                    .collect::<Vec<_>>()
                    .join(", ")
            ),
        );
        return r;
    };
    r.schema = Some(schema.clone());

    let presents: BTreeSet<&str> = noms.iter().map(|s| s.as_str()).collect();
    let manquants: Vec<&str> = attendus
        .iter()
        .copied()
        .filter(|m| !presents.contains(m))
        .collect();
    let surplus: Vec<&str> = noms
        .iter()
        .map(|s| s.as_str())
        .filter(|n| !attendus.contains(n))
        .collect();
    if manquants.is_empty() {
        b.controle(
            Etat::Pass,
            &format!("membres attendus par le schema {schema}"),
            &if surplus.is_empty() {
                format!("les {} membres du schema sont presents", attendus.len())
            } else {
                format!("membres en surplus : {surplus:?}")
            },
        );
    } else {
        b.controle(
            Etat::Fail,
            &format!("membres attendus par le schema {schema}"),
            &format!("manquants : {manquants:?}"),
        );
    }

    // ---- 4. checksums.sha256 : les deux sens ----------------------------
    //
    // Les DEUX sens comptent, et les confondre laisserait un trou :
    //   - une empreinte annoncee doit correspondre au membre ;
    //   - tout membre doit etre COUVERT par une empreinte.
    // Le second attrape un fichier glisse dans l archive apres l export.
    let Some(c_membre) = a.trouver("checksums.sha256") else {
        b.controle(Etat::Fail, "checksums.sha256 present", "membre absent");
        return r;
    };
    let octets_c = match a.lire(c_membre) {
        Ok(o) => o,
        Err(e) => {
            b.controle(Etat::Fail, "checksums.sha256 lisible", &e.0);
            return r;
        }
    };
    let texte_c = match std::str::from_utf8(&octets_c) {
        Ok(t) => t,
        Err(_) => {
            b.controle(
                Etat::Fail,
                "checksums.sha256 lisible",
                "le fichier d empreintes n est pas de l UTF-8 valide",
            );
            return r;
        }
    };
    let mut declares: BTreeMap<String, String> = BTreeMap::new();
    let mut malformees: Vec<String> = Vec::new();
    for (n, ligne) in texte_c.lines().enumerate() {
        if ligne.trim().is_empty() {
            continue;
        }
        // Le format est celui de `sha256sum` : 64 caracteres, DEUX espaces,
        // le nom. Accepter un seul espace laisserait deux ecritures.
        match ligne.split_once("  ") {
            Some((e, nom)) if e.len() == 64 && e.bytes().all(|c| c.is_ascii_hexdigit()) => {
                if declares.insert(nom.to_string(), e.to_ascii_lowercase()).is_some() {
                    malformees.push(format!("ligne {} : {nom} declare DEUX fois", n + 1));
                }
            }
            _ => malformees.push(format!("ligne {} : forme inattendue", n + 1)),
        }
    }
    if !malformees.is_empty() {
        b.controle(
            Etat::Fail,
            "checksums.sha256 bien forme",
            &malformees[..malformees.len().min(5)].join(" ; "),
        );
        return r;
    }

    let mut divergents: Vec<String> = Vec::new();
    let mut annonces_absents: Vec<String> = Vec::new();
    for (nom, attendu) in &declares {
        match a.trouver(nom) {
            None => annonces_absents.push(nom.clone()),
            Some(m) => match a.lire(m) {
                Err(e) => divergents.push(format!("{nom} (illisible : {})", e.0)),
                Ok(o) => {
                    let reel = sha(&o);
                    r.empreintes_membres.insert(nom.clone(), reel.clone());
                    if &reel != attendu {
                        divergents.push(format!(
                            "{nom} (declare {}..., recalcule {}...)",
                            &attendu[..16],
                            &reel[..16]
                        ));
                    }
                }
            },
        }
    }
    if divergents.is_empty() && annonces_absents.is_empty() {
        b.controle(
            Etat::Pass,
            &format!("empreintes des {} membres declares", declares.len()),
            "toutes recalculees depuis les octets de l archive",
        );
    } else {
        b.controle(
            Etat::Fail,
            &format!("empreintes des {} membres declares", declares.len()),
            &format!(
                "divergents : {} ; annonces et absents : {}",
                if divergents.is_empty() {
                    "aucun".into()
                } else {
                    divergents.join(", ")
                },
                if annonces_absents.is_empty() {
                    "aucun".into()
                } else {
                    annonces_absents.join(", ")
                }
            ),
        );
    }

    let non_couverts: Vec<&str> = noms
        .iter()
        .map(|s| s.as_str())
        .filter(|n| *n != "checksums.sha256" && !declares.contains_key(*n))
        .collect();
    if non_couverts.is_empty() {
        b.controle(
            Etat::Pass,
            "chaque membre est couvert par une empreinte",
            "aucun membre hors du fichier d empreintes",
        );
    } else {
        b.controle(
            Etat::Fail,
            "chaque membre est couvert par une empreinte",
            &format!(
                "{} membre(s) sans empreinte declaree : {non_couverts:?}. Un \
                 fichier glisse apres l export se verrait ici",
                non_couverts.len()
            ),
        );
    }

    // ---- 5. les decomptes et les references croisees --------------------
    let decomptes = objet(&manifeste, "decomptes");
    let lire_registre = |nom: &str| -> Option<Vec<BTreeMap<String, Valeur>>> {
        a.trouver(nom)
            .and_then(|m| a.lire(m).ok())
            .and_then(|o| lire_jsonl(&o).ok())
    };

    let observations = lire_registre("observations.jsonl");
    let ids_observations: BTreeSet<String> = match &observations {
        Some(v) => v
            .iter()
            .filter_map(|o| reduire(o).record_id)
            .collect(),
        None => BTreeSet::new(),
    };

    match (&observations, decomptes.and_then(|d| d.get("observations"))) {
        (Some(v), Some(Valeur::Nombre(n))) => {
            let annonce = n.parse::<usize>().ok();
            if annonce == Some(v.len()) {
                b.controle(
                    Etat::Pass,
                    &format!("le manifeste compte les observations livrees ({})", v.len()),
                    "decompte annonce et lignes livrees concordent",
                );
            } else {
                b.controle(
                    Etat::Fail,
                    "le manifeste compte les observations livrees",
                    &format!("annonce {n}, livrees {}", v.len()),
                );
            }
        }
        (Some(v), _) => b.controle(
            Etat::Fail,
            "le manifeste compte les observations livrees",
            &format!(
                "`decomptes.observations` absent ou non entier, {} ligne(s) livrees",
                v.len()
            ),
        ),
        (None, _) => b.controle(
            Etat::Fail,
            "observations.jsonl lisible",
            "registre absent ou illisible",
        ),
    }

    for (fichier, champ) in REGISTRES_LIES {
        if !attendus.contains(&fichier) {
            continue;
        }
        let Some(lignes) = lire_registre(fichier) else {
            b.controle(
                Etat::Fail,
                &format!("{fichier} lisible"),
                "registre absent ou illisible",
            );
            continue;
        };
        match decomptes.and_then(|d| d.get(champ)) {
            Some(Valeur::Nombre(n)) if n.parse::<usize>().ok() == Some(lignes.len()) => {
                b.controle(
                    Etat::Pass,
                    &format!(
                        "le manifeste compte les enregistrements de {fichier} ({})",
                        lignes.len()
                    ),
                    "decompte annonce et lignes livrees concordent",
                );
            }
            Some(Valeur::Nombre(n)) => b.controle(
                Etat::Fail,
                &format!("le manifeste compte les enregistrements de {fichier}"),
                &format!("annonce {n}, livrees {}", lignes.len()),
            ),
            _ => b.controle(
                Etat::Fail,
                &format!("le manifeste compte les enregistrements de {fichier}"),
                &format!("`decomptes.{champ}` absent ou non entier"),
            ),
        }

        // ORPHELINS : un enregistrement qui se réfère à une observation
        // absente. C'est la cohérence interne des références, et elle est
        // recalculable — donc elle doit l'être.
        let orphelins: Vec<String> = lignes
            .iter()
            .map(reduire)
            .filter_map(|e| {
                let r = e.observation_ref?;
                if ids_observations.contains(&r) {
                    None
                } else {
                    Some(r)
                }
            })
            .collect();
        let sans_reference = lignes
            .iter()
            .map(reduire)
            .filter(|e| e.observation_ref.is_none())
            .count();
        if orphelins.is_empty() && sans_reference == 0 {
            b.controle(
                Etat::Pass,
                &format!("aucun orphelin dans {fichier}"),
                &format!(
                    "{} enregistrement(s), tous rattaches a une observation livree",
                    lignes.len()
                ),
            );
        } else if !orphelins.is_empty() {
            b.controle(
                Etat::Fail,
                &format!("aucun orphelin dans {fichier}"),
                &format!(
                    "{} enregistrement(s) referencent une observation absente : {:?}",
                    orphelins.len(),
                    &orphelins[..orphelins.len().min(3)]
                ),
            );
        } else {
            b.controle(
                Etat::Fail,
                &format!("aucun orphelin dans {fichier}"),
                &format!(
                    "{sans_reference} enregistrement(s) ne referencent aucune \
                     observation : le rattachement ne peut pas etre verifie"
                ),
            );
        }
    }

    // ---- 6. les absences declarees sont reelles -------------------------
    //
    // L EGALITE D ENSEMBLES, ET NON UNE INCLUSION.
    //
    // La regle est : l ensemble des observations NON COUVERTES par un
    // registre doit etre EXACTEMENT celui que le manifeste declare. Les deux
    // sens comptent :
    //
    //   - une absence DECLAREE que le registre contredit est une fausse
    //     declaration ;
    //   - une absence CONSTATEE et NON declaree est un trou : le manifeste
    //     affirme une couverture qu il n a pas.
    //
    // CORRECTION. Une premiere version ne verifiait que le premier sens. Le
    // banc differentiel l a vu : sur une archive ou une mesure pointe vers
    // une observation inexistante -- donc ou une observation perd sa
    // mesure --, Python rendait `FAIL` et ce module `PASS`. Un controle
    // nomme << les absences declarees sont reelles >> qui ne regarde qu une
    // moitie de la relation est un controle trompeur.
    if let Some(abs) = objet(&manifeste, "absences") {
        let mut ecarts: Vec<String> = Vec::new();
        for (champ, fichier) in [
            ("observations_sans_mesure", "measurements.jsonl"),
            ("observations_sans_evaluation", "reference_evaluations.jsonl"),
        ] {
            if !presents.contains(fichier) {
                continue;
            }
            let couvertes: BTreeSet<String> = lire_registre(fichier)
                .map(|v| v.iter().filter_map(|o| reduire(o).observation_ref).collect())
                .unwrap_or_default();
            let constatees: BTreeSet<String> = ids_observations
                .difference(&couvertes)
                .cloned()
                .collect();
            let declarees: BTreeSet<String> = match abs.get(champ) {
                Some(Valeur::Tableau(t)) => {
                    t.iter().filter_map(|v| v.comme_texte()).map(str::to_string).collect()
                }
                _ => BTreeSet::new(),
            };
            if constatees != declarees {
                let manquantes: Vec<&String> =
                    constatees.difference(&declarees).take(3).collect();
                let en_trop: Vec<&String> =
                    declarees.difference(&constatees).take(3).collect();
                ecarts.push(format!(
                    "{champ} : {} constatee(s) non declaree(s) {manquantes:?}, \
                     {} declaree(s) que {fichier} contredit {en_trop:?}",
                    constatees.difference(&declarees).count(),
                    declarees.difference(&constatees).count()
                ));
            }
        }
        if ecarts.is_empty() {
            b.controle(
                Etat::Pass,
                "les absences declarees sont reelles",
                "l ensemble des observations non couvertes est EXACTEMENT \
                 celui que le manifeste declare, dans les deux sens",
            );
        } else {
            b.controle(
                Etat::Fail,
                "les absences declarees sont reelles",
                &ecarts.join(" ; "),
            );
        }
    } else {
        b.hors_portee(
            "les absences declarees sont reelles",
            Raison::NonApplicable,
            "le manifeste ne declare aucune rubrique d absences",
        );
    }

    // ---- 7. bundle_sha256 re-derive -------------------------------------
    //
    // L EMPREINTE DE L ARCHIVE est celle de ses octets. C est elle qu une
    // attestation declare, et c est elle que la concordance compare.
    b.controle(
        Etat::Pass,
        "empreinte de l archive recalculee",
        &format!("{}", empreinte_archive),
    );

    // ---- 8. les trois lignes HORS DE PORTEE, declarees ------------------
    //
    // Elles sont NOT TESTED chez Python aussi, pour les memes raisons. Les
    // rendre PASS demanderait soit une seconde implementation du registre
    // (ce qui ferait exactement le bug que ce dispositif cherche a eviter),
    // soit une information qui n est pas dans l archive.
    let registre = objet(&manifeste, "registre");
    let tete = registre
        .and_then(|r| txt(r, "empreinte_de_tete"))
        .unwrap_or("non declaree");
    b.hors_portee(
        "chainage canonique du registre d origine",
        Raison::HorsPortee,
        &format!(
            "hors de portee : le recalculer ici serait une SECONDE \
             implementation du chainage du registre, et deux implementations \
             du meme profil de canonicalisation divergeraient un jour sur un \
             cas rare -- la classe de bug la plus pernicieuse de ce \
             dispositif. L archive declare une empreinte de tete {}... A \
             confronter avec : station ledger verify --path <registre>",
            &tete[..tete.len().min(16)]
        ),
    );
    let a_contrat = registre
        .map(|r| {
            r.contains_key("enregistrements_exportes") && r.contains_key("types_exclus")
        })
        .unwrap_or(false);
    if a_contrat {
        b.hors_portee(
            "completude de l export",
            Raison::HorsPortee,
            "l archive declare un contrat de completude ; ce verificateur ne \
             le confronte pas encore a une source exterieure.",
        );
    } else {
        b.hors_portee(
            "completude de l export",
            Raison::HorsPortee,
            "l archive ne declare pas de contrat de completude : il lui manque \
             `registre.enregistrements_exportes` et `registre.types_exclus`. \
             Son integrite interne peut etre entiere et son export PARTIEL -- \
             une chaine valide ne dit rien de ce qui n a pas ete exporte.",
        );
    }
    b.hors_portee(
        "origine et horodatage de l archive",
        Raison::HorsPortee,
        "hors de portee de toute verification locale : aucune signature \
         tierce, aucun ancrage exterieur. Une attestation detachee peut \
         etablir une signature sur l empreinte de cette archive -- la \
         fournir a ce programme avec l attestation.",
    );

    r
}
