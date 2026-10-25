"""Read Calgary's 2021 community-profile PDFs into a small JSON file.

The profile HTML pages only link to the PDFs. This script downloads each
community PDF, keeps the parent-facing census fields, and writes
web/data/community_profiles.json. It does not score schools, and it does not
invent a field the PDF did not print. Cached PDFs stay in data/raw/community_profiles/.
"""
import json
import re
import sys
from pathlib import Path

import requests
from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_data import normalize_name
from store import write_if_changed

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "community_profiles"
OUT = ROOT / "web" / "data" / "community_profiles.json"
COMMUNITIES = ROOT / "web" / "data" / "communities.geojson"
SOURCE = "https://www.calgary.ca/communities/profiles.html"
PDF_ROOT = (
    "https://www.calgary.ca/content/dam/www/programs-services/"
    "property-housing-and-neighbourhoods/neighbourhood-and-community-relationships/profiles/"
)
PAGE_ROOT = "https://www.calgary.ca/communities/profiles/"
# The City prints the community column first and Calgary second. These are the
# racialized groups in that table, in the PDF's own order.
RACIALIZED_GROUPS = (
    "South Asian", "Chinese", "Black", "Filipino", "Arab", "Latin American",
    "Southeast Asian", "West Asian", "Korean", "Japanese",
)
SKIP_LANGUAGES = {"english", "french", "non-official language", "population in private households"}


def profile_slug(name: str) -> str:
    """Turn a community name into the City's profile filename stem."""
    text = (name or "").lower().replace("&", " and ")
    text = re.sub(r"\bst\.\s*", "st ", text)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text


def _tidy(text: str) -> str:
    return text.replace("\u00a0", " ").replace("\ufeff", "")


def _section(text: str, start: str, end: str) -> str:
    begin = text.find(start)
    if begin < 0:
        return ""
    finish = text.find(end, begin + len(start))
    return text[begin:finish if finish > begin else None]


def _num(token: str) -> int | None:
    try:
        return int(token.replace(",", ""))
    except (TypeError, ValueError):
        return None


def _pct(token: str) -> float | None:
    try:
        value = float(token)
    except (TypeError, ValueError):
        return None
    return int(value) if value.is_integer() else value


def _first(pattern: str, text: str) -> re.Match | None:
    return re.search(pattern, text, re.S)


def parse_profile(text: str) -> dict:
    """Pull the parent-facing 2021 census fields from one profile's text.

    The community column is the first number after each label. A missing label
    stays None. A printed 0 stays 0. Returns an empty dict when the snapshot
    population cannot be read, so a bad extract is not stored as a community.
    """
    text = _tidy(text)
    snapshot = _section(text, "2021 Census of Canada Snapshot", "Contents")
    pop = _first(
        r"Population in private households in 2021:.*?([\d,]+)\s+0-14 years:\s*65\+\s*years:\s*([\d.]+)%\s*([\d.]+)%",
        snapshot,
    )
    if not pop or _num(pop.group(1)) is None:
        return {}
    shelter = _first(r"Per cent immigrants in 2021\s*([\d.]+)%\s*([\d.]+)%", snapshot)
    income = _first(r"often at home\s*\$([\d,]+)\s*([\d.]+)%", snapshot)
    housing = _section(text, "Housing Tenure", "Dwelling Condition")
    owner = _first(r"Owner households\s+([\d,]+)\s+([\d.]+)%", housing)
    renter = _first(r"Renter households\s+([\d,]+)\s+([\d.]+)%", housing)
    costs = _first(r"\$([\d,]+)\s+\$([\d,]+)\s+\$([\d,]+)\s+\$([\d,]+)\s+Owned dwellings", housing)
    minority = _section(text, "Visible Minority (Racialized Population)", "Not a visible minority")
    minority_total = _first(r"Visible minority\s+([\d,]+)\s+([\d.]+)%", minority)
    groups = []
    for name in RACIALIZED_GROUPS:
        match = _first(re.escape(name) + r"\s+([\d,]+)\s+([\d.]+)%", minority)
        if match and _pct(match.group(2)) is not None:
            groups.append({"name": name, "pct": _pct(match.group(2))})
    languages = _home_languages(_section(text, "Languages Spoken Most Often at Home", "Mother Tongue"))
    degree = _first(r"bachelor level or\s*above\s*([\d,]+)\s*([\d.]+)%", text)
    driver = _first(r"van\s+([\d,]+)\s+([\d.]+)%", _section(text, "Mode of Transportation to Work", "Commuting Duration"))
    transit = _first(r"Public transit\s+([\d,]+)\s+([\d.]+)%", text)
    return {
        "population": _num(pop.group(1)),
        "age_0_14_pct": _pct(pop.group(2)),
        "age_65_plus_pct": _pct(pop.group(3)),
        "shelter_30_pct": _pct(shelter.group(1)) if shelter else None,
        "immigrant_pct": _pct(shelter.group(2)) if shelter else None,
        "median_household_income": _num(income.group(1)) if income else None,
        "english_home_pct": _pct(income.group(2)) if income else None,
        "owner_pct": _pct(owner.group(2)) if owner else None,
        "renter_pct": _pct(renter.group(2)) if renter else None,
        "shelter_owner": _num(costs.group(1)) if costs else None,
        "shelter_renter": _num(costs.group(2)) if costs else None,
        "racialized_pct": _pct(minority_total.group(2)) if minority_total else None,
        "racialized": groups,
        "home_languages": languages,
        "bachelor_pct": _pct(degree.group(2)) if degree else None,
        "drive_pct": _pct(driver.group(2)) if driver else None,
        "transit_pct": _pct(transit.group(2)) if transit else None,
    }


