from __future__ import annotations

from typing import Any

MAX_STAFF_DRIFT_M = 0.20


def report_passes(report: dict[str, Any], thresholds) -> bool:
    if set(report.get('animations', ())) != {'Idle', 'Walk', 'Run'}:
        return False
    gear = report.get('gear', {})
    for name in ('belt', 'mantle'):
        stats = gear.get(name)
        if not stats:
            return False
        if int(stats['unweighted_vertices']) > thresholds.max_unweighted_vertices:
            return False
        if int(stats['max_influences']) > thresholds.max_influences_per_vertex:
            return False
        if float(stats['floating_vertex_ratio']) > thresholds.max_floating_vertex_ratio:
            return False
        if float(stats['penetration_ratio']) > thresholds.max_penetration_ratio:
            return False
    staff = report.get('staff', {})
    if staff.get('parent_bone') != 'Socket_RightHand':
        return False
    if float(staff.get('max_socket_drift_m', float('inf'))) > MAX_STAFF_DRIFT_M:
        return False
    return True


def _weight_stats(obj) -> tuple[int, int]:
    unweighted = 0
    max_influences = 0
    for vertex in obj.data.vertices:
        nonzero = [g for g in vertex.groups if g.weight > 1e-6]
        if not nonzero:
            unweighted += 1
        max_influences = max(max_influences, len(nonzero))
    return unweighted, max_influences


def _sample_frames(action) -> list[int]:
    start, end = action.frame_range
    start = float(start)
    span = float(end - start)
    return sorted({int(round(start + fraction * span)) for fraction in (0.0, 0.25, 0.5, 0.75, 1.0)})


def _evaluated_positions_normals(obj, depsgraph):
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    world = evaluated.matrix_world
    normal_matrix = world.to_3x3().inverted().transposed()
    try:
        values = [
            (world @ vertex.co, (normal_matrix @ vertex.normal).normalized())
            for vertex in mesh.vertices
        ]
    finally:
        evaluated.to_mesh_clear()
    return values


def _surface_ratios(body, gear, depsgraph, max_distance: float, *, ignore_below_z: float | None = None) -> tuple[float, float]:
    from .surface_fit import world_bvh, classify_distance

    bvh = world_bvh(body, depsgraph)
    eligible = floating = penetrating = 0
    for world_pos, _world_normal in _evaluated_positions_normals(gear, depsgraph):
        if ignore_below_z is not None and world_pos.z < ignore_below_z:
            continue
        eligible += 1
        nearest, normal, _index, _distance = bvh.find_nearest(world_pos)
        if nearest is None:
            floating += 1
            continue
        is_floating, is_penetrating = classify_distance(world_pos - nearest, normal, max_distance)
        floating += int(is_floating)
        penetrating += int(is_penetrating)
    if eligible == 0:
        raise RuntimeError('no eligible garment vertices were validated')
    return floating / eligible, penetrating / eligible


def _staff_socket_drift(armature, staff) -> float:
    from mathutils import Vector

    socket = armature.pose.bones.get('Socket_RightHand')
    if socket is None:
        return float('inf')
    local_offset = Vector(staff.get('socket_grip_offset', (0.0, -0.035, 0.0)))
    expected = armature.matrix_world @ (socket.matrix @ local_offset)
    return (staff.matrix_world.translation - expected).length


def validate_scene(body, armature, belt, mantle, staff, thresholds) -> dict[str, Any]:
    import bpy
    from .scene_state import set_action

    missing_bones = [
        name for name in ('ABR_HIPS', 'ABR_SPINE', 'ABR_CHEST', 'ABR_HEAD', 'ABR_RIGHT_HAND', 'ABR_LEFT_HAND', 'ABR_RIGHT_FOOT', 'ABR_LEFT_FOOT')
        if armature.data.bones.get(name) is None
    ]
    if missing_bones:
        raise RuntimeError(f'missing canonical bone roles: {missing_bones}')

    actions = {name: bpy.data.actions.get(name) for name in ('Idle', 'Walk', 'Run')}
    animation_names = [name for name, action in actions.items() if action is not None]
    print('Validation world scales:', tuple(body.matrix_world.to_scale()), tuple(armature.matrix_world.to_scale()), flush=True)
    gear_stats = {}
    for name, obj in (('belt', belt), ('mantle', mantle)):
        unweighted, max_influences = _weight_stats(obj)
        gear_stats[name] = {
            'unweighted_vertices': unweighted,
            'max_influences': max_influences,
            'floating_vertex_ratio': 0.0,
            'penetration_ratio': 0.0,
        }

    max_staff_drift = 0.0
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for action in actions.values():
        if action is None:
            continue
        set_action(armature, action)
        for frame in _sample_frames(action):
            bpy.context.scene.frame_set(frame)
            depsgraph.update()
            for name, obj in (('belt', belt), ('mantle', mantle)):
                ignore_below = float(mantle.get('hem_target_z')) if name == 'mantle' and mantle.get('hem_target_z') is not None else None
                floating, penetration = _surface_ratios(
                    body,
                    obj,
                    depsgraph,
                    thresholds.max_floating_distance_m,
                    ignore_below_z=ignore_below,
                )
                gear_stats[name]['floating_vertex_ratio'] = max(gear_stats[name]['floating_vertex_ratio'], floating)
                gear_stats[name]['penetration_ratio'] = max(gear_stats[name]['penetration_ratio'], penetration)
            max_staff_drift = max(max_staff_drift, _staff_socket_drift(armature, staff))

    report: dict[str, Any] = {
        'animations': animation_names,
        'gear': gear_stats,
        'staff': {
            'parent_bone': staff.parent_bone if staff.parent_type == 'BONE' else None,
            'max_socket_drift_m': max_staff_drift,
        },
    }
    report['pass'] = report_passes(report, thresholds)
    return report
