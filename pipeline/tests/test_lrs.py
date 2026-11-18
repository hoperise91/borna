import pytest
from shapely.geometry import LineString, Point

from borna.lrs import (
    Control,
    _end_refs,
    anchors_for,
    attach_junctions,
    build_path,
    decide_orientation,
    normalise_osm_ref,
    segment_quality,
)

BYPASS = {"CB", "VTM", "7CC"}


@pytest.mark.parametrize("token,expected", [
    ("DN 6", ("DN6", "DN")),
    ("DJ103G", ("DJ103G", "DJ")),
    ("DEx12", ("DX12", "DX")),
    ("DNCB", ("CB", "V")),
    ("DN7CC", ("7CC", "V")),
    ("VTM", ("VTM", "V")),
    ("34", None),
    ("E60", None),
    ("DC", None),
])
def test_normalise_osm_ref(token, expected):
    assert normalise_osm_ref(token, BYPASS) == expected


def test_end_refs():
    assert _end_refs("Chichiș (DN 11)- Sfântu Gheorghe- Toplița (DN 15)") == ("DN11", "DN15")
    assert _end_refs("DN 1C - Muncel") == ("DN1C", None)
    assert _end_refs("București- Ploiești") == (None, None)


def test_build_path_bridges_gap_and_picks_one_carriageway():
    lines = [
        LineString([(0, 0), (1000, 0)]),
        LineString([(1100, 0), (2000, 0)]),                        # 100 m mapping gap
        LineString([(2000, 0), (2500, 0), (3000, 0)]),             # carriageway A
        LineString([(2000, 0), (2500, 30), (3000, 0)]),            # carriageway B (longer)
    ]
    path = build_path(lines)
    assert path.length == pytest.approx(3000 + 100 * 0, abs=1)   # gap bridged straight
    assert Point(0, 0).distance(Point(path.coords[0])) < 1 or \
        Point(0, 0).distance(Point(path.coords[-1])) < 1


def test_build_path_leaves_far_pieces_out():
    lines = [LineString([(0, 0), (1000, 0)]), LineString([(5000, 0), (5200, 0)])]
    assert build_path(lines).length == pytest.approx(1000)


def test_orientation_from_controls_and_route_ends():
    rev, how = decide_orientation(10000, 0, 10, [Control(1000, 9, "border"),
                                                 Control(9000, 1, "milestone")], None)
    assert (rev, how) == (True, "controls")
    assert decide_orientation(10000, 0, 10, [], 500) == (False, "route_ends")
    assert decide_orientation(10000, 0, 10, [], -500) == (True, "route_ends")
    assert decide_orientation(10000, 0, 10, [], None) == (False, "none")


def test_anchors_official_ends_without_controls():
    a = anchors_for(10000, 0, 10, [])
    assert [(c.pos, c.km, c.kind) for c in a] == [(0, 0, "start"), (10000, 10, "end")]


def test_anchors_drop_outlier_and_extrapolate():
    controls = [Control(2000, 12, "milestone"), Control(5000, 15, "milestone"),
                Control(6000, 3, "milestone"),            # wrong km: dropped
                Control(8000, 18, "milestone")]
    a = anchors_for(10000, 0, 30, controls)
    assert [c.km for c in a] == [10, 12, 15, 18, 20]       # extended at scale 1 both ways
    assert a[0].kind == a[-1].kind == "extrapolated"


def test_anchors_end_junctions_become_ends():
    a = anchors_for(5000, 0, 5.2, [Control(0, 0, "junction"), Control(5000, 5.2, "junction")])
    assert [(c.pos, c.kind) for c in a] == [(0, "junction"), (5000, "junction")]
    assert segment_quality(a[0], a[1], True) == "calibrated"


def test_attach_junctions_extends_path_to_the_other_road():
    path = LineString([(0, 0), (1000, 0)])
    other = LineString([(-80, -500), (-80, 500)])          # crossing road 80 m before the start
    new, controls = attach_junctions(path, other, None, 0.0, 1.0)
    assert new.length == pytest.approx(1080)
    assert [(c.pos, c.km) for c in controls] == [(0, 0.0)]
