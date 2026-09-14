from __future__ import annotations


def _bpy():
    import bpy
    return bpy


def clear_scene():
    bpy = _bpy()
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)


def import_glb(path: str):
    bpy = _bpy()
    before = {obj.name for obj in bpy.data.objects}
    bpy.ops.import_scene.gltf(filepath=path)
    return [obj for obj in bpy.data.objects if obj.name not in before]


def find_primary_armature():
    bpy = _bpy()
    armatures = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE']
    if not armatures:
        raise RuntimeError('canonical base contains no armature')
    return max(armatures, key=lambda o: len(o.data.bones))


def find_primary_body_mesh(armature):
    bpy = _bpy()
    meshes = [
        o for o in bpy.context.scene.objects
        if o.type == 'MESH'
        and any(m.type == 'ARMATURE' and m.object == armature for m in o.modifiers)
    ]
    if not meshes:
        raise RuntimeError('canonical rig has no skinned mesh')
    return max(meshes, key=lambda o: len(o.data.vertices))


def world_bbox(objects):
    from mathutils import Vector

    _bpy().context.view_layer.update()
    points = []
    for obj in objects:
        if obj.type != 'MESH':
            continue
        points.extend(obj.matrix_world @ Vector(corner) for corner in obj.bound_box)
    if not points:
        raise RuntimeError('no mesh bounds available')
    mins = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    maxs = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    return mins, maxs


def join_meshes(objects, name: str):
    bpy = _bpy()
    meshes = [obj for obj in objects if obj.type == 'MESH']
    if not meshes:
        raise RuntimeError('source contains no mesh')
    bpy.ops.object.select_all(action='DESELECT')
    for obj in meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    result = bpy.context.view_layer.objects.active
    bpy.context.view_layer.update()
    world = result.matrix_world.copy()
    result.parent = None
    result.matrix_world = world
    bpy.context.view_layer.update()
    result.name = name
    return result


def apply_object_transforms(obj, *, location=False, rotation=True, scale=True):
    bpy = _bpy()
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.context.view_layer.update()
    bpy.ops.object.transform_apply(location=location, rotation=rotation, scale=scale)
    bpy.context.view_layer.update()


def vertex_weight_snapshot(obj, vertex_index: int) -> list[tuple[str, float]]:
    vertex = obj.data.vertices[vertex_index]
    return [
        (obj.vertex_groups[item.group].name, float(item.weight))
        for item in vertex.groups
        if item.weight > 1e-8
    ]


def limit_and_normalize_weights(target, max_influences: int = 4) -> None:
    if max_influences < 1:
        raise ValueError('max_influences must be >= 1')
    for vertex in target.data.vertices:
        influences = sorted(vertex_weight_snapshot(target, vertex.index), key=lambda item: item[1], reverse=True)
        if not influences:
            raise RuntimeError(f'unweighted vertex after transfer: {vertex.index}')
        keep = influences[:max_influences]
        keep_names = {name for name, _ in keep}
        for name, _ in influences[max_influences:]:
            target.vertex_groups[name].remove([vertex.index])
        total = sum(weight for _, weight in keep)
        if total <= 1e-8:
            raise RuntimeError(f'zero total vertex weight: {vertex.index}')
        for name, weight in keep:
            target.vertex_groups[name].add([vertex.index], weight / total, 'REPLACE')


def restrict_vertex_groups(target, allowed_names: set[str]) -> None:
    for vertex in target.data.vertices:
        original = sorted(vertex_weight_snapshot(target, vertex.index), key=lambda item: item[1], reverse=True)
        kept = [(name, weight) for name, weight in original if name in allowed_names]
        if not kept and original:
            kept = [original[0]]
        keep_names = {name for name, _ in kept}
        for name, _ in original:
            if name not in keep_names:
                target.vertex_groups[name].remove([vertex.index])
        total = sum(weight for _, weight in kept)
        if total <= 1e-8:
            raise RuntimeError(f'weight restriction left vertex unweighted: {vertex.index}')
        for name, weight in kept:
            target.vertex_groups[name].add([vertex.index], weight / total, 'REPLACE')


def transfer_weights_nearest(target, source_body, armature, max_influences: int = 4):
    bpy = _bpy()
    deform_names = {bone.name for bone in armature.data.bones if bone.use_deform}
    for group in list(target.vertex_groups):
        if group.name not in deform_names:
            target.vertex_groups.remove(group)
    for bone in armature.data.bones:
        if bone.use_deform and target.vertex_groups.get(bone.name) is None:
            target.vertex_groups.new(name=bone.name)

    bpy.context.view_layer.objects.active = target
    target.select_set(True)
    modifier = target.modifiers.new(name='TransferWeights', type='DATA_TRANSFER')
    modifier.object = source_body
    modifier.use_vert_data = True
    modifier.data_types_verts = {'VGROUP_WEIGHTS'}
    modifier.vert_mapping = 'POLYINTERP_NEAREST'
    if hasattr(modifier, 'layers_vgroup_select_src'):
        modifier.layers_vgroup_select_src = 'ALL'
    if hasattr(modifier, 'layers_vgroup_select_dst'):
        modifier.layers_vgroup_select_dst = 'NAME'
    bpy.ops.object.modifier_apply(modifier=modifier.name)

    limit_and_normalize_weights(target, max_influences=max_influences)
    armature_modifiers = [m for m in target.modifiers if m.type == 'ARMATURE']
    if not armature_modifiers:
        armature_modifier = target.modifiers.new(name='AbrahamArmature', type='ARMATURE')
        armature_modifier.object = armature
    else:
        for modifier in armature_modifiers:
            modifier.object = armature
    world = target.matrix_world.copy()
    target.parent = armature
    target.matrix_parent_inverse = armature.matrix_world.inverted()
    target.matrix_world = world
    bpy.context.view_layer.update()
    return target
