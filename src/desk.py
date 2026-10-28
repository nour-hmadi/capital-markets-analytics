"""Trade desk: book a new trade at the market price of its trade date, and value it today.

Uses the same pricing and valuation functions as the official book.
`market` is a dict of wide tables indexed by date: {"equities", "curves", "fx"}.
"""
import pandas as pd

from pricing import bond_price, fx_forward
from trades import COUNTERPARTIES, DEPOSIT_RATES, FX_TENORS_MONTHS
from valuation import value_trade_on

INSTRUMENTS = {
    "EQUITY_INDEX": {"desk": "EQUITY", "underlyings": ["INDEX_US", "INDEX_TECH", "INDEX_EU"]},
    "BOND": {"desk": "RATES", "underlyings": ["GOV_1Y", "GOV_2Y", "GOV_5Y", "GOV_10Y", "GOV_30Y"]},
    "FX_FORWARD": {"desk": "FX", "underlyings": ["EURUSD", "GBPUSD", "USDJPY"]},
}
MAX_QUANTITY = 100_000_000


def book_trade(instrument_type, underlying, direction, quantity, trade_date, counterparty,
               market, tenor_months=None):
    """A complete trade, priced at the market on its trade date. Invalid input raises ValueError."""
    if instrument_type not in INSTRUMENTS:
        raise ValueError(f"Unknown instrument type: {instrument_type}")
    if underlying not in INSTRUMENTS[instrument_type]["underlyings"]:
        raise ValueError(f"{underlying} is not a valid underlying for {instrument_type}")
    if direction not in ("BUY", "SELL"):
        raise ValueError("Direction must be BUY or SELL")
    if counterparty not in COUNTERPARTIES:
        raise ValueError(f"Unknown counterparty: {counterparty}")
    if not (isinstance(quantity, int) and 0 < quantity <= MAX_QUANTITY):
        raise ValueError(f"Quantity must be a whole number from 1 to {MAX_QUANTITY:,}")
    date = pd.Timestamp(trade_date)
    if date not in market["equities"].index:
        raise ValueError(f"{date:%Y-%m-%d} is not a trading day in the market data")

    trade = {"trade_date": date, "desk": INSTRUMENTS[instrument_type]["desk"],
             "instrument_type": instrument_type, "underlying": underlying, "direction": direction,
             "quantity": quantity, "counterparty": counterparty, "coupon_rate": None,
             "maturity_years": None, "spot_at_trade": None, "maturity_date": None}

    if instrument_type == "EQUITY_INDEX":
        trade["trade_price"] = round(float(market["equities"].loc[date, underlying]), 2)
    elif instrument_type == "BOND":
        tenor = underlying.removeprefix("GOV_")
        years = int(tenor.rstrip("Y"))
        market_yield = market["curves"].loc[date, tenor] / 100
        coupon_rate = round(market_yield * 400) / 400               # nearest 0.25%, like the book
        trade.update(coupon_rate=coupon_rate, maturity_years=years,
                     trade_price=round(bond_price(100, coupon_rate, years, market_yield), 4))
    else:
        if tenor_months not in FX_TENORS_MONTHS:
            raise ValueError(f"FX forwards need a tenor of {FX_TENORS_MONTHS} months")
        base, quote = underlying[:3], underlying[3:]
        spot = float(market["fx"].loc[date, underlying])
        forward = fx_forward(spot, DEPOSIT_RATES[base], DEPOSIT_RATES[quote], tenor_months / 12)
        trade.update(spot_at_trade=spot, maturity_date=date + pd.DateOffset(months=tenor_months),
                     trade_price=round(forward, 3 if quote == "JPY" else 5))
    return trade


def value_today(trade, market):
    """Market value, P&L, DV01 and status on the last market date."""
    today = market["equities"].index.max()
    result = value_trade_on(pd.Series(trade), today, market["equities"], market["curves"], market["fx"])
    rounded = {key: round(value, 2) if isinstance(value, float) else value for key, value in result.items()}
    return {"valuation_date": today.date().isoformat(), **rounded}
