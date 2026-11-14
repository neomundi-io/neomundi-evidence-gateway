//! Modules 2, 3 et 5 — validation structurelle, intégrité, attestations.
//!
//! L'ORCHESTRATION, ET SON ORDRE
//!
//!   1. forme du paquet        dossier ou ZIP lisible
//!   2. chemins du paquet      TOUS les membres, déclarés ou non
//!   3. manifeste              présent, lisible, schéma connu
//!   4. champs obligatoires    et champs hors contrat, NOMMÉS
//!   5. identifiant, date      forme publiée
//!   6. identité du soumetteur DECLARE, jamais contrôlée
//!   7. conditions d'exécution nature, modèle, motif d'absence
//!   8. artefacts              empreintes RECALCULÉES, tailles, rôles
//!   9. fichiers non déclarés  NOMMÉS, jamais avalés
//!  10. attestations           détectées, et NON vérifiées
//!  11. provenance, limites    DECLARE
//!  12. que l'exécution ait eu lieu   NON DEMONTRABLE
//!
//! Chaque étape produit sa ou ses lignes. Aucune n'est silencieuse.

use crate::bilan::{Bilan, Etat, Nature, Raison};
use crate::chemins;
use crate::contrat as c;
use crate::json::{self, Valeur};
use crate::sha256::Sha256;
use crate::zip::Archive;
use std::collections::BTreeMap;
use std::path::Path;

/// La source des octets d'un paquet : un dossier, ou une archive en mémoire.
enum Source {
    Dossier(std::path::PathBuf),
    Zip(Archive),
}

pub struct Artefact {
    pub chemin: String,
    pub etat: String,
    pub sha256_recalcule: Option<String>,
    pub sha256_declare: Option<String>,
    pub octets_reels: Option<u64>,
    pub octets_declares: Option<i64>,
    pub role_declare: Option<String>,
    pub pourquoi: Option<String>,
}

pub struct Resultat {
    pub bilan: Bilan,
    pub paquet: String,
    pub submission_id: Option<String>,
    pub submission_schema: Option<String>,
    pub artefacts: Vec<Artefact>,
    pub fichiers_non_declares: Vec<String>,
    pub declare_verbatim: BTreeMap<String, Valeur>,
}

/// Une erreur d'EXÉCUTION du programme, à ne pas confondre avec un verdict
/// de vérification. Un fichier illisible n'est pas un paquet refusé.
#[derive(Debug)]
pub struct ErreurExecution(pub String);

impl std::fmt::Display for ErreurExecution {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.0)
    }
}

