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


def test_run_blender_propagates_python_script_failures(tmp_path: Path, monkeypatch):
    import pipeline.blender_runner as runner

    fake = tmp_path / 'blender'
    fake.write_text('')
    fake.chmod(0o755)
    monkeypatch.setenv('BLENDER_BIN', str(fake))
    observed = {}

    def fake_run(cmd, **kwargs):
        observed['cmd'] = cmd
        class Result:
            returncode = 0
        return Result()

    monkeypatch.setattr(runner.subprocess, 'run', fake_run)
    runner.run_blender(tmp_path, tmp_path / 'stage.py', ['--stage', 'normalize-base'])
    assert '--python-exit-code' in observed['cmd']
    idx = observed['cmd'].index('--python-exit-code')
    assert observed['cmd'][idx + 1] == '1'
