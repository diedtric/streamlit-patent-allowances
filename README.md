# U.S. Patent Allowances

This Streamlit app reads `patent_allowances.csv`, a fictional dataset created
for a classroom demonstration. The app requires no USPTO API key. The default
view shows the seven days ending on the most recent mailing date in the file.

## Run locally

```sh
python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py
```

## Update the PatentRetrieval deployment

Upload `app.py`, `patent_data.py`, `patent_allowances.csv`, and
`requirements.txt` into the root of the GitHub repository. Commit them to the
branch connected to Streamlit Community Cloud. The entry point remains `app.py`.
If the app is already deployed, Streamlit redeploys when it detects the commit.
The theme in `.streamlit/config.toml` is optional.

## Use your own records

Upload a CSV in the sidebar using the same ten headers as the sample file.
Use YYYY-MM-DD for the Notice of Allowance mailing date. The allowed claims
field stores claim numbers or ranges as supplied in the CSV. Keep publication
and application identifiers as text. For PDF links, enter a U.S. publication
number such as `US 2025/0123456 A1`, and use the format
`US 12,345,678 B2 | 2026-10-13` in the patent number and issue date column.
Leave unavailable values blank.

The two download buttons export either the complete fictional sample or the
currently filtered records. Sample identifiers are used for demonstration only.
The app offers USPTO document links from identifiers in uploaded records.