pub fn verifier(paquet: &Path) -> Result<Resultat, ErreurExecution> {
    let mut b = Bilan::new();
    let mut r = Resultat {
        bilan: Bilan::new(),
        paquet: paquet.display().to_string(),
        submission_id: None,
        submission_schema: None,
        artefacts: Vec::new(),
        fichiers_non_declares: Vec::new(),
        declare_verbatim: BTreeMap::new(),
    };

    // ---- 1. forme du paquet ------------------------------------------
    let source = if paquet.is_dir() {
        b.controle(
            Etat::Pass,
            "forme du paquet",
            "dossier lu sur place, aucune extraction",
        );
        Source::Dossier(paquet.to_path_buf())
    } else {
        // LA TAILLE EST LUE AVANT LE FICHIER.
        //
        // Les bornes du module ZIP s'appliquent au répertoire central, donc
        // après ce `read`. Sans ce contrôle, un fichier de plusieurs
        // gigaoctets n'était pas refusé : il faisait échouer l'allocation,
        // et `panic = "abort"` rendait le code 134 -- hors du contrat de
        // sortie. Un paquet trop gros doit être un REFUS, pas un abandon.
        match std::fs::metadata(paquet) {
            Ok(m) if m.len() > c::PAQUET_OCTETS_MAX => {
                b.controle(
                    Etat::Fail,
                    "forme du paquet",
                    &format!(
                        "fichier de {} octets, borne {}. Refuse AVANT lecture :                          un paquet de soumission n a pas cette taille",
                        m.len(),
                        c::PAQUET_OCTETS_MAX
                    ),
                );
                return Ok(finir(r, b));
            }
            Ok(_) => {}
            Err(e) => {
                return Err(ErreurExecution(format!("paquet illisible : {e}")))
            }
        }
        let octets = std::fs::read(paquet).map_err(|e| {
            ErreurExecution(format!("paquet illisible : {e}"))
        })?;
        match Archive::ouvrir(octets) {
            Ok(a) => {
                let n = a.fichiers().len();
                b.controle(
                    Etat::Pass,
                    "forme du paquet",
                    &format!(
                        "archive ZIP de {n} membre(s), lue EN MEMOIRE, aucune \
                         extraction sur le systeme de fichiers"
                    ),
                );
                Source::Zip(a)
            }
            Err(refus) => {
                b.controle(Etat::Fail, "forme du paquet", &refus.0);
                return Ok(finir(r, b));
            }
        }
    };

    // ---- 2. chemins du paquet : TOUS les membres ---------------------
    // Un membre dangereux ne doit pas pouvoir entrer, même si le manifeste
    // ne le nomme jamais.
    if let Source::Zip(a) = &source {
        let mauvais: Vec<String> = a
            .membres
            .iter()
            .filter_map(|m| {
                chemins::membre_sur(&m.nom)
                    .err()
                    .map(|p| format!("{:?} : {p}", m.nom))
            })
            .collect();
        if !mauvais.is_empty() {
            b.controle(
                Etat::Fail,
                "chemins du paquet",
                &format!(
                    "{} membre(s) refuse(s) : {}",
                    mauvais.len(),
                    mauvais
                        .iter()
                        .take(6)
                        .cloned()
                        .collect::<Vec<_>>()
                        .join(" ; ")
                ),
            );
            return Ok(finir(r, b));
        }
        b.controle(
            Etat::Pass,
            "chemins du paquet",
            &format!("{} membre(s), tous relatifs et sans remontee", a.membres.len()),
        );
    }

    // ---- 3. manifeste ------------------------------------------------
    let octets_manifeste = match lire(&source, c::MANIFESTE) {
        Ok(Some(o)) => o,
        Ok(None) => {
            b.controle(
                Etat::Fail,
                "manifeste de soumission",
                &format!("`{}` absent a la racine du paquet", c::MANIFESTE),
            );
            return Ok(finir(r, b));
        }
        Err(e) => {
            b.controle(Etat::Fail, "manifeste de soumission", &e);
            return Ok(finir(r, b));
        }
    };
    let doc = match json::analyser(&octets_manifeste) {
        Ok(Valeur::Objet(o)) => o,
        Ok(autre) => {
            b.controle(
                Etat::Fail,
                "manifeste de soumission",
                &format!(
                    "le manifeste n est pas un objet JSON (lu : {})",
                    autre.nom_du_type()
                ),
            );
            return Ok(finir(r, b));
        }
        Err(e) => {
            b.controle(
                Etat::Fail,
                "manifeste de soumission",
                &format!("`{}` illisible : {e}", c::MANIFESTE),
            );
            return Ok(finir(r, b));
        }
    };

    let version = match doc.get("schema").and_then(|v| v.comme_texte()) {
        Some(s) if s == c::SCHEMA_V1 || s == c::SCHEMA_V2 => s.to_string(),
        autre => {
            b.controle(
                Etat::Fail,
                "schema du manifeste",
                &format!(
                    "attendu `{}` ou `{}`, declare {:?}",
                    c::SCHEMA_V1,
                    c::SCHEMA_V2,
                    autre.unwrap_or("<absent ou non textuel>")
                ),
            );
            return Ok(finir(r, b));
        }
    };
    r.submission_schema = Some(version.clone());
    b.controle(
        Etat::Pass,
        "manifeste de soumission",
        &format!("{version}, {} octets", octets_manifeste.len()),
    );

    // ---- 4. champs obligatoires, et champs hors contrat -------------
    let manquants: Vec<&str> = c::CHAMPS_REQUIS
        .iter()
        .copied()
        .filter(|k| !doc.contains_key(*k))
        .collect();
    if manquants.is_empty() {
        b.controle(
            Etat::Pass,
            "champs obligatoires",
            &format!("les {} champs du contrat sont presents", c::CHAMPS_REQUIS.len()),
        );
    } else {
        b.controle(
            Etat::Fail,
            "champs obligatoires",
            &format!("absents : {}", manquants.join(", ")),
        );
    }
    dire_surplus(&mut b, "champs du manifeste hors contrat", &doc, &c::CHAMPS_CONNUS);

    // ---- 5. identifiant et date -------------------------------------
    match doc.get("submission_id").and_then(|v| v.comme_texte()) {
        Some(s) if c::identifiant_bien_forme(s) => {
            r.submission_id = Some(s.to_string());
            b.controle(Etat::Pass, "identifiant de soumission", s);
        }
        autre => b.controle(
            Etat::Fail,
            "identifiant de soumission",
            &format!(
                "non conforme a `^[a-z0-9][a-z0-9-]{{2,63}}$` : {:?}",
                autre.unwrap_or("<absent ou non textuel>")
            ),
        ),
    }
    if let Some(v) = doc.get("submitted_at_declared") {
        match v.comme_texte() {
            Some(s) if c::instant_bien_forme(s) => {}
            _ => b.controle(
                Etat::Fail,
                "date declaree",
                &format!(
                    "`submitted_at_declared` = {} : le contrat exige UTC a la \
                     seconde, avec `Z` final. Sa VERACITE reste hors de portee ; \
                     sa FORME, non.",
                    bref(v)
                ),
            ),
        }
    }

    // ---- 6. identité du soumetteur : DECLARE ------------------------
    match doc.get("pilot") {
        None | Some(Valeur::Nul) => b.controle(
            Etat::Fail,
            "identite du soumetteur",
            "`pilot.name_declared` absent ou vide",
        ),
        Some(Valeur::Objet(p)) => {
            dire_surplus(&mut b, "champs de pilote hors contrat", p, &c::CHAMPS_PILOTE);
            match p.get("name_declared").and_then(|v| v.comme_texte()) {
                Some(n) if c::porte_un_non_blanc(n) => b.non_teste(
                    Nature::Declare,
                    "identite du soumetteur",
                    &format!(
                        "{n:?} -- declaree, et non verifiee. Aucun controle sur \
                         un paquet ne peut etablir qui l a produit."
                    ),
                    Raison::Declaration,
                    false,
                ),
                _ => b.controle(
                    Etat::Fail,
                    "identite du soumetteur",
                    "`pilot.name_declared` absent ou vide",
                ),
            }
        }
        Some(_) => b.controle(
            Etat::Fail,
            "identite du soumetteur",
            "`pilot` n est pas un objet JSON",
        ),
    }

    // ---- 7. conditions d'exécution ----------------------------------
    controle_execution(&mut b, &doc, &version);

    // ---- 8. artefacts : les empreintes RECALCULÉES ------------------
    controle_artefacts(&mut b, &mut r, &source, &doc);

    // ---- 9. fichiers non déclarés -----------------------------------
    controle_non_declares(&mut b, &mut r, &source, &doc);

    // ---- 10. attestations : détectées, NON vérifiées ----------------
    controle_attestations(&mut b, &doc);

    // ---- 11. provenance et limites : DECLARE ------------------------
    controle_provenance(&mut b, &doc);

    // ---- 12. ce qu'aucun contrôle ne pourrait établir ---------------
    b.non_teste(
        Nature::NonDemontrable,
        "que l execution ait eu lieu",
        "hors de portee d une verification de paquet. Nous recalculons des \
         empreintes de FICHIERS ; qu ils proviennent de l execution annoncee \
         est une declaration, et le restera.",
        Raison::HorsPortee,
        false,
    );

    for k in [
        "pilot",
        "execution",
        "provenance_declared",
        "limits_declared",
        "submitted_at_declared",
    ] {
        if let Some(v) = doc.get(k) {
            r.declare_verbatim.insert(k.to_string(), v.clone());
        }
    }
    Ok(finir(r, b))
}

