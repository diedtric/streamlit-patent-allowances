"""Read allowance records and derive links from formatted U.S. identifiers."""

import re

import pandas as pd

MAILED = "Notice of Allowance mailing date"
APPLICATION = "U.S. application number"
CLAIMS = "Allowed claims"
TITLE = "Invention title"
STATUS = "Current application status"
PARTIES = "Applicant and recorded assignee"
PUBLICATION = "U.S. publication number"
PATENT = "U.S. patent number and issue date"
FILING = "Filing date and claimed priority"
CPC = "CPC classification"
COLUMNS = [MAILED, APPLICATION, CLAIMS, TITLE, STATUS, PARTIES, PUBLICATION, PATENT, FILING, CPC]

PDF_BASE = "https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/"
CENTER_BASE = "https://patentcenter.uspto.gov/applications/"


def load_csv(source):
    table = pd.read_csv(source, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    table.columns = table.columns.str.strip().str.casefold()
    missing = [name for name in COLUMNS if name.casefold() not in table.columns]
    if missing:
        raise ValueError("Missing CSV columns — " + ", ".join(missing))
    table = table[[name.casefold() for name in COLUMNS]].copy()
    table.columns = COLUMNS
    for name in COLUMNS:
        table[name] = table[name].str.strip()
    dates = pd.to_datetime(table[MAILED], format="%Y-%m-%d", errors="coerce")
    if dates.isna().any():
        bad_rows = ", ".join(str(index + 2) for index in dates[dates.isna()].index[:5])
        raise ValueError(f"Use YYYY-MM-DD mailing dates. Check CSV row numbers {bad_rows}.")
    table[MAILED] = dates.dt.strftime("%Y-%m-%d")
    return table.sort_values(MAILED, ascending=False, kind="stable")


def csv_bytes(table):
    safe = table.map(
        lambda text: "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text
    )
    return safe.to_csv(index=False).encode("utf-8-sig")


def document_links(record):
    application = re.sub(r"[\s/,]", "", record[APPLICATION])
    publication = re.sub(r"[\s/,\-]", "", record[PUBLICATION].upper())
    patent = re.sub(r"[\s,\-]", "", record[PATENT].partition("|")[0].upper())
    pub_match = re.fullmatch(r"(?:US)?([0-9]{11})(?:A[0-9])?", publication)
    patent_match = re.fullmatch(r"(?:US)?((?:D|PP|RE)?[0-9]{5,8})(?:[BESP][0-9]?)?", patent)
    return {
        "Published application PDF": PDF_BASE + pub_match[1] if pub_match else "",
        "Issued patent PDF": PDF_BASE + patent_match[1] if patent_match else "",
        "Patent Center": CENTER_BASE + application if re.fullmatch(r"[0-9]{8}", application) else "",
    }
