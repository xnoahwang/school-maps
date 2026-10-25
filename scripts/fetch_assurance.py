"""Read the Assurance survey from each CBE School Improvement Results report.

Responsibility: find the report linked from the school's own CBE page, read
the six survey rows in the official summary table, and write
web/data/assurance.json. The table is an image, so the numbers come from OCR.
Does not score exams and does not invent a figure the table left blank.
Cached PDFs stay in data/raw/assurance/.
"""
from __future__ import annotations

import io
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from PIL import Image
from pypdf import PdfReader
from rapidocr_onnxruntime import RapidOCR

sys.path.insert(0, str(Path(__file__).resolve().parent))
from store import write_if_changed

ROOT = Path(__file__).resolve().parent.parent
DIRECTORY = ROOT / "web" / "data" / "cbe_directory.json"
OUT = ROOT / "web" / "data" / "assurance.json"
RAW = ROOT / "data" / "raw" / "assurance"
USER_AGENT = "school-maps (CBE school improvement reports)"
# The summary table's survey rows. The first matching label wins.
MEASURES = (
    ("learning_engagement", ("studentlearningengagement",)),
    ("citizenship", ("citizenship",)),
    ("education_quality", ("educationquality",)),
    ("safe_caring", ("wcrsle", "welcomingcaring")),
    ("access_supports", ("accesstosupport",)),
    ("parental_involvement", ("parentalinvolvement", "parentinvolvement")),
)
VALUE = re.compile(r"^(?:n/?a|nla|\*|\d{1,3}(?:\.\d)?)$", re.I)
# OCR tokens this close vertically are one survey row. The label and its
# percentages sit on the same band, including a label that wraps once.
ROW_Y_TOLERANCE_PX = 16


def compact(text: str) -> str:
    """Letters and digits only, so OCR spacing does not hide a measure name."""
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def cell_value(text: str) -> float | None:
    """A survey percentage, or None for n/a and a suppressed star.

    A number outside 0–100 is treated as a misread, not as a score.
    """
    token = text.strip().replace(" ", "")
    if not VALUE.match(token):
        return None
    if token.lower() in {"n/a", "na", "nla", "*"}:
        return None
    number = float(token)
    if 0 <= number <= 100:
        return number
    return None


def find_report(session: requests.Session, website: str) -> str | None:
    """Absolute URL of the School Improvement Results PDF, or None.

    Looks at the school's /school page first, then the about page and the
    home page. A host that is not a CBE school site is skipped.
    """
    origin = website if website.startswith("http") else "https://" + website
    host = (urlparse(origin).hostname or "").lower()
    if not host.endswith(".cbe.ab.ca"):
        return None
    origin = origin.split("?")[0].rstrip("/")
    for path in ("/school", "/about-us", "/"):
        try:
            response = session.get(origin + path, timeout=30)
        except requests.RequestException:
            continue
        if response.status_code != 200:
            continue
        hits = []
        for href in re.findall(r'href="([^"]+)"', response.text, flags=re.I):
            low = href.lower()
            if "improvement" in low and "result" in low and ".pdf" in low:
                hits.append(urljoin(origin + "/", href.split("?")[0]))
        if hits:
            hits.sort(key=lambda url: (0 if "results-report" in url.lower() else 1, url))
            return hits[0]
    return None


def group_tokens(tokens: list[dict]) -> list[dict]:
    """Group OCR tokens into survey rows.

    Each token needs y, x, and text. Tokens within ROW_Y_TOLERANCE_PX of the
    running row mean join that row. An empty list returns no rows. A token
    missing y raises KeyError; the OCR step is what builds these dicts.
    """
    ordered = sorted(tokens, key=lambda token: (token["y"], token["x"]))
    rows: list[dict] = []
    for token in ordered:
        if rows and abs(token["y"] - rows[-1]["y"]) <= ROW_Y_TOLERANCE_PX:
            rows[-1]["tokens"].append(token)
            rows[-1]["y"] = sum(item["y"] for item in rows[-1]["tokens"]) / len(rows[-1]["tokens"])
        else:
            rows.append({"y": token["y"], "tokens": [token]})
    return rows


def rows_from_image(engine: RapidOCR, image: Image.Image) -> list[dict]:
    """OCR one table image into rows of text with a horizontal position."""
    result, _ = engine(image)
    tokens = []
    for item in result or []:
        box, text, _score = item
        tokens.append({
            "y": sum(point[1] for point in box) / 4,
            "x": sum(point[0] for point in box) / 4,
            "text": text,
        })
    return group_tokens(tokens)


def measures_from_rows(rows: list[dict]) -> dict[str, float | None]:
    """School current-year percentage for each survey measure found in the rows.

    The leftmost value in a measure row is the school's current result.
    Later columns are the previous year, the three-year average, and Alberta.
    """
    found: dict[str, float | None] = {}
    for row in rows:
        label = compact(" ".join(token["text"] for token in row["tokens"] if token["x"] < 520))
        if any(skip in label for skip in ("pat6", "pat9", "diploma", "completion")):
            continue
        key = next((name for name, needles in MEASURES if any(needle in label for needle in needles)), None)
        if key is None or key in found:
            continue
        values = [token for token in row["tokens"] if cell_value(token["text"]) is not None or VALUE.match(token["text"].strip().replace(" ", ""))]
        values.sort(key=lambda token: token["x"])
        # A header row can contain the word without a number. Leave it for a later row.
        if not values:
            continue
        found[key] = cell_value(values[0]["text"])
    return found