fn finir(mut r: Resultat, b: Bilan) -> Resultat {
    r.bilan = b;
    r
}

fn bref(v: &Valeur) -> String {
    match v {
        Valeur::Texte(s) => format!("{s:?}"),
        Valeur::Nombre(n) => n.clone(),
        Valeur::Nul => "null".into(),
        Valeur::Bool(x) => x.to_string(),
        autre => format!("<{}>", autre.nom_du_type()),
    }
}

/// Nomme les champs hors contrat. Ne refuse PAS.
///
/// `additionalProperties: false` est la lettre du schéma, et la refuser
/// serait défendable. L'implémentation Python a tranché autrement -- un
/// champ en surplus n'invalide rien, et le refuser romprait un paquet que
/// le contrat précédent acceptait -- mais le TAIRE laisserait croire qu'il
/// a été lu.
///
/// **DIVERGENCE ASSUMÉE avec le schéma, et concordante avec Python.**
/// Elle est nommée ici, dans `04_MATRICE_PYTHON_RUST.md`, et dans le
/// rapport lui-même. Une divergence nommée est une politique ; une
/// divergence inconnue serait le défaut.
fn dire_surplus(
    b: &mut Bilan,
    intitule: &str,
    objet: &BTreeMap<String, Valeur>,
    connus: &[&str],
) {
    let surplus: Vec<&str> = objet
        .keys()
        .map(|s| s.as_str())
        .filter(|k| !connus.contains(k))
        .collect();
    if !surplus.is_empty() {
        b.non_teste(
            Nature::Controle,
            intitule,
            &format!(
                "{} champ(s) hors du contrat declare, donc NON controle(s) : {}",
                surplus.len(),
                surplus.join(", ")
            ),
            Raison::HorsPortee,
            false,
        );
    }
}

