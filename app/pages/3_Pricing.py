import numpy as np
import pandas as pd
import streamlit as st

from app_data import load_market      # import first: it makes src/ importable
from analytics import pip_size
from pricing import bond_price, dv01, fx_forward, macaulay_duration, modified_duration
from trades import DEPOSIT_RATES

st.set_page_config(page_title="Pricing tools", page_icon="🧮", layout="wide")
st.title("Pricing tools")
st.caption("Built on the same tested pricing functions as the rest of the project.")

bond_tab, fx_tab = st.tabs(["Bond pricer", "FX forward"])

# ---------- Bond pricer ----------
with bond_tab:
    c1, c2, c3, c4 = st.columns(4)
    face = c1.number_input("Face value", min_value=100.0, value=1_000_000.0, step=100_000.0, format="%.0f")
    coupon_pct = c2.number_input("Coupon (%)", min_value=0.0, max_value=20.0, value=5.0, step=0.25)
    years = int(c3.number_input("Maturity (years)", min_value=1, max_value=50, value=10, step=1))
    ytm_pct = c4.number_input("Yield (%)", min_value=0.0, max_value=20.0, value=4.5, step=0.05)

    coupon, ytm = coupon_pct / 100, ytm_pct / 100
    price = bond_price(face, coupon, years, ytm)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Price (per 100 face)", f"{price / face * 100:.4f}")
    m2.metric("DV01", f"${dv01(face, coupon, years, ytm):,.2f}")
    m3.metric("Macaulay duration", f"{macaulay_duration(face, coupon, years, ytm):.2f} years")
    m4.metric("Modified duration", f"{modified_duration(face, coupon, years, ytm):.2f}")

    if abs(coupon - ytm) < 1e-12:
        st.info("**Par bond:** yield = coupon, so the price is exactly 100.")
    elif coupon > ytm:
        st.success("**Premium bond:** the coupon is above the market yield, so buyers pay more than 100.")
    else:
        st.warning("**Discount bond:** the coupon is below the market yield, so the price is below 100.")

    yields = np.round(np.arange(max(ytm_pct - 3, 0.05), ytm_pct + 3.01, 0.05), 2)
    curve = pd.DataFrame({"Price (per 100 face)": [bond_price(100, coupon, years, y / 100) for y in yields]},
                         index=yields)
    curve.index.name = "Yield (%)"
    st.line_chart(curve)
    st.caption("Price falls as yield rises, and the line bends (convexity). "
               "Longer maturities make it steeper: try 30 years.")

# ---------- FX forward ----------
with fx_tab:
    fx = load_market("FX")
    pair = st.selectbox("Currency pair", ["EURUSD", "GBPUSD", "USDJPY"])
    base, quote = pair[:3], pair[3:]

    c1, c2, c3, c4 = st.columns(4)
    spot = c1.number_input(f"Spot {base}/{quote}", min_value=0.0001, value=float(fx[pair].iloc[-1]),
                           format="%.3f" if quote == "JPY" else "%.5f", key=f"spot_{pair}")
    base_rate = c2.number_input(f"{base} interest rate (%)", value=DEPOSIT_RATES[base] * 100,
                                step=0.25, key=f"base_{pair}") / 100
    quote_rate = c3.number_input(f"{quote} interest rate (%)", value=DEPOSIT_RATES[quote] * 100,
                                 step=0.25, key=f"quote_{pair}") / 100
    months = c4.selectbox("Tenor (months)", [1, 3, 6, 12], index=3)

    forward = fx_forward(spot, base_rate, quote_rate, months / 12)
    points = (forward - spot) / pip_size(pair)

    m1, m2 = st.columns(2)
    m1.metric("Forward rate", f"{forward:.3f}" if quote == "JPY" else f"{forward:.5f}")
    m2.metric("Forward points", f"{points:+.1f} pips")

    if quote_rate > base_rate:
        st.info(f"{quote} has the higher interest rate, so {base} is **more expensive forward** than spot.")
    elif quote_rate < base_rate:
        st.info(f"{base} has the higher interest rate, so {base} is **cheaper forward** than spot.")
    else:
        st.info("Equal interest rates: the forward equals the spot.")
