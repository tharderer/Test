from __future__ import annotations

import re

from .common import import_glb
from .rig_contract import CANONICAL, resolve_bone_roles

_BONE_PATH = re.compile(r'pose\.bones\["([^"]+)"\]')


def _find_action(imported, bpy):
    for obj in imported:
        if obj.type == 'ARMATURE' and obj.animation_data and obj.animation_data.action:
            return obj, obj.animation_data.action
    for action in bpy.data.actions:
        if action.users:
            return None, action
    raise RuntimeError('animation GLB contains no action')


def _retarget_fcurve_paths(action, source_to_canonical: dict[str, str]) -> None:
    for curve in action.fcurves:
        match = _BONE_PATH.search(curve.data_path)
        if not match:
            continue
        source = match.group(1)
        target = source_to_canonical.get(source)
        if target:
            curve.data_path = curve.data_path.replace(f'pose.bones["{source}"]', f'pose.bones["{target}"]')


def import_action(glb_path: str, canonical_armature, alias_map: dict[str, list[str]], action_name: str):
    import bpy

    imported = import_glb(glb_path)
    temp_armature, action = _find_action(imported, bpy)
    if temp_armature is None:
        raise RuntimeError('animation action is not attached to an imported armature')
    role_map = resolve_bone_roles(temp_armature, alias_map)
    source_to_canonical = {
        source_name: CANONICAL[role]
        for role, source_name in role_map.items()
        if role in CANONICAL
    }
    _retarget_fcurve_paths(action, source_to_canonical)
    action.name = action_name

    if canonical_armature.animation_data is None:
        canonical_armature.animation_data_create()
    canonical_armature.animation_data.action = action
    action.use_fake_user = True

    for obj in imported:
        bpy.data.objects.remove(obj, do_unlink=True)
    return action
