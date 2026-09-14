from pathlib import Path
import json

from blender_pipeline.validate import report_passes
from pipeline.schema import ValidationThresholds


def thresholds():
    return ValidationThresholds(
        max_unweighted_vertices=0,
        max_influences_per_vertex=4,
        max_floating_distance_m=0.06,
        max_penetration_ratio=0.08,
        max_bundle_mb=18.0,
    )


def clean_report():
    return {
        'animations': ['Idle', 'Walk', 'Run'],
        'gear': {
            'belt': {'unweighted_vertices': 0, 'max_influences': 4, 'floating_vertex_ratio': 0.01, 'penetration_ratio': 0.01},
            'mantle': {'unweighted_vertices': 0, 'max_influences': 4, 'floating_vertex_ratio': 0.03, 'penetration_ratio': 0.04},
        },
        'staff': {'parent_bone': 'Socket_RightHand', 'max_socket_drift_m': 0.02},
    }


def test_report_passes_clean_proof():
    assert report_passes(clean_report(), thresholds()) is True


def test_report_fails_floating_mantle():
    report = clean_report()
    report['gear']['mantle']['floating_vertex_ratio'] = 0.25
    assert report_passes(report, thresholds()) is False


def test_report_fails_wrong_staff_parent():
    report = clean_report()
    report['staff']['parent_bone'] = 'ABR_RIGHT_HAND'
    assert report_passes(report, thresholds()) is False


def test_validation_report_schema_when_present():
    path = Path('assets/build/reports/validation.json')
    if not path.exists():
        return
    report = json.loads(path.read_text())
    assert report['pass'] is True
    assert set(report['animations']) == {'Idle', 'Walk', 'Run'}
    for gear in ('belt', 'mantle'):
        assert report['gear'][gear]['unweighted_vertices'] == 0
        assert report['gear'][gear]['max_influences'] <= 4
