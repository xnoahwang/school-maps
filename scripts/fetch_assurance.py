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

from typing import TYPE_CHECKING

import requests
from PIL import Image
from pypdf import PdfReader

if TYPE_CHECKING:
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
BLANK = re.compile(r"^(?:n/?a|nla|\*)$", re.I)
# Spellings RapidOCR uses for the six measure names. The folded form is what
# the needles match. A garbled digit is not repaired here.
OCR_FOLDS = (
    ("educaltion", "education"),
    ("leaming", "learning"),
    ("enqagement", "engagement"),
    ("cifizenship", "citizenship"),
    ("ciizenship", "citizenship"),
    ("arcess", "access"),
    ("lnvolvement", "involvement"),
)
# OCR tokens this close vertically are one survey row. The label and its
# percentages sit on the same band, including a label that wraps once.
ROW_Y_TOLERANCE_PX = 16
_UNREAD = object()


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
    if BLANK.match(token):
        return None
    number = float(token)
    if 0 <= number <= 100:
        return number
    return None


def published_blank(text: str) -> bool:
    """True when the cell is n/a or a suppressed star, which stays null."""
    return bool(BLANK.match(text.strip().replace(" ", "")))


def garbled_number(text: str) -> bool:
    """True when OCR left a broken digit, such as 6'69, in a number cell.

    A clean percentage and a published blank are not garbled. Letters that
    are not part of a number are left for the label matcher.
    """
    token = text.strip().replace(" ", "")
    if not token or published_blank(text) or cell_value(text) is not None:
        return False
    return bool(re.fullmatch(r"[0-9'’`.,:/\\|Oo]{2,8}", token)) and any(ch.isdigit() for ch in token)


def fold_ocr(text: str) -> str:
    """Compact a label and repair the spellings that hide a measure name."""
    folded = compact(text)
    for bad, good in OCR_FOLDS:
        folded = folded.replace(bad, good)
    return folded


def is_results_report(href: str, text: str = "") -> bool:
    """True when a link is a School Improvement Results PDF.

    SIRR is the short name some school sites put in the file name and the
    link text. Anything that is not a PDF is ignored.
    """
    if ".pdf" not in href.lower().split("?")[0]:
        return False
    blob = f"{href} {text}".lower()
    if re.search(r"(?<![a-z])sirr(?![a-z])", blob):
        return True
    return "improvement" in blob and "result" in blob


def results_report_urls(html: str, origin: str) -> list[str]:
    """Results-report PDF URLs on one school page, best name first.

    An empty page returns no URLs. The origin is the school site used to
    resolve a relative href.
    """
    pattern = re.compile(r"<a\b[^>]*?\bhref=(['\"])([^'\"]+)\1[^>]*>(.*?)</a>", re.I | re.S)
    pairs = [(match.group(2), re.sub(r"<[^>]+>", " ", match.group(3))) for match in pattern.finditer(html)]
    if not pairs:
        pairs = [(href, "") for href in re.findall(r"href=[\"']([^\"']+)[\"']", html, flags=re.I)]
    found = []
    seen = set()
    for href, text in pairs:
        if not is_results_report(href, text):
            continue
        url = urljoin(origin + "/", href.split("?")[0])
        if url in seen:
            continue
        seen.add(url)
        found.append(url)
    found.sort(key=lambda url: (0 if "result" in url.lower() and "report" in url.lower() else 1, url))
    return found


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
        hits = results_report_urls(response.text, origin)
        if hits:
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
    return group_tokens(tokens_from_ocr(result))


def tokens_from_ocr(result) -> list[dict]:
    """Turn one RapidOCR result into tokens that keep their boxes.

    A missing result is no tokens. Each item is a box, the text, and a score.
    """
    tokens = []
    for item in result or []:
        box, text, _score = item
        xs = [point[0] for point in box]
        ys = [point[1] for point in box]
        tokens.append({
            "y": sum(ys) / 4,
            "x": sum(xs) / 4,
            "text": text,
            "box": (min(xs), min(ys), max(xs), max(ys)),
        })
    return tokens


def leftmost_measure(tokens: list[dict]) -> str | None:
    """The survey measure whose name starts furthest left, or None.

    PAT, diploma, and completion rows are not survey measures. When two
    names land on one band, the left one owns that band's first number.
    """
    ordered = sorted(tokens, key=lambda token: token["x"])
    blob = "".join(fold_ocr(token["text"]) for token in ordered if token_kind(token["text"]) == "text")
    if any(skip in blob for skip in ("pat6", "pat9", "diploma", "completion")):
        return None
    hits = []
    for name, needles in MEASURES:
        positions = [blob.find(needle) for needle in needles if needle in blob]
        if positions:
            hits.append((min(positions), name))
    if not hits:
        return None
    hits.sort()
    return hits[0][1]


