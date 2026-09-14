import pytest
from blender_pipeline.pose_clearance import clearance_correction


def test_exterior_point_is_unchanged():
    assert clearance_correction((0, .024, 0), (0, 0, 0), (0, 1, 0)) == (0., 0., 0.)


def test_embedded_point_moves_out_not_further_inside():
    assert clearance_correction((0, -.009, 0), (0, 0, 0), (0, 1, 0)) == pytest.approx((0, .017, 0))


def test_large_distance_is_a_real_fit_failure_not_silently_squashed():
    with pytest.raises(ValueError, match='outside'):
        clearance_correction((.3, 0, 0), (0, 0, 0), (1, 0, 0))
