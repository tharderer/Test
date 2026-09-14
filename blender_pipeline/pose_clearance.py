"""Resolve cloth intersections in author space across actual animation poses."""
from __future__ import annotations
from math import sqrt


def clearance_correction(point, nearest, normal, margin=.008, maximum=.06):
    offset = tuple(float(a) - float(b) for a, b in zip(point, nearest))
    distance = sqrt(sum(a*a for a in offset))
    if distance > maximum:
        raise ValueError('garment vertex is outside the supported fit envelope')
    signed = sum(a * float(b) for a, b in zip(offset, normal))
    if signed >= margin:
        return (0., 0., 0.)
    return tuple(float(n) * (margin - signed) for n in normal)


def resolve_pose_clearance(gear, body, armature, rounds=8):
    import bpy
    from mathutils import Vector, Matrix
    from .scene_state import reset_pose, set_action
    from .surface_fit import world_bvh

    actions = [None] + [bpy.data.actions.get(n) for n in ('Idle', 'Walk', 'Run')]
    frames = []
    for action in actions:
        if action is None:
            frames.append((None, 1))
        else:
            lo, hi = action.frame_range
            frames += [(action, int(round(lo + t * (hi-lo)))) for t in (0., .25, .5, .75, 1.)]
    groups = {g.index: g.name for g in gear.vertex_groups}
    influences = [[(groups[g.group], g.weight) for g in v.groups if g.weight > 1e-8]
                  for v in gear.data.vertices]
    deps = bpy.context.evaluated_depsgraph_get()
    total_moves = 0
    for iteration in range(rounds):
        worst = 0
        for action, frame in frames:
            set_action(armature, action)
            bpy.context.scene.frame_set(frame)
            deps.update()
            bvh = world_bvh(body, deps)
            evaluated = gear.evaluated_get(deps)
            mesh = evaluated.to_mesh()
            positions = [evaluated.matrix_world @ v.co for v in mesh.vertices]
            evaluated.to_mesh_clear()
            if len(positions) != len(gear.data.vertices):
                raise RuntimeError('clearance solver requires stable garment topology')
            prefix = armature.matrix_world
            suffix = armature.matrix_world.inverted() @ gear.matrix_world
            bone_matrices = {b.name: (prefix @ b.matrix @ b.bone.matrix_local.inverted() @ suffix).to_3x3()
                             for b in armature.pose.bones}
            moves = 0
            for vertex, position, weights in zip(gear.data.vertices, positions, influences):
                nearest, normal, _face, _distance = bvh.find_nearest(position)
                if nearest is None:
                    raise RuntimeError('missing body surface during pose clearance')
                correction = Vector(clearance_correction(position, nearest, normal))
                if correction.length < .001:
                    continue
                if correction.length > .012:
                    correction *= .012 / correction.length
                matrix = Matrix(((0., 0., 0.), (0., 0., 0.), (0., 0., 0.)))
                for name, weight in weights:
                    matrix += bone_matrices[name] * weight
                vertex.co += matrix.inverted() @ correction
                moves += 1
            gear.data.update()
            deps.update()
            total_moves += moves
            worst = max(worst, moves)
        print(f'{gear.name}: clearance round {iteration+1}, most adjusted vertices in one pose {worst}', flush=True)
        if worst == 0:
            break
    reset_pose(armature)
    bpy.context.scene.frame_set(1)
    deps.update()
    gear['clearance_solver_moves'] = total_moves
