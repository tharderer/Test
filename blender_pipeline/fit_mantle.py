from __future__ import annotations

from .common import apply_object_transforms, import_glb, join_meshes, limit_and_normalize_weights, world_bbox
from .surface_fit import fit_radial_surface


def mantle_vertical_targets(min_z: float, max_z: float, profile: dict[str, object]) -> tuple[float, float]:
    height = float(max_z) - float(min_z)
    return (float(min_z) + float(profile['shoulder_fraction_of_height']) * height,
            float(min_z) + float(profile['hem_fraction_of_height']) * height)


def mantle_anchor_floor(min_z: float, max_z: float, shoulder_z: float) -> float:
    return float(shoulder_z) - .18 * (float(max_z) - float(min_z))


def mantle_face_is_in_template(point, cx, cy, hem, shoulder, half_width):
    x, y, z = point
    if not hem <= z <= shoulder or abs(x - cx) > half_width:
        return False
    return not (y < cy and abs(x - cx) < .055 and z < shoulder - .055)


def _author_body_template(body, design, armature, hem, shoulder, clearance):
    """Use the canonical robe topology and exact weights for a compatible shell.

    The AI garment supplies the material/UV design, not unrelated topology
    stretched across moving joints. The robe itself always stays present.
    """
    import bpy
    import bmesh

    lower, upper = world_bbox([body])
    center = (lower + upper) * .5
    template = body.copy()
    template.data = body.data.copy()
    bpy.context.collection.objects.link(template)
    template.name = 'Mantle_Template'
    template.matrix_world = body.matrix_world.copy()
    if template.animation_data:
        template.animation_data_clear()
    for modifier in list(template.modifiers):
        template.modifiers.remove(modifier)
    world = template.matrix_world.copy()
    inverse = world.inverted()
    normals = world.to_3x3().inverted().transposed()
    bm = bmesh.new()
    bm.from_mesh(template.data)
    source_index = bm.verts.layers.int.new('template_source_index')
    for v in bm.verts:
        v[source_index] = v.index
    remove = []
    for face in bm.faces:
        point = world @ face.calc_center_median()
        if not mantle_face_is_in_template(point, center.x, center.y, hem, shoulder,
                                          .14 * (upper.z - lower.z)):
            remove.append(face)
    bmesh.ops.delete(bm, geom=remove, context='FACES')
    for v in bm.verts:
        source = body.data.vertices[v[source_index]]
        normal = (normals @ source.normal).normalized()
        v.co = inverse @ ((world @ v.co) + normal * clearance)
    bm.to_mesh(template.data)
    bm.free()
    template.data.update()
    if len(template.data.polygons) < 100:
        raise RuntimeError('canonical mantle template has insufficient surface coverage')

    template.data.materials.clear()
    for material in design.data.materials:
        template.data.materials.append(material)
    for polygon in template.data.polygons:
        polygon.material_index = 0
        polygon.use_smooth = True
    if not template.data.uv_layers:
        template.data.uv_layers.new(name='UVMap')
    bpy.ops.object.select_all(action='DESELECT')
    template.select_set(True)
    bpy.context.view_layer.objects.active = template
    uv = template.modifiers.new(name='TransferAIGarmentUVs', type='DATA_TRANSFER')
    uv.object = design
    uv.use_loop_data = True
    uv.data_types_loops = {'UV'}
    uv.loop_mapping = 'POLYINTERP_NEAREST'
    uv.layers_uv_select_src = 'ACTIVE'
    uv.layers_uv_select_dst = 'ACTIVE'
    bpy.ops.object.modifier_apply(modifier=uv.name)
    modifier = template.modifiers.new(name='AbrahamArmature', type='ARMATURE')
    modifier.object = armature
    limit_and_normalize_weights(template, 4)
    template['template_authored'] = True
    print(f'Mantle authored from canonical robe: {len(template.data.vertices)} vertices, exact source skin weights', flush=True)
    bpy.data.objects.remove(design, do_unlink=True)
    template.name = 'Equip_Mantle'
    return template


def fit_mantle(source_path: str, body, armature, profile: dict[str, object]):
    import bpy
    from mathutils import Vector
    from .scene_state import reset_pose

    reset_pose(armature)
    bpy.context.view_layer.update()
    design = join_meshes(import_glb(source_path), 'Mantle_AIDesign')
    apply_object_transforms(design, location=True, rotation=True, scale=True)
    lower, upper = world_bbox([body])
    shoulder, hem = mantle_vertical_targets(lower.z, upper.z, profile)
    design_min, design_max = world_bbox([design])
    source_height = design_max.z - design_min.z
    if source_height <= 1e-8:
        raise RuntimeError('AI mantle has zero height')
    scale = (shoulder - hem) / source_height
    design.scale = (scale, scale, scale)
    apply_object_transforms(design, rotation=False, scale=True)
    design_min, design_max = world_bbox([design])
    center = (lower + upper) * .5
    design.location += Vector((center.x, center.y, (shoulder + hem) / 2)) - (design_min + design_max) * .5
    apply_object_transforms(design, location=True, rotation=False, scale=False)
    clearance = float(profile.get('surface_clearance_m', .024))
    fit_radial_surface(design, body, (center.x, center.y), clearance, .015)
    mantle = _author_body_template(body, design, armature, hem, shoulder, clearance)
    mantle['hem_target_z'] = float(hem)
    mantle['validation_anchor_floor_z'] = mantle_anchor_floor(lower.z, upper.z, shoulder)
    return mantle
