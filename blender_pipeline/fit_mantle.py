from __future__ import annotations

from .common import (
    apply_object_transforms,
    import_glb,
    join_meshes,
    limit_and_normalize_weights,
    restrict_vertex_groups,
    transfer_weights_nearest,
    world_bbox,
)
from .rig_contract import CANONICAL


def mantle_vertical_targets(min_z: float, max_z: float, profile: dict[str, object]) -> tuple[float, float]:
    height = float(max_z) - float(min_z)
    shoulder = float(min_z) + float(profile['shoulder_fraction_of_height']) * height
    hem = float(min_z) + float(profile['hem_fraction_of_height']) * height
    return shoulder, hem


def _cloth_allowed_groups(target, armature, profile: dict[str, object]) -> set[str]:
    allowed_roles = [role for role in profile.get('allowed_bone_roles', []) if role not in {'left_hand', 'right_hand'}]
    allowed = {
        CANONICAL[role]
        for role in allowed_roles
        if role in CANONICAL and armature.data.bones.get(CANONICAL[role]) is not None
    }
    for group in target.vertex_groups:
        token = group.name.lower().replace('_', '').replace('-', '')
        if 'hand' in token:
            continue
        if any(part in token for part in ('shoulder', 'clavicle', 'upperarm')) or token.endswith('arm'):
            allowed.add(group.name)
    return allowed


def fit_mantle(source_path: str, body, armature, profile: dict[str, object]):
    import bpy
    from mathutils import Vector

    imported = import_glb(source_path)
    mantle = join_meshes(imported, 'Equip_Mantle')
    apply_object_transforms(mantle, location=True, rotation=True, scale=True)

    body_min, body_max = world_bbox([body])
    shoulder_z, hem_z = mantle_vertical_targets(body_min.z, body_max.z, profile)
    mantle_min, mantle_max = world_bbox([mantle])
    source_height = mantle_max.z - mantle_min.z
    target_height = shoulder_z - hem_z
    if source_height <= 1e-8 or target_height <= 1e-8:
        raise RuntimeError('mantle has invalid source/target height')
    scale = target_height / source_height
    mantle.scale = (scale, scale, scale)
    apply_object_transforms(mantle, rotation=False, scale=True)

    mantle_min, mantle_max = world_bbox([mantle])
    mantle_center = (mantle_min + mantle_max) * 0.5
    body_center = (body_min + body_max) * 0.5
    target_center = Vector((body_center.x, body_center.y, shoulder_z - (mantle_max.z - mantle_min.z) * 0.5))
    mantle.location += target_center - mantle_center
    apply_object_transforms(mantle, location=True, rotation=False, scale=False)

    shrink_group = mantle.vertex_groups.new(name='MantleShrinkwrap')
    close_indices = []
    for vertex in mantle.data.vertices:
        world = mantle.matrix_world @ vertex.co
        inside_xy = (
            body_min.x - 0.09 <= world.x <= body_max.x + 0.09
            and body_min.y - 0.09 <= world.y <= body_max.y + 0.09
        )
        if inside_xy and world.z >= hem_z:
            close_indices.append(vertex.index)
    if close_indices:
        shrink_group.add(close_indices, 1.0, 'REPLACE')
        bpy.context.view_layer.objects.active = mantle
        mantle.select_set(True)
        shrink = mantle.modifiers.new(name='FitToAbraham', type='SHRINKWRAP')
        shrink.target = body
        shrink.wrap_method = 'NEAREST_SURFACEPOINT'
        shrink.wrap_mode = 'OUTSIDE_SURFACE'
        shrink.offset = float(profile.get('surface_clearance_m', 0.012))
        shrink.vertex_group = shrink_group.name
        bpy.ops.object.modifier_apply(modifier=shrink.name)

    transfer_weights_nearest(mantle, body, armature, max_influences=4)
    allowed = _cloth_allowed_groups(mantle, armature, profile)
    restrict_vertex_groups(mantle, allowed)

    bpy.ops.object.select_all(action='DESELECT')
    mantle.select_set(True)
    bpy.context.view_layer.objects.active = mantle
    if mantle.vertex_groups:
        bpy.ops.object.vertex_group_smooth(group_select_mode='ALL', factor=0.5, repeat=3)
    limit_and_normalize_weights(mantle, max_influences=4)

    for obj in imported:
        if obj.type == 'ARMATURE' and obj != armature and obj.name in bpy.data.objects:
            bpy.data.objects.remove(obj, do_unlink=True)
    mantle['hem_target_z'] = float(hem_z)
    mantle.name = 'Equip_Mantle'
    return mantle
