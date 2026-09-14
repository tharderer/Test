"""Keep fitting in the bind pose and scale each imported hierarchy once."""
from __future__ import annotations


def hierarchy_roots(objects):
    objects = list(objects)
    identities = {id(obj) for obj in objects}
    return [obj for obj in objects if id(obj.parent) not in identities]


def reset_pose(armature) -> None:
    if armature.animation_data is not None:
        armature.animation_data.action = None
        armature.animation_data.use_nla = False
    for bone in armature.pose.bones:
        bone.location = (0.0, 0.0, 0.0)
        bone.rotation_euler = (0.0, 0.0, 0.0)
        bone.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        bone.rotation_axis_angle = (0.0, 0.0, 1.0, 0.0)
        bone.scale = (1.0, 1.0, 1.0)


def set_action(armature, action) -> None:
    reset_pose(armature)
    if action is None:
        return
    if armature.animation_data is None:
        armature.animation_data_create()
    armature.animation_data.action = action
    slots = getattr(action, 'slots', ())
    if slots:
        armature.animation_data.action_slot = slots[0]


def normalize_hierarchy(objects, meshes, height_m: float) -> None:
    import bpy
    from mathutils import Matrix
    from .common import world_bbox

    for obj in objects:
        if obj.type == 'ARMATURE':
            reset_pose(obj)
    bpy.context.view_layer.update()
    lower, upper = world_bbox(meshes)
    height = upper.z - lower.z
    if height <= 1e-8 or height_m <= 0:
        raise ValueError('character height must be positive')
    factor = height_m / height
    center_x = (lower.x + upper.x) * 0.5
    center_y = (lower.y + upper.y) * 0.5
    transform = Matrix.Scale(factor, 4) @ Matrix.Translation((-center_x, -center_y, -lower.z))
    # Do not scale both a parent and its children or apply scale to rest bones.
    # Animation translation channels remain in the original armature space.
    roots = hierarchy_roots(objects)
    original = [(obj, obj.matrix_world.copy()) for obj in roots]
    for obj, matrix in original:
        obj.matrix_world = transform @ matrix
    bpy.context.view_layer.update()
    lower, upper = world_bbox(meshes)
    actual = upper.z - lower.z
    if abs(actual - height_m) > 0.001:
        raise RuntimeError(f'canonical height mismatch: {actual:.6f} vs {height_m:.6f}')
