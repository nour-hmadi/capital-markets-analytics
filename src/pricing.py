"""Pricing functions for bonds and FX (moved from the Day 2 notebook)."""


def bond_price(face_value, coupon_rate, years, ytm):
    """Price of a bond paying an annual coupon, discounted at the yield to maturity."""
    if years < 1:
        raise ValueError("years must be at least 1")
    if ytm <= -1:
        raise ValueError("ytm must be greater than -100%")
    coupon = face_value * coupon_rate
    price = sum(coupon / (1 + ytm) ** t for t in range(1, years + 1))
    price += face_value / (1 + ytm) ** years
    return price


def dv01(face_value, coupon_rate, years, ytm):
    """Price change when the yield rises by 1 basis point (0.0001)."""
    return (bond_price(face_value, coupon_rate, years, ytm)
            - bond_price(face_value, coupon_rate, years, ytm + 0.0001))


def macaulay_duration(face_value, coupon_rate, years, ytm):
    """Average time to receive the cash flows, weighted by their present value."""
    coupon = face_value * coupon_rate
    price = bond_price(face_value, coupon_rate, years, ytm)
    weighted_time = 0
    for t in range(1, years + 1):
        cash_flow = coupon + (face_value if t == years else 0)
        weighted_time += t * cash_flow / (1 + ytm) ** t
    return weighted_time / price


def modified_duration(face_value, coupon_rate, years, ytm):
    """Approximate % price change for a 1% (100 bp) change in yield."""
    return macaulay_duration(face_value, coupon_rate, years, ytm) / (1 + ytm)


def cross_rate(base_usd, quote_usd):
    """Cross rate when USD is the quote currency in both, e.g. EUR/GBP = EUR/USD / GBP/USD."""
    return base_usd / quote_usd


def fx_forward(spot, r_base, r_quote, years):
    """FX forward from interest rate parity: spot * (1 + r_quote)^T / (1 + r_base)^T."""
    return spot * (1 + r_quote) ** years / (1 + r_base) ** years