fn controle_execution(b: &mut Bilan, doc: &BTreeMap<String, Valeur>, version: &str) {
    let Some(Valeur::Objet(exe)) = doc.get("execution") else {
        b.controle(
            Etat::Fail,
            "conditions d execution",
            "`execution` n est pas un objet JSON",
        );
        return;
    };

    // La nature : une clef ABSENTE est un oubli, une valeur hors
    // énumération est une erreur. Les deux sont des FAIL, et les messages
    // les séparent.
    match exe.get("kind_declared") {
        None | Some(Valeur::Nul) => {
            b.controle(
                Etat::Fail,
                "conditions d execution",
                "`execution.kind_declared` absent",
            );
            return;
        }
        Some(v) => {
            let ok = v
                .comme_texte()
                .map(|s| c::NATURES_EXECUTION.contains(&s))
                .unwrap_or(false);
            if !ok {
                b.controle(
                    Etat::Fail,
                    "conditions d execution",
                    &format!(
                        "`execution.kind_declared` = {}, hors des {} natures du \
                         contrat : {}",
                        bref(v),
                        c::NATURES_EXECUTION.len(),
                        c::NATURES_EXECUTION.join(", ")
                    ),
                );
            }
        }
    }

    let connus = c::champs_execution(version);
    dire_surplus(b, "champs d execution hors contrat", exe, &connus);

    let nature = exe
        .get("kind_declared")
        .and_then(|v| v.comme_texte())
        .unwrap_or("<?>")
        .to_string();
    let modele = exe.get("model_declared");
    let motif = exe.get("model_absence_reason_declared");
    let note = exe.get("model_absence_note_declared");

    // La clef `model_declared` est OBLIGATOIRE dans les deux contrats : une
    // clef omise est un oubli, un `null` explicite est une déclaration, et
    // les deux ne sont pas la même chose.
    let Some(modele) = modele else {
        b.controle(
            Etat::Fail,
            "conditions d execution",
            "`execution.model_declared` absent",
        );
        return;
    };

    // LA LAXITÉ DE `/1`, ET POURQUOI ELLE EST RESPECTÉE
    //
    // `/1` publie `{"type": "string", "minLength": 1}` sur
    // `model_declared` -- et RIEN DE PLUS. Un identifiant fait de blancs y
    // est donc VALIDE. `/2` ajoute `pattern: "\\S"`, et lui seul.
    //
    // Appliquer la règle de `/2` à un paquet `/1` serait un durcissement
    // RÉTROACTIF : il refuserait un paquet que le contrat publié appelle
    // bon, sur la décision du vérificateur et de personne d'autre.
    //
    // Cette ligne est le résultat d'une divergence Python/Rust constatée au
    // premier passage du banc comparatif : Rust refusait `v1-modele-blanc`,
    // Python l'acceptait. Le contrat tranche pour Python, et c'est Rust qui
    // a été corrigé. Voir la divergence **D-A** de
    // `04_MATRICE_PYTHON_RUST.md`.
    let exige_non_blanc = version == c::SCHEMA_V2;
    match modele {
        Valeur::Texte(id) if !id.is_empty() && (!exige_non_blanc || c::porte_un_non_blanc(id)) => {
            // Un modèle nommé INTERDIT un motif d'absence : déclarer les
            // deux est une contradiction, et rien dans le paquet ne dit
            // laquelle des deux affirmations est fausse.
            let contradit = matches!(motif, Some(v) if !matches!(v, Valeur::Nul))
                || matches!(note, Some(v) if !matches!(v, Valeur::Nul));
            if contradit {
                b.controle(
                    Etat::Fail,
                    "conditions d execution",
                    &format!(
                        "un modele est nomme ET un motif d absence est declare \
                         ({}) : une des deux affirmations est fausse, et rien \
                         dans ce paquet ne dit laquelle",
                        bref(motif.unwrap_or(&Valeur::Nul))
                    ),
                );
            } else {
                b.non_teste(
                    Nature::Declare,
                    "conditions d execution",
                    &format!(
                        "modele {id:?}, nature {nature:?} -- declares. Ce paquet \
                         ne porte rien qui permette de les confronter."
                    ),
                    Raison::Declaration,
                    false,
                );
            }
        }
        Valeur::Nul => {
            if version != c::SCHEMA_V2 {
                b.controle(
                    Etat::Fail,
                    "conditions d execution",
                    &format!(
                        "`execution.model_declared` est nul, et le contrat \
                         declare ne l admet pas. Le declarer nul exige le \
                         contrat {}, et un motif.",
                        c::SCHEMA_V2
                    ),
                );
                return;
            }
            let motif_txt = motif.and_then(|v| v.comme_texte());
            let Some(m) = motif_txt.filter(|m| c::MOTIFS_ABSENCE_MODELE.contains(m))
            else {
                b.controle(
                    Etat::Fail,
                    "conditions d execution",
                    &format!(
                        "`execution.model_declared` est nul et le motif vaut {} : \
                         attendu `{}` ou `{}`. Une absence sans motif reconnu ne \
                         se distingue pas d un oubli.",
                        bref(motif.unwrap_or(&Valeur::Nul)),
                        c::MOTIFS_ABSENCE_MODELE[0],
                        c::MOTIFS_ABSENCE_MODELE[1]
                    ),
                );
                return;
            };
            // Le motif seul est une étiquette, et une étiquette ne se
            // soupèse pas. La note est exigée, et non vide de blancs.
            let note_ok = note
                .and_then(|v| v.comme_texte())
                .map(c::porte_un_non_blanc)
                .unwrap_or(false);
            if !note_ok {
                b.controle(
                    Etat::Fail,
                    "conditions d execution",
                    &format!(
                        "motif `{m}` declare et note absente, vide ou non \
                         textuelle ({}) : le motif dit laquelle des deux \
                         situations c est, la note dit ce qui s est passe.",
                        bref(note.unwrap_or(&Valeur::Nul))
                    ),
                );
                return;
            }
            let n = note.and_then(|v| v.comme_texte()).unwrap_or("");
            let prose = if m == "not_applicable" {
                "aucun modele declare, motif `not_applicable` : le soumetteur \
                 declare qu AUCUN modele d IA n est intervenu."
            } else {
                "aucun modele declare, motif `unavailable` : un modele d IA est \
                 intervenu et son identite n a pas pu etre etablie. Elle reste \
                 INCONNUE, et rien ne lui est substitue."
            };
            b.non_teste(
                Nature::Declare,
                "conditions d execution",
                &format!(
                    "{prose} Nature {nature:?}, note {n:?} -- declarees, et non \
                     controlees."
                ),
                Raison::Declaration,
                false,
            );
        }
        autre => b.controle(
            Etat::Fail,
            "conditions d execution",
            &format!(
                "`execution.model_declared` n est ni un identifiant non vide ni \
                 nul : {}",
                bref(autre)
            ),
        ),
    }
}

