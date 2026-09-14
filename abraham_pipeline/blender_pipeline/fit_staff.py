from __future__ import annotations

from math import radians

from .common import apply_object_transforms, import_glb, join_meshes


def staff_target_length(canonical_height_m: float, profile: dict[str, object]) -> float:
    return float(canonical_height_m) * float(profile['height_fraction'])


def staff_grip_fraction_from_bottom(profile: dict[str, object]) -> float:
    return 1.0 - float(profile['grip_fraction_from_top'])


def _rotate_longest_axis_to_z(obj) -> None:
    from mathutils import Vector

    dims = obj.dimensions
    largest = max(range(3), key=lambda i: dims[i])
    axis = (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)))[largest]
    if largest != 2:
        obj.rotation_mode = 'QUATERNION'
        obj.rotation_quaternion = axis.rotation_difference(Vector((0, 0, 1))) @ obj.rotation_quaternion
        obj.rotation_mode = 'XYZ'
        apply_object_transforms(obj, rotation=True, scale=False)


def fit_staff(
    source_path: str,
    armature,
    *,
    socket_bone: str = 'Socket_RightHand',
    canonical_height_m: float = 1.82,
    profile: dict[str, object] | None = None,
):
    from mathutils import Matrix

    profile = profile or {
        'height_fraction': 0.88,
        'grip_fraction_from_top': 0.38,
        'long_axis': 'Z',
        'handedness': 'right',
    }
    if armature.data.bones.get(socket_bone) is None:
        raise RuntimeError(f'missing staff socket bone: {socket_bone}')

    imported = import_glb(source_path)
    staff = join_meshes(imported, 'Equip_Staff')
    apply_object_transforms(staff, rotation=True, scale=True)
    _rotate_longest_axis_to_z(staff)

    current_length = max(staff.dimensions)
    if current_length <= 1e-8:
        raise RuntimeError('staff source has zero length')
    scale = staff_target_length(canonical_height_m, profile) / current_length
    staff.scale = (scale, scale, scale)
    apply_object_transforms(staff, rotation=False, scale=True)

    local_z = [vertex.co.z for vertex in staff.data.vertices]
    min_z, max_z = min(local_z), max(local_z)
    grip_z = min_z + staff_grip_fraction_from_bottom(profile) * (max_z - min_z)
    staff.data.transform(Matrix.Translation((0.0, 0.0, -grip_z)))
    staff.data.update()

    staff.parent = armature
    staff.parent_type = 'BONE'
    staff.parent_bone = socket_bone
    staff.matrix_parent_inverse = Matrix.Identity(4)
    staff.location = (0.0, -0.035, 0.0)
    staff.rotation_mode = 'XYZ'
    staff.rotation_euler = (0.0, 0.0, radians(-8.0))
    staff.scale = (1.0, 1.0, 1.0)
    return staff
