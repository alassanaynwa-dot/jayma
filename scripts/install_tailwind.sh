#!/usr/bin/env bash
# Télécharge le binaire Tailwind CSS CLI standalone (pas besoin de Node).
# À exécuter une seule fois après clone du repo.

set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p .bin

ARCH="$(uname -m)"
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"

case "$OS-$ARCH" in
  linux-x86_64)  SUFFIX="linux-x64" ;;
  linux-aarch64) SUFFIX="linux-arm64" ;;
  darwin-x86_64) SUFFIX="macos-x64" ;;
  darwin-arm64)  SUFFIX="macos-arm64" ;;
  *) echo "Plateforme non supportée : $OS-$ARCH" ; exit 1 ;;
esac

URL="https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-${SUFFIX}"

echo "Téléchargement de Tailwind CLI ($SUFFIX)..."
curl -sL -o .bin/tailwindcss "$URL"
chmod +x .bin/tailwindcss

echo "OK : $(.bin/tailwindcss --help | head -1)"
