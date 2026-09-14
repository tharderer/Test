"""Author-space fitting helpers. Distances and geometry are in world metres."""
from __future__ import annotations

from math import atan2, cos, hypot, pi, sin, sqrt


def torso_sample_indices(points, torso_weights, waist_z, half_band):
    eligible = [i for i, weight in enumerate(torso_weights) if weight >= 0.5]
    if not eligible:
        raise ValueError('body has no torso-weighted vertices for waist fitting')
    band = [i for i in eligible if abs(points[i][2] - waist_z) <= half_band]
    return band or sorted(eligible, key=lambda i: abs(points[i][2] - waist_z))[:128]


def radial_detail(radius, baseline, maximum):
    return max(0.0, min(float(maximum), float(radius) - float(baseline)))


def classify_distance(offset, normal, maximum):
    distance = sqrt(sum(float(value) ** 2 for value in offset))
    signed = sum(float(a) * float(b) for a, b in zip(offset, normal))
    return distance > maximum, signed < -0.004


def world_bvh(body, depsgraph):
    from mathutils.bvhtree import BVHTree
    evaluated = body.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        points = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
        faces = [tuple(poly.vertices) for poly in mesh.polygons]
        return BVHTree.FromPolygons(points, faces, all_triangles=False)
    finally:
        evaluated.to_mesh_clear()


def fit_radial_surface(gear, body, center_xy, clearance, max_detail):
    """Map garment radial columns to the torso, retaining bounded relief.

    Both sides of a thick generated garment must not be shrinkwrapped to
    the exact same surface. A local lower-envelope radius preserves that
    thickness and the original UVs. This runs once during Blender authoring.
    """
    import bpy
    from mathutils import Vector

    bpy.context.view_layer.update()
    bvh = world_bvh(body, bpy.context.evaluated_depsgraph_get())
    positions = [gear.matrix_world @ v.co for v in gear.data.vertices]
    if not positions:
        raise RuntimeError('cannot fit an empty garment')
    z_min = min(p.z for p in positions)
    span = max(p.z for p in positions) - z_min
    if span <= 1e-8:
        raise RuntimeError('garment has zero height')
    cx, cy = center_xy
    bins = {}
    records = []
    for p in positions:
        theta = atan2(p.y - cy, p.x - cx)
        radius = hypot(p.x - cx, p.y - cy)
        angle_bin = int((theta + pi) * 64 / (2 * pi)) % 64
        z_bin = min(23, max(0, int((p.z - z_min) / span * 24)))
        key = (angle_bin, z_bin)
        bins[key] = min(radius, bins.get(key, float('inf')))
        records.append((theta, radius, angle_bin, z_bin))

    inverse = gear.matrix_world.inverted()
    ray_misses = 0
    for vertex, position, record in zip(gear.data.vertices, positions, records):
        theta, radius, angle_bin, z_bin = record
        neighbours = [bins[((angle_bin + da) % 64, z_bin + dz)]
                      for da in (-1, 0, 1) for dz in (-1, 0, 1)
                      if ((angle_bin + da) % 64, z_bin + dz) in bins]
        baseline = min(neighbours)
        direction = Vector((cos(theta), sin(theta), 0.0))
        origin = Vector((cx, cy, position.z))
        hit, normal, _face, _distance = bvh.ray_cast(origin, direction, 2.5)
        if hit is None:
            ray_misses += 1
            hit, normal, _face, _distance = bvh.find_nearest(position)
            if hit is None:
                raise RuntimeError('no body surface found for garment vertex')
            target = hit + normal * clearance
        else:
            relief = radial_detail(radius, baseline, max_detail)
            target = hit + direction * (clearance + relief)
        vertex.co = inverse @ target
    gear.data.update()
    bpy.context.view_layer.update()
    gear['surface_fit_ray_misses'] = ray_misses
    print(f'{gear.name}: radial fit {len(positions)} vertices; {ray_misses} nearest-surface fallbacks', flush=True)
    if ray_misses / len(positions) > 0.10:
        raise RuntimeError('garment extends outside the supported torso fitting region')
