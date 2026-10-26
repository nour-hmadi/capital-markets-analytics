import streamlit as st

import app_data  # noqa: F401  (sets up the import path for the pages)

st.set_page_config(page_title="Capital Markets Analytics", page_icon="📈", layout="wide")

st.title("Capital Markets Analytics")
st.markdown(
    "An end-to-end capital markets data project: market data, a trade book, "
    "daily valuation and risk, a tested data pipeline, and this live app."
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Trades in the book", "60")
c2.metric("Daily valuations", "7,403")
c3.metric("Python tests", "140")
c4.metric("dbt tests", "24")

st.subheader("Explore")
st.markdown(
    "- **Market:** equity indices, the yield curve on any date, and FX rates\n"
    "- **Portfolio:** P&L and risk by desk\n"
    "- **Pricing:** price a bond or an FX forward yourself"
)

st.info("All market data is synthetic (simulated with a fixed seed), not real market data.")
st.markdown("Code, tests and documentation: "
            "[github.com/nour-hmadi/capital-markets-analytics]"
            "(https://github.com/nour-hmadi/capital-markets-analytics)")
