//! Module 2 — les règles du contrat, telles qu'elles sont PUBLIÉES.
//!
//! Chaque constante porte le chemin exact dans le schéma dont elle est
//! tirée. Rien ici ne vient de la lecture du code Python : ce qui en vient
//! est marqué `COMPORTEMENT OBSERVE` et justifié sur place.
//!
//! Les deux contrats `/1` et `/2` sont acceptés. Ils publient les mêmes
//! règles sur tout ce que ce module contrôle, SAUF une : `/2` admet un
//! `model_declared` nul, motivé ; `/1` ne l'admet pas. C'est la version du
//! contrat qui sépare les deux lectures, et un paquet `/1` au modèle nul
//! reste refusé — exactement comme du côté Python.

/// `properties.schema.const` des deux schémas publiés.
pub const SCHEMA_V1: &str = "neomundi.evidence.submission/1";
pub const SCHEMA_V2: &str = "neomundi.evidence.submission/2";

/// `properties.schema` du rapport que NOUS produisons. Volontairement
/// distinct de celui de l'implémentation Python
/// (`neomundi.evidence.ingestion-report/1`) : deux implémentations qui
/// publieraient le même identifiant de rapport laisseraient croire que
/// leurs sorties sont interchangeables octet par octet. Elles ne le sont
/// pas, et n'ont pas à l'être — seule l'équivalence SÉMANTIQUE est exigée.
pub const SCHEMA_RAPPORT: &str = "neomundi.evidence.verification-report-rs/1";

pub const VERSION_VERIFICATEUR: &str = env!("CARGO_PKG_VERSION");
pub const NOM_VERIFICATEUR: &str = env!("CARGO_PKG_NAME");

/// Le manifeste, à la racine du paquet. `adapters/ingest.py` emploie le
/// même nom ; le schéma ne le publie pas — il décrit le document, pas son
/// emplacement. **AMBIGUITE-2** du document de baseline.
pub const MANIFESTE: &str = "submission.json";

/// `required` au premier niveau, identique dans `/1` et `/2`.
pub const CHAMPS_REQUIS: [&str; 6] = [
    "schema",
    "submission_id",
    "submitted_at_declared",
    "pilot",
    "execution",
    "artifacts",
];

/// `properties` au premier niveau. `additionalProperties: false` -- un
/// champ hors de cette liste viole la lettre du schéma.
pub const CHAMPS_CONNUS: [&str; 9] = [
    "schema",
    "submission_id",
    "submitted_at_declared",
    "pilot",
    "execution",
    "artifacts",
    "attestations",
    "provenance_declared",
    "limits_declared",
];

/// `properties.pilot` : `type: object`, `required: [name_declared]`,
/// `additionalProperties: false`.
pub const CHAMPS_PILOTE: [&str; 3] =
    ["name_declared", "reference_declared", "contact_declared"];

/// `properties.execution.properties`, contrat `/1`.
pub const CHAMPS_EXECUTION_V1: [&str; 6] = [
    "kind_declared",
    "model_declared",
    "provider_declared",
    "executed_at_declared",
    "parameters_declared",
    "notes_declared",
];

/// Les deux champs que `/2` ajoute.
pub const CHAMPS_EXECUTION_V2_SUP: [&str; 2] =
    ["model_absence_reason_declared", "model_absence_note_declared"];

/// `properties.provenance_declared.properties`.
pub const CHAMPS_PROVENANCE: [&str; 4] = [
    "code_reference_declared",
    "environment_declared",
    "evaluator_declared",
    "notes_declared",
];

/// `properties.artifacts.items.properties`.
pub const CHAMPS_ARTEFACT: [&str; 5] =
    ["path", "sha256", "bytes", "role", "media_type"];

/// `properties.artifacts.items.required`.
pub const ARTEFACT_REQUIS: [&str; 4] = ["path", "sha256", "bytes", "role"];

/// `properties.execution.properties.kind_declared.enum`.
pub const NATURES_EXECUTION: [&str; 4] =
    ["single_call", "batch", "replay", "other"];

/// `properties.artifacts.items.properties.role.enum`.
pub const ROLES_ARTEFACT: [&str; 8] = [
    "prompt",
    "response",
    "recording",
    "transcript",
    "measurement",
    "receipt",
    "attestation",
    "other",
];

/// `properties.execution.allOf[0].then.properties.model_absence_reason_declared.enum`
pub const MOTIFS_ABSENCE_MODELE: [&str; 2] = ["not_applicable", "unavailable"];

