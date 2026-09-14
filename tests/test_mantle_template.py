from blender_pipeline.fit_mantle import mantle_face_is_in_template


def test_mantle_template_preserves_back_and_front_opening():
    assert mantle_face_is_in_template((0, .12, 1.1), 0, 0, .69, 1.5, .25)
    assert not mantle_face_is_in_template((0, -.12, 1.1), 0, 0, .69, 1.5, .25)
    assert mantle_face_is_in_template((.12, -.12, 1.1), 0, 0, .69, 1.5, .25)


def test_mantle_template_excludes_head_legs_and_forearms():
    for p in ((0, 0, 1.7), (0, 0, .3), (.45, 0, 1.1)):
        assert not mantle_face_is_in_template(p, 0, 0, .69, 1.5, .25)
