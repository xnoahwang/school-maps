"""Download the public CBE school directory and attach it to our schools.

Responsibility: pull the same fragment API the directory page uses
(school profiles and programs), keep the fields that page shows, and record
which City school each directory row is. Does not score exams and does not
fetch attendance zones.

The City school file lags the directory, so rows that do not match a City
school are still written. The page adds those rows itself.
"""
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_data import normalize_name
from store import write_if_changed

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "data" / "cbe_directory.json"
RAW = ROOT / "data" / "raw" / "cbe_directory"
API = "https://www.cbe.ab.ca/sys/api/query?structureKeys={key}&pageSize=300&ignoreCurrentSite=true"
SOURCE = "https://www.cbe.ab.ca/school-directory"

# Directory display name -> the name in the City school file, after normalize_name.
ALIASES = {
    normalize_name("Alexander Ferguson School"): normalize_name("Alex Ferguson School"),
    normalize_name("Arbour Lake School"): normalize_name("Arbour Lake Middle School"),
    normalize_name("Home Education"): normalize_name("Calgary Home Education"),
    normalize_name("CBE Home Education"): normalize_name("Calgary Home Education"),
}
HIDDEN_EVERYWHERE = "hidden-everywhere"
HIDDEN_IN_SEARCH = "hidden-in-search-only"


def fetch_rows(structure_key: str) -> list:
    """GET one CBE fragment collection. Raises URLError or ValueError on failure."""
    url = API.format(key=structure_key)
    request = urllib.request.Request(url, headers={"User-Agent": "school-maps"})
    with urllib.request.urlopen(request, timeout=90) as response:
        payload = json.load(response)
    rows = payload.get("Rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{structure_key} returned no rows")
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / f"{structure_key}.json").write_text(json.dumps(payload), encoding="utf-8")
    return rows


def grade_num(value) -> int | None:
    """Map a CBE grade token to a number. Kindergarten is 0. Blank stays None."""
    text = str(value or "").strip().lower()
    if text in ("", "none"):
        return None
    if text in ("k", "kindergarten", "0"):
        return 0
    try:
        return int(text)
    except ValueError:
        return None


def grade_label(number: int) -> str:
    """K for kindergarten, otherwise the grade number."""
    return "K" if number == 0 else str(number)


def grade_range(low: int | None, high: int | None) -> str:
    """'K-6', '4', or '' when both ends are missing."""
    if low is None and high is None:
        return ""
    if low is None:
        return grade_label(high)
    if high is None:
        return grade_label(low)
    return grade_label(low) if low == high else f"{grade_label(low)}-{grade_label(high)}"


def program_index(rows: list) -> dict:
    """Map fragment id -> {name, hidden}. Rows without a name are skipped."""
    index = {}
    for row in rows:
        programs = (row.get("data") or {}).get("programs") or {}
        name = (programs.get("name") or "").strip()
        if not name or not row.get("id"):
            continue
        index[row["id"]] = {"name": name, "hidden": str(programs.get("hidden") or "").strip().lower()}
    return index


def span_rank(high: int | None) -> str | None:
    """PAT list code for a directory-only school, or None.

    Grade 9 and above, but not high school, is `pat9`. Anything else with a
    top grade is `pat6`, including a school that stops at grade 4 or grade 8.
    Grade 10 or higher returns None. The high-school list uses
    `diploma_latest`, not this field.
    """
    if high is None or high >= 10:
        return None
    if high >= 9:
        return "pat9"
    return "pat6"


def directory_school(row: dict, programs: dict) -> dict | None:
    """One directory row, or None when CBE hides it or it has no name."""
    data = row.get("data") or {}
    profile = data.get("profile") or {}
    if str(profile.get("hidden") or "").strip() == "1":
        return None
    name = (profile.get("schooldisplayname") or profile.get("schoolname") or "").strip()
    if not name:
        return None
    listed = []
    for entry in data.get("programs") or []:
        fragment = str(entry.get("programFragment") or "").replace("fragment://", "")
        info = programs.get(fragment)
        if not info or info["hidden"] == HIDDEN_EVERYWHERE:
            continue
        low, high = grade_num(entry.get("programLowGrade")), grade_num(entry.get("programHighGrade"))
        label_range = grade_range(low, high)
        listed.append({
            "name": info["name"],
            "low": low,
            "high": high,
            "label": f"{info['name']} ({label_range})" if label_range else info["name"],
            "searchable": info["hidden"] != HIDDEN_IN_SEARCH,
        })
    profile_low, profile_high = grade_num(profile.get("lowgrade")), grade_num(profile.get("highgrade"))
    numbers = [n for n in (profile_low, profile_high) if n is not None]
    for program in listed:
        numbers.extend(n for n in (program["low"], program["high"]) if n is not None)
    point = data.get("latlng") or {}
    return {
        "name": name,
        "code": str(profile.get("schoolcode") or "").strip() or None,
        "phone": (profile.get("phone") or "").strip() or None,
        "website": (profile.get("website") or "").strip() or None,
        "address": (profile.get("address") or "").strip() or None,
        "grades": grade_range(profile_low, profile_high),
        "grade_min": min(numbers) if numbers else None,
        "grade_max": max(numbers) if numbers else None,
        "programs": [{"name": p["name"], "low": p["low"], "high": p["high"], "label": p["label"]} for p in listed],
        "program_names": [p["name"] for p in listed],
        "lat": point.get("lat"),
        "lon": point.get("lng"),
        "rank_exam": span_rank(profile_high if profile_high is not None else (max(numbers) if numbers else None)),
        "school_id": None,
        "_searchable": [p["name"] for p in listed if p["searchable"]],
    }


def attach_city_ids(schools: list[dict], city: list[dict]) -> None:
    """Set school_id when one City CBE row has this directory name. Writes in place."""
    by_name: dict[str, list[int]] = {}
    for school in city:
        board = school.get("board") or ""
        if "calgary school division" not in board.lower():
            continue
        by_name.setdefault(normalize_name(school["name"]), []).append(school["id"])
    used = set()
    for row in schools:
        key = normalize_name(row["name"])
        ids = by_name.get(key) or by_name.get(ALIASES.get(key, ""))
        # Several City rows can share one name (a duplicate record). Attach once.
        if not ids or ids[0] in used:
            continue
        row["school_id"] = ids[0]
        used.add(ids[0])


def main() -> int:
    """Write web/data/cbe_directory.json. Exit 1 when the API is short or Regular is missing."""
    profiles = fetch_rows("school_profile_fragment")
    programs = program_index(fetch_rows("program_fragment"))
    if "Regular" not in {item["name"] for item in programs.values()}:
        print("FAIL program list has no Regular", file=sys.stderr)
        return 1
    schools = [row for row in (directory_school(raw, programs) for raw in profiles) if row]
    if len(schools) < 200:
        print(f"FAIL only {len(schools)} directory schools", file=sys.stderr)
        return 1
    city = json.loads((ROOT / "web" / "data" / "schools.json").read_text(encoding="utf-8"))
    attach_city_ids(schools, city)
    searchable = sorted({name for row in schools for name in row.pop("_searchable")})
    schools.sort(key=lambda row: row["name"])
    payload = {
        "source": SOURCE,
        "schools_api": API.format(key="school_profile_fragment"),
        "programs": searchable,
        "schools": schools,
    }
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    write_if_changed(OUT, text)
    matched = sum(1 for row in schools if row["school_id"] is not None)
    print(f"directory schools {len(schools)}, matched {matched}, new {len(schools) - matched}, programs {len(searchable)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
