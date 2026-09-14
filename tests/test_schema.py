from pathlib import Path
import json
import pytest

from pipeline.schema import load_build_config, load_source_manifest


def test_abraham_config_has_three_equipment_classes(tmp_path: Path):
    path = tmp_path / 'config.json'
    path.write_text(json.dumps({
        'canonical_height_m': 1.82,
        'equipment': {
            'staff': {'class': 'rigid', 'target_bone_role': 'right_hand'},
            'belt': {'class': 'semi_skinned', 'target_bone_role': 'hips'},
            'mantle': {'class': 'fully_skinned', 'target_bone_role': 'chest'},
        },
        'validation': {
            'max_unweighted_vertices': 0,
            'max_influences_per_vertex': 4,
            'max_floating_distance_m': 0.06,
            'max_penetration_ratio': 0.08,
            'max_bundle_mb': 18.0,
        },
    }))
    config = load_build_config(path)
    assert config.canonical_height_m == pytest.approx(1.82)
    assert config.equipment['staff'].equipment_class == 'rigid'
    assert config.equipment['belt'].equipment_class == 'semi_skinned'
    assert config.equipment['mantle'].equipment_class == 'fully_skinned'


def test_manifest_requires_base_staff_belt_mantle_and_three_clips(tmp_path: Path):
    path = tmp_path / 'sources.json'
    path.write_text(json.dumps({'assets': []}))
    with pytest.raises(ValueError, match='missing required source roles'):
        load_source_manifest(path)
