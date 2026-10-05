"""Download Alberta's public school directory and keep phone and website.

Responsibility: write web/data/ab_contacts.json from the open school file.
The page uses it only when a school has no phone or website yet, so the CBE
directory still wins for CBE schools. Does not score exams or invent a site
when the file leaves the school website blank.
"""
import json
import math
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_data import normalize_name

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "authority_and_school.xlsx"
OUT = ROOT / "web" / "data" / "ab_contacts.json"
FILE_URL = "https://education.alberta.ca/media/1626669/authority_and_school.xlsx"
SOURCE = "https://open.alberta.ca/opendata/alberta-education-schools-and-authorities"


def clean_text(value) -> str | None:
    """Return a stripped cell, or None for blanks and pandas NaN."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none"}:
        return None
    return text


def clean_website(value) -> str | None:
    """Return a usable URL, or None when the school website cell is blank.

    A value with no scheme gets https://. The authority website is never
    substituted for a blank school website.
    """
    text = clean_text(value)
    if text is None:
        return None
    if not text.startswith(("http://", "https://")):
        text = "https://" + text
    return text


def school_code(value) -> str | None:
    """Return the Alberta school code with leading zeros removed."""
    text = clean_text(value)
    if text is None:
        return None
    if text.endswith(".0"):
        text = text[:-2]
    stripped = text.lstrip("0")
    return stripped or "0"


def download() -> None:
    """Save the public workbook under data/raw. A failed download reuses the cache."""
    RAW.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(FILE_URL, headers={"User-Agent": "school-maps"})
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            RAW.write_bytes(response.read())
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        if RAW.exists():
            print(f"WARN using cached school directory: {exc}", file=sys.stderr)
            return
        sys.exit(f"FATAL school directory: {exc}")


def rows_from_sheet(frame, names: set[str]) -> tuple[list[dict], str | None]:
    """Keep Calgary rows, plus any row whose name is one of ours.

    names is the set of normalize_name keys from schools.json. A blank phone
    and a blank website are both kept as null. Returns the rows and the
    extract date from the sheet.
    """
    rows = []
    as_of = None
    for record in frame.to_dict("records"):
        name = clean_text(record.get("School Name"))
        if name is None:
            continue
        city = (clean_text(record.get("School City")) or "").lower()
        key = normalize_name(name)
        if city != "calgary" and key not in names:
            continue
        phone = clean_text(record.get("School Phone"))
        website = clean_website(record.get("School Website"))
        if phone is None and website is None:
            continue
        dated = clean_text(record.get("Extract Date"))
        if dated and as_of is None:
            as_of = dated[:10]
        rows.append({
            "code": school_code(record.get("School Code")),
            "name": name,
            "key": key,
            "phone": phone,
            "website": website,
        })
    return rows, as_of


def main() -> None:
    import pandas as pd

    download()
    frame = pd.read_excel(RAW, sheet_name="School Information Report", header=2)
    schools_path = ROOT / "web" / "data" / "schools.json"
    names = set()
    if schools_path.exists():
        schools = json.loads(schools_path.read_text(encoding="utf-8"))
        names = {normalize_name(school.get("name") or "") for school in schools}
        names.discard("")
    rows, as_of = rows_from_sheet(frame, names)
    payload = {
        "source": SOURCE,
        "file": FILE_URL,
        "as_of": as_of,
        "schools": rows,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    with_site = sum(1 for row in rows if row["website"])
    print(f"ab contacts: {len(rows)} schools, {with_site} with a website, as of {as_of}")


if __name__ == "__main__":
    main()
