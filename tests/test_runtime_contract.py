from pathlib import Path
import json
import pytest

from blender_pipeline.rig_contract import canonical_bone_name, resolve_role_names
from blender_pipeline.fit_staff import staff_target_length, staff_grip_fraction_from_bottom
from blender_pipeline.fit_belt import belt_waist_z, torso_half_width_cap
from blender_pipeline.fit_mantle import mantle_vertical_targets, mantle_anchor_floor
from pipeline.schema import load_build_config


def test_bone_aliases_cover_required_roles():
    aliases = json.loads(Path('configs/bone_aliases.json').read_text())
    required = {'hips', 'spine', 'chest', 'neck', 'head', 'right_hand', 'left_hand', 'right_foot', 'left_foot'}
    assert required <= set(aliases)


def test_canonical_bone_names_are_stable():
    assert canonical_bone_name('right_hand') == 'ABR_RIGHT_HAND'
    assert canonical_bone_name('hips') == 'ABR_HIPS'


def test_resolve_role_names_prefers_case_insensitive_exact_then_punctuation_stripped():
    aliases = {'hips': ['Hips', 'mixamorig:Hips'], 'right_hand': ['RightHand', 'mixamorig:RightHand']}
    names = ['MIXAMORIG:HIPS', 'mixamorig_RightHand']
    resolved = resolve_role_names(names, aliases, required={'hips', 'right_hand'})
    assert resolved == {'hips': 'MIXAMORIG:HIPS', 'right_hand': 'mixamorig_RightHand'}


def test_resolve_role_names_fails_closed_for_missing_required_role():
    aliases = {'hips': ['Hips'], 'head': ['Head']}
    with pytest.raises(RuntimeError, match='missing canonical bone roles'):
        resolve_role_names(['Hips'], aliases, required={'hips', 'head'})


def test_staff_fit_profile_and_math_are_canonical():
    config = load_build_config(Path('configs/abraham_proof.json'))
    staff = config.equipment['staff']
    assert staff_target_length(config.canonical_height_m, staff.fit) == pytest.approx(1.6016)
    assert staff_grip_fraction_from_bottom(staff.fit) == 0.62


def test_belt_waist_fraction_is_deterministic():
    config = load_build_config(Path('configs/abraham_proof.json'))
    belt = config.equipment['belt']
    assert belt_waist_z(0.1, 1.9, belt.fit) == 1.09


def test_belt_torso_sampling_excludes_apose_hands():
    assert torso_half_width_cap(1.82) == pytest.approx(0.4368)


def test_mantle_vertical_targets_are_deterministic():
    config = load_build_config(Path('configs/abraham_proof.json'))
    mantle = config.equipment['mantle']
    shoulder, hem = mantle_vertical_targets(0.1, 1.9, mantle.fit)
    assert shoulder == pytest.approx(1.576)
    assert hem == pytest.approx(0.784)


def test_mantle_validation_only_requires_upper_garment_to_hug_body():
    assert mantle_anchor_floor(0.1, 1.9, 1.576) == pytest.approx(1.252)


def test_viewer_has_no_runtime_fitting_controls():
    js = Path('abraham_upgrade_proof/main.js').read_text()
    for token in ['fitSelected', 'position.set(', 'rotation.set(', 'scale.set(', 'clearanceMeters']:
        assert token not in js


def test_viewer_uses_fixed_equipment_node_names():
    js = Path('abraham_upgrade_proof/main.js').read_text()
    for name in ('Equip_Staff', 'Equip_Belt', 'Equip_Mantle'):
        assert name in js


def test_viewer_loads_one_local_bundle():
    js = Path('abraham_upgrade_proof/main.js').read_text()
    assert "const MODEL_URL = './assets/abraham_upgrade_bundle.glb';" in js
    assert js.count('loader.load(') == 1
