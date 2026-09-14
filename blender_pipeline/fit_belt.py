from __future__ import annotations

from .common import apply_object_transforms, import_glb, join_meshes, restrict_vertex_groups, transfer_weights_nearest, world_bbox
from .rig_contract import CANONICAL


def belt_waist_z(min_z: float, max_z: float, profile: dict[str, object]) -> float:
    return float(min_z) + float(profile['waist_fraction_of_height']) * (float(max_z) - float(min_z))


def torso_half_width_cap(height: float) -> float:
    """Central X band used to exclude A-pose hands/forearms from waist fitting."""
    return float(height) * 0.24


def _rotate_shortest_axis_to_z(obj) -> None:
    from mathutils import Vector
    dims = obj.dimensions
    shortest = min(range(3), key=lambda i: dims[i])
    if shortest == 2:
        return
    axis = (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)))[shortest]
    obj.rotation_mode = 'QUATERNION'
    obj.rotation_quaternion = axis.rotation_difference(Vector((0, 0, 1))) @ obj.rotation_quaternion
    obj.rotation_mode = 'XYZ'
    apply_object_transforms(obj, rotation=True, scale=False)


def fit_belt(source_path: str, body, armature, profile: dict[str, object]):
    import bpy
    from mathutils import Vector

    imported = import_glb(source_path)
    belt = join_meshes(imported, 'Equip_Belt')
    apply_object_transforms(belt, location=True, rotation=True, scale=True)
    _rotate_shortest_axis_to_z(belt)

    body_min, body_max = world_bbox([body])
    height = body_max.z - body_min.z
    waist_z = belt_waist_z(body_min.z, body_max.z, profile)
    body_center_x = (body_min.x + body_max.x) * 0.5
    cap = torso_half_width_cap(height)
    world_points = [body.matrix_world @ vertex.co for vertex in body.data.vertices]
    sample = [p for p in world_points if abs(p.z - waist_z) <= 0.045 and abs(p.x - body_center_x) <= cap]
    if len(sample) < 8:
        central = [p for p in world_points if abs(p.x - body_center_x) <= cap]
        sample = sorted(central, key=lambda p: abs(p.z - waist_z))[:max(8, min(128, len(central)))]
    if not sample:
        raise RuntimeError('cannot sample Abraham torso waist geometry')

    x_min, x_max = min(p.x for p in sample), max(p.x for p in sample)
    y_min, y_max = min(p.y for p in sample), max(p.y for p in sample)
    clearance = float(profile.get('radial_clearance_m', 0.008))
    target_x = (x_max - x_min) + 2 * clearance
    target_y = (y_max - y_min) + 2 * clearance

    dims = belt.dimensions
    if min(dims.x, dims.y) <= 1e-8:
        raise RuntimeError('belt source has degenerate dimensions')
    belt.scale.x *= target_x / dims.x
    belt.scale.y *= target_y / dims.y
    # Keep the belt visually slim even if the generated source includes bulky pouches.
    target_z = min(max(0.07, 0.045 * height), 0.11)
    if dims.z > 1e-8:
        belt.scale.z *= target_z / dims.z
    apply_object_transforms(belt, rotation=False, scale=True)

    belt_min, belt_max = world_bbox([belt])
    belt_center = (belt_min + belt_max) * 0.5
    target_center = Vector(((x_min + x_max) * 0.5, (y_min + y_max) * 0.5, waist_z))
    belt.location += target_center - belt_center
    apply_object_transforms(belt, location=True, rotation=False, scale=False)

    # Conform the belt to the robe/body surface before skinning so it cannot float.
    shrink_group = belt.vertex_groups.new(name='BeltFitSurface')
    shrink_group.add([v.index for v in belt.data.vertices], 1.0, 'REPLACE')
    bpy.context.view_layer.objects.active = belt
    belt.select_set(True)
    shrink = belt.modifiers.new(name='FitBeltToAbraham', type='SHRINKWRAP')
    shrink.target = body
    shrink.wrap_method = 'NEAREST_SURFACEPOINT'
    shrink.wrap_mode = 'OUTSIDE_SURFACE'
    shrink.offset = clearance
    shrink.vertex_group = shrink_group.name
    bpy.ops.object.modifier_apply(modifier=shrink.name)

    transfer_weights_nearest(belt, body, armature, max_influences=4)
    allowed = {CANONICAL[role] for role in profile.get('allowed_bone_roles', ['hips', 'spine', 'chest']) if role in CANONICAL and armature.data.bones.get(CANONICAL[role]) is not None}
    restrict_vertex_groups(belt, allowed)
    belt.name = 'Equip_Belt'
    return belt