def token_kind(text: str) -> str:
    """number, blank, garble, or text."""
    if cell_value(text) is not None:
        return "number"
    if published_blank(text):
        return "blank"
    if garbled_number(text):
        return "garble"
    return "text"


def parse_measure_rows(rows: list[dict]) -> tuple[dict[str, float | None], list[dict]]:
    """Pair survey rows with the school's current-year percentage.

    Returns the resolved measures and the cells whose current-result token
    was garbled. Those cells still need a second read. The previous-year
    number is not used in their place. An empty row list returns no measures.
    """
    found: dict[str, float | None] = {}
    pending: list[dict] = []
    claimed = set()
    for row in rows:
        tokens = row.get("tokens") or []
        key = leftmost_measure(tokens)
        if key is None or key in claimed:
            continue
        candidates = [token for token in tokens if token_kind(token["text"]) != "text"]
        candidates.sort(key=lambda token: token["x"])
        if not candidates:
            continue
        claimed.add(key)
        first = candidates[0]
        kind = token_kind(first["text"])
        if kind == "number":
            found[key] = cell_value(first["text"])
        elif kind == "blank":
            found[key] = None
        else:
            pending.append({"key": key, "box": first.get("box")})
    return found, pending


def reread_cell(engine: RapidOCR, image: Image.Image, box: tuple | None):
    """Read one number cell again, then once with a wider crop.

    Returns the percentage, None for n/a or a star, or _UNREAD when neither
    crop is a clean cell. A missing box is unread.
    """
    if not box:
        return _UNREAD
    width, height = image.size
    left, top, right, bottom = box
    for pad in (8, 22):
        crop_box = (
            max(0, int(left) - pad),
            max(0, int(top) - pad),
            min(width, int(right) + pad),
            min(height, int(bottom) + pad),
        )
        if crop_box[2] <= crop_box[0] or crop_box[3] <= crop_box[1]:
            continue
        crop = image.crop(crop_box)
        if crop.width < 60:
            crop = crop.resize((crop.width * 3, crop.height * 3), Image.Resampling.LANCZOS)
        try:
            result, _score = engine(crop.convert("RGB"))
        except Exception:
            continue
        verdict = verdict_from_ocr(result)
        if verdict is not _UNREAD:
            return verdict
    return _UNREAD


def verdict_from_ocr(result):
    """A percentage or a published blank from one crop, else unread."""
    if not result:
        return _UNREAD
    saw_blank = False
    for item in result:
        text = item[1]
        if cell_value(text) is not None:
            return cell_value(text)
        if published_blank(text):
            saw_blank = True
    joined = " ".join(item[1] for item in result)
    if cell_value(joined) is not None:
        return cell_value(joined)
    if saw_blank or published_blank(joined):
        return None
    return _UNREAD


def measures_from_picture(engine: RapidOCR, image: Image.Image) -> dict[str, float | None]:
    """Survey measures in one summary image, re-reading a broken number cell."""
    picture = image.convert("RGB")
    found, pending = parse_measure_rows(rows_from_image(engine, picture))
    for item in pending:
        if item["key"] in found:
            continue
        verdict = reread_cell(engine, picture, item.get("box"))
        if verdict is _UNREAD:
            continue
        found[item["key"]] = verdict
    return found


TEXT_MEASURES = (
    ("learning_engagement", r"Student Learning Engagement\s+([0-9.]+|n/a|\*)"),
    ("citizenship", r"Citizenship\s+([0-9.]+|n/a|\*)"),
    ("education_quality", r"Education Quality\s+([0-9.]+|n/a|\*)"),
    ("safe_caring", r"(?:WCRSLE\)|Safe Learning Environments)\s+([0-9.]+|n/a|\*)"),
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
    found = dict(from_text)
    # A text read can miss one row. The summary image is not always on the
    # last page, so keep looking until each measure has been read once.
    if all(key in found for key, _needles in MEASURES):
        return found, year
    for page in reversed(reader.pages):
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
            for key, value in measures_from_picture(engine, picture).items():
                if key not in found:
                    found[key] = value
            if all(key in found for key, _needles in MEASURES):
                return found, year
    return found, year


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
    # Imported here so name-folding and row-grouping tests do not load OCR.
    from rapidocr_onnxruntime import RapidOCR
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
