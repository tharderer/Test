from pathlib import Path
import pytest

from pipeline.blender_runner import blender_binary


def test_blender_binary_prefers_blender_bin_env(tmp_path: Path, monkeypatch):
    fake = tmp_path / 'blender'
    fake.write_text('')
    fake.chmod(0o755)
    monkeypatch.setenv('BLENDER_BIN', str(fake))
    assert blender_binary(tmp_path) == fake


def test_blender_binary_fails_with_bootstrap_hint(tmp_path: Path, monkeypatch):
    monkeypatch.delenv('BLENDER_BIN', raising=False)
    with pytest.raises(FileNotFoundError, match='bootstrap_blender.sh'):
        blender_binary(tmp_path)
