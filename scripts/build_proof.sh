#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
bash scripts/bootstrap_blender.sh
python -m pipeline.build --config configs/abraham_proof.json --sources configs/source_assets.json
mkdir -p abraham_upgrade_proof/assets
cp assets/build/mobile/abraham_upgrade_bundle.glb abraham_upgrade_proof/assets/abraham_upgrade_bundle.glb
printf 'Proof ready: %s\n' "$ROOT/abraham_upgrade_proof/index.html"
