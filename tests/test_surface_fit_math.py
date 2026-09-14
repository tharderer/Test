import pytest
from blender_pipeline.surface_fit import torso_sample_indices, radial_detail, classify_distance


def test_waist_sampling_excludes_arms_at_same_height():
    points = [(-.16, 0, 1.0), (.16, 0, 1.0), (-.50, 0, 1.0), (.50, 0, 1.0)]
    weights = [.95, .95, .01, .01]
    assert torso_sample_indices(points, weights, 1.0, .04) == [0, 1]


def test_waist_sampling_fails_instead_of_falling_back_to_hands():
    with pytest.raises(ValueError, match='torso'):
        torso_sample_indices([(0, 0, 1)], [0.0], 1.0, .04)


def test_radial_detail_preserves_thickness_but_limits_large_offsets():
    assert radial_detail(.20, .20, .02) == 0.0
    assert radial_detail(.215, .20, .02) == pytest.approx(.015)
    assert radial_detail(.30, .20, .02) == .02


def test_world_space_clearance_is_not_gear_normal_dependent():
    assert classify_distance((0, -.012, 0), (0, -1, 0), .06) == (False, False)
    assert classify_distance((0, .01, 0), (0, -1, 0), .06) == (False, True)
    assert classify_distance((0, -.10, 0), (0, -1, 0), .06) == (True, False)


def test_clearance_remains_normal_to_sloping_shoulders():
    from blender_pipeline.surface_fit import surface_offset
    from math import sqrt
    normal = (.1, 0., sqrt(.99))
    offset = surface_offset(normal, (1., 0., 0.), .024, .015)
    assert sum(a * b for a, b in zip(offset, normal)) >= .024
    assert sqrt(sum(a*a for a in offset)) < .06
