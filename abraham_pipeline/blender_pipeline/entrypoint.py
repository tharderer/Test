from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender_pipeline.animations import import_action
from blender_pipeline.common import clear_scene, find_primary_armature, find_primary_body_mesh, import_glb, world_bbox
from blender_pipeline.rig_contract import CANONICAL, ensure_socket, normalize_rig, resolve_bone_roles
from blender_pipeline.fit_staff import fit_staff
from blender_pipeline.fit_belt import fit_belt
from blender_pipeline.fit_mantle import fit_mantle
from blender_pipeline.validate import validate_scene
from blender_pipeline.export_bundle import export_validated_scene
from pipeline.schema import load_build_config


def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', required=True)
    parser.add_argument('--config', required=True)
    parser.add_argument('--aliases', required=True)
    parser.add_argument('--source-dir', required=True)
    parser.add_argument('--out-dir', required=True)
    return parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])


def _load_aliases(path: Path) -> dict[str, list[str]]:
    return json.loads(path.read_text())


def _normalize_base(args) -> None:
    import bpy

    config = load_build_config(Path(args.config))
    aliases = _load_aliases(Path(args.aliases))
    source_dir = Path(args.source_dir)
    out_dir = Path(args.out_dir)
    work_dir = out_dir / 'work'
    reports_dir = out_dir / 'reports'
    work_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    clear_scene()
    imported = import_glb(str(source_dir / 'abraham_base_rigged.glb'))
    armature = find_primary_armature()
    body = find_primary_body_mesh(armature)
    armature.name = 'Abraham_Rig'
    body.name = 'Abraham_Body'

    role_map = resolve_bone_roles(armature, aliases)
    normalize_rig(armature, role_map)

    mesh_objects = [obj for obj in imported if obj.type == 'MESH']
    mins, maxs = world_bbox(mesh_objects)
    height = maxs.z - mins.z
    if height <= 1e-8:
        raise RuntimeError('canonical character height is zero')
    factor = config.canonical_height_m / height
    for obj in imported:
        obj.scale = tuple(component * factor for component in obj.scale)

    bpy.ops.object.select_all(action='DESELECT')
    for obj in imported:
        obj.select_set(True)
    if imported:
        bpy.context.view_layer.objects.active = imported[0]
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    ensure_socket(armature)

    actions = {
        'Idle': source_dir / 'idle.glb',
        'Walk': source_dir / 'walk_armature.glb',
        'Run': source_dir / 'run_armature.glb',
    }
    for action_name, path in actions.items():
        import_action(str(path), armature, aliases, action_name)

    final_mins, final_maxs = world_bbox([obj for obj in bpy.context.scene.objects if obj.type == 'MESH'])
    final_height = final_maxs.z - final_mins.z
    report = {
        'role_map': {role: CANONICAL.get(role, role) for role in role_map},
        'canonical_bones': sorted(b.name for b in armature.data.bones if b.name.startswith('ABR_')),
        'height_m': final_height,
        'mesh_vertex_count': len(body.data.vertices),
        'action_names': sorted(name for name in ('Idle', 'Walk', 'Run') if bpy.data.actions.get(name) is not None),
    }
    (reports_dir / 'rig_contract.json').write_text(json.dumps(report, indent=2))
    bpy.ops.wm.save_as_mainfile(filepath=str((work_dir / 'base_normalized.blend').resolve()))


def _export_glb(path: Path) -> None:
    import bpy
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(path.resolve()), export_format='GLB', export_animations=True, export_apply=True)


def _fit_staff_stage(args) -> None:
    import bpy
    config = load_build_config(Path(args.config))
    out_dir = Path(args.out_dir)
    work_dir = out_dir / 'work'
    source_quality = out_dir / 'source-quality'
    bpy.ops.wm.open_mainfile(filepath=str((work_dir / 'base_normalized.blend').resolve()))
    armature = bpy.data.objects.get('Abraham_Rig')
    if armature is None:
        raise RuntimeError('normalized scene missing Abraham_Rig')
    fit_staff(
        str(Path(args.source_dir) / 'staff_source.glb'),
        armature,
        canonical_height_m=config.canonical_height_m,
        profile=config.equipment['staff'].fit or {},
    )
    bpy.ops.wm.save_as_mainfile(filepath=str((work_dir / 'staff_fitted.blend').resolve()))
    _export_glb(source_quality / 'staff_fitted.glb')


def _fit_belt_stage(args) -> None:
    import bpy
    config = load_build_config(Path(args.config))
    out_dir = Path(args.out_dir)
    work_dir = out_dir / 'work'
    source_quality = out_dir / 'source-quality'
    bpy.ops.wm.open_mainfile(filepath=str((work_dir / 'staff_fitted.blend').resolve()))
    armature = bpy.data.objects.get('Abraham_Rig')
    body = bpy.data.objects.get('Abraham_Body')
    if armature is None or body is None:
        raise RuntimeError('staff scene missing canonical Abraham rig/body')
    belt = fit_belt(str(Path(args.source_dir) / 'belt_source.glb'), body, armature, config.equipment['belt'].fit or {})
    assert any(m.type == 'ARMATURE' and m.object == armature for m in belt.modifiers)
    assert all(sum(g.weight for g in v.groups) > 0 for v in belt.data.vertices)
    assert max((len(v.groups) for v in belt.data.vertices), default=0) <= 4
    bpy.ops.wm.save_as_mainfile(filepath=str((work_dir / 'belt_fitted.blend').resolve()))
    _export_glb(source_quality / 'belt_skinned.glb')


