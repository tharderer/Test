import pytest
from blender_pipeline.rig_contract import resolve_role_names


def test_missing_role_error_shows_actual_source_bone_names():
    with pytest.raises(RuntimeError, match='Spine02'):
        resolve_role_names(['Hips', 'Spine02'], {'chest': ['Chest']}, required={'chest'})
