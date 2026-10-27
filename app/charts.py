"""Line charts with one look on every page.

st.line_chart is quick, but it zooms when you scroll over it and always starts
the y-axis at 0, which flattens prices and yields. line_chart() fixes both and
keeps the legend in the same order as the columns (the same order as the cards).
"""
import altair as alt
import pandas as pd


def line_chart(data, y_title, height=320):
    """One line per column of `data`; the index (dates or numbers) is the x-axis."""
    table = data.to_frame() if isinstance(data, pd.Series) else data
    x = table.index.name or "x"
    long = table.reset_index(names=x).melt(id_vars=x, var_name="series", value_name="value")
    x_type = "temporal" if pd.api.types.is_datetime64_any_dtype(table.index) else "quantitative"
    series = list(table.columns)

    return (
        alt.Chart(long)
        .mark_line()
        .encode(
            x=alt.X(x, type=x_type, title=None if x_type == "temporal" else x),
            y=alt.Y("value:Q", title=y_title, scale=alt.Scale(zero=False)),
            color=alt.Color("series:N", sort=series, title=None,
                            legend=alt.Legend(orient="bottom") if len(series) > 1 else None),
            tooltip=[alt.Tooltip(x, type=x_type), "series:N", "value:Q"],
        )
        .properties(height=height)
    )


def bar_chart(values, x_title):
    """Horizontal bars, one per label: blue above zero, red below. Labels stay horizontal."""
    table = values.rename("value").rename_axis("label").reset_index()
    table["sign"] = table["value"].ge(0).map({True: "Positive", False: "Negative"})

    return (
        alt.Chart(table)
        .mark_bar()
        .encode(
            y=alt.Y("label:N", sort=list(table["label"]), title=None),
            x=alt.X("value:Q", title=x_title, axis=alt.Axis(format="~s")),
            color=alt.Color("sign:N", legend=None,
                            scale=alt.Scale(domain=["Positive", "Negative"], range=["#2a78d6", "#e34948"])),
            tooltip=["label:N", alt.Tooltip("value:Q", title=x_title, format=",.0f")],
        )
        .properties(height=45 * len(table) + 30)
    )
