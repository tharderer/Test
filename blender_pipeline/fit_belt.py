from __future__ import annotations

from .common import (apply_object_transforms, import_glb, join_meshes,
                     restrict_vertex_groups, transfer_weights_nearest, world_bbox)
from .rig_contract import CANONICAL
from .surface_fit import torso_sample_indices, fit_radial_surface


def belt_waist_z(min_z: float, max_z: float, profile: dict[str, object]) -> float:
    return float(min_z) + float(profile['waist_fraction_of_height']) * (float(max_z) - float(min_z))


def torso_half_width_cap(height: float) -> float:
    return 0.24 * float(height)


def _rotate_shortest_axis_to_z(obj) -> None:
    from mathutils import Vector
    shortest = min(range(3), key=lambda i: obj.dimensions[i])
    if shortest == 2:
        return
    axis = (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)))[shortest]
    obj.rotation_mode = 'QUATERNION'
    obj.rotation_quaternion = axis.rotation_difference(Vector((0, 0, 1))) @ obj.rotation_quaternion
    obj.rotation_mode = 'XYZ'
    apply_object_transforms(obj, rotation=True, scale=False)


def fit_belt(source_path: str, body, armature, profile: dict[str, object]):
    from mathutils import Vector
    from .scene_state import reset_pose
    import bpy
    reset_pose(armature)
    bpy.context.view_layer.update()
    imported = import_glb(source_path)
    belt = join_meshes(imported, 'Equip_Belt')
    apply_object_transforms(belt, location=True, rotation=True, scale=True)
    _rotate_shortest_axis_to_z(belt)
    body_min, body_max = world_bbox([body])
    waist_z = belt_waist_z(body_min.z, body_max.z, profile)
    allowed = {CANONICAL[role] for role in ('hips', 'spine', 'chest', 'upper_chest') if role in CANONICAL}
    points = [body.matrix_world @ v.co for v in body.data.vertices]
    torso_weights = [sum(g.weight for g in v.groups if body.vertex_groups[g.group].name in allowed)
                     for v in body.data.vertices]
    indices = torso_sample_indices(points, torso_weights, waist_z, 0.035)
    x_center = (body_min.x + body_max.x) * .5
    cap = torso_half_width_cap(body_max.z - body_min.z)
    sample = [points[i] for i in indices if abs(points[i].x - x_center) <= cap]
    if not sample:
        raise RuntimeError('no torso samples inside the canonical waist region')
    x_min, x_max = min(p.x for p in sample), max(p.x for p in sample)
    y_min, y_max = min(p.y for p in sample), max(p.y for p in sample)
    center = Vector(((x_min + x_max) / 2, (y_min + y_max) / 2, waist_z))
    clearance = float(profile.get('radial_clearance_m', .008))
    target_dims = Vector((x_max - x_min + .03, y_max - y_min + .03,
                          float(profile.get('band_height_m', .055))))
    if min(belt.dimensions) <= 1e-8:
        raise RuntimeError('belt source has degenerate dimensions')
    belt.scale = tuple(target_dims[i] / belt.dimensions[i] for i in range(3))
    apply_object_transforms(belt, rotation=False, scale=True)
    lower, upper = world_bbox([belt])
    belt.location += center - (lower + upper) * .5
    apply_object_transforms(belt, location=True, rotation=False, scale=False)
    fit_radial_surface(belt, body, (center.x, center.y), clearance, .018)
    transfer_weights_nearest(belt, body, armature, max_influences=4)
    restrict_vertex_groups(belt, allowed)
    belt.name = 'Equip_Belt'
    print(f'Belt torso-only dimensions: {tuple(round(v, 4) for v in belt.dimensions)}', flush=True)
    return belt
