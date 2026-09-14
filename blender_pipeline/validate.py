from __future__ import annotations
from typing import Any
MAX_STAFF_DRIFT_M = 0.20

def report_passes(report: dict[str, Any], thresholds) -> bool:
    if set(report.get('animations', ())) != {'Idle', 'Walk', 'Run'}: return False
    for name in ('belt','mantle'):
        stats=report.get('gear',{}).get(name)
        if not stats: return False
        if int(stats['unweighted_vertices']) > thresholds.max_unweighted_vertices: return False
        if int(stats['max_influences']) > thresholds.max_influences_per_vertex: return False
        if float(stats['floating_vertex_ratio']) > thresholds.max_floating_vertex_ratio: return False
        if float(stats['penetration_ratio']) > thresholds.max_penetration_ratio: return False
    staff=report.get('staff',{})
    return staff.get('parent_bone')=='Socket_RightHand' and float(staff.get('max_socket_drift_m',float('inf'))) <= MAX_STAFF_DRIFT_M

def _weight_stats(obj):
    unweighted=0; max_influences=0
    for v in obj.data.vertices:
        nonzero=[g for g in v.groups if g.weight>1e-6]
        unweighted += not nonzero
        max_influences=max(max_influences,len(nonzero))
    return unweighted,max_influences

def _sample_frames(action):
    start,end=action.frame_range; span=float(end-start)
    return sorted({int(round(float(start)+f*span)) for f in (0,.25,.5,.75,1)})

def _evaluated_positions_normals(obj,depsgraph):
    evaluated=obj.evaluated_get(depsgraph); mesh=evaluated.to_mesh(); world=evaluated.matrix_world; nm=world.to_3x3().inverted().transposed()
    try: return [(world@v.co,(nm@v.normal).normalized()) for v in mesh.vertices]
    finally: evaluated.to_mesh_clear()

def _surface_ratios(body,gear,depsgraph,max_distance,*,ignore_below_z=None):
    from mathutils.bvhtree import BVHTree
    bvh=BVHTree.FromObject(body,depsgraph)
    if bvh is None: raise RuntimeError('could not build Abraham body BVH')
    inv=body.matrix_world.inverted(); eligible=floating=penetrating=0
    for world_pos,world_normal in _evaluated_positions_normals(gear,depsgraph):
        if ignore_below_z is not None and world_pos.z<ignore_below_z: continue
        eligible+=1; local=inv@world_pos; nearest,_normal,_index,distance=bvh.find_nearest(local)
        if nearest is None: floating+=1; continue
        if distance>max_distance: floating+=1
        if distance<0.004:
            nearest_world=body.matrix_world@nearest; direction=nearest_world-world_pos
            if direction.length>1e-8 and world_normal.dot(direction.normalized())<0: penetrating+=1
    return (0.0,0.0) if eligible==0 else (floating/eligible,penetrating/eligible)

def _staff_socket_drift(armature,staff):
    from mathutils import Vector
    socket=armature.pose.bones.get('Socket_RightHand')
    if socket is None: return float('inf')
    expected=armature.matrix_world@(socket.matrix@Vector((0,-0.035,0)))
    return (staff.matrix_world.translation-expected).length

def validate_scene(body,armature,belt,mantle,staff,thresholds):
    import bpy
    required=('ABR_HIPS','ABR_SPINE','ABR_CHEST','ABR_HEAD','ABR_RIGHT_HAND','ABR_LEFT_HAND','ABR_RIGHT_FOOT','ABR_LEFT_FOOT')
    missing=[n for n in required if armature.data.bones.get(n) is None]
    if missing: raise RuntimeError(f'missing canonical bone roles: {missing}')
    actions={n:bpy.data.actions.get(n) for n in ('Idle','Walk','Run')}; names=[n for n,a in actions.items() if a]
    gear={}
    for name,obj in (('belt',belt),('mantle',mantle)):
        u,m=_weight_stats(obj); gear[name]={'unweighted_vertices':u,'max_influences':m,'floating_vertex_ratio':0.0,'penetration_ratio':0.0}
    drift=0.0; deps=bpy.context.evaluated_depsgraph_get()
    for action in actions.values():
        if action is None: continue
        if armature.animation_data is None: armature.animation_data_create()
        armature.animation_data.action=action
        for frame in _sample_frames(action):
            bpy.context.scene.frame_set(frame); deps.update()
            for name,obj in (('belt',belt),('mantle',mantle)):
                floor=float(mantle.get('validation_anchor_floor_z')) if name=='mantle' and mantle.get('validation_anchor_floor_z') is not None else None
                floating,penetration=_surface_ratios(body,obj,deps,thresholds.max_floating_distance_m,ignore_below_z=floor)
                gear[name]['floating_vertex_ratio']=max(gear[name]['floating_vertex_ratio'],floating)
                gear[name]['penetration_ratio']=max(gear[name]['penetration_ratio'],penetration)
            drift=max(drift,_staff_socket_drift(armature,staff))
    report={'animations':names,'gear':gear,'staff':{'parent_bone':staff.parent_bone if staff.parent_type=='BONE' else None,'max_socket_drift_m':drift}}
    report['pass']=report_passes(report,thresholds); return report