fn controle_artefacts(
    b: &mut Bilan,
    r: &mut Resultat,
    source: &Source,
    doc: &BTreeMap<String, Valeur>,
) {
    let Some(Valeur::Tableau(liste)) = doc.get("artifacts") else {
        b.controle(Etat::Fail, "artefacts declares", "aucun artefact declare");
        return;
    };
    if liste.len() < c::ARTEFACTS_MIN {
        b.controle(Etat::Fail, "artefacts declares", "aucun artefact declare");
        return;
    }
    if liste.len() > c::ARTEFACTS_MAX {
        b.controle(
            Etat::Fail,
            "artefacts declares",
            &format!("{} artefacts, borne {}", liste.len(), c::ARTEFACTS_MAX),
        );
        return;
    }

    let mut concordants = 0usize;
    let mut discordants = 0usize;
    let mut absents = 0usize;
    let mut refuses = 0usize;
    let mut total: u64 = 0;
    let mut sans_role: Vec<String> = Vec::new();
    let mut role_hors_enum: Vec<String> = Vec::new();
    let mut requis_manquants: Vec<String> = Vec::new();
    let mut surplus_artefact: Vec<String> = Vec::new();
    //: `$defs.sha256.pattern` = `^[0-9a-f]{64}$`. Une empreinte declaree en
    //: MAJUSCULES, ou de mauvaise longueur, viole le contrat -- et ce n est
    //: pas la meme faute qu une empreinte qui ne concorde pas. La confondre
    //: avec une discordance dirait au soumetteur de regarder son fichier,
    //: alors que c est son manifeste qu il doit corriger.
    let mut empreinte_mal_formee: Vec<String> = Vec::new();
    //: `bytes` : `type: integer, minimum: 0`. `1e3` et `1000.0` sont des
    //: nombres JSON valides, et ne sont PAS des entiers.
    let mut taille_mal_formee: Vec<String> = Vec::new();

    for entree in liste {
        let Valeur::Objet(a) = entree else {
            refuses += 1;
            r.artefacts.push(Artefact {
                chemin: "<entree non objet>".into(),
                etat: "chemin_refuse".into(),
                sha256_recalcule: None,
                sha256_declare: None,
                octets_reels: None,
                octets_declares: None,
                role_declare: None,
                pourquoi: Some("entree d artefact qui n est pas un objet JSON".into()),
            });
            continue;
        };
        for k in c::ARTEFACT_REQUIS {
            if !a.contains_key(k) {
                requis_manquants.push(k.to_string());
            }
        }
        for k in a.keys() {
            if !c::CHAMPS_ARTEFACT.contains(&k.as_str())
                && !surplus_artefact.contains(k)
            {
                surplus_artefact.push(k.clone());
            }
        }
        let brut = a.get("path").and_then(|v| v.comme_texte()).unwrap_or("");
        let etiquette = if brut.is_empty() { "?".to_string() } else { brut.to_string() };

        match a.get("role") {
            None => sans_role.push(etiquette.clone()),
            Some(v) => {
                let ok = v
                    .comme_texte()
                    .map(|s| c::ROLES_ARTEFACT.contains(&s))
                    .unwrap_or(false);
                if !ok {
                    role_hors_enum.push(format!("{etiquette} -> {}", bref(v)));
                }
            }
        }

        // La FORME de l empreinte et de la taille declarees, avant toute
        // comparaison : une empreinte en majuscules n est pas une
        // discordance, c est un manifeste hors contrat.
        if let Some(v) = a.get("sha256") {
            let bien = v.comme_texte().map(c::sha256_bien_forme).unwrap_or(false);
            if !bien {
                empreinte_mal_formee.push(format!("{etiquette} -> {}", bref(v)));
            }
        }
        if let Some(v) = a.get("bytes") {
            match v.comme_entier() {
                Some(n) if n >= 0 => {}
                _ => taille_mal_formee.push(format!("{etiquette} -> {}", bref(v))),
            }
        }

        if let Err(pourquoi) = chemins::chemin_sur(brut) {
            refuses += 1;
            r.artefacts.push(Artefact {
                chemin: etiquette,
                etat: "chemin_refuse".into(),
                sha256_recalcule: None,
                sha256_declare: a
                    .get("sha256")
                    .and_then(|v| v.comme_texte())
                    .map(str::to_string),
                octets_reels: None,
                octets_declares: a.get("bytes").and_then(|v| v.comme_entier()),
                role_declare: a.get("role").and_then(|v| v.comme_texte()).map(str::to_string),
                pourquoi: Some(pourquoi),
            });
            continue;
        }

        let octets = match lire(source, brut) {
            Ok(Some(o)) => o,
            Ok(None) => {
                absents += 1;
                r.artefacts.push(Artefact {
                    chemin: etiquette,
                    etat: "absent".into(),
                    sha256_recalcule: None,
                    sha256_declare: a
                        .get("sha256")
                        .and_then(|v| v.comme_texte())
                        .map(str::to_string),
                    octets_reels: None,
                    octets_declares: a.get("bytes").and_then(|v| v.comme_entier()),
                    role_declare: a
                        .get("role")
                        .and_then(|v| v.comme_texte())
                        .map(str::to_string),
                    pourquoi: None,
                });
                continue;
            }
            Err(e) => {
                refuses += 1;
                r.artefacts.push(Artefact {
                    chemin: etiquette,
                    etat: "chemin_refuse".into(),
                    sha256_recalcule: None,
                    sha256_declare: None,
                    octets_reels: None,
                    octets_declares: None,
                    role_declare: None,
                    pourquoi: Some(e),
                });
                continue;
            }
        };

        if octets.len() as u64 > crate::zip::OCTETS_PAR_MEMBRE_MAX {
            refuses += 1;
            r.artefacts.push(Artefact {
                chemin: etiquette,
                etat: "trop_volumineux".into(),
                sha256_recalcule: None,
                sha256_declare: None,
                octets_reels: Some(octets.len() as u64),
                octets_declares: a.get("bytes").and_then(|v| v.comme_entier()),
                role_declare: None,
                pourquoi: None,
            });
            continue;
        }
        total = total.saturating_add(octets.len() as u64);
        if total > crate::zip::OCTETS_TOTAL_MAX {
            b.controle(
                Etat::Fail,
                "volume du paquet",
                &format!("au-dela de {} octets au total", crate::zip::OCTETS_TOTAL_MAX),
            );
            return;
        }

        // L'EMPREINTE EST RECALCULÉE SUR LES OCTETS ORIGINAUX. Aucune
        // normalisation, aucune conversion de fin de ligne, aucun retrait de
        // BOM : un artefact est une suite d'octets, et c'est elle qui est
        // condensée.
        let mut h = Sha256::new();
        h.alimenter(&octets);
        let reel = crate::sha256::en_hex(&h.terminer());
        let annonce = a.get("sha256").and_then(|v| v.comme_texte());
        let taille_declaree = a.get("bytes").and_then(|v| v.comme_entier());
        let empreinte_ok = annonce == Some(reel.as_str());
        let taille_ok = taille_declaree == Some(octets.len() as i64);

        if empreinte_ok && taille_ok {
            concordants += 1;
            r.artefacts.push(Artefact {
                chemin: etiquette,
                etat: "concordant".into(),
                sha256_recalcule: Some(reel),
                sha256_declare: annonce.map(str::to_string),
                octets_reels: Some(octets.len() as u64),
                octets_declares: taille_declaree,
                role_declare: a
                    .get("role")
                    .and_then(|v| v.comme_texte())
                    .map(str::to_string),
                pourquoi: None,
            });
        } else {
            discordants += 1;
            r.artefacts.push(Artefact {
                chemin: etiquette,
                etat: "discordant".into(),
                sha256_recalcule: Some(reel),
                sha256_declare: annonce.map(str::to_string),
                octets_reels: Some(octets.len() as u64),
                octets_declares: taille_declaree,
                role_declare: a
                    .get("role")
                    .and_then(|v| v.comme_texte())
                    .map(str::to_string),
                pourquoi: None,
            });
        }
    }

    if !requis_manquants.is_empty() {
        requis_manquants.sort();
        requis_manquants.dedup();
        b.controle(
            Etat::Fail,
            "champs obligatoires des artefacts",
            &format!(
                "champ(s) obligatoire(s) absent(s) d au moins un artefact : {}",
                requis_manquants.join(", ")
            ),
        );
    }
    if !empreinte_mal_formee.is_empty() {
        b.controle(
            Etat::Fail,
            "forme des empreintes declarees",
            &format!(
                "{} empreinte(s) hors de `^[0-9a-f]{{64}}$` : {}",
                empreinte_mal_formee.len(),
                empreinte_mal_formee
                    .iter()
                    .take(6)
                    .cloned()
                    .collect::<Vec<_>>()
                    .join(", ")
            ),
        );
    }
    if !taille_mal_formee.is_empty() {
        b.controle(
            Etat::Fail,
            "forme des tailles declarees",
            &format!(
                "{} taille(s) qui ne sont pas des entiers positifs : {}",
                taille_mal_formee.len(),
                taille_mal_formee
                    .iter()
                    .take(6)
                    .cloned()
                    .collect::<Vec<_>>()
                    .join(", ")
            ),
        );
    }

    let detail = format!(
        "{concordants} concordant(s), {discordants} discordant(s), \
         {absents} absent(s), {refuses} refuse(s), {total} octets recalcules"
    );
    if discordants > 0 || refuses > 0 {
        b.controle(Etat::Fail, "empreintes des artefacts declares", &detail);
    } else if absents > 0 {
        // Un artefact annoncé et non fourni n'est pas une fraude : c'est un
        // paquet incomplet, et le soumetteur peut le compléter.
        b.non_teste(
            Nature::Controle,
            "empreintes des artefacts declares",
            &detail,
            Raison::NonApplicable,
            true,
        );
    } else {
        b.controle(Etat::Pass, "empreintes des artefacts declares", &detail);
    }

    if !sans_role.is_empty() {
        b.controle(
            Etat::Fail,
            "role des artefacts",
            &format!(
                "{} artefact(s) sans `role`, champ obligatoire du contrat : {}",
                sans_role.len(),
                sans_role.iter().take(6).cloned().collect::<Vec<_>>().join(", ")
            ),
        );
    }
    if !role_hors_enum.is_empty() {
        b.controle(
            Etat::Fail,
            "role des artefacts",
            &format!(
                "{} role(s) hors des {} valeurs du contrat ({}) : {}",
                role_hors_enum.len(),
                c::ROLES_ARTEFACT.len(),
                c::ROLES_ARTEFACT.join(", "),
                role_hors_enum.iter().take(6).cloned().collect::<Vec<_>>().join(", ")
            ),
        );
    }
    if !surplus_artefact.is_empty() {
        surplus_artefact.sort();
        b.non_teste(
            Nature::Controle,
            "champs d artefact hors contrat",
            &format!(
                "{} champ(s) hors du contrat declare, donc NON controle(s) : {}",
                surplus_artefact.len(),
                surplus_artefact.join(", ")
            ),
            Raison::HorsPortee,
            false,
        );
    }
}

