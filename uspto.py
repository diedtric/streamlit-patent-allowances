"""USPTO requests and conversion of file wrappers into allowance rows."""

from datetime import date, timedelta
import re

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API = "https://api.uspto.gov/api/v1/patent/applications"
PDF = "https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/"
MAIL_CODE = "MN/=."
MAIL_DESCRIPTION = "mail notice of allowance"
COLUMNS = [
    "Mail date", "Application number", "Title", "Applicant", "Type",
    "Current status", "Filing date", "Publication number", "Patent number",
    "Grant date", "Published application PDF", "Issued patent PDF", "Patent Center",
]


class USPTOError(Exception):
    pass


def days_between(start, end):
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def document_number(value, pattern):
    compact = re.sub(r"[\s,/-]", "", str(value or "").upper())
    match = re.fullmatch(rf"(?:US)?({pattern})(?:[A-Z]\d?)?", compact)
    return match[1] if match else ""


def allowance_rows(records, start, end):
    rows = {}
    for record in records:
        number = str(record.get("applicationNumberText") or "")
        if not re.fullmatch(r"[0-9]{8}", number):
            continue
        meta = record.get("applicationMetaData") or {}
        publication = document_number(meta.get("earliestPublicationNumber"), r"[0-9]{11}")
        patent = document_number(meta.get("patentNumber"), r"(?:D|PP|RE)?[0-9]+")
        grant_date = str(meta.get("grantDate") or "")[:10]
        for event in record.get("eventDataBag") or []:
            description = str(event.get("eventDescriptionText") or "").strip().lower()
            if event.get("eventCode") != MAIL_CODE and description != MAIL_DESCRIPTION:
                continue
            try:
                mailed = date.fromisoformat(str(event.get("eventDate"))[:10])
            except ValueError:
                continue
            if start <= mailed <= end:
                rows[(mailed, number)] = {
                    "Mail date": mailed.isoformat(),
                    "Application number": number,
                    "Title": meta.get("inventionTitle") or "",
                    "Applicant": meta.get("firstApplicantName") or "",
                    "Type": meta.get("applicationTypeLabelName") or meta.get("applicationTypeCategory") or "Unknown",
                    "Current status": meta.get("applicationStatusDescriptionText") or "",
                    "Filing date": meta.get("filingDate") or "",
                    "Publication number": publication,
                    "Patent number": patent if grant_date else "",
                    "Grant date": grant_date,
                    "Published application PDF": PDF + publication if publication else "",
                    "Issued patent PDF": PDF + patent if patent and grant_date else "",
                    "Patent Center": f"https://patentcenter.uspto.gov/applications/{number}",
                }
    return [rows[key] for key in sorted(rows, reverse=True)]


def search_day(session, day):
    # Match code and date server-side, then verify they occur on the same event.
    query = (
        'eventDataBag.eventCode:"MN\\/=." '
        f"AND eventDataBag.eventDate:[{day} TO {day}]"
    )
    offset = 0
    while True:
        try:
            response = session.get(
                f"{API}/search",
                params={"q": query, "offset": offset, "limit": 100,
                        "sort": "applicationNumberText asc"},
                timeout=(8, 45),
            )
        except requests.RequestException as exc:
            raise USPTOError("Could not reach the USPTO. Try again shortly.") from exc
        if response.status_code in (401, 403):
            raise USPTOError("The USPTO rejected the API key or access to the endpoint.")
        if response.status_code == 429:
            raise USPTOError("The USPTO rate limit was reached. Try again shortly.")
        if response.status_code == 404 and offset == 0:
            try:
                message = str(response.json().get("errorDetails", "")).lower()
            except (ValueError, AttributeError):
                message = ""
            if "no matching records" in message:
                return
        if not response.ok:
            raise USPTOError(f"USPTO search for {day} returned HTTP {response.status_code}.")
        try:
            payload = response.json()
            total = int(payload["count"])
            page = payload.get("patentFileWrapperDataBag") or []
            if not isinstance(page, list):
                raise ValueError
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise USPTOError("The USPTO returned an unexpected search response.") from exc
        if not page and offset < total:
            raise USPTOError(f"The USPTO returned an incomplete page for {day}.")
        if page and not any("eventDataBag" in record for record in page):
            raise USPTOError("USPTO search omitted transaction histories, so mailing dates could not be verified.")
        yield from page
        offset += len(page)
        if offset >= total:
            return


def fetch_allowances(api_key, start, end):
    results = []
    with requests.Session() as session:
        session.headers["X-API-KEY"] = api_key
        session.mount("https://", HTTPAdapter(max_retries=Retry(
            total=2, status_forcelist=(500, 502, 503, 504), backoff_factor=1,
            raise_on_status=False,
        )))
        for day in days_between(start, end):
            results.extend(allowance_rows(search_day(session, day), day, day))
    return sorted(results, key=lambda row: (row["Mail date"], row["Application number"]), reverse=True)


def demo_allowances(start, end):
    records = []
    for i, day in enumerate(days_between(start, end)):
        for j in range(i % 3 + 1):
            records.append({
                "applicationNumberText": str(99000000 + i * 3 + j),
                "applicationMetaData": {
                    "inventionTitle": ["Modular irrigation controller", "Optical alignment fixture",
                                       "Adjustable mounting bracket"][j],
                    "firstApplicantName": ["Example Water Systems", "Example Optics", "Example Design"][j],
                    "applicationTypeLabelName": "Design" if j == 2 else "Utility",
                    "applicationStatusDescriptionText": "Notice of Allowance Mailed",
                },
                "eventDataBag": [{"eventCode": MAIL_CODE, "eventDate": day.isoformat()}],
            })
    rows = allowance_rows(records, start, end)
    for row in rows:
        row["Patent Center"] = ""
    return rows
