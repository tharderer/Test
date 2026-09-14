from __future__ import annotations

import argparse
from pathlib import Path

from .blender_runner import run_blender
from .fetch import fetch_sources
from .schema import load_source_manifest

STAGES = ('normalize-base', 'fit-staff', 'fit-belt', 'fit-mantle', 'validate', 'export')


def run_stage(repo_root: Path, stage: str, config_path: Path) -> None:
    try:
        run_blender(
            repo_root,
            repo_root / 'blender_pipeline' / 'entrypoint.py',
            [
                '--stage', stage,
                '--config', str(config_path),
                '--aliases', 'configs/bone_aliases.json',
                '--source-dir', 'assets/source',
                '--out-dir', 'assets/build',
            ],
        )
    except Exception as exc:
        raise RuntimeError(f'Blender stage failed: {stage}') from exc


def build_proof(repo_root: Path, config_path: Path, sources_path: Path) -> None:
    manifest = load_source_manifest(sources_path)
    fetch_sources(manifest, repo_root / 'assets' / 'source')
    for stage in STAGES:
        print(f'==> {stage}', flush=True)
        run_stage(repo_root, stage, config_path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='configs/abraham_proof.json')
    parser.add_argument('--sources', default='configs/source_assets.json')
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    repo_root = Path.cwd()
    build_proof(repo_root, Path(args.config), Path(args.sources))


if __name__ == '__main__':
    main()