fn controle_non_declares(
    b: &mut Bilan,
    r: &mut Resultat,
    source: &Source,
    doc: &BTreeMap<String, Valeur>,
) {
    let mut declares: Vec<String> = vec![c::MANIFESTE.to_string()];
    if let Some(Valeur::Tableau(liste)) = doc.get("artifacts") {
        for e in liste {
            if let Valeur::Objet(a) = e {
                if let Some(p) = a.get("path").and_then(|v| v.comme_texte()) {
                    declares.push(p.to_string());
                }
            }
        }
    }
    if let Some(Valeur::Tableau(atts)) = doc.get("attestations") {
        for e in atts {
            if let Valeur::Objet(a) = e {
                for k in ["jws_path", "subject_path"] {
                    if let Some(p) = a.get(k).and_then(|v| v.comme_texte()) {
                        declares.push(p.to_string());
                    }
                }
            }
        }
    }
    let presents = lister(source);
    let surplus: Vec<String> = presents
        .iter()
        .filter(|p| !declares.contains(p))
        .cloned()
        .collect();
    r.fichiers_non_declares = surplus.clone();
    if surplus.is_empty() {
        b.controle(
            Etat::Pass,
            "fichiers non declares",
            &format!(
                "aucun : les {} fichier(s) du paquet sont tous declares",
                presents.len()
            ),
        );
    } else {
        // Pas un FAIL : un fichier en surplus n'invalide pas les empreintes
        // de ceux qui sont déclarés. Mais le taire laisserait croire qu'il a
        // été couvert.
        b.non_teste(
            Nature::Controle,
            "fichiers non declares",
            &format!(
                "{} fichier(s) present(s) et non declare(s), donc NON \
                 controle(s) : {}",
                surplus.len(),
                surplus.iter().take(6).cloned().collect::<Vec<_>>().join(", ")
            ),
            Raison::HorsPortee,
            false,
        );
    }
}

