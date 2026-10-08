"""Generate a synthetic trade book: equity, bond and FX forward trades.

Every trade is booked on a real date from the market data, at that day's
market price, so trades and market data are consistent.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from pricing import bond_price, fx_forward

SEED = 7
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
COUNTERPARTIES = ["Alpha Bank", "Beta Asset Management", "Gamma Insurance", "Delta Pension Fund"]
DEPOSIT_RATES = {"USD": 0.04, "EUR": 0.02, "GBP": 0.045, "JPY": 0.005}  # simple fixed rates
FX_TENORS_MONTHS = [3, 6, 12]


def load_market(name):
    return pd.read_csv(DATA_DIR / name, index_col="date", parse_dates=True)


def tenor_to_years(tenor):
    """'10Y' -> 10"""
    return int(tenor.rstrip("Y"))


def generate_equity_trades(rng, equities, n_trades=20):
    """Buy or sell units of an index at that day's closing level."""
    trades = []
    for _ in range(n_trades):
        date = equities.index[rng.integers(0, len(equities))]
        index_name = str(rng.choice(equities.columns))
        trades.append({
            "trade_date": date,
            "desk": "EQUITY",
            "instrument_type": "EQUITY_INDEX",
            "underlying": index_name,
            "direction": str(rng.choice(["BUY", "SELL"])),
            "quantity": int(rng.integers(1, 11)) * 100,   # 100 to 1,000 units
            "trade_price": equities.loc[date, index_name],
            "counterparty": str(rng.choice(COUNTERPARTIES)),
        })
    return pd.DataFrame(trades)


def generate_bond_trades(rng, curves, n_trades=20):
    """Buy or sell government bonds. Prices are quoted per 100 of face value."""
    trades = []
    for _ in range(n_trades):
        date = curves.index[rng.integers(0, len(curves))]
        tenor = str(rng.choice(curves.columns))
        years = tenor_to_years(tenor)
        market_yield = curves.loc[date, tenor] / 100        # stored in %, used as a decimal
        coupon_rate = round(market_yield * 400) / 400       # nearest 0.25%
        trades.append({
            "trade_date": date,
            "desk": "RATES",
            "instrument_type": "BOND",
            "underlying": f"GOV_{tenor}",
            "direction": str(rng.choice(["BUY", "SELL"])),
            "quantity": int(rng.integers(1, 11)) * 1_000_000,  # face value
            "trade_price": round(bond_price(100, coupon_rate, years, market_yield), 4),
            "coupon_rate": coupon_rate,
            "maturity_years": years,
            "counterparty": str(rng.choice(COUNTERPARTIES)),
        })
    return pd.DataFrame(trades)


def generate_fx_forward_trades(rng, fx, n_trades=20, pairs=("EURUSD", "GBPUSD", "USDJPY")):
    """Agree today on an exchange rate for a future date (interest rate parity)."""
    trades = []
    for _ in range(n_trades):
        date = fx.index[rng.integers(0, len(fx))]
        pair = str(rng.choice(pairs))
        base, quote = pair[:3], pair[3:]
        months = int(rng.choice(FX_TENORS_MONTHS))
        spot = fx.loc[date, pair]
        forward = fx_forward(spot, DEPOSIT_RATES[base], DEPOSIT_RATES[quote], months / 12)
        trades.append({
            "trade_date": date,
            "desk": "FX",
            "instrument_type": "FX_FORWARD",
            "underlying": pair,
            "direction": str(rng.choice(["BUY", "SELL"])),     # buy or sell the base currency
            "quantity": int(rng.integers(1, 11)) * 1_000_000,  # in base currency
            "trade_price": round(forward, 3 if quote == "JPY" else 5),
            "spot_at_trade": spot,
            "maturity_date": date + pd.DateOffset(months=months),
            "counterparty": str(rng.choice(COUNTERPARTIES)),
        })
    return pd.DataFrame(trades)
def generate_trade_book(seed=SEED, n_per_type=20):
    """All trades in one table, sorted by date, each with a unique trade ID."""
    rng = np.random.default_rng(seed)
    book = pd.concat([
        generate_equity_trades(rng, load_market("equities.csv"), n_per_type),
        generate_bond_trades(rng, load_market("yield_curves.csv"), n_per_type),
        generate_fx_forward_trades(rng, load_market("fx_rates.csv"), n_per_type),
    ], ignore_index=True)
    book = book.sort_values(["trade_date", "desk"], kind="stable").reset_index(drop=True)
    book.insert(0, "trade_id", [f"T{i:05d}" for i in range(1, len(book) + 1)])
    return book


def main():
    book = generate_trade_book()
    book.to_csv(DATA_DIR / "trades.csv", index=False, date_format="%Y-%m-%d")
    print(f"Saved trades.csv: {len(book)} trades")
    print(book["instrument_type"].value_counts().to_string())


if __name__ == "__main__":
    main()
