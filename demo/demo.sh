#!/bin/sh
# Demonstration reproductible du NeoMundi Evidence Gateway -- cinq scenarios.
#
# Elle ne touche a aucune donnee confidentielle : les artefacts employes sont
# ceux du jeu de demonstration SYNTHETIQUE du moteur (`examples/dossier-v1/`),
# publies avec lui. Le scenario 5 n emploie aucun artefact du tout.
#
#   1. artefact valide, corpus fourni, mode strict         -> code 0
#   2. artefact altere (un membre reecrit ici meme)        -> code 1
#   3. artefact non verifiable (corpus non fourni, strict) -> code 2
#   4. requete refusee (operation inconnue)                -> code 4
#   5. moteur indisponible                                 -> code 3
#
# Emploi :
#   EVIDENCE_ENGINE_HOME=/chemin/vers/le/moteur sh demo/demo.sh
#   sh demo/demo.sh --no-engine        # scenarios 4 et 5 seulement
#
# Chaque reponse est ecrite dans `demo/out/`. Les codes de sortie observes
# sont recapitules a la fin, et compares aux codes ATTENDUS : la
# demonstration echoue si un seul differe.

set -u

RACINE=$(cd "$(dirname "$0")/.." && pwd)
SORTIE="$RACINE/demo/out"
PY=${EVIDENCE_PYTHON:-python3}
command -v "$PY" >/dev/null 2>&1 || PY=python

SANS_MOTEUR=0
[ "${1:-}" = "--no-engine" ] && SANS_MOTEUR=1

rm -rf "$SORTIE"
mkdir -p "$SORTIE"

OBSERVES=""
ATTENDUS=""
ECARTS=0

titre() {
  echo ""
  echo "=============================================================="
  echo "  $1"
  echo "=============================================================="
}

relever() {
  # relever <intitule> <code_attendu> <code_observe>
  OBSERVES="$OBSERVES $1=$3"
  ATTENDUS="$ATTENDUS $1=$2"
  if [ "$2" != "$3" ]; then
    echo "  >>> ECART : attendu $2, observe $3"
    ECARTS=$((ECARTS + 1))
  else
    echo "  >>> code $3, conforme a l attendu"
  fi
}

if [ "$SANS_MOTEUR" -eq 0 ]; then
  if [ -z "${EVIDENCE_ENGINE_HOME:-}" ]; then
    echo "EVIDENCE_ENGINE_HOME n est pas pose."
    echo "Poser la racine du moteur Evidence, ou lancer : sh demo/demo.sh --no-engine"
    exit 2
  fi
  MOTEUR="$EVIDENCE_ENGINE_HOME"
  ARCHIVE="examples/dossier-v1/NEOMUNDI_EVIDENCE_V1_DEMO.zip"
  if [ ! -f "$MOTEUR/$ARCHIVE" ]; then
    echo "le moteur declare ne porte pas $ARCHIVE -- demonstration impossible."
    exit 2
  fi

  titre "1. ARTEFACT VALIDE -- corpus fourni, mode strict"
  "$PY" "$RACINE/gateway.py" submit "$RACINE/examples/02-verify-corpus-strict.json" \
    --artifact-root "$MOTEUR" --out "$SORTIE/01-valide.json" >/dev/null
  relever "1-valide" 0 "$?"

  titre "2. ARTEFACT ALTERE -- un membre de l archive est reecrit"
  "$PY" - "$MOTEUR/$ARCHIVE" "$SORTIE/altere.zip" <<'FIN'
import sys, zipfile
source, cible = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(source) as entree:
    noms = entree.namelist()
    vise = next((n for n in noms if n.endswith(".jsonl")), noms[-1])
    with zipfile.ZipFile(cible, "w", zipfile.ZIP_DEFLATED) as sortie:
        for nom in noms:
            donnees = entree.read(nom)
            if nom == vise:
                donnees = donnees + b"\n"
            sortie.writestr(nom, donnees)
print("membre reecrit :", vise)
FIN
  "$PY" "$RACINE/gateway.py" verify altere.zip \
    --artifact-root "$SORTIE" --out "$SORTIE/02-altere.json" >/dev/null
  relever "2-altere" 1 "$?"

  titre "3. ARTEFACT NON VERIFIABLE -- corpus non fourni, mode strict"
  "$PY" "$RACINE/gateway.py" verify "$ARCHIVE" --strict \
    --artifact-root "$MOTEUR" --out "$SORTIE/03-non-verifiable.json" >/dev/null
  relever "3-non-verifiable" 2 "$?"
else
  echo "mode --no-engine : les scenarios 1 a 3 ne sont pas joues."
fi

titre "4. REQUETE REFUSEE -- operation inconnue, aucun moteur lance"
"$PY" "$RACINE/gateway.py" submit "$RACINE/examples/04-rejected-unknown-operation.json" \
  --artifact-root "$RACINE" --out "$SORTIE/04-refusee.json" >/dev/null
relever "4-refusee" 4 "$?"

titre "5. MOTEUR INDISPONIBLE -- racine declaree inexistante"
: > "$SORTIE/artefact-factice.zip"
"$PY" "$RACINE/gateway.py" verify artefact-factice.zip \
  --artifact-root "$SORTIE" --engine-home "$SORTIE/moteur-qui-n-existe-pas" \
  --out "$SORTIE/05-indisponible.json" >/dev/null
relever "5-indisponible" 3 "$?"

titre "RECAPITULATIF"
echo "  attendus :$ATTENDUS"
echo "  observes :$OBSERVES"
echo ""
echo "  reponses ecrites dans demo/out/"
echo ""
echo "  CE QUE CETTE DEMONSTRATION ETABLIT"
echo "    - le gateway distingue cinq situations par son code de sortie,"
echo "      dont DEUX ou aucune verification n a eu lieu (3 et 4) ;"
echo "    - le verdict publie est celui du moteur, et l enveloppe le dit."
echo ""
echo "  CE QU ELLE N ETABLIT PAS"
echo "    - rien sur la verite du contenu de l artefact ;"
echo "    - aucune verification INDEPENDANTE : le moteur tourne ici, chez"
echo '      l operateur de ce gateway. Une attestation de cle de TEST ne vaut'
echo "      pas davantage ;"
echo "    - aucune propriete du moteur lui-meme : ses propres suites et son"
echo "      corpus de conformite s en chargent, pas celle-ci."
echo ""
echo "  REPRODUCTIBILITE, MESUREE"
echo "    verdicts et codes de sortie : identiques d un passage a l autre."
if [ "$SANS_MOTEUR" -eq 0 ]; then
  echo "    Les reponses des scenarios 1, 3, 4 et 5 sont identiques a l octet ;"
  echo "    celle du scenario 2 ne l est PAS, parce que l archive alteree est"
  echo "    refabriquee a chaque passage et qu un ZIP porte l horodatage de ses"
  echo "    membres -- donc une autre empreinte. Comparer les verdicts, jamais"
  echo "    l empreinte d une archive refabriquee."
else
  echo "    Les reponses des scenarios 4 et 5 sont identiques a l octet. Ce"
  echo "    passage n a pas joue les scenarios 1 a 3 : rien n est affirme ici"
  echo "    de leur reproductibilite."
fi

if [ "$ECARTS" -ne 0 ]; then
  echo ""
  echo "DEMONSTRATION EN ECHEC : $ECARTS code(s) de sortie hors attendu."
  exit 1
fi
echo ""
echo "DEMONSTRATION CONFORME : tous les codes de sortie observes sont ceux attendus."
exit 0
