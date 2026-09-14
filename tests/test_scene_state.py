from types import SimpleNamespace


def test_only_hierarchy_roots_are_scaled_once():
    from blender_pipeline.scene_state import hierarchy_roots
    root = SimpleNamespace(parent=None)
    rig = SimpleNamespace(parent=root)
    mesh = SimpleNamespace(parent=rig)
    loose = SimpleNamespace(parent=None)
    assert hierarchy_roots([root, rig, mesh, loose]) == [root, loose]


def test_reset_clears_last_animation_pose_and_nla():
    from blender_pipeline.scene_state import reset_pose
    bone = SimpleNamespace(location=(2, 3, 4), rotation_euler=(1, 2, 3),
                           rotation_quaternion=(0, 1, 0, 0),
                           rotation_axis_angle=(1, 1, 0, 0), scale=(2, 2, 2))
    data = SimpleNamespace(action='Run', use_nla=True)
    rig = SimpleNamespace(animation_data=data, pose=SimpleNamespace(bones=[bone]))
    reset_pose(rig)
    assert data.action is None
    assert data.use_nla is False
    assert bone.location == (0.0, 0.0, 0.0)
    assert bone.rotation_euler == (0.0, 0.0, 0.0)
    assert bone.rotation_quaternion == (1.0, 0.0, 0.0, 0.0)
    assert bone.scale == (1.0, 1.0, 1.0)


def test_action_switch_uses_its_own_slot_not_previous_animation_slot():
    from blender_pipeline.scene_state import set_action
    data = SimpleNamespace(action=None, action_slot='stale', use_nla=True)
    rig = SimpleNamespace(animation_data=data, pose=SimpleNamespace(bones=[]))
    action = SimpleNamespace(slots=['correct-slot'])
    set_action(rig, action)
    assert data.action is action
    assert data.action_slot == 'correct-slot'
    assert data.use_nla is False