/// Module 5 — les attestations. DÉTECTÉES, et NON vérifiées.
///
/// LA FRONTIÈRE, ET POURQUOI ELLE EST ICI
///
/// Ce vérificateur **ne vérifie aucune signature**, et le déclare. Quatre
/// propriétés sont à distinguer, et aucune n'implique la suivante :
///
///   1. la signature est cryptographiquement valide
///   2. l'identité du signataire est DÉCLARÉE
///   3. l'identité est VÉRIFIÉE selon une politique de confiance
///   4. l'événement signé a réellement eu lieu
///
/// Établir (1) demanderait Ed25519 et l'analyse JWS. Établir (3)
/// demanderait une politique de confiance que le contrat de soumission **ne
/// publie pas** : `attestations[].trust_store_declared` est explicitement
/// « quel magasin le soumetteur CROIT qui le cautionne », et le schéma dit
/// que l'ingestion emploie le magasin de l'OPÉRATEUR, jamais celui du
/// paquet. Ce magasin n'est pas décrit dans le contrat de soumission.
///
/// Conséquence : implémenter (1) sans (3) produirait un rapport qui dirait
/// « signature valide » sans pouvoir dire par qui — exactement le verdict
/// trompeur que la mission interdit. Le contrôle est donc `NOT TESTED`,
/// avec sa raison, et le périmètre est déclaré dans
/// `07_LIMITES_ET_GARANTIES.md`.
fn controle_attestations(b: &mut Bilan, doc: &BTreeMap<String, Valeur>) {
    match doc.get("attestations") {
        None => b.non_teste(
            Nature::Controle,
            "signatures existantes",
            "le paquet ne declare aucune attestation. Son niveau ne depassera \
             donc pas `reference_verifiable`.",
            Raison::NonApplicable,
            false,
        ),
        Some(Valeur::Tableau(t)) if t.is_empty() => b.non_teste(
            Nature::Controle,
            "signatures existantes",
            "le paquet ne declare aucune attestation. Son niveau ne depassera \
             donc pas `reference_verifiable`.",
            Raison::NonApplicable,
            false,
        ),
        Some(Valeur::Tableau(t)) => b.non_teste(
            Nature::Controle,
            "signatures existantes",
            &format!(
                "{} attestation(s) declaree(s). CE VERIFICATEUR NE VERIFIE \
                 AUCUNE SIGNATURE : etablir sa validite sans politique de \
                 confiance ne dirait pas PAR QUI elle est signee, et le \
                 contrat de soumission ne publie aucune politique. Le controle \
                 est donc NON TESTE, et non suppose.",
                t.len()
            ),
            Raison::HorsPortee,
            true,
        ),
        Some(autre) => b.controle(
            Etat::Fail,
            "signatures existantes",
            &format!(
                "`attestations` = {} : le contrat attend un tableau.",
                bref(autre)
            ),
        ),
    }
}

fn controle_provenance(b: &mut Bilan, doc: &BTreeMap<String, Valeur>) {
    match doc.get("provenance_declared") {
        None => b.non_teste(
            Nature::NonDemontrable,
            "provenance de l execution",
            "aucun champ de provenance declare. Toute affirmation sur \
             l environnement ou l instrument de cette execution est donc \
             `not_demonstrable`.",
            Raison::NonApplicable,
            false,
        ),
        Some(Valeur::Objet(p)) => {
            dire_surplus(b, "champs de provenance hors contrat", p, &c::CHAMPS_PROVENANCE);
            let champs = [
                "code_reference_declared",
                "environment_declared",
                "evaluator_declared",
            ];
            let renseignes: Vec<&str> = champs
                .iter()
                .copied()
                .filter(|k| {
                    p.get(*k)
                        .and_then(|v| v.comme_texte())
                        .map(c::porte_un_non_blanc)
                        .unwrap_or(false)
                })
                .collect();
            let absents: Vec<&str> = champs
                .iter()
                .copied()
                .filter(|k| !renseignes.contains(k))
                .collect();
            if renseignes.is_empty() {
                b.non_teste(
                    Nature::NonDemontrable,
                    "provenance de l execution",
                    "aucun champ de provenance declare. Toute affirmation sur \
                     l environnement ou l instrument de cette execution est \
                     donc `not_demonstrable`.",
                    Raison::NonApplicable,
                    false,
                );
            } else {
                b.non_teste(
                    Nature::Declare,
                    "provenance de l execution",
                    &format!(
                        "renseignee : {} ; absente : {}. Declaree et non \
                         verifiable depuis ce paquet.",
                        renseignes.join(", "),
                        if absents.is_empty() {
                            "aucune".to_string()
                        } else {
                            absents.join(", ")
                        }
                    ),
                    Raison::Declaration,
                    false,
                );
            }
        }
        Some(autre) => b.controle(
            Etat::Fail,
            "provenance de l execution",
            &format!(
                "`provenance_declared` = {} : le contrat attend un objet, et \
                 dire qu il n y en a pas se fait en OMETTANT la clef.",
                bref(autre)
            ),
        ),
    }

    match doc.get("limits_declared") {
        None => {}
        Some(Valeur::Tableau(t)) if t.is_empty() => {}
        Some(Valeur::Tableau(t)) => {
            let textes: Vec<String> = t.iter().map(bref).collect();
            b.non_teste(
                Nature::Declare,
                "limites annoncees par le soumetteur",
                &format!(
                    "{} limite(s), conservee(s) verbatim : {}",
                    t.len(),
                    tronquer(&textes.join(" | "), 240)
                ),
                Raison::Declaration,
                false,
            );
        }
        Some(autre) => b.controle(
            Etat::Fail,
            "limites annoncees par le soumetteur",
            &format!(
                "`limits_declared` = {} : le contrat attend un tableau.",
                bref(autre)
            ),
        ),
    }
}

