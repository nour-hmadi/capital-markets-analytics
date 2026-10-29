import streamlit as st

import app_data  # noqa: F401  (sets up the import path for the pages)

st.set_page_config(page_title="Capital Markets Analytics", page_icon="📈", layout="wide")

if "backend_woken" not in st.session_state:   # once per visitor
    st.session_state.backend_woken = True
    app_data.wake_backend()

st.title("Capital Markets Analytics")
st.markdown(
    "An end-to-end capital markets data project: market data, a trade book, "
    "daily valuation and risk, a tested data pipeline, and this live app."
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Trades in the book", "60", border=True)
c2.metric("Daily valuations", "7,403", border=True)
c3.metric("Python tests", "165", border=True)
c4.metric("dbt tests", "34", border=True)
st.markdown("[![Tests](https://github.com/nour-hmadi/capital-markets-analytics/actions/workflows/tests.yml/badge.svg)]"
            "(https://github.com/nour-hmadi/capital-markets-analytics/actions)")

st.subheader("Explore")
st.markdown(
    "- **Market:** equity indices, the yield curve on any date, and FX rates\n"
    "- **Portfolio:** P&L and risk by desk\n"
    "- **Pricing:** price a bond or an FX forward yourself\n"
    "- **Trade desk:** book, change and delete your own trades (sign in with Google to keep them)\n"
    "- **Learn:** the trading basics behind each page, with short quizzes"
)

st.info("All market data is synthetic (simulated with a fixed seed), not real market data.")
st.caption("The free backend sleeps when nobody uses it. Opening this page wakes it up, "
           "so the other pages load faster.")
st.markdown("Code, tests and documentation: "
            "[github.com/nour-hmadi/capital-markets-analytics]"
            "(https://github.com/nour-hmadi/capital-markets-analytics)")
st.page_link("pages/6_Privacy_and_terms.py", label="Privacy and terms", icon="🔒")
