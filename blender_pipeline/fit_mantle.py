from __future__ import annotations

from .common import apply_object_transforms, import_glb, join_meshes, limit_and_normalize_weights, restrict_vertex_groups, transfer_weights_nearest, world_bbox
from .rig_contract import CANONICAL


def mantle_vertical_targets(min_z: float, max_z: float, profile: dict[str, object]) -> tuple[float, float]:
    height = float(max_z) - float(min_z)
    return (float(min_z) + float(profile['shoulder_fraction_of_height']) * height, float(min_z) + float(profile['hem_fraction_of_height']) * height)


def mantle_anchor_floor(min_z: float, max_z: float, shoulder_z: float) -> float:
    return float(shoulder_z) - 0.18 * (float(max_z) - float(min_z))


def _cloth_allowed_groups(target, armature, profile: dict[str, object]) -> set[str]:
    roles = [r for r in profile.get('allowed_bone_roles', []) if r not in {'left_hand', 'right_hand'}]
    allowed = {CANONICAL[r] for r in roles if r in CANONICAL and armature.data.bones.get(CANONICAL[r]) is not None}
    for group in target.vertex_groups:
        token = group.name.lower().replace('_', '').replace('-', '')
        if 'hand' not in token and (any(p in token for p in ('shoulder', 'clavicle', 'upperarm')) or token.endswith('arm')):
            allowed.add(group.name)
    return allowed


def fit_mantle(source_path: str, body, armature, profile: dict[str, object]):
    import bpy
    from mathutils import Vector
    imported = import_glb(source_path)
    mantle = join_meshes(imported, 'Equip_Mantle')
    apply_object_transforms(mantle, location=True, rotation=True, scale=True)
    body_min, body_max = world_bbox([body])
    height = body_max.z - body_min.z
    shoulder_z, hem_z = mantle_vertical_targets(body_min.z, body_max.z, profile)
    body_center = (body_min + body_max) * 0.5
    mantle_min, mantle_max = world_bbox([mantle])
    source_height = mantle_max.z - mantle_min.z
    target_height = shoulder_z - hem_z
    if source_height <= 1e-8 or target_height <= 1e-8:
        raise RuntimeError('mantle has invalid source/target height')
    uniform = target_height / source_height
    mantle.scale = (uniform, uniform, uniform)
    apply_object_transforms(mantle, rotation=False, scale=True)
    points = [body.matrix_world @ v.co for v in body.data.vertices]
    cap = 0.30 * height
    sample = [p for p in points if abs(p.z - shoulder_z) <= 0.10 * height and abs(p.x - body_center.x) <= cap]
    if len(sample) < 8:
        sample = [p for p in points if abs(p.x - body_center.x) <= cap]
    if not sample:
        raise RuntimeError('cannot sample Abraham shoulder geometry')
    sx0, sx1 = min(p.x for p in sample), max(p.x for p in sample)
    sy0, sy1 = min(p.y for p in sample), max(p.y for p in sample)
    dims = mantle.dimensions
    if dims.x > 1e-8:
        mantle.scale.x *= max(0.48, (sx1 - sx0) * 1.30) / dims.x
    if dims.y > 1e-8:
        mantle.scale.y *= max(0.20, (sy1 - sy0) + 0.08) / dims.y
    apply_object_transforms(mantle, rotation=False, scale=True)
    mantle_min, mantle_max = world_bbox([mantle])
    mantle_center = (mantle_min + mantle_max) * 0.5
    target_center = Vector((body_center.x, body_center.y, shoulder_z - (mantle_max.z - mantle_min.z) * 0.5))
    mantle.location += target_center - mantle_center
    apply_object_transforms(mantle, location=True, rotation=False, scale=False)
    anchor_floor = mantle_anchor_floor(body_min.z, body_max.z, shoulder_z)
    group = mantle.vertex_groups.new(name='MantleShrinkwrap')
    ids = [v.index for v in mantle.data.vertices if (mantle.matrix_world @ v.co).z >= anchor_floor]
    if ids:
        group.add(ids, 1.0, 'REPLACE')
        bpy.context.view_layer.objects.active = mantle
        mantle.select_set(True)
        mod = mantle.modifiers.new(name='FitToAbraham', type='SHRINKWRAP')
        mod.target = body
        mod.wrap_method = 'NEAREST_SURFACEPOINT'
        mod.wrap_mode = 'OUTSIDE_SURFACE'
        mod.offset = float(profile.get('surface_clearance_m', 0.012))
        mod.vertex_group = group.name
        bpy.ops.object.modifier_apply(modifier=mod.name)
    transfer_weights_nearest(mantle, body, armature, max_influences=4)
    restrict_vertex_groups(mantle, _cloth_allowed_groups(mantle, armature, profile))
    bpy.ops.object.select_all(action='DESELECT')
    mantle.select_set(True)
    bpy.context.view_layer.objects.active = mantle
    if mantle.vertex_groups:
        bpy.ops.object.mode_set(mode='EDIT')
        try:
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.object.vertex_group_smooth(group_select_mode='ALL', factor=0.5, repeat=3)
        finally:
            bpy.ops.object.mode_set(mode='OBJECT')
    limit_and_normalize_weights(mantle, max_influences=4)
    for obj in imported:
        if obj.type == 'ARMATURE' and obj != armature and obj.name in bpy.data.objects:
            bpy.data.objects.remove(obj, do_unlink=True)
    mantle['hem_target_z'] = float(hem_z)
    mantle['validation_anchor_floor_z'] = float(anchor_floor)
    mantle.name = 'Equip_Mantle'
    return mantle
