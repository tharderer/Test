from pathlib import Path
import pytest

from blender_pipeline.export_bundle import MOBILE_NODE_NAMES, enforce_bundle_size


def test_mobile_node_names_are_runtime_api():
    assert MOBILE_NODE_NAMES == {'Abraham_Base', 'Equip_Staff', 'Equip_Belt', 'Equip_Mantle', 'Abraham_Rig'}


def test_enforce_bundle_size_accepts_under_ceiling(tmp_path: Path):
    path = tmp_path / 'bundle.glb'
    path.write_bytes(b'x' * 1024)
    assert enforce_bundle_size(path, 1.0) < 1.0


def test_enforce_bundle_size_rejects_over_ceiling(tmp_path: Path):
    path = tmp_path / 'bundle.glb'
    path.write_bytes(b'x' * (2 * 1024 * 1024))
    with pytest.raises(RuntimeError, match='exceeds 1.0 MB ceiling'):
        enforce_bundle_size(path, 1.0)
