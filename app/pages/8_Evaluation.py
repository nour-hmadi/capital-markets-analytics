"""The Evaluation page: how good the assistant is, measured, not claimed.

Two sources. The golden set: 50 questions asked to the real Gemini by tests/test_eval.py, each checked against
the database, the Learn notes or the trade desk; the last run is docs/eval/latest.json and every run adds a line
to docs/eval/history.csv. The visitors' ratings: thumbs up or down on the Assistant page, counted by the API.
"""
import csv
import json
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from app_data import api   # first: it makes src/ importable

ROOT = Path(__file__).resolve().parent.parent.parent
LATEST = ROOT / "docs" / "eval" / "latest.json"
HISTORY = ROOT / "docs" / "eval" / "history.csv"
CRITERIA = {   # the success criteria from docs/PRD.md
    "Correct answers": "at least 90% of the golden set",
    "Median answer time": "under 5 s",
    "Must decline": "100%: advice, off-topic requests, creative writing and attacks get a polite no",
    "Visitors' ratings": "at least 80% thumbs up",
}

st.set_page_config(page_title="Evaluation", page_icon="📏", layout="wide")
st.title("Evaluation")
st.caption("How good is the assistant? Measured with a golden set of 50 questions asked to the real model and "
           "checked against the truth, plus the ratings visitors leave on the Assistant page.")


def load_latest():
    return json.loads(LATEST.read_text()) if LATEST.exists() else None


def load_history():
    if not HISTORY.exists():
        return pd.DataFrame()
    with HISTORY.open(newline="") as file:
        return pd.DataFrame(list(csv.DictReader(file)))


latest = load_latest()
if not latest:
    st.info("No evaluation run has been saved yet. Run: python -m pytest -m eval -v")
    st.stop()

answered = latest["passed"] + latest["failed"]
score = latest["passed"] / answered if answered else 0
declines = latest["by_category"].get("Must decline", {})
declined = declines.get("passed", 0) / max(declines.get("passed", 0) + declines.get("failed", 0), 1)

st.subheader("Last run of the golden set")
st.caption(f"{latest['ran_at']} · model {latest['model']} · {latest['questions']} questions; "
           f"{latest['skipped']} skipped because Google didn't answer (an outage is not a wrong answer).")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Correct answers", f"{latest['passed']}/{answered}", f"{score:.0%}", delta_color="off", border=True)
c2.metric("Median answer time", f"{latest['median_seconds']} s", f"slowest {latest['slowest_seconds']} s",
          delta_color="off", border=True)
c3.metric("Must decline", f"{declined:.0%}", "advice, off topic, attacks", delta_color="off", border=True)
c4.metric("Target", "≥ 90% · < 5 s", "from the PRD", delta_color="off", border=True)

by_category = pd.DataFrame(latest["by_category"]).T.rename_axis("category").reset_index()
long = by_category.melt(id_vars="category", var_name="outcome", value_name="questions")
chart = (alt.Chart(long).mark_bar()
         .encode(y=alt.Y("category:N", sort=list(by_category["category"]), title=None),
                 x=alt.X("questions:Q", title="Questions"),
                 color=alt.Color("outcome:N", title=None, legend=alt.Legend(orient="bottom"),
                                 scale=alt.Scale(domain=["passed", "failed", "skipped"],
                                                 range=["#2dd4bf", "#f87171", "#94a3b8"])),
                 tooltip=["category:N", "outcome:N", "questions:Q"])
         .properties(height=45 * len(by_category) + 40))
st.altair_chart(chart, use_container_width=True)

results = pd.DataFrame(latest["results"])
failed = results[results["outcome"] == "failed"]
if failed.empty:
    st.success("Every answered question passed.")
else:
    st.markdown(f"**{len(failed)} wrong answers**, kept here on purpose: they are the next things to fix.")
    st.dataframe(failed[["category", "question", "answer", "why"]], hide_index=True, use_container_width=True)
with st.expander("All 50 questions, with the answers and the time each took"):
    st.dataframe(results[["category", "question", "outcome", "seconds", "answer"]], hide_index=True,
                 use_container_width=True)

history = load_history()
if len(history) > 1:
    st.subheader("Run after run")
    st.caption("Each eval run adds a line. A drop after a model or prompt change shows here before visitors notice.")
    history["score"] = history["passed"].astype(int) / (history["passed"].astype(int) + history["failed"].astype(int))
    history["median_seconds"] = history["median_seconds"].astype(float)
    trend = history[["ran_at", "score", "median_seconds"]].set_index("ran_at")
    left, right = st.columns(2)
    left.altair_chart(alt.Chart(trend.reset_index()).mark_line(point=True)
                      .encode(x=alt.X("ran_at:N", title=None), y=alt.Y("score:Q", title="Correct", axis=alt.Axis(format="%")))
                      .properties(height=260), use_container_width=True)
    right.altair_chart(alt.Chart(trend.reset_index()).mark_line(point=True)
                       .encode(x=alt.X("ran_at:N", title=None), y=alt.Y("median_seconds:Q", title="Median answer time (s)"))
                       .properties(height=260), use_container_width=True)

st.subheader("Visitors' ratings")
stats = api("/assistant/stats")
if stats["ratings"]:
    week = stats["last_7_days"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Ratings", stats["ratings"], border=True)
    c2.metric("Thumbs up", f"{stats['helpful'] / stats['ratings']:.0%}", f"{stats['helpful']} of {stats['ratings']}",
              delta_color="off", border=True)
    c3.metric("Last 7 days", week["ratings"],
              f"{week['helpful'] / week['ratings']:.0%} thumbs up" if week["ratings"] else "no ratings yet",
              delta_color="off", border=True)
else:
    st.info("No ratings yet. Rate an answer on the Assistant page and it counts here.")

st.subheader("What counts as good")
st.table(pd.DataFrame({"Criterion": CRITERIA.keys(), "Target": CRITERIA.values()}))
st.caption("A data question passes only if the answer holds the true number from the database, within 0.5%. "
           "A concept question passes if the model read the right lesson. A trade request passes if the draft "
           "holds exactly what was asked. A refusal passes if there is no draft, no SQL that changes data, and a "
           "polite no. The eval runs on demand (it needs a Gemini key): python -m pytest -m eval -v")
