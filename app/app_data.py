"""Shared data loading for every page. Results are cached, so each CSV is read only once."""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
sys.path.insert(0, str(ROOT / "src"))      # lets pages import analytics.py and pricing.py


@st.cache_data
def load_market(name):
    return pd.read_csv(DATA_DIR / name, index_col="date", parse_dates=True)


@st.cache_data
def load_trades():
    return pd.read_csv(DATA_DIR / "trades.csv", parse_dates=["trade_date", "maturity_date"])


@st.cache_data
def load_valuations():
    return pd.read_csv(DATA_DIR / "valuations.csv", parse_dates=["date"])
