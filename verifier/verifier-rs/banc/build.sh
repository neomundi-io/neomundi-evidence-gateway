#!/usr/bin/env bash
# Compile le verificateur Rust. A lancer DANS WSL (ou tout Linux).
#
# La cible de compilation est placee hors de /mnt/c : Cargo y ecrit des
# milliers de petits fichiers, et le pont NTFS de WSL rend cela dix fois
# plus lent. Les SOURCES, elles, restent dans le depot.
set -euo pipefail

RACINE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CAISSE="$RACINE/verifier-rs"
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-$HOME/evr-target}"

if ! command -v cargo >/dev/null 2>&1; then
  if [ -f "$HOME/.cargo/env" ]; then
    # shellcheck disable=SC1091
    . "$HOME/.cargo/env"
  fi
fi
command -v cargo >/dev/null 2>&1 || {
  echo "cargo absent. Voir 06_BUILD_ET_REPRODUCTIBILITE.md" >&2
  exit 1
}

echo "rustc  : $(rustc --version)"
echo "cargo  : $(cargo --version)"
echo "cible  : $(rustc --print host-tuple 2>/dev/null || echo inconnue)"
echo "sources: $CAISSE"
echo "target : $CARGO_TARGET_DIR"
echo

cd "$CAISSE"
# `--offline` : apres la premiere compilation, aucun acces reseau n est
# necessaire. Il n y a aucune dependance a telecharger.
cargo build --release --offline
echo
echo "binaire : $CARGO_TARGET_DIR/release/evidence-verify-rs"
sha256sum "$CARGO_TARGET_DIR/release/evidence-verify-rs"
