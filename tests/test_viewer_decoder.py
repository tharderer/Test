from pathlib import Path


def test_compressed_bundle_has_matching_decoder():
    text = Path('abraham_upgrade_proof/main.js').read_text()
    assert "import { DRACOLoader }" in text
    assert 'loader.setDRACOLoader(draco)' in text


def test_camera_and_ground_use_gltf_y_up():
    text = Path('abraham_upgrade_proof/main.js').read_text()
    assert 'ground.position.y = bounds.min.y' in text
    assert 'camera.position.z = center.z + maxSize * 2.15' in text
