"""The app must show series in a fixed order, whatever order the API returns them in."""
import app_data


def fake_api(series_names):
    rows = [{"price_date": "2025-01-02", "series": s, "value": 1.0} for s in series_names]
    return lambda path, params=None, as_text=False: {"prices": rows}


def test_fx_pairs_keep_eurusd_first(monkeypatch):
    monkeypatch.setattr(app_data, "api", fake_api(["EURGBP", "EURUSD", "GBPUSD", "USDJPY"]))
    assert list(app_data.load_market("FX").columns) == ["EURUSD", "GBPUSD", "USDJPY", "EURGBP"]


def test_yield_curve_keeps_maturity_order(monkeypatch):
    monkeypatch.setattr(app_data, "api", fake_api(["10Y", "1Y", "2Y", "30Y", "5Y"]))
    assert list(app_data.load_market("RATES").columns) == ["1Y", "2Y", "5Y", "10Y", "30Y"]


def test_unknown_series_are_kept_at_the_end(monkeypatch):
    monkeypatch.setattr(app_data, "api", fake_api(["INDEX_EU", "INDEX_NEW", "INDEX_US", "INDEX_TECH"]))
    columns = list(app_data.load_market("EQUITY").columns)
    assert columns == ["INDEX_US", "INDEX_TECH", "INDEX_EU", "INDEX_NEW"]
