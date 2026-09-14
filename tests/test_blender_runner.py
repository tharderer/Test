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


def test_python_exception_is_nonzero_and_visible_in_ci(tmp_path, monkeypatch, capfd):
    import subprocess
    import sys
    from pipeline.blender_runner import run_blender

    fake = tmp_path / 'blender'
    fake.write_text(
        f'#!{sys.executable}\n'
        'import sys\n'
        'print("Blender validation diagnostic", flush=True)\n'
        'print("Refusing invalid export", file=sys.stderr, flush=True)\n'
        'if "--python-exit-code" in sys.argv:\n'
        '    sys.exit(int(sys.argv[sys.argv.index("--python-exit-code") + 1]))\n'
    )
    fake.chmod(0o755)
    monkeypatch.setenv('BLENDER_BIN', str(fake))
    with pytest.raises(subprocess.CalledProcessError) as error:
        run_blender(tmp_path, tmp_path / 'entrypoint.py', ['--stage', 'validate'])
    assert error.value.returncode == 2
    captured = capfd.readouterr()
    assert 'Blender validation diagnostic' in captured.out
    assert 'Refusing invalid export' in captured.err
