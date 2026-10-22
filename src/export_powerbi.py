"""Export the dashboard tables to one Excel workbook (one sheet per table) for Power BI on the web."""
import pandas as pd

from analytics import curve_shape, curve_spread_bp, daily_returns, drawdown, rolling_volatility
from load_db import DATA_DIR, build_dim_date, build_market_prices, read_market

OUTPUT = DATA_DIR / "powerbi" / "capital_markets.xlsx"


def build_price_analytics():
    """Daily return, 21-day volatility and drawdown for each equity index and FX pair, in long format."""
    parts = []
    for file_name, asset_class in [("equities.csv", "EQUITY"), ("fx_rates.csv", "FX")]:
        prices = read_market(file_name)
        returns = daily_returns(prices)
        metrics = {
            "daily_return": returns,
            "rolling_vol_21d": rolling_volatility(returns),
            "drawdown": drawdown(prices),
        }
        table = None
        for metric, wide in metrics.items():
            long = wide.reset_index().melt(id_vars="date", var_name="series", value_name=metric)
            table = long if table is None else table.merge(long, on=["date", "series"], how="outer")
        table["asset_class"] = asset_class
        parts.append(table)
    columns = ["date", "asset_class", "series", "daily_return", "rolling_vol_21d", "drawdown"]
    return pd.concat(parts, ignore_index=True)[columns]


def build_curve_summary():
    curves = read_market("yield_curves.csv")
    spread = curve_spread_bp(curves)
    return pd.DataFrame({
        "date": curves.index,
        "spread_10y_2y_bp": spread.round(2).values,
        "curve_shape": curve_shape(spread).values,
    })


def build_tables():
    market = build_market_prices()
    return {
        "dim_date": build_dim_date(market["date"]),
        "dim_trade": pd.read_csv(DATA_DIR / "trades.csv", parse_dates=["trade_date", "maturity_date"]),
        "fact_market_prices": market,
        "fact_price_analytics": build_price_analytics(),
        "fact_curve": build_curve_summary(),
        "fact_valuations": pd.read_csv(DATA_DIR / "valuations.csv", parse_dates=["date"]),
    }


def main():
    OUTPUT.parent.mkdir(exist_ok=True)
    with pd.ExcelWriter(OUTPUT, engine="openpyxl") as writer:
        for name, table in build_tables().items():
            table.to_excel(writer, sheet_name=name, index=False)
            print(f"{name:<22} {len(table):>6} rows")
    print(f"Saved {OUTPUT}")


if __name__ == "__main__":
    main()
