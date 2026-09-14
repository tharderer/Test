# Abraham Modular Upgrade Proof

This repository contains the deterministic authoring pipeline for the first modular Abraham equipment proof. Fal provides source assets; Blender 4.5.13 is the authoring authority that normalizes the one canonical Abraham rig, fits/skinning equipment, validates motion, optimizes the final GLB, and exports a runtime bundle. AppDeploy is not part of asset generation.

## One-command proof build

```bash
make proof
```

The wrapper bootstraps Blender 4.5.13, downloads missing proof inputs, executes these fail-closed stages in order, and copies the successful mobile bundle into the static viewer:

```text
fetch -> normalize-base -> fit-staff -> fit-belt -> fit-mantle -> validate -> export
```

A failed fitting or validation stage stops the build; export never continues after a failed validation report.

## Tests and full verification

```bash
make test
make verify
```

`make test` runs all non-Blender contract tests. `make verify` additionally builds the actual proof and rejects a bundle over 18 MB.

## Mobile proof workflow

1. Run `make proof`.
2. Serve the viewer with `python -m http.server 8080 -d abraham_upgrade_proof`.
3. Open `http://<computer-ip>:8080` on the Android test phone.
4. Test `Base -> Staff -> Belt -> Mantle -> Fully Equipped`.
5. At every stage, play Idle, Walk, and Run.
6. Staff pass condition: it stays with the right-hand socket throughout each animation.
7. Belt pass condition: it stays around the waist and deforms with hips/spine rather than floating.
8. Mantle pass condition: **mantle remains attached across shoulders/torso** for a full Walk and Run cycle without teleporting, scattering, or catastrophic clipping.
9. Switch all upgrades off and confirm the base character remains usable.
10. Test the optional-gear failure path by using a copy of the bundle/viewer with one equipment node name changed; the base must remain visible and the viewer must show a warning.

## Source asset retention

Fal URLs are proof inputs and may expire. Once the seven files have been downloaded into `assets/source/`, the deterministic Blender build can be repeated locally without Fal. The raw inputs and generated outputs are gitignored because they are large binary build artifacts.

## Runtime contract

The shipping viewer loads one `abraham_upgrade_bundle.glb`. The runtime API is the fixed node set `Abraham_Base`, `Equip_Staff`, `Equip_Belt`, `Equip_Mantle`, `Abraham_Rig` plus animations `Idle`, `Walk`, and `Run`. The browser never performs accessory position, rotation, scale, shrinkwrap, or weight fitting; it only toggles visibility and switches animation clips.
