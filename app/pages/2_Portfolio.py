import streamlit as st

from app_data import load_trades, load_valuations

st.set_page_config(page_title="Portfolio", page_icon="💼", layout="wide")
st.title("Portfolio: P&L and risk")
st.caption("60 synthetic trades, marked to market every trading day. All figures in USD.")


def usd(value):
    """$1,234 or -$1,234."""
    return f"-${abs(value):,.0f}" if value < 0 else f"${value:,.0f}"


trades = load_trades()
valuations = load_valuations().merge(
    trades[["trade_id", "desk", "instrument_type", "underlying", "counterparty"]], on="trade_id")

# ---------- Desk filter: every number below follows it ----------
all_desks = sorted(trades["desk"].unique())
desks = st.multiselect("Desks", all_desks, default=all_desks)
if not desks:
    st.warning("Pick at least one desk.")
    st.stop()
valuations = valuations[valuations["desk"].isin(desks)]

last_date = valuations["date"].max()
latest = valuations[valuations["date"] == last_date]

# ---------- Headline numbers ----------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total P&L", usd(latest["pnl"].sum()))
c2.metric("Rates DV01 (per bp)", usd(latest["dv01"].sum()))
c3.metric("Live trades", int((latest["status"] == "LIVE").sum()))
c4.metric("Matured FX forwards", int((latest["status"] == "MATURED").sum()))
st.caption(f"As of {last_date:%d %B %Y}")

# ---------- P&L ----------
st.subheader("P&L over time, by desk")
daily = valuations.pivot_table(index="date", columns="desk", values="pnl", aggfunc="sum")
st.line_chart(daily.round(0))

left, right = st.columns(2)
with left:
    st.subheader("P&L by desk, latest")
    st.bar_chart(latest.groupby("desk")["pnl"].sum().round(0))

with right:
    st.subheader("Rates risk by bond")
    bonds = latest[latest["instrument_type"] == "BOND"]
    if bonds.empty:
        st.info("No bond positions in the selected desks.")
    else:
        st.bar_chart(bonds.groupby("underlying")["dv01"].sum().round(0))
        st.metric("P&L if all rates rise 10 bp", usd(-10 * bonds["dv01"].sum()))

# ---------- Winners and losers ----------
st.subheader("Biggest winners and losers, latest")
columns = ["trade_id", "desk", "underlying", "counterparty", "pnl", "status"]
ranked = latest.sort_values("pnl")[columns]
losers_col, winners_col = st.columns(2)
losers_col.markdown("**Top 5 losers**")
losers_col.dataframe(ranked.head(5).style.format({"pnl": usd}), hide_index=True)
winners_col.markdown("**Top 5 winners**")
winners_col.dataframe(ranked.tail(5).iloc[::-1].style.format({"pnl": usd}), hide_index=True)

with st.expander("All trades"):
    st.dataframe(trades[trades["desk"].isin(desks)], hide_index=True)
