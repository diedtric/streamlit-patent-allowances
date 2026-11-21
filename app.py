"""Streamlit dashboard for allowance records loaded from a CSV."""

from datetime import date, timedelta
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from patent_data import (
    APPLICATION, CLAIMS, CPC, MAILED, PARTIES, STATUS, TITLE,
    csv_bytes, document_links, load_csv,
)

SAMPLE_PATH = Path(__file__).with_name("patent_allowances.csv")

st.set_page_config(page_title="U.S. Patent Allowances", page_icon="📄", layout="wide")


def allowance_chart(table, start, end, group):
    if group == MAILED:
        dates = pd.date_range(start, end).strftime("%Y-%m-%d").tolist()
        counts = table[group].value_counts().reindex(dates, fill_value=0)
        sort_order = dates
    else:
        counts = table[group].replace("", "Unspecified").value_counts().head(12)
        sort_order = "-y"
    summary = counts.rename_axis(group).reset_index(name="Records")
    return alt.Chart(summary).mark_bar(color="#237678").encode(
        x=alt.X(f"{group}:N", sort=sort_order, axis=alt.Axis(labelAngle=-25)),
        y=alt.Y("Records:Q", axis=alt.Axis(tickMinStep=1)),
        tooltip=[alt.Tooltip(f"{group}:N"), alt.Tooltip("Records:Q")],
    ).properties(height=270)


def main():
    st.title("U.S. Patent Allowances")
    st.caption("Explore Notices of Allowance using a CSV of patent application records.")
    uploaded = st.sidebar.file_uploader("Load your own allowance CSV", type=["csv"])
    source = SAMPLE_PATH if uploaded is None else uploaded
    try:
        table = load_csv(source)
    except (OSError, ValueError) as exc:
        st.error(f"Could not read the CSV. {exc}")
        return
    if table.empty:
        st.info("The CSV contains column headers but has no records.")
        return

    if uploaded is None:
        st.info("Sample data · Fictional records for the class demonstration.")
    else:
        st.caption(f"Source file · {uploaded.name}")

    earliest = date.fromisoformat(table[MAILED].min())
    latest = date.fromisoformat(table[MAILED].max())
    with st.sidebar:
        end = st.date_input("Week ending", value=latest, min_value=earliest, max_value=latest)
        statuses = st.multiselect(
            "Current application status", sorted(set(table[STATUS]) - {""}),
        )
        st.download_button(
            "Download sample CSV", SAMPLE_PATH.read_bytes(),
            file_name=SAMPLE_PATH.name, mime="text/csv",
        )

    start = end - timedelta(days=6)
    st.subheader(f"{start:%b %d, %Y} – {end:%b %d, %Y}")
    term = st.text_input("Search title, application number, applicant, assignee or CPC").strip()
    filtered = table[table[MAILED].between(start.isoformat(), end.isoformat())]
    if statuses:
        filtered = filtered[filtered[STATUS].isin(statuses)]
    if term:
        searchable = filtered[[TITLE, APPLICATION, PARTIES, CPC]]
        matches = searchable.apply(lambda column: column.str.contains(term, case=False, regex=False))
        filtered = filtered[matches.any(axis=1)]

    left, right = st.columns(2)
    left.metric("Allowance records", len(filtered))
    right.metric("Unique applications", filtered.loc[filtered[APPLICATION] != "", APPLICATION].nunique())

    group = st.selectbox(
        "Group chart by", [MAILED, STATUS, CPC],
        format_func=lambda field: "Mailing date" if field == MAILED else field,
    )
    if group == CPC:
        st.caption("Up to 12 classification entries. Multiple codes in one cell appear together.")
    st.altair_chart(allowance_chart(filtered, start, end, group), width="stretch")
    st.subheader("Allowance records")
    st.dataframe(filtered, hide_index=True, width="stretch",
                 column_config={CLAIMS: st.column_config.TextColumn(CLAIMS, width="medium")})
    if filtered.empty:
        st.info("No records match the selected week and filters.")
    st.download_button(
        "Download filtered CSV", csv_bytes(filtered),
        file_name=f"{'sample-' if uploaded is None else ''}allowances-{end}.csv",
        mime="text/csv", disabled=filtered.empty,
    )
    if uploaded is not None and not filtered.empty:
        st.subheader("USPTO documents")
        options = filtered.reset_index(drop=True)
        index = st.selectbox(
            "Select a record", options.index,
            format_func=lambda i: f"{options.at[i, APPLICATION]} · {options.at[i, TITLE]}",
        )
        links = document_links(options.loc[index])
        for label, url in links.items():
            if url:
                st.link_button(label, url)
        if not any(links.values()):
            st.caption("The selected record has no recognized U.S. document identifiers.")


if __name__ == "__main__":
    main()
