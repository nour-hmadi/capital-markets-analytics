"""Value every trade in the book: market value, P&L and DV01.

Reporting currency is USD. Simplification: equity indices and government
bonds are treated as USD instruments.
"""
import pandas as pd

from pricing import bond_price, dv01, fx_forward
from trades import DATA_DIR, DEPOSIT_RATES, load_market


def direction_sign(direction):
    """BUY = +1 (long position), SELL = -1 (short position)."""
    if direction == "BUY":
        return 1
    if direction == "SELL":
        return -1
    raise ValueError(f"Unknown direction: {direction}")


def value_equity(trade, price_today):
    """Market value and P&L of an equity index trade at today's price."""
    sign = direction_sign(trade["direction"])
    quantity = trade["quantity"]
    return {
        "market_value": sign * quantity * price_today,
        "pnl": sign * quantity * (price_today - trade["trade_price"]),
        "dv01": 0.0,
        "status": "LIVE",
    }


def value_bond(trade, yield_today_pct):
    """Market value, P&L and DV01 of a bond trade at today's yield (given in %)."""
    sign = direction_sign(trade["direction"])
    face = trade["quantity"]
    years = int(trade["maturity_years"])
    ytm = yield_today_pct / 100
    price_today = bond_price(100, trade["coupon_rate"], years, ytm)   # per 100 of face
    return {
        "market_value": sign * face * price_today / 100,
        "pnl": sign * face * (price_today - trade["trade_price"]) / 100,
        "dv01": sign * face / 100 * dv01(100, trade["coupon_rate"], years, ytm),
        "status": "LIVE",
    }


def value_fx_forward(trade, spot_today, valuation_date):
    """Mark-to-market of an FX forward in USD. Market value = P&L (a forward costs nothing at booking)."""
    sign = direction_sign(trade["direction"])
    pair = trade["underlying"]
    base, quote = pair[:3], pair[3:]
    notional = trade["quantity"]                                   # in base currency
    maturity = pd.Timestamp(trade["maturity_date"])
    years_left = max((maturity - pd.Timestamp(valuation_date)).days, 0) / 365

    forward_today = fx_forward(spot_today, DEPOSIT_RATES[base], DEPOSIT_RATES[quote], years_left)
    pnl_quote = sign * notional * (forward_today - trade["trade_price"])
    pnl_quote /= (1 + DEPOSIT_RATES[quote]) ** years_left           # discount to today

    if quote == "USD":
        pnl_usd = pnl_quote
    elif base == "USD":
        pnl_usd = pnl_quote / spot_today                            # e.g. JPY -> USD
    else:
        raise NotImplementedError(f"No USD conversion for {pair}")

    return {
        "market_value": pnl_usd,
        "pnl": pnl_usd,
        "dv01": 0.0,
        "status": "LIVE" if years_left > 0 else "MATURED",
    }
def value_trade_on(trade, date, equities, curves, fx):
    """Value one trade on one date, using the right market data for its type."""
    kind = trade["instrument_type"]
    if kind == "EQUITY_INDEX":
        return value_equity(trade, equities.loc[date, trade["underlying"]])
    if kind == "BOND":
        return value_bond(trade, curves.loc[date, f"{int(trade['maturity_years'])}Y"])
    if kind == "FX_FORWARD":
        spot_date = min(date, pd.Timestamp(trade["maturity_date"]))   # freeze at maturity
        spot = fx.loc[:spot_date, trade["underlying"]].iloc[-1]        # last spot on or before
        return value_fx_forward(trade, spot, date)
    raise ValueError(f"Unknown instrument type: {kind}")


def value_book(book, equities, curves, fx):
    """One row per trade per market date, from the trade date onwards."""
    rows = []
    for _, trade in book.iterrows():
        trade_date = pd.Timestamp(trade["trade_date"])
        for date in equities.index[equities.index >= trade_date]:
            result = value_trade_on(trade, date, equities, curves, fx)
            rows.append({"date": date, "trade_id": trade["trade_id"], **result})
    return pd.DataFrame(rows).round({"market_value": 2, "pnl": 2, "dv01": 2})


def main():
    book = pd.read_csv(DATA_DIR / "trades.csv", parse_dates=["trade_date", "maturity_date"])
    valuations = value_book(book, load_market("equities.csv"),
                            load_market("yield_curves.csv"), load_market("fx_rates.csv"))
    valuations.to_csv(DATA_DIR / "valuations.csv", index=False, date_format="%Y-%m-%d")
    print(f"Saved valuations.csv: {len(valuations)} rows")

    last = valuations[valuations["date"] == valuations["date"].max()]
    by_desk = last.merge(book[["trade_id", "desk"]], on="trade_id").groupby("desk")[["pnl", "dv01"]].sum()
    print("\nP&L and DV01 on the last date, by desk (USD):")
    print(by_desk.round(0).to_string())
    print(f"\nTotal P&L: {last['pnl'].sum():,.0f} USD")


if __name__ == "__main__":
    main()
