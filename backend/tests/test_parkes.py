import numpy as np
import pytest

from rozmarra.twin.parkes import parkes_zones, zone_shares


# Each expected zone was worked out by hand from the boundary coordinates for Type 2 Diabetes
# (Pfützner and colleagues, 2013). The reference value comes first.
@pytest.mark.parametrize(
    ("reference", "estimate", "zone"),
    [
        (100, 100, "A"),
        (100, 135, "A"),  # The upper B boundary is at 148 mg/dL for a reference of 100 mg/dL.
        (100, 160, "B"),
        (60, 40, "B"),  # The lower B boundary is at 42.5 mg/dL for a reference of 60 mg/dL.
        (40, 65, "B"),
        (40, 85, "C"),
        (150, 60, "B"),
        (300, 120, "C"),
        (20, 85, "D"),
        (300, 60, "D"),
        (20, 250, "E"),
    ],
)
def test_points_fall_in_the_expected_zone(reference, estimate, zone):
    assert parkes_zones([reference], [estimate])[0] == zone


def test_the_grid_extends_above_550_mg_dl():
    zones = parkes_zones([600, 20, 700], [600, 700, 100])
    assert list(zones) == ["A", "E", "D"]


def test_a_perfect_forecast_is_always_in_zone_a():
    values = np.linspace(20, 500, 50)
    assert set(parkes_zones(values, values)) == {"A"}


def test_the_zone_shares_add_up_to_one():
    result = zone_shares(parkes_zones([100, 100, 20, 300], [100, 160, 250, 60]))
    assert result["pairs"] == 4
    assert sum(result["shares"].values()) == pytest.approx(1.0)
    assert result["share_a_and_b"] == 0.5
