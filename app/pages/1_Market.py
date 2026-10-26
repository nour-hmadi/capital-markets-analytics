import pandas as pd
import streamlit as st

from app_data import load_market
from analytics import (annualised_volatility, curve_spread_bp, daily_returns,
                       drawdown, max_drawdown, rolling_volatility)

st.set_page_config(page_title="Market", page_icon="📈", layout="wide")
st.title("Market overview")
st.caption("Synthetic data: one year of trading days.")

equities = load_market("EQUITY")
curves = load_market("RATES")
fx = load_market("FX")

# ---------- Equities ----------
st.header("Equity indices")
returns = daily_returns(equities)

for column, name in zip(st.columns(len(equities.columns)), equities.columns):
    year_change = equities[name].iloc[-1] / equities[name].iloc[0] - 1
    column.metric(name, f"{equities[name].iloc[-1]:,.0f}", f"{year_change:+.1%} over the year")

view = st.radio("Show", ["Performance (rebased to 100)", "21-day volatility", "Drawdown"], horizontal=True)
if view == "Performance (rebased to 100)":
    st.line_chart((equities / equities.iloc[0] * 100).round(2))
elif view == "21-day volatility":
    st.line_chart(rolling_volatility(returns))
else:
    st.line_chart(drawdown(equities))

summary = pd.DataFrame({
    "Annualised volatility": annualised_volatility(returns),
    "Max drawdown": max_drawdown(equities),
})
st.dataframe(summary.style.format("{:.1%}"))

# ---------- Rates ----------
st.header("Yield curve")
chosen = st.select_slider("Pick a date", options=list(curves.index.date), value=curves.index[-1].date())
day = pd.Timestamp(chosen)

curve = pd.DataFrame({"Yield (%)": curves.loc[day].values}, index=[1, 2, 5, 10, 30])
curve.index.name = "Maturity (years)"
st.line_chart(curve)

spread = curve_spread_bp(curves)
c1, c2 = st.columns(2)
c1.metric("10y − 2y spread", f"{spread.loc[day]:.0f} bp")
c2.metric("Curve shape", "Normal" if spread.loc[day] >= 0 else "Inverted")
st.line_chart(spread.rename("10y − 2y spread (bp)"))

# ---------- FX ----------
st.header("FX rates")
pair = st.selectbox("Currency pair", list(fx.columns))
st.line_chart(fx[pair])

