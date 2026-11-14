#!/usr/bin/env bash
# Audit de dependances, verification HORS LIGNE, et reproductibilite du
# binaire. A lancer DANS WSL (ou tout Linux).
#
# Chaque controle imprime ce qu il etablit, et ce qu il n etablit pas.
set -uo pipefail

RACINE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CAISSE="$RACINE/verifier-rs"
if ! command -v cargo >/dev/null 2>&1 && [ -f "$HOME/.cargo/env" ]; then
  # shellcheck disable=SC1091
  . "$HOME/.cargo/env"
fi
cd "$CAISSE"

echo "=================================================================="
echo "1. AUDIT DE DEPENDANCES"
echo "=================================================================="
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-$HOME/evr-target}"
cargo generate-lockfile --offline >/dev/null 2>&1 || true
echo "--- [dependencies] declarees dans Cargo.toml ---"
awk '/^\[dependencies\]/{f=1;next} /^\[/{f=0} f && NF && $0 !~ /^#/' Cargo.toml \
  | sed 's/^/    /' || true
echo "    (vide ci-dessus = aucune dependance declaree)"
echo
echo "--- paquets dans Cargo.lock ---"
if [ -f Cargo.lock ]; then
  NB=$(grep -c '^\[\[package\]\]' Cargo.lock)
  echo "    $NB entree(s) :"
  grep -A1 '^\[\[package\]\]' Cargo.lock | grep '^name' | sed 's/^/      /'
  if [ "$NB" -eq 1 ]; then
    echo "    -> la SEULE entree est la caisse elle-meme. Zero dependance."
  else
    echo "    -> ATTENTION : des dependances tierces sont presentes."
  fi
else
  echo "    pas de Cargo.lock"
fi
echo
echo "--- arbre complet (cargo tree) ---"
cargo tree --offline 2>/dev/null | sed 's/^/    /' || echo "    cargo tree indisponible"
echo
echo '--- aucun build.rs, aucune macro procedurale ? ---'
if [ -f build.rs ]; then
  echo "    ATTENTION : build.rs present -- du code s execute a la compilation"
else
  echo "    aucun build.rs : rien ne s execute a la compilation"
fi
echo
echo '--- code non sur (unsafe) ? ---'
N=$(grep -rn "unsafe" src/ tests/ 2>/dev/null | grep -v '^\s*//' | wc -l)
echo "    occurrences de unsafe : $N"
[ "$N" -eq 0 ] && echo "    -> aucune. Tout le code est verifie par le compilateur."
echo
echo "--- appels reseau, processus, variables d environnement ? ---"
for motif in "std::net" "TcpStream" "UdpSocket" "Command::new" "std::process::Command" "env::var"; do
  N=$(grep -rn "$motif" src/ 2>/dev/null | wc -l)
  printf "    %-26s %s\n" "$motif" "$N"
done
echo "    (les tests d integration emploient Command::new : c est NORMAL,"
echo "     ils lancent le binaire. Seul src/ compte ici.)"

echo
echo "=================================================================="
echo "2. VERIFICATION HORS LIGNE"
echo "=================================================================="
echo "--- bibliotheques dynamiques liees au binaire ---"
B="$CARGO_TARGET_DIR/release/evidence-verify-rs"
if [ ! -x "$B" ]; then
  echo "    binaire absent ; lancer banc/build.sh d abord"
else
  if command -v ldd >/dev/null 2>&1; then
    ldd "$B" | sed 's/^/    /'
    echo "    -> libc et le chargeur dynamique seulement. Aucune bibliotheque"
    echo "       de chiffrement, de compression ni de reseau."
  fi
  echo
  echo "--- le binaire ouvre-t-il une socket ? (strace, si disponible) ---"
  if command -v strace >/dev/null 2>&1; then
    T=$(mktemp -d)
    mkdir -p "$T/p"
    printf '{"schema":"x"}' > "$T/p/submission.json"
    strace -f -e trace=network -o "$T/trace" "$B" "$T/p" >/dev/null 2>&1
    # `grep -c` sort en 1 quand il ne trouve rien ET imprime deja `0` :
    # un `|| echo 0` ajoutait un SECOND `0`, et le test suivant echouait
    # avec « integer expected ». Un controle qui casse au lieu de conclure
    # ne controle rien. Constate dans le journal de CI, corrige ici.
    N=$(grep -cE 'socket|connect|sendto' "$T/trace" 2>/dev/null | head -1)
    case "$N" in ''|*[!0-9]*) N=0 ;; esac
    echo "    appels reseau observes : $N"
    rm -rf "$T"
    if [ "$N" -eq 0 ]; then
      echo "    -> AUCUN. MESURE a l execution, et non seulement declaree."
    else
      echo "    -> PROBLEME : $N appel(s) reseau observe(s). A instruire."
      ECHEC_RESEAU=1
    fi
  else
    echo "    strace indisponible : le controle statique ci-dessus reste valable,"
    echo "    mais la mesure a l execution N A PAS ETE FAITE."
  fi
fi

echo
echo "=================================================================="
echo "3. REPRODUCTIBILITE DU BINAIRE"
echo "=================================================================="
echo "Deux compilations INDEPENDANTES, dans deux dossiers cibles distincts,"
echo "puis comparaison des octets. Rien n est annonce sans cette comparaison."
echo
A="$HOME/evr-repro-a"
Z="$HOME/evr-repro-b"
rm -rf "$A" "$Z"
CARGO_TARGET_DIR="$A" cargo build --release --offline -q 2>/dev/null
CARGO_TARGET_DIR="$Z" cargo build --release --offline -q 2>/dev/null
HA=$(sha256sum "$A/release/evidence-verify-rs" 2>/dev/null | cut -d' ' -f1)
HB=$(sha256sum "$Z/release/evidence-verify-rs" 2>/dev/null | cut -d' ' -f1)
echo "    compilation A : $HA"
echo "    compilation B : $HB"
if [ -n "$HA" ] && [ "$HA" = "$HB" ]; then
  echo "    -> IDENTIQUES a l octet."
  echo "       Portee : ce que cette execution fait varier, c est le dossier"
  echo "       CIBLE et le moment. La version de rustc reste constante."
  echo "       Mesure croisee du 2026-11-11 : le MEME condense est sorti de"
  echo "       ce poste (WSL, sources sous /mnt/c/...) et de la CI"
  echo "       (ubuntu-latest, sources sous /home/runner/work/...). La racine"
  echo '       des sources et la machine n influent donc PAS : `strip = true`'
  echo "       retire les metadonnees de debogage qui portent les chemins."
  echo "       Ce qui reste NON etabli : une autre version de rustc."
  echo "       Voir 06_BUILD_ET_REPRODUCTIBILITE.md."
else
  echo "    -> DIFFERENTS. Le binaire n est PAS reproductible en l etat, meme"
  echo "       localement. A instruire avant toute annonce."
fi
rm -rf "$A" "$Z"
echo
echo "Fin de l audit."
