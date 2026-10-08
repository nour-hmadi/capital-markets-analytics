from pathlib import Path

import pandas as pd
import pytest

from analytics import curve_changes_bp, curve_shape, curve_spread_bp, fx_moves_pips, pip_size

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def test_curve_change_in_bp():
    curves = pd.DataFrame({"10Y": [3.00, 3.25]})
    assert curve_changes_bp(curves)["10Y"].iloc[0] == pytest.approx(25)


def test_spread_and_shape_match_day1_examples():
    curves = pd.DataFrame({"2Y": [3.3, 4.7], "10Y": [4.1, 4.0]})
    spread = curve_spread_bp(curves)
    assert spread.tolist() == pytest.approx([80, -70])
    assert curve_shape(spread).tolist() == ["normal", "inverted"]


@pytest.mark.parametrize("pair, size", [("EURUSD", 0.0001), ("GBPUSD", 0.0001), ("USDJPY", 0.01)])
def test_pip_size(pair, size):
    assert pip_size(pair) == size


def test_fx_moves_in_pips():
    fx = pd.DataFrame({"EURUSD": [1.1000, 1.1025], "USDJPY": [150.00, 149.50]})
    moves = fx_moves_pips(fx)
    assert moves["EURUSD"].iloc[0] == pytest.approx(25)
    assert moves["USDJPY"].iloc[0] == pytest.approx(-50)


def test_generated_curve_starts_normal_with_80bp_spread():
    curves = pd.read_csv(DATA_DIR / "yield_curves.csv", index_col="date", parse_dates=True)
    assert curve_spread_bp(curves).iloc[0] == pytest.approx(80)