/// `properties.artifacts.minItems`.
pub const ARTEFACTS_MIN: usize = 1;

/// `COMPORTEMENT OBSERVE` -- `adapters/ingest.py::MAX_ARTEFACTS`. Le schéma
/// ne publie **aucun** `maxItems` sur `artifacts`. La borne est reproduite
/// pour que les deux vérificateurs concordent, et elle est déclarée comme
/// non contractuelle : voir `AMBIGUITE-3`.
pub const ARTEFACTS_MAX: usize = 512;

/// Taille maximale du FICHIER de paquet, lue avant de l'ouvrir.
///
/// `COMPORTEMENT CHOISI ICI`, non contractuel -- `AMBIGUITE-3`.
///
/// POURQUOI ELLE EXISTE
///
/// Les bornes du module ZIP (64 Mio par membre, 256 Mio décompressés) sont
/// vérifiées sur le répertoire central, donc **après** que le fichier entier
/// a été chargé en mémoire. Mesuré : un fichier de 256 Mio qui n'est même
/// pas un ZIP valide faisait culminer la mémoire à 264 Mio avant tout refus,
/// et la consommation suivait la taille du fichier à l'unité près. Un
/// fichier de 20 Gio n'était donc pas refusé : il faisait échouer
/// l'allocation, et `panic = "abort"` rend alors le code **134**, hors du
/// contrat de sortie {0, 1, 2, 3}.
///
/// La valeur : les 256 Mio décompressés du module ZIP, plus 64 Mio de marge
/// pour les en-têtes et un éventuel commentaire. Un paquet légitime pèse
/// quelques mégaoctets.
pub const PAQUET_OCTETS_MAX: u64 = 320 * 1024 * 1024;

/// Taille maximale d'un FICHIER lu dans un paquet-dossier, vérifiée sur les
/// métadonnées avant la lecture. Même raison que ci-dessus : un paquet-
/// dossier n'a pas de répertoire central pour annoncer ses tailles.
pub const FICHIER_OCTETS_MAX: u64 = 64 * 1024 * 1024;

/// `$defs.sha256.pattern` : `^[0-9a-f]{64}$`. Minuscules, et rien d'autre.
pub fn sha256_bien_forme(s: &str) -> bool {
    s.len() == 64 && s.bytes().all(|c| c.is_ascii_hexdigit() && !c.is_ascii_uppercase())
}

/// `$defs.instant.pattern` :
/// `^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$`
///
/// La FORME, et rien de plus. La véracité de la date reste hors de portée :
/// aucune horloge de confiance n'intervient, et ce vérificateur ne lit
/// JAMAIS sa propre horloge pour contredire une date déclarée.
pub fn instant_bien_forme(s: &str) -> bool {
    let o = s.as_bytes();
    if o.len() != 20 {
        return false;
    }
    let chiffres = [0, 1, 2, 3, 5, 6, 8, 9, 11, 12, 14, 15, 17, 18];
    let fixes: [(usize, u8); 6] =
        [(4, b'-'), (7, b'-'), (10, b'T'), (13, b':'), (16, b':'), (19, b'Z')];
    chiffres.iter().all(|&i| o[i].is_ascii_digit())
        && fixes.iter().all(|&(i, c)| o[i] == c)
}

/// `properties.submission_id.pattern` : `^[a-z0-9][a-z0-9-]{2,63}$`
pub fn identifiant_bien_forme(s: &str) -> bool {
    let o = s.as_bytes();
    if o.len() < 3 || o.len() > 64 {
        return false;
    }
    let premier = o[0];
    if !(premier.is_ascii_lowercase() || premier.is_ascii_digit()) {
        return false;
    }
    o[1..]
        .iter()
        .all(|&c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == b'-')
}

/// `pattern: "\\S"` sur `model_declared` et sur
/// `model_absence_note_declared` : au moins un caractère non blanc.
/// Une note faite de blancs satisfait `minLength: 1` et n'explique rien.
pub fn porte_un_non_blanc(s: &str) -> bool {
    s.chars().any(|c| !c.is_whitespace())
}

pub fn champs_execution(version: &str) -> Vec<&'static str> {
    let mut v: Vec<&'static str> = CHAMPS_EXECUTION_V1.to_vec();
    if version == SCHEMA_V2 {
        v.extend_from_slice(&CHAMPS_EXECUTION_V2_SUP);
    }
    v
}
