<div align="center">

<img width="1200" height="475" alt="GHBanner" src="https://github.com/user-attachments/assets/0aa67016-6eaf-458a-adb2-6e31a0763ed6" />

  <h1>Built with AI Studio</h2>

  <p>The fastest path from prompt to production with Gemini.</p>

  <a href="https://aistudio.google.com/apps">Start building</a>

</div>

---

# Abraham Modular Upgrade Proof

This branch contains the deterministic authoring pipeline for the first modular Abraham equipment proof. Fal provides existing source assets; Blender 4.5.13 normalizes the canonical Abraham rig, fits and skins equipment, validates motion, and exports a mobile GLB. AppDeploy and SpeedVerse are not involved in this build.

## Build and verification

Use Python 3.13 and run `python -m pip install pytest`, then `make verify`. This runs the unit tests and the real proof build once. `make proof` builds without rerunning the tests.

Stages: fetch -> normalize-base -> fit-staff -> fit-belt -> fit-mantle -> validate -> export.

A failed stage stops the build. A model is not considered usable merely because unit tests pass; Blender must produce a passing validation report and the exported model must be visually reviewed.

## Mobile proof

Serve `abraham_upgrade_proof` with `python -m http.server 8080 -d abraham_upgrade_proof` after a successful build.

Test Base -> Staff -> Belt -> Mantle -> Fully Equipped with Idle, Walk, and Run at every level. The mantle remains attached across shoulders/torso throughout the full animation cycle; equipment must not scatter, float away, or catastrophically clip. Toggle all equipment off and confirm the base remains visible.

## Outputs

- `assets/build/mobile/abraham_upgrade_bundle.glb`: single mobile bundle, maximum 18 MiB.
- `assets/build/reports/`: validation JSON and actual Blender-rendered pose checks.
- `assets/build/source-quality/`: authored source-quality exports.
- `abraham_upgrade_proof/`: static viewer with the successful bundle copied into its assets directory.

The browser only toggles `Equip_Staff`, `Equip_Belt`, and `Equip_Mantle` and switches animations; it does not fit gear at runtime.

Fal URLs are proof inputs and may expire. The seven existing source files are downloaded from `configs/source_assets.json`; this build does not submit new paid Fal jobs or require any API secrets.
