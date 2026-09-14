#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS="$ROOT/.tools"
VERSION="4.5.13"
ARCHIVE="blender-${VERSION}-linux-x64.tar.xz"
URL="https://download.blender.org/release/Blender4.5/${ARCHIVE}"
mkdir -p "$TOOLS"
if [ ! -x "$TOOLS/blender-${VERSION}-linux-x64/blender" ]; then
  curl -fL "$URL" -o "$TOOLS/$ARCHIVE"
  tar -xJf "$TOOLS/$ARCHIVE" -C "$TOOLS"
  rm "$TOOLS/$ARCHIVE"
fi
"$TOOLS/blender-${VERSION}-linux-x64/blender" --version | head -1
