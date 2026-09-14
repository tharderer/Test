from pathlib import Path


def test_build_wrapper_runs_pipeline_and_copies_bundle():
    script = Path('scripts/build_proof.sh').read_text()
    assert 'scripts/bootstrap_blender.sh' in script
    assert 'python -m pipeline.build' in script
    assert 'abraham_upgrade_proof/assets/abraham_upgrade_bundle.glb' in script
    assert 'AppDeploy' not in script


def test_makefile_exposes_test_proof_verify():
    text = Path('Makefile').read_text()
    for target in ('test:', 'proof:', 'verify:'):
        assert target in text


def test_readme_contains_mobile_mantle_pass_condition():
    text = Path('README.md').read_text()
    assert 'Base -> Staff -> Belt -> Mantle -> Fully Equipped' in text
    assert 'mantle remains attached across shoulders/torso' in text
    assert 'Fal URLs are proof inputs and may expire' in text
