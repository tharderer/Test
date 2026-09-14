from __future__ import annotations

from .common import apply_object_transforms, import_glb, join_meshes, transfer_weights_nearest, world_bbox
from .surface_fit import fit_radial_surface


def mantle_vertical_targets(min_z: float, max_z: float, profile: dict[str, object]) -> tuple[float, float]:
    height = float(max_z) - float(min_z)
    shoulder = float(min_z) + float(profile['shoulder_fraction_of_height']) * height
    hem = float(min_z) + float(profile['hem_fraction_of_height']) * height
    return shoulder, hem


def mantle_anchor_floor(min_z: float, max_z: float, shoulder_z: float) -> float:
    return float(shoulder_z) - .18 * (float(max_z) - float(min_z))


def fit_mantle(source_path: str, body, armature, profile: dict[str, object]):
    import bpy
    from mathutils import Vector
    from .scene_state import reset_pose
    reset_pose(armature)
    bpy.context.view_layer.update()
    imported = import_glb(source_path)
    mantle = join_meshes(imported, 'Equip_Mantle')
    apply_object_transforms(mantle, location=True, rotation=True, scale=True)
    lower, upper = world_bbox([body])
    shoulder_z, hem_z = mantle_vertical_targets(lower.z, upper.z, profile)
    source_lower, source_upper = world_bbox([mantle])
    source_height = source_upper.z - source_lower.z
    if source_height <= 1e-8 or shoulder_z <= hem_z:
        raise RuntimeError('mantle has invalid source/target height')
    factor = (shoulder_z - hem_z) / source_height
    mantle.scale = (factor, factor, factor)
    apply_object_transforms(mantle, rotation=False, scale=True)
    source_lower, source_upper = world_bbox([mantle])
    center = (lower + upper) * .5
    mantle.location += Vector((center.x, center.y, (shoulder_z + hem_z) / 2)) - (source_lower + source_upper) * .5
    apply_object_transforms(mantle, location=True, rotation=False, scale=False)
    fit_radial_surface(mantle, body, (center.x, center.y),
                       float(profile.get('surface_clearance_m', .012)), .015)
    # Barycentric body-surface weights keep corresponding cloth/body points
    # moving together. Do not smooth across unrelated sides of a thick mesh.
    transfer_weights_nearest(mantle, body, armature, max_influences=4)
    for obj in imported:
        if obj.type == 'ARMATURE' and obj != armature and obj.name in bpy.data.objects:
            bpy.data.objects.remove(obj, do_unlink=True)
    mantle['hem_target_z'] = float(hem_z)
    mantle['validation_anchor_floor_z'] = mantle_anchor_floor(lower.z, upper.z, shoulder_z)
    mantle.name = 'Equip_Mantle'
    return mantle