def _look_at(camera, target):
    direction = target - camera.location
    camera.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()


def _render_mantle_validation(out_dir: Path, armature) -> None:
    import bpy
    from mathutils import Vector
    render_dir = out_dir / 'reports' / 'renders'
    render_dir.mkdir(parents=True, exist_ok=True)
    body = bpy.data.objects.get('Abraham_Body')
    mins, maxs = world_bbox([body])
    center = (mins + maxs) * 0.5
    height = maxs.z - mins.z
    camera_data = bpy.data.cameras.new('ValidationCamera')
    camera = bpy.data.objects.new('ValidationCamera', camera_data)
    bpy.context.collection.objects.link(camera)
    camera.location = center + Vector((0.0, -2.4 * height, 0.15 * height))
    camera.data.lens = 55
    _look_at(camera, center)
    bpy.context.scene.camera = camera
    light_data = bpy.data.lights.new('ValidationKey', type='AREA')
    light_data.energy = 900
    light_data.shape = 'DISK'
    light_data.size = 4.0
    light = bpy.data.objects.new('ValidationKey', light_data)
    bpy.context.collection.objects.link(light)
    light.location = center + Vector((-1.5, -2.0, 2.5))
    bpy.context.scene.render.engine = 'BLENDER_EEVEE_NEXT'
    bpy.context.scene.render.resolution_x = 512
    bpy.context.scene.render.resolution_y = 512
    bpy.context.scene.render.resolution_percentage = 100
    bpy.context.scene.world.color = (0.08, 0.08, 0.08)

    frames = [('mantle_apose.png', None, 1)]
    walk = bpy.data.actions.get('Walk')
    run = bpy.data.actions.get('Run')
    if walk:
        start, end = walk.frame_range
        frames.extend([
            ('mantle_walk_left.png', walk, int(start + 0.25 * (end - start))),
            ('mantle_walk_right.png', walk, int(start + 0.75 * (end - start))),
        ])
    if run:
        start, end = run.frame_range
        frames.append(('mantle_run.png', run, int(start + 0.5 * (end - start))))
    for filename, action, frame in frames:
        if armature.animation_data is None:
            armature.animation_data_create()
        armature.animation_data.action = action
        bpy.context.scene.frame_set(frame)
        bpy.context.scene.render.filepath = str((render_dir / filename).resolve())
        bpy.ops.render.render(write_still=True)


def _fit_mantle_stage(args) -> None:
    import bpy
    config = load_build_config(Path(args.config))
    out_dir = Path(args.out_dir)
    work_dir = out_dir / 'work'
    source_quality = out_dir / 'source-quality'
    bpy.ops.wm.open_mainfile(filepath=str((work_dir / 'belt_fitted.blend').resolve()))
    armature = bpy.data.objects.get('Abraham_Rig')
    body = bpy.data.objects.get('Abraham_Body')
    if armature is None or body is None:
        raise RuntimeError('belt scene missing canonical Abraham rig/body')
    fit_mantle(str(Path(args.source_dir) / 'mantle_source.glb'), body, armature, config.equipment['mantle'].fit or {})
    bpy.ops.wm.save_as_mainfile(filepath=str((work_dir / 'mantle_fitted.blend').resolve()))
    _export_glb(source_quality / 'mantle_skinned.glb')
    _render_mantle_validation(out_dir, armature)


def _validate_stage(args) -> None:
    import bpy
    config = load_build_config(Path(args.config))
    out_dir = Path(args.out_dir)
    work_dir = out_dir / 'work'
    reports_dir = out_dir / 'reports'
    reports_dir.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str((work_dir / 'mantle_fitted.blend').resolve()))
    required = {name: bpy.data.objects.get(name) for name in ('Abraham_Rig', 'Abraham_Body', 'Equip_Belt', 'Equip_Mantle', 'Equip_Staff')}
    missing = [name for name, obj in required.items() if obj is None]
    if missing:
        raise RuntimeError(f'validation scene missing objects: {missing}')
    report = validate_scene(
        required['Abraham_Body'],
        required['Abraham_Rig'],
        required['Equip_Belt'],
        required['Equip_Mantle'],
        required['Equip_Staff'],
        config.validation,
    )
    (reports_dir / 'validation.json').write_text(json.dumps(report, indent=2))
    if not report['pass']:
        raise SystemExit(2)


def _export_stage(args) -> None:
    import bpy
    config = load_build_config(Path(args.config))
    out_dir = Path(args.out_dir)
    validation_path = out_dir / 'reports' / 'validation.json'
    if not validation_path.exists():
        raise RuntimeError('validation report missing; export is fail-closed')
    validation = json.loads(validation_path.read_text())
    if validation.get('pass') is not True:
        raise RuntimeError('validation report did not pass; refusing export')
    bpy.ops.wm.open_mainfile(filepath=str((out_dir / 'work' / 'mantle_fitted.blend').resolve()))
    export_validated_scene(out_dir, config)


def main() -> None:
    args = _parse_args()
    if args.stage == 'normalize-base':
        _normalize_base(args)
        return
    if args.stage == 'fit-staff':
        _fit_staff_stage(args)
        return
    if args.stage == 'fit-belt':
        _fit_belt_stage(args)
        return
    if args.stage == 'fit-mantle':
        _fit_mantle_stage(args)
        return
    if args.stage == 'validate':
        _validate_stage(args)
        return
    if args.stage == 'export':
        _export_stage(args)
        return
    raise SystemExit(f'unsupported stage: {args.stage}')


if __name__ == '__main__':
    main()
