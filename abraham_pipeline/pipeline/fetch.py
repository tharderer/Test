from pathlib import Path
from urllib.request import urlopen

from .schema import SourceManifest


def fetch_sources(manifest: SourceManifest, destination: Path, opener=urlopen) -> dict[str, Path]:
    destination.mkdir(parents=True, exist_ok=True)
    result: dict[str, Path] = {}
    for asset in manifest.assets:
        target = destination / asset.filename
        if not target.exists():
            temp = target.with_suffix(target.suffix + '.part')
            try:
                with opener(asset.url) as response, temp.open('wb') as out:
                    while chunk := response.read(1024 * 1024):
                        out.write(chunk)
                temp.replace(target)
            except Exception:
                temp.unlink(missing_ok=True)
                raise
        result[asset.role] = target
    return result
