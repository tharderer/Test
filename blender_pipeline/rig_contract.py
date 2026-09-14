from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

CANONICAL = {
    'hips': 'ABR_HIPS',
    'spine': 'ABR_SPINE',
    'chest': 'ABR_CHEST',
    'upper_chest': 'ABR_UPPER_CHEST',
    'neck': 'ABR_NECK',
    'head': 'ABR_HEAD',
    'right_hand': 'ABR_RIGHT_HAND',
    'left_hand': 'ABR_LEFT_HAND',
    'right_foot': 'ABR_RIGHT_FOOT',
    'left_foot': 'ABR_LEFT_FOOT',
}

REQUIRED_ROLES = {
    'hips', 'spine', 'chest', 'neck', 'head',
    'right_hand', 'left_hand', 'right_foot', 'left_foot',
}


def canonical_bone_name(role: str) -> str:
    try:
        return CANONICAL[role]
    except KeyError as exc:
        raise KeyError(f'unknown canonical bone role: {role}') from exc


def _token(value: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', value.lower())


def resolve_role_names(
    bone_names: Iterable[str],
    alias_map: Mapping[str, list[str]],
    *,
    required: set[str] | None = None,
) -> dict[str, str]:
    names = list(bone_names)
    lower_lookup = {name.lower(): name for name in names}
    token_lookup: dict[str, str] = {}
    for name in names:
        token_lookup.setdefault(_token(name), name)

    resolved: dict[str, str] = {}
    for role, aliases in alias_map.items():
        exact = next((lower_lookup[a.lower()] for a in aliases if a.lower() in lower_lookup), None)
        if exact is not None:
            resolved[role] = exact
            continue
        normalized = next((token_lookup[_token(a)] for a in aliases if _token(a) in token_lookup), None)
        if normalized is not None:
            resolved[role] = normalized

    required_roles = REQUIRED_ROLES if required is None else required
    missing = sorted(required_roles - set(resolved))
    if missing:
        raise RuntimeError(f'missing canonical bone roles: {missing}; available source bones: {names}')
    return resolved


def resolve_bone_roles(armature, alias_map: Mapping[str, list[str]]) -> dict[str, str]:
    return resolve_role_names((bone.name for bone in armature.data.bones), alias_map)


def normalize_rig(armature, role_map: Mapping[str, str]) -> None:
    scene_meshes = [obj for obj in armature.users_scene[0].objects if obj.type == 'MESH'] if armature.users_scene else []
    for role, source_name in role_map.items():
        target_name = canonical_bone_name(role)
        bone = armature.data.bones.get(source_name)
        if bone is None:
            continue
        old_name = bone.name
        bone.name = target_name
        for obj in scene_meshes:
            group = obj.vertex_groups.get(old_name)
            if group is not None:
                group.name = target_name


def ensure_socket(
    armature,
    bone_name: str = 'ABR_RIGHT_HAND',
    socket_name: str = 'Socket_RightHand',
):
    import bpy
    from mathutils import Vector

    existing = armature.data.bones.get(socket_name)
    if existing is not None:
        return existing
    source = armature.data.bones.get(bone_name)
    if source is None:
        raise RuntimeError(f'missing socket parent bone: {bone_name}')

    previous_active = bpy.context.view_layer.objects.active
    previous_mode = armature.mode
    bpy.context.view_layer.objects.active = armature
    armature.select_set(True)
    if previous_mode != 'EDIT':
        bpy.ops.object.mode_set(mode='EDIT')
    edit_source = armature.data.edit_bones.get(bone_name)
    socket = armature.data.edit_bones.new(socket_name)
    socket.parent = edit_source
    socket.use_connect = False
    socket.use_deform = False
    socket.head = edit_source.tail.copy()
    direction = edit_source.tail - edit_source.head
    if direction.length < 1e-6:
        direction = Vector((0.0, 0.05, 0.0))
    else:
        direction.normalize()
        direction *= 0.05
    socket.tail = socket.head + direction
    bpy.ops.object.mode_set(mode='OBJECT')
    if previous_active is not None:
        bpy.context.view_layer.objects.active = previous_active
    return armature.data.bones[socket_name]
