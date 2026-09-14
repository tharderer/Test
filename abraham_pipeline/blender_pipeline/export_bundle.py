from __future__ import annotations

from pathlib import Path

MOBILE_NODE_NAMES = {'Abraham_Base', 'Equip_Staff', 'Equip_Belt', 'Equip_Mantle', 'Abraham_Rig'}


def enforce_bundle_size(path: Path, max_bundle_mb: float) -> float:
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > max_bundle_mb:
        raise RuntimeError(f'mobile bundle {size_mb:.1f} MB exceeds {max_bundle_mb:.1f} MB ceiling')
    return size_mb


def _bpy():
    import bpy
    return bpy


def _select_only(objects) -> None:
    bpy = _bpy()
    bpy.ops.object.select_all(action='DESELECT')
    first = None
    for obj in objects:
        if obj is None:
            continue
        obj.select_set(True)
        first = first or obj
    bpy.context.view_layer.objects.active = first


def _export_glb(path: Path, *, selection: bool, draco: bool = False) -> None:
    bpy = _bpy()
    path.parent.mkdir(parents=True, exist_ok=True)
    kwargs = dict(
        filepath=str(path.resolve()),
        export_format='GLB',
        use_selection=selection,
        export_animations=True,
        export_apply=True,
    )
    if draco:
        kwargs.update(
            export_draco_mesh_compression_enable=True,
            export_draco_mesh_compression_level=6,
        )
    bpy.ops.export_scene.gltf(**kwargs)


def _remove_export_junk() -> None:
    bpy = _bpy()
    armature = bpy.data.objects.get('Abraham_Rig')
    for obj in list(bpy.context.scene.objects):
        if obj.type in {'CAMERA', 'LIGHT'}:
            bpy.data.objects.remove(obj, do_unlink=True)
        elif obj.type == 'ARMATURE' and obj != armature:
            bpy.data.objects.remove(obj, do_unlink=True)


def _ensure_base_parent():
    bpy = _bpy()
    existing = bpy.data.objects.get('Abraham_Base')
    if existing is not None:
        return existing
    base = bpy.data.objects.new('Abraham_Base', None)
    bpy.context.collection.objects.link(base)
    equipment = {'Equip_Staff', 'Equip_Belt', 'Equip_Mantle'}
    for obj in list(bpy.context.scene.objects):
        if obj.type != 'MESH' or obj.name in equipment:
            continue
        world = obj.matrix_world.copy()
        obj.parent = base
        obj.matrix_world = world
    return base


def _base_meshes():
    bpy = _bpy()
    equipment = {'Equip_Staff', 'Equip_Belt', 'Equip_Mantle'}
    return [obj for obj in bpy.context.scene.objects if obj.type == 'MESH' and obj.name not in equipment]


def _triangle_count(obj) -> int:
    return sum(max(1, len(poly.vertices) - 2) for poly in obj.data.polygons)


def _decimate_to(obj, target_triangles: int) -> None:
    bpy = _bpy()
    current = _triangle_count(obj)
    if current <= target_triangles or current <= 0:
        return
    ratio = max(0.01, min(1.0, target_triangles / current))
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    mod = obj.modifiers.new(name='MobileDecimate', type='DECIMATE')
    mod.decimate_type = 'COLLAPSE'
    mod.ratio = ratio
    bpy.ops.object.modifier_apply(modifier=mod.name)


def _images_for_object(obj) -> set:
    images = set()
    for slot in obj.material_slots:
        material = slot.material
        if material is None or not material.use_nodes or material.node_tree is None:
            continue
        for node in material.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.image is not None:
                images.add(node.image)
    return images


def _resize_image(image, max_dimension: int) -> None:
    width, height = image.size
    if max(width, height) <= max_dimension or width <= 0 or height <= 0:
        return
    scale = max_dimension / max(width, height)
    image.scale(max(1, int(round(width * scale))), max(1, int(round(height * scale))))


def _optimize_mobile_scene() -> None:
    bpy = _bpy()
    targets = {
        'Equip_Staff': 8_000,
        'Equip_Belt': 10_000,
        'Equip_Mantle': 18_000,
    }
    equipment_images = set()
    for name, target in targets.items():
        obj = bpy.data.objects.get(name)
        if obj is None:
            raise RuntimeError(f'missing required equipment object: {name}')
        _decimate_to(obj, target)
        equipment_images |= _images_for_object(obj)

    base_images = set()
    for obj in _base_meshes():
        base_images |= _images_for_object(obj)
    for image in base_images - equipment_images:
        _resize_image(image, 2048)
    for image in equipment_images:
        _resize_image(image, 1024)
    try:
        bpy.ops.file.pack_all()
    except RuntimeError:
        pass


def export_validated_scene(out_dir: Path, config) -> dict[str, Path]:
    bpy = _bpy()
    out_dir = Path(out_dir)
    source_dir = out_dir / 'source-quality'
    mobile_dir = out_dir / 'mobile'
    source_dir.mkdir(parents=True, exist_ok=True)
    mobile_dir.mkdir(parents=True, exist_ok=True)

    _remove_export_junk()
    armature = bpy.data.objects.get('Abraham_Rig')
    staff = bpy.data.objects.get('Equip_Staff')
    belt = bpy.data.objects.get('Equip_Belt')
    mantle = bpy.data.objects.get('Equip_Mantle')
    if any(obj is None for obj in (armature, staff, belt, mantle)):
        raise RuntimeError('validated scene is missing canonical rig/equipment nodes')
    _ensure_base_parent()

    outputs = {
        'base': source_dir / 'abraham_base_rigged.glb',
        'staff': source_dir / 'staff_fitted.glb',
        'belt': source_dir / 'belt_skinned.glb',
        'mantle': source_dir / 'mantle_skinned.glb',
        'bundle': mobile_dir / 'abraham_upgrade_bundle.glb',
    }

    _select_only([armature, *_base_meshes()])
    _export_glb(outputs['base'], selection=True)
    _select_only([armature, staff])
    _export_glb(outputs['staff'], selection=True)
    _select_only([armature, belt])
    _export_glb(outputs['belt'], selection=True)
    _select_only([armature, mantle])
    _export_glb(outputs['mantle'], selection=True)

    _optimize_mobile_scene()
    bpy.ops.object.select_all(action='SELECT')
    _export_glb(outputs['bundle'], selection=False, draco=True)
    enforce_bundle_size(outputs['bundle'], config.validation.max_bundle_mb)
    return outputs