TEXT_MEASURES = (
    ("learning_engagement", r"Student Learning Engagement\s+([0-9.]+|n/a|\*)"),
    ("citizenship", r"Citizenship\s+([0-9.]+|n/a|\*)"),
    ("education_quality", r"Education Quality\s+([0-9.]+|n/a|\*)"),
    ("safe_caring", r"WCRSLE\)\s+([0-9.]+|n/a|\*)"),
    ("access_supports", r"Access to Supports and Services\s+([0-9.]+|n/a|\*)"),
    ("parental_involvement", r"Parental Involvement\s+([0-9.]+|n/a|\*)"),
)


def measures_from_text(text: str) -> dict[str, float | None]:
    """Survey percentages when the summary table is real text, not an image.

    The official table is at the end, so the last match wins over a sentence
    that happens to put a number after the measure name.
    """
    found = {}
    for key, pattern in TEXT_MEASURES:
        matches = re.findall(pattern, text, flags=re.I)
        if matches:
            found[key] = cell_value(matches[-1])
    return found


def survey_from_pdf(engine: RapidOCR, data: bytes) -> tuple[dict[str, float | None], int | None]:
    """Six survey measures and the Fall year printed in one results PDF.

    The year is read from the text layer ('Fall 2025'). Some reports print the
    summary as text; others paste it as an image, which is then read with OCR.
    A PDF with no readable table returns nulls.
    """
    reader = PdfReader(io.BytesIO(data))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    year_match = re.search(r"Fall\s+(20\d{2})", text)
    year = int(year_match.group(1)) if year_match else None
    from_text = measures_from_text(text)
    if len(from_text) >= 4:
        return from_text, year
    best: dict[str, float | None] = {}
    for page in reversed(reader.pages[-2:]):
        try:
            images = list(page.images)
        except Exception:
            continue
        pictures = []
        for image in images:
            try:
                picture = Image.open(io.BytesIO(image.data))
            except Exception:
                continue
            if picture.width >= 700:
                pictures.append(picture)
        pictures.sort(key=lambda picture: picture.width, reverse=True)
        for picture in pictures[:2]:
            measures = measures_from_rows(rows_from_image(engine, picture.convert("RGB")))
            if len(measures) > len(best):
                best = measures
            if len(best) >= 4:
                return best, year
    return (best if len(best) >= len(from_text) else from_text), year


def load_one(row: dict) -> dict | None:
    """Download one school's report, using the cache when the PDF is already stored."""
    code = str(row.get("code") or "").strip()
    website = row.get("website") or ""
    if not code or not website:
        return None
    cache = RAW / f"{code}.pdf"
    url_path = RAW / f"{code}.url"
    report = url_path.read_text(encoding="utf-8").strip() if url_path.exists() else ""
    if cache.exists() and report:
        return {"code": code, "name": row.get("name") or "", "report": report, "pdf": cache.read_bytes()}
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    report = find_report(session, website) or ""
    if not report:
        return {"code": code, "name": row.get("name") or "", "report": None, "pdf": None}
    try:
        response = session.get(report, timeout=60)
        response.raise_for_status()
    except requests.RequestException:
        return {"code": code, "name": row.get("name") or "", "report": report, "pdf": None}
    RAW.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(response.content)
    url_path.write_text(report, encoding="utf-8")
    return {"code": code, "name": row.get("name") or "", "report": report, "pdf": response.content}


def main() -> int:
    directory = json.loads(DIRECTORY.read_text(encoding="utf-8"))
    schools = [row for row in directory.get("schools") or [] if row.get("code") and row.get("website")]
    loaded = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(load_one, row) for row in schools]
        for future in as_completed(futures):
            item = future.result()
            if item:
                loaded.append(item)
    engine = RapidOCR()
    records = []
    with_measure = 0
    for item in sorted(loaded, key=lambda row: row["name"]):
        measures, year = ({}, None)
        if item["pdf"]:
            try:
                measures, year = survey_from_pdf(engine, item["pdf"])
            except Exception as exc:
                print(f"unreadable {item['name']}: {exc}")
        record = {
            "code": item["code"],
            "name": item["name"],
            "year": year,
            "report": item["report"],
        }
        for key, _needles in MEASURES:
            record[key] = measures.get(key)
        got = sum(1 for key, _needles in MEASURES if record[key] is not None)
        if got:
            with_measure += 1
        if len(records) % 25 == 0:
            print(f"{len(records)} {item['name']}: {got}", flush=True)
        records.append(record)
    payload = {
        "source": "CBE School Improvement Results reports. The survey is Alberta Education's Assurance survey.",
        "note": "Except parental_involvement (parents and teachers), each percentage combines students, parents, and teachers. n/a and a suppressed group are null. Not mixed into the PAT score.",
        "schools": records,
    }
    text = json.dumps(payload, indent=1, ensure_ascii=False)
    print(write_if_changed(OUT, text + "\n"))
    print(f"schools {len(records)}; with a survey figure {with_measure}")
    return 0 if with_measure else 1


if __name__ == "__main__":
    sys.exit(main())