fn tronquer(s: &str, n: usize) -> String {
    if s.chars().count() <= n {
        s.to_string()
    } else {
        s.chars().take(n).collect()
    }
}

// --------------------------------------------------------------------------
// Accès aux octets, par source
// --------------------------------------------------------------------------

/// Les octets d'un chemin du paquet, ou `None` s'il est absent.
///
/// Côté dossier, le chemin est reconstruit segment par segment et la cible
/// est confinée : un lien symbolique ou une cible hors du paquet est un
/// refus. Côté ZIP, rien n'est jamais écrit.
fn lire(source: &Source, chemin: &str) -> Result<Option<Vec<u8>>, String> {
    match source {
        Source::Dossier(racine) => {
            let mut cible = racine.clone();
            for segment in chemin.split('/') {
                if segment.is_empty() || segment == "." || segment == ".." {
                    return Err("segment de chemin refuse".into());
                }
                cible.push(segment);
            }
            // Le lien symbolique est refusé AVANT toute lecture : il passe
            // le motif de chemin et sort du paquet.
            match std::fs::symlink_metadata(&cible) {
                Ok(m) if m.file_type().is_symlink() => {
                    return Err("lien symbolique : la cible peut sortir du paquet".into())
                }
                Ok(m) if m.is_dir() => return Ok(None),
                Ok(_) => {}
                Err(_) => return Ok(None),
            }
            // Confinement : la cible résolue doit rester sous la racine
            // résolue. Le motif de chemin ne suffit pas.
            let (rr, rc) = (racine.canonicalize(), cible.canonicalize());
            match (rr, rc) {
                (Ok(rr), Ok(rc)) if rc.starts_with(&rr) => {}
                (Ok(_), Ok(_)) => {
                    return Err("cible hors du paquet apres resolution".into())
                }
                _ => return Err("chemin non resolvable".into()),
            }
            // Même raison que pour l'archive : la borne par membre du
            // module ZIP ne protège pas un paquet-DOSSIER, qui n'annonce
            // aucune taille. Elle était appliquée après la lecture.
            match std::fs::metadata(&cible) {
                Ok(m) if m.len() > crate::contrat::FICHIER_OCTETS_MAX => {
                    return Err(format!(
                        "fichier de {} octets, borne {} : refuse AVANT lecture",
                        m.len(),
                        crate::contrat::FICHIER_OCTETS_MAX
                    ))
                }
                Ok(_) => {}
                Err(e) => return Err(e.to_string()),
            }
            std::fs::read(&cible).map(Some).map_err(|e| e.to_string())
        }
        Source::Zip(a) => match a.trouver(chemin) {
            None => Ok(None),
            Some(m) => a.lire(m).map(Some).map_err(|e| e.0),
        },
    }
}

/// Tous les fichiers du paquet, en chemins relatifs à barres obliques.
fn lister(source: &Source) -> Vec<String> {
    match source {
        Source::Zip(a) => {
            let mut v: Vec<String> = a.fichiers().iter().map(|s| s.to_string()).collect();
            v.sort();
            v
        }
        Source::Dossier(racine) => {
            let mut v = Vec::new();
            parcourir(racine, racine, &mut v);
            v.sort();
            v
        }
    }
}

fn parcourir(racine: &Path, courant: &Path, sortie: &mut Vec<String>) {
    let Ok(entrees) = std::fs::read_dir(courant) else {
        return;
    };
    for e in entrees.flatten() {
        let p = e.path();
        let Ok(m) = std::fs::symlink_metadata(&p) else {
            continue;
        };
        if m.file_type().is_symlink() {
            // Un lien symbolique est SIGNALÉ comme fichier non déclaré, et
            // jamais suivi : le suivre pourrait sortir du paquet.
            if let Ok(rel) = p.strip_prefix(racine) {
                sortie.push(rel.to_string_lossy().replace('\\', "/"));
            }
            continue;
        }
        if m.is_dir() {
            parcourir(racine, &p, sortie);
        } else if let Ok(rel) = p.strip_prefix(racine) {
            sortie.push(rel.to_string_lossy().replace('\\', "/"));
        }
    }
}
