import pandas as pd
import streamlit as st

from app_data import API_URL, load_pnl_history, load_positions, load_risk, load_trade_xml

st.set_page_config(page_title="Portfolio", page_icon="💼", layout="wide")
st.title("Portfolio: P&L and risk")
st.caption("60 synthetic trades, marked to market every trading day. All figures in USD.")


def usd(value):
    """$1,234 or -$1,234."""
    return f"-${abs(value):,.0f}" if value < 0 else f"${value:,.0f}"


history = load_pnl_history()
as_of, positions = load_positions()
risk = load_risk()

# ---------- Desk filter: every number below follows it ----------
all_desks = sorted(positions["desk"].unique())
desks = st.multiselect("Desks", all_desks, default=all_desks)
if not desks:
    st.warning("Pick at least one desk.")
    st.stop()
positions = positions[positions["desk"].isin(desks)]
history = history[[desk for desk in history.columns if desk in desks]]

# ---------- Headline numbers ----------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total P&L", usd(positions["pnl_usd"].sum()))
c2.metric("Rates DV01 (per bp)", usd(positions["dv01_usd"].sum()))
c3.metric("Live trades", int((positions["trade_status"] == "LIVE").sum()))
c4.metric("Matured FX forwards", int((positions["trade_status"] == "MATURED").sum()))
st.caption(f"As of {pd.Timestamp(as_of):%d %B %Y} · served live by the API: {API_URL}/docs")

# ---------- P&L ----------
st.subheader("P&L over time, by desk")
st.line_chart(history.round(0))

left, right = st.columns(2)
with left:
    st.subheader("P&L by desk, latest")
    st.bar_chart(positions.groupby("desk")["pnl_usd"].sum().round(0))

with right:
    st.subheader("Rates risk by bond")
    if "RATES" not in desks:
        st.info("Select the RATES desk to see interest rate risk.")
    else:
        bonds = pd.DataFrame(risk["bonds"]).set_index("security")
        st.bar_chart(bonds["dv01_usd"].round(0))
        st.metric("P&L if all rates rise 10 bp", usd(risk["pnl_if_rates_up_10bp_usd"]))

# ---------- Winners and losers (pnl second, so it stays visible on phones) ----------
st.subheader("Biggest winners and losers, latest")
columns = ["trade_id", "pnl_usd", "desk", "underlying", "trade_status", "counterparty"]
losers_col, winners_col = st.columns(2)
losers_col.markdown("**Top 5 losers**")
losers_col.dataframe(positions.head(5)[columns].style.format({"pnl_usd": usd}), hide_index=True)
winners_col.markdown("**Top 5 winners**")
winners_col.dataframe(positions.tail(5).iloc[::-1][columns].style.format({"pnl_usd": usd}),
                      hide_index=True)

# ---------- XML trade message ----------
st.subheader("Trade message (XML)")
trade_id = st.selectbox("Pick a trade", sorted(positions["trade_id"]))
xml = load_trade_xml(trade_id)
st.download_button("Download trade message (XML)", data=xml,
                   file_name=f"{trade_id}.xml", mime="application/xml")
with st.expander("Preview the message"):
    st.code(xml, language="xml")