def _home_languages(block: str) -> list[dict]:
    """Top non-English languages in the community column of the home-language table.

    The table's left column is this community. A line with no percent is the
    wrapped start of that left-hand name. A fragment like "Filipino)" is the
    wrapped Calgary column and is ignored.
    """
    if not block:
        return []
    lines = [" ".join(raw.split()) for raw in block.splitlines() if raw.strip()]
    start = 0
    for index, line in enumerate(lines):
        if "Non-official language" in line and "%" in line:
            start = index + 1
            break
    found = []
    pending = ""
    for line in lines[start:]:
        if "Multiple languages" in line:
            break
        if pending:
            line = f"{pending} {line}"
            pending = ""
        if "%" not in line:
            pending = line
            continue
        match = re.match(r"(.+?)\s+[\d,]+\s+([\d.]+)%", line)
        if not match:
            continue
        name = match.group(1).strip()
        if name.endswith(")") and "(" not in name:
            continue
        if name.lower() in SKIP_LANGUAGES or len(name) > 40:
            continue
        pct = _pct(match.group(2))
        if pct is None:
            continue
        found.append({"name": name, "pct": pct})
    return found[:5]


def pdf_text(path: Path) -> str:
    """Extract text from every page, in order. A page that yields nothing is skipped."""
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def community_names() -> list[str]:
    """Names from the built community file. Missing file returns an empty list."""
    if not COMMUNITIES.exists():
        return []
    data = json.loads(COMMUNITIES.read_text(encoding="utf-8"))
    names = []
    seen = set()
    for feature in data.get("features") or []:
        name = (feature.get("properties") or {}).get("name")
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def _pdf_link_from_page(html: str) -> str | None:
    for href in re.findall(r'href="([^"]+\.pdf)"', html, re.I):
        if "population-projection" in href:
            continue
        if "/profiles/" in href:
            return href if href.startswith("http") else "https://www.calgary.ca" + href
    return None


def download_pdf(session: requests.Session, name: str) -> tuple[Path, str] | None:
    """Save one profile PDF. A cached file is reused. A 404 tries the HTML page once.

    Returns the cache path and the URL that served it, or None when neither
    URL is a PDF.
    """
    slug = profile_slug(name)
    dest = RAW / f"{slug}.pdf"
    url_note = dest.with_suffix(".url")
    if dest.exists() and dest.stat().st_size > 1000:
        url = url_note.read_text(encoding="utf-8").strip() if url_note.exists() else PDF_ROOT + slug + ".pdf"
        return dest, url
    RAW.mkdir(parents=True, exist_ok=True)
    url = PDF_ROOT + slug + ".pdf"
    response = session.get(url, timeout=60)
    if response.status_code == 404:
        page = session.get(PAGE_ROOT + slug + ".html", timeout=60)
        if page.status_code != 200:
            print(f"missing {name}", file=sys.stderr)
            return None
        found = _pdf_link_from_page(page.text)
        if not found:
            print(f"missing {name}", file=sys.stderr)
            return None
        url = found
        response = session.get(url, timeout=60)
    if response.status_code != 200 or not response.content.startswith(b"%PDF"):
        print(f"missing {name}", file=sys.stderr)
        return None
    dest.write_bytes(response.content)
    url_note.write_text(url, encoding="utf-8")
    return dest, url


def main() -> None:
    """Download every community profile and write the JSON. A failed PDF is skipped."""
    names = community_names()
    if not names:
        sys.exit("FATAL communities.geojson has no names")
    session = requests.Session()
    session.headers["User-Agent"] = "school-maps community-profile fetch"
    communities = {}
    failed = []
    for name in names:
        downloaded = download_pdf(session, name)
        if downloaded is None:
            failed.append(name)
            continue
        path, url = downloaded
        try:
            parsed = parse_profile(pdf_text(path))
        except Exception as exc:
            print(f"WARN {name}: {exc}", file=sys.stderr)
            failed.append(name)
            continue
        if not parsed:
            print(f"WARN {name}: snapshot not read", file=sys.stderr)
            failed.append(name)
            continue
        parsed["name"] = name
        parsed["pdf"] = url
        communities[normalize_name(name)] = parsed
        print(f"ok {name}")
    payload = {
        "source": SOURCE,
        "census_year": 2021,
        "income_year": 2020,
        "communities": communities,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=1)
    if not communities:
        print("skipped write: no profiles parsed", file=sys.stderr)
        sys.exit(1)
    status = write_if_changed(OUT, text + "\n")
    print(f"{status} {OUT.name}: {len(communities)} profiles, {len(failed)} missing")


if __name__ == "__main__":
    main()
