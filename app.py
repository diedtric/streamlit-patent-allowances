"""Streamlit dashboard for allowance records loaded from a CSV."""

from datetime import date, timedelta
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from patent_data import (
    APPLICATION, CLAIMS, CPC, MAILED, NOT_MAILED, PARTIES, STATUS, TITLE,
    csv_bytes, document_links, load_csv,
)

SAMPLE_PATH = Path(__file__).with_name("patent_allowances.csv")

st.set_page_config(page_title="U.S. Patent Allowances", page_icon="📄", layout="wide")


def allowance_chart(table, start, end, group):
    if group == MAILED:
        dates = pd.date_range(start, end).strftime("%Y-%m-%d").tolist()
        counts = table[group].value_counts().reindex(dates, fill_value=0)
        sort_order = dates
    elif group == "Applicant":
        applicants = table[PARTIES].str.split("|", n=1, regex=False).str[0].str.strip()
        counts = applicants.replace("", "Unspecified").value_counts().head(12)
        sort_order = "-y"
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

    allowances = table[table[MAILED] != NOT_MAILED]
    earliest = date.fromisoformat(allowances[MAILED].min()) if not allowances.empty else date.today()
    latest = date.fromisoformat(allowances[MAILED].max()) if not allowances.empty else earliest
    with st.sidebar:
        end = st.date_input("Week ending", value=latest, min_value=earliest, max_value=latest,
                            disabled=allowances.empty)
        statuses = st.multiselect(
            "Current application status", sorted(set(table[STATUS]) - {""}),
        )
        st.download_button(
            "Download sample CSV", SAMPLE_PATH.read_bytes(),
            file_name=SAMPLE_PATH.name, mime="text/csv",
        )

    start = end - timedelta(days=6)
    term = st.text_input("Search title, application number, applicant, assignee or CPC").strip()
    if statuses:
        table = table[table[STATUS].isin(statuses)]
    if term:
        searchable = table[[TITLE, APPLICATION, PARTIES, CPC]]
        matches = searchable.apply(lambda column: column.str.contains(term, case=False, regex=False))
        table = table[matches.any(axis=1)]
    pending = table[table[MAILED] == NOT_MAILED]
    filtered = table[table[MAILED].between(start.isoformat(), end.isoformat())]
    st.subheader(f"Allowances · {start:%b %d, %Y} – {end:%b %d, %Y}")

    left, right = st.columns(2)
    left.metric("Allowance records", len(filtered))
    right.metric("Unique applications", filtered.loc[filtered[APPLICATION] != "", APPLICATION].nunique())

    group = st.selectbox(
        "Group chart by", [MAILED, "Applicant", STATUS, CPC],
        format_func=lambda field: "Mailing date" if field == MAILED else field,
    )
    if group == "Applicant":
        st.caption("Up to 12 applicants by allowance count.")
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
    st.subheader("Pending applications")
    st.caption("Applications awaiting a Notice of Allowance across all filing dates.")
    if pending.empty:
        st.info("No pending applications match the current filters.")
    else:
        st.dataframe(pending, hide_index=True, width="stretch")
        st.download_button(
            "Download pending CSV", csv_bytes(pending),
            file_name="pending_applications.csv", mime="text/csv",
        )

    document_rows = pd.concat([filtered, pending])
    if uploaded is not None and not document_rows.empty:
        st.subheader("USPTO documents")
        options = document_rows.reset_index(drop=True)
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
