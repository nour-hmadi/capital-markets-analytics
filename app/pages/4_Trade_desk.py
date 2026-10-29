import datetime as dt

import pandas as pd
import streamlit as st

from app_data import send, sign_in_ready, signed_in_email      # import first: it makes src/ importable
from desk import INSTRUMENTS, MAX_QUANTITY
from trades import COUNTERPARTIES, FX_TENORS_MONTHS

st.set_page_config(page_title="Trade desk", page_icon="🧾", layout="wide")
st.title("Trade desk")
st.caption("Book a trade at the market price of any trading day in 2025 and see its P&L on the last day. "
           "Your trades are kept apart from the official book, up to 20 per person. "
           "Guest trades are cleared every morning: sign in with Google to keep yours.")

user = signed_in_email()                              # None for a guest
if user or sign_in_ready():
    left, right = st.columns([4, 1], vertical_alignment="center")
    if user:
        left.markdown(f"Signed in as **{user}**")
        right.button("Log out", on_click=st.logout)
    else:
        left.markdown("You are trading as a **guest**.")
        right.button("Sign in with Google", on_click=st.login, type="primary")

LABELS = {"EQUITY_INDEX": "Equity index", "BOND": "Government bond", "FX_FORWARD": "FX forward"}


def usd(value):
    return f"-${abs(value):,.0f}" if value < 0 else f"${value:,.0f}"


if "flash" in st.session_state:                       # a message from the last action, shown once
    st.success(st.session_state.pop("flash"))

# ---------- Book a trade ----------
st.subheader("Book a trade")
instrument = st.radio("Instrument", list(INSTRUMENTS), format_func=LABELS.get, horizontal=True)
with st.form("book"):
    c1, c2, c3 = st.columns(3)
    underlying = c1.selectbox("Underlying", INSTRUMENTS[instrument]["underlyings"])
    direction = c2.radio("Direction", ["BUY", "SELL"], horizontal=True)
    quantity = c3.number_input("Units" if instrument == "EQUITY_INDEX" else "Notional",
                               min_value=1, max_value=MAX_QUANTITY,
                               value=100 if instrument == "EQUITY_INDEX" else 1_000_000)
    c4, c5, c6 = st.columns(3)
    trade_date = c4.date_input("Trade date", value=dt.date(2025, 3, 3),
                               min_value=dt.date(2025, 1, 1), max_value=dt.date(2025, 12, 18))
    counterparty = c5.selectbox("Counterparty", COUNTERPARTIES)
    tenor = c6.selectbox("Tenor (months)", FX_TENORS_MONTHS) if instrument == "FX_FORWARD" else None
    booked = st.form_submit_button("Book trade", type="primary")

if booked:
    ok, result = send("POST", "/desk/trades", {
        "instrument_type": instrument, "underlying": underlying, "direction": direction,
        "quantity": int(quantity), "trade_date": trade_date.isoformat(),
        "counterparty": counterparty, "tenor_months": tenor}, user=user)
    if ok:
        st.session_state["flash"] = (f"Booked {result['trade_id']}: checked ✓ priced at that day's market "
                                     f"({result['trade_price']:,}) ✓ saved ✓ valued ✓ · P&L {usd(result['pnl'])}")
        st.rerun()
    st.error(result)

# ---------- Your trades ----------
st.subheader("Your trades")
with st.spinner("Loading from the API… (the free backend can take up to a minute to wake up)"):
    ok, trades = send("GET", "/desk/trades", user=user)
if not ok:
    st.error(trades)
    st.stop()
if not trades:
    st.info("No trades yet: book one above.")
    st.stop()

table = pd.DataFrame(trades)
columns = ["trade_id", "pnl", "underlying", "direction", "quantity", "trade_date", "trade_price", "dv01", "status"]
st.dataframe(table[columns].style.format({"pnl": usd, "dv01": usd, "quantity": "{:,.0f}"}), hide_index=True)
st.metric("P&L of your trades", usd(table["pnl"].sum()))

# ---------- Change or delete ----------
st.subheader("Change or delete a trade")
chosen = st.selectbox("Trade", table["trade_id"])
row = table.set_index("trade_id").loc[chosen]
c1, c2, c3, c4 = st.columns([2, 2, 1, 1], vertical_alignment="bottom")
new_direction = c1.radio("New direction", ["BUY", "SELL"], index=["BUY", "SELL"].index(row["direction"]),
                         horizontal=True, key=f"direction_{chosen}")
new_quantity = c2.number_input("New quantity", min_value=1, max_value=MAX_QUANTITY,
                               value=int(row["quantity"]), key=f"quantity_{chosen}")
if c3.button("Update"):
    ok, result = send("PUT", f"/desk/trades/{chosen}", {"direction": new_direction, "quantity": int(new_quantity)},
                      user=user)
    if ok:
        st.session_state["flash"] = f"Updated {chosen} · P&L {usd(result['pnl'])}"
        st.rerun()
    st.error(result)
if c4.button("Delete"):
    ok, result = send("DELETE", f"/desk/trades/{chosen}", user=user)
    if ok:
        st.session_state["flash"] = f"Deleted {chosen}"
        st.rerun()
    st.error(result)

with st.expander(f"Trade message (XML) for {chosen}"):
    ok, xml = send("GET", f"/desk/trades/{chosen}/xml", as_text=True, user=user)
    if ok:
        st.code(xml, language="xml")
    else:
        st.error(xml)
