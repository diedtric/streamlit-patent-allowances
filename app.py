"""Streamlit dashboard for public U.S. patent application allowances."""

from datetime import datetime, timedelta
import os
from zoneinfo import ZoneInfo

import altair as alt
import pandas as pd
import streamlit as st

from uspto import COLUMNS, USPTOError, days_between, demo_allowances, fetch_allowances

st.set_page_config(page_title="U.S. Patent Allowances", layout="wide", page_icon="📄")


@st.cache_data(ttl=1800, max_entries=20, show_spinner=False)
def load_live(api_key, start, end):
    return fetch_allowances(api_key, start, end)


def export_csv(table):
    # Prevent text from public records from being interpreted as spreadsheet formulas.
    safe = table.map(
        lambda value: "'" + value if isinstance(value, str)
        and value.lstrip().startswith(("=", "+", "-", "@")) else value
    )
    return safe.to_csv(index=False).encode("utf-8-sig")


def chart_results(table, start, end, grouping):
    if grouping == "Day mailed":
        dates = [day.isoformat() for day in days_between(start, end)]
        counts = table["Mail date"].value_counts().reindex(dates, fill_value=0)
        chart = pd.DataFrame({"Mail date": dates, "Allowances": counts.to_numpy()})
        field, order = "Mail date", dates
    else:
        field = grouping
        labels = table[field].replace("", "Unknown")
        counts = labels.value_counts().head(12)
        chart = counts.rename_axis(field).reset_index(name="Allowances")
        order = "-y"

    return alt.Chart(chart).mark_bar(color="#237678", cornerRadiusTopLeft=4,
                                     cornerRadiusTopRight=4).encode(
        x=alt.X(f"{field}:N", sort=order, axis=alt.Axis(labelAngle=-30)),
        y=alt.Y("Allowances:Q", axis=alt.Axis(tickMinStep=1)),
        tooltip=[field, "Allowances"],
    ).properties(height=280)


def main():
    st.title("U.S. Patent Allowances")
    st.caption("Explore public applications by the date the USPTO mailed a Notice of Allowance.")
    today = datetime.now(ZoneInfo("America/Phoenix")).date()
    configured_key = os.getenv("USPTO_API_KEY", "").strip()
    with st.sidebar:
        st.header("Data")
        mode = st.radio("Source", ["Live USPTO", "Demo data"], index=0)
        api_key = configured_key
        if mode == "Live USPTO" and not api_key:
            api_key = st.text_input("USPTO Open Data Portal API key", type="password").strip()
            st.markdown("[Get an API key](https://data.uspto.gov/)")
        end = st.date_input("Week ending", today - timedelta(days=1), max_value=today)
        start = end - timedelta(days=6)
        refresh = st.button("Refresh USPTO data", disabled=mode != "Live USPTO" or not api_key)
    st.subheader(f"{start:%b %d, %Y} – {end:%b %d, %Y}")
    if mode == "Demo data":
        st.info("Fictional records for trying the filters, chart and CSV export.")
        rows = demo_allowances(start, end)
    else:
        if not api_key:
            st.info("Enter your USPTO API key to load the past week, or choose Demo data.")
            return
        if refresh:
            load_live.clear(api_key, start, end)
        try:
            with st.spinner("Retrieving public allowance records from the USPTO…"):
                rows = load_live(api_key, start, end)
        except USPTOError as exc:
            st.error(str(exc))
            return

    table = pd.DataFrame(rows, columns=COLUMNS)
    if table.empty:
        st.info("The USPTO search returned no verified public allowance events for this week.")
        return
    left, right = st.columns(2)
    search = left.text_input("Search title, applicant or application number")
    types = right.multiselect("Application type", sorted(table["Type"].unique()))
    if search.strip():
        columns = ["Title", "Applicant", "Application number"]
        term = search.strip().replace("/", "").replace(",", "") or search.strip()
        match = table[columns].apply(
            lambda column: column.str.contains(term if column.name == "Application number"
                                               else search.strip(), case=False, regex=False)
        )
        table = table[match.any(axis=1)]
    if types:
        table = table[table["Type"].isin(types)]

    count, unique = st.columns(2)
    count.metric("Allowance events", f"{len(table):,}")
    unique.metric("Unique applications", f"{table['Application number'].nunique():,}")
    if table.empty:
        st.info("No records match these filters.")
        return
    grouping = st.selectbox("Group chart by", ["Day mailed", "Type", "Applicant"])
    if grouping == "Applicant":
        st.caption("Up to 12 applicants by number of allowance events.")
    st.altair_chart(chart_results(table, start, end, grouping), width="stretch")
    st.subheader("Allowance records")
    link_columns = {
        column: st.column_config.LinkColumn(column, display_text=label)
        for column, label in [("Published application PDF", "Application PDF"),
                              ("Issued patent PDF", "Patent PDF"),
                              ("Patent Center", "Open record")]
    }
    st.dataframe(table, hide_index=True, width="stretch", column_config=link_columns)
    prefix = "demo-" if mode == "Demo data" else ""
    st.download_button("Download filtered CSV", export_csv(table),
                       file_name=f"{prefix}allowances-{start}-to-{end}.csv", mime="text/csv")
    if mode == "Live USPTO":
        st.caption("PDF links appear when a U.S. publication or issued grant is listed. "
                   "Open Patent Center to view available file-wrapper documents, including the notice.")
        st.caption("Source: USPTO Open Data Portal. Public coverage and indexing delays can affect totals.")


if __name__ == "__main__":
    main()
