from pathlib import Path
import os
import subprocess


def blender_binary(repo_root: Path) -> Path:
    candidates: list[Path] = []
    if os.getenv('BLENDER_BIN'):
        candidates.append(Path(os.environ['BLENDER_BIN']))
    candidates.append(repo_root / '.tools/blender-4.5.13-linux-x64/blender')
    for path in candidates:
        if path.exists() and os.access(path, os.X_OK):
            return path
    raise FileNotFoundError('Blender 4.5.13 not found; run scripts/bootstrap_blender.sh')


def run_blender(repo_root: Path, script: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    cmd = [
        str(blender_binary(repo_root)), '--background', '--factory-startup', '--python',
        str(script), '--', *args,
    ]
    return subprocess.run(cmd, cwd=repo_root, check=True, text=True, capture_output=True)
