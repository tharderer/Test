import json
from pathlib import Path

from blender_pipeline.rig_contract import resolve_role_names


def test_zero_padded_meshy_spine_names_are_recognized_without_merging_roles():
    names = [
        'Hips', 'LeftUpLeg', 'LeftLeg', 'LeftFoot', 'LeftToeBase',
        'RightUpLeg', 'RightLeg', 'RightFoot', 'RightToeBase',
        'Spine02', 'Spine01', 'Spine', 'LeftShoulder', 'LeftArm',
        'LeftForeArm', 'LeftHand', 'RightShoulder', 'RightArm',
        'RightForeArm', 'RightHand', 'neck', 'Head', 'head_end', 'headfront',
    ]
    aliases = json.loads(Path('configs/bone_aliases.json').read_text())
    resolved = resolve_role_names(names, aliases)
    assert resolved['chest'] == 'Spine01'
    assert resolved['upper_chest'] == 'Spine02'
    assert len(set(resolved.values())) == len(resolved)
