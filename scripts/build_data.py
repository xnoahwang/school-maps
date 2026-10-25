"""Build the front-end data for the Calgary school ranking page.

Responsibility: download public sources into data/raw/build/ (cached; delete a
file to refetch), join them, and write compact JSON/GeoJSON into web/data/.
Community features keep the boundary, the 2026 assessed value, and the census
shares the zone panel shows. It does NOT serve or render anything.

Run:  .venv/bin/python scripts/build_data.py [--refresh]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import pandas as pd
import requests
from shapely.geometry import Point, shape
from shapely.prepared import prep

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "build"
OUT = ROOT / "web" / "data"

SOCRATA = "https://data.calgary.ca/resource"
SOURCES = {
    # ab7m-fwn6 is a map *view* whose API returns empty features; surr-xmvs is
    # the backing dataset (same name/update time) so we read that instead.
    "communities": f"{SOCRATA}/surr-xmvs.geojson?$limit=5000",
    "schools": f"{SOCRATA}/fd9t-tdn2.json?$limit=5000",
    "pat": "https://www.alberta.ca/system/files/custom_downloaded_images/ed-pat-multiyear-sch-list.xlsx",
    # The Open Data catalogue copy of this report stopped at 2015/2016.
    "diploma": "https://www.alberta.ca/system/files/custom_downloaded_images/diploma-multiyear-sch-list-annual.xlsx",
    # p84b-7zbi (Assessments by Community) only holds 2016-2017, so we take the
    # current parcel roll and compute medians ourselves.
    "parcels": (f"{SOCRATA}/4bsw-nn7w.csv?$select=comm_code,comm_name,assessed_value"
                "&$where=assessment_class='RE' AND property_type='LI'&$limit=2000000"),
    "census_age": (f"{SOCRATA}/f9wk-wej9.json?$select=community_code,pop_age_0_to_14,"
                   "pop_age_0_to_14_percent,total_pop_household&$limit=5000"),
    "census_families": (f"{SOCRATA}/msjx-5ygv.json?$select=community_code,total_census_families,"
                        "married_with_children,commonlaw_with_children,one_parent_families&$limit=5000"),
    "enrolment": f"{SOCRATA}/9qye-mibh.json?$limit=20000",
}
RAW_FILES = {
    "communities": "communities.geojson", "schools": "schools.json", "pat": "pat.xlsx",
    "diploma": "diploma.xlsx",
    "parcels": "parcels_res.csv", "census_age": "census_age.json",
    "census_families": "census_families.json", "enrolment": "enrolment.json",
}
# Socrata view ids, used only to read rowsUpdatedAt. Not all of these are downloaded.
SOCRATA_IDS = {
    "communities": "surr-xmvs", "schools": "fd9t-tdn2", "parcels": "4bsw-nn7w",
    "census_age": "f9wk-wej9",
    "census_families": "msjx-5ygv", "enrolment": "9qye-mibh",
}
LICENCES = {
    "pat": "https://open.alberta.ca/licence",
    "diploma": "https://open.alberta.ca/licence",
}
OGL_CALGARY = "https://data.calgary.ca/d/Open-Data-Terms/u45n-7awa"
REQUIRED = {"communities", "schools", "pat", "diploma"}
PAT_YEARS_TO_AVERAGE = 3
MIN_ACCOUNTS_FOR_MEDIAN = 50
USER_AGENT = "Mozilla/5.0 (school-map prototype; data build)"


def fetch(key: str, refresh: bool = False) -> Path | None:
    """Return the cached raw file for source `key`, downloading it if needed.

    Returns None (with a warning) when an optional source fails; exits the
    process when a required source (REQUIRED) cannot be obtained, because the
    map is meaningless without it. Socrata/alberta.ca sometimes return an HTML
    error page with HTTP 200, so tiny or HTML bodies are treated as failures.
    """
    path = RAW / RAW_FILES[key]
    if path.exists() and path.stat().st_size > 1000 and not refresh:
        return path
    RAW.mkdir(parents=True, exist_ok=True)
    try:
        resp = requests.get(SOURCES[key], headers={"User-Agent": USER_AGENT}, timeout=300)
        resp.raise_for_status()
        if resp.content[:200].lstrip().lower().startswith((b"<!doctype", b"<html")):
            raise ValueError("got an HTML page instead of data")
        path.write_bytes(resp.content)
        return path
    except Exception as exc:  # noqa: BLE001 - report any network/parse failure uniformly
        msg = f"[{key}] download failed: {exc}"
        if key in REQUIRED:
            sys.exit(f"FATAL {msg}")
        print(f"WARN {msg} -> fields will be null", file=sys.stderr)
        return None


def to_float(value) -> float | None:
    """Parse a numeric cell; 'n/a', blanks and junk become None (never 0)."""
    try:
        number = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return None if math.isnan(number) else number


_STOP_WORDS = {"the", "school", "of", "and", "campus"}


def normalize_name(name: str) -> str:
    """Normalise a school name for matching across City and Alberta Education lists.

    Lower-cases, maps '&'->'and', 'st.'->'saint', strips accents-insensitive
    punctuation and filler words. Empty/None input returns ''.
    """
    text = (name or "").lower().replace("&", " and ")
    text = re.sub(r"\bst\.?\s", "saint ", text)
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return " ".join(w for w in text.split() if w not in _STOP_WORDS)


def _pat_parts(grp, years: list[int]) -> tuple[list[float], list[float]]:
    """Collect non-suppressed % acceptable and % excellence cells for these years."""
    acc = [v for y in years for v in grp[f"{y} Sch % Acc of Enrol"].map(to_float) if pd.notna(v)]
    exc = [v for y in years for v in grp[f"{y} Sch % Exc of Enrol"].map(to_float) if pd.notna(v)]
    return acc, exc


def _pat_record(acc: list[float], exc: list[float], years: list[int]) -> dict:
    """Mean of the collected cells. An empty list stays None, never 0."""
    return {
        "acc": round(sum(acc) / len(acc), 1) if acc else None,
        "exc": round(sum(exc) / len(exc), 1) if exc else None,
        "years": years,
    }


def pat_school_results(xlsx: Path) -> tuple[dict, list[int]]:
    """Compute per-school PAT results for grades 6 and 9.

    For each (authority, school, grade) we average '% Acc of Enrol' and
    '% Exc of Enrol' over all regular courses (K&E courses excluded: a separate,
    alternative program) in the latest PAT_YEARS_TO_AVERAGE years that have any
    data in the file. Suppressed cells ('n/a') are skipped, not zeroed.
    `g6` / `g9` are that multi-year average. `g6_latest` / `g9_latest` are the
    same average for the newest year that school actually published, and they
    carry `year`. The ranking list uses the latest year only.
    Returns ({(authority, norm_name): {...}}, years_used).
    """
    df = pd.read_excel(xlsx, dtype=str)
    years = sorted({int(m.group(1)) for c in df.columns if (m := re.match(r"(\d{4}) Sch % Acc of Enrol", c))})
    years_with_data = [y for y in years if df[f"{y} Sch % Acc of Enrol"].map(to_float).notna().any()]
    used = years_with_data[-PAT_YEARS_TO_AVERAGE:]
    df = df[~df["Course Name"].str.startswith("K&E")].copy()
    df["grade"] = df["Course Name"].str.extract(r"\b(6|9)\b")[0]
    df = df[df["grade"].notna()]
    results: dict = {}
    for (auth, code, school, grade), grp in df.groupby(["Authority Name", "School Code", "School Name", "grade"]):
        # Series.map turns None into NaN, so filter on notna() rather than `is not None`.
        years_present = [y for y in used if grp[f"{y} Sch % Acc of Enrol"].map(to_float).notna().any()]
        acc, exc = _pat_parts(grp, years_present)
        entry = results.setdefault((auth, normalize_name(school)), {"code": code, "pat_name": school})
        entry[f"g{grade}"] = _pat_record(acc, exc, years_present)
        if years_present:
            latest_year = max(years_present)
            lacc, lexc = _pat_parts(grp, [latest_year])
            latest = _pat_record(lacc, lexc, [latest_year])
            latest["year"] = latest_year
            entry[f"g{grade}_latest"] = latest
    return results, used


def assign_rank_score(school: dict) -> None:
    """Record the PAT fields `rank_exam`, `rank_score`, and `rank_year`.

    The page does not rank from these fields. Elementary uses `g6_latest`,
    junior high uses `g9_latest`, and high school uses `diploma_latest`.
    Elementary-only schools store the latest Grade 6 PAT. Schools that
    continue through grade 9 and do not offer high school store the latest
    Grade 9 PAT, even when they also have a Grade 6 result. A high school
    leaves the three rank fields empty so it is not ranked on PAT.
    A missing or suppressed result stays None, never 0.
    """
    if school["senior"]:
        school["rank_exam"] = None
        school["rank_score"] = None
        school["rank_year"] = None
        return
    if school["junior"]:
        latest, exam = school.get("g9_latest"), "pat9"
    elif school["elem"]:
        latest, exam = school.get("g6_latest"), "pat6"
    else:
        school["rank_exam"] = None
        school["rank_score"] = None
        school["rank_year"] = None
        return
    score = school_score(latest)
    school["rank_exam"] = exam
    school["rank_score"] = score
    school["rank_year"] = latest.get("year") if latest and score is not None else None


def diploma_latest_by_school(frame) -> dict:
    """Newest-year diploma exam rates, keyed by (authority, normalised name).

    Uses the exam mark columns, not the school-awarded mark. Suppressed cells
    are skipped. A school with no published exam rate is omitted. The footnote
    row in the Diploma Course column is not a course. An empty frame returns {}.
    A frame missing the course, authority, or school columns raises KeyError.
    """
    if frame is None or len(frame) == 0:
        return {}
    data = frame[~frame["Diploma Course"].fillna("").astype(str).str.startswith("1. Due")].copy()
    years = sorted({int(column[:4]) for column in data.columns if column[:4].isdigit() and column.endswith("Sch Exam Mark % Acc")})
    results: dict = {}
    grouped = data.groupby(["Authority Name", "School Code", "School Name"], dropna=False)
    for (auth, code, school), grp in grouped:
        present = []
        for year in years:
            acc_col = f"{year} Sch Exam Mark % Acc"
            exc_col = f"{year} Sch Exam Mark % Exc"
            if acc_col not in grp.columns or exc_col not in grp.columns:
                continue
            acc = [v for v in grp[acc_col].map(to_float) if pd.notna(v)]
            exc = [v for v in grp[exc_col].map(to_float) if pd.notna(v)]
            if acc or exc:
                present.append((year, acc, exc))
        if not present:
            continue
        year, acc, exc = present[-1]
        record = _pat_record(acc, exc, [year])
        record["year"] = year
        if record["acc"] is None or record["exc"] is None:
            continue
        authority = str(auth or "").strip()
        results[(authority, normalize_name(str(school or "")))] = {"code": code, "diploma_latest": record}
    return results


def diploma_school_results(xlsx: Path) -> dict:
    """Read the school diploma workbook and return diploma_latest_by_school."""
    return diploma_latest_by_school(pd.read_excel(xlsx, dtype=str))


def attach_diploma(schools: list[dict], results: dict) -> None:
    """Set diploma_latest on senior schools. Other schools are left unchanged.

    Board and name match first. A name that occurs once in the file matches
    when the board does not. A senior school with no row gets null, not 0.
    """
    by_name: dict[str, list] = {}
    for (auth, norm), res in results.items():
        by_name.setdefault(norm, []).append((auth, res))
    for school in schools:
        if not school.get("senior"):
            continue
        norm = normalize_name(school.get("name") or "")
        result = results.get((school.get("board"), norm))
        if result is None and len(by_name.get(norm, [])) == 1:
            result = by_name[norm][0][1]
        school["diploma_latest"] = None if result is None else result["diploma_latest"]


def school_score(result: dict | None) -> float | None:
    """0-100 school score = mean of % acceptable and % excellence (both of enrolled).

    Excellence is ~20-50% while acceptable is ~70-95%, so the blend rewards
    both a high floor and a strong top end. None if either part is missing.
    """
    if not result or result.get("acc") is None or result.get("exc") is None:
        return None
    return round((result["acc"] + result["exc"]) / 2, 1)


def board_bucket(name: str | None) -> str:
    """Collapse a board name to a coarse bucket so City and Alberta lists can join."""
    text = (name or "").lower()
    if "roman catholic" in text or "catholic" in text:
        return "catholic"
    if "calgary school div" in text or "calgary school district" in text:
        return "public"
    if "francophone" in text:
        return "francophone"
    if "palliser" in text:
        return "palliser"
    return "other"


def latest_school_year(years: list[str]) -> str | None:
    """Pick the latest school-year label. Accepts '2023-2024' and '2013_2014'."""
    parsed = []
    for year in years:
        match = re.match(r"(\d{4})", year or "")
        if match:
            parsed.append((int(match.group(1)), year))
    return max(parsed)[1] if parsed else None


def load_enrolment(path: Path | None) -> tuple[dict, dict, str | None]:
    """Headcount for the newest year, keyed by Alberta school code and by name.

    The 2023-2024 rows in `9qye-mibh` publish a school code but no school name.
    Names are recovered from earlier years that share that code.
    Returns ({}, {}, None) when the source is missing.
    """
    if path is None:
        return {}, {}, None
    rows = json.loads(path.read_text())
    labels = [r.get("school_year") or "" for r in rows]
    newest = latest_school_year(labels)
    if newest is None:
        return {}, {}, None
    code_to_name: dict[str, str] = {}
    for row in rows:
        code = str(row.get("school_code") or "").lstrip("0")
        if code and row.get("school_name"):
            code_to_name[code] = row["school_name"]
    by_code: dict[str, int] = {}
    by_name: dict[tuple[str, str], int] = {}
    for row in rows:
        if row.get("school_year") != newest:
            continue
        total = to_float(row.get("total"))
        code = str(row.get("school_code") or "").lstrip("0")
        if total is None or not code:
            continue
        by_code[code] = by_code.get(code, 0) + int(total)
        name = row.get("school_name") or code_to_name.get(code)
        if not name:
            continue
        key = (board_bucket(row.get("school_authority_name")), normalize_name(name))
        by_name[key] = by_name.get(key, 0) + int(total)
    return by_code, by_name, newest.replace("_", "-")


def index_by_code(path: Path | None) -> dict[str, dict]:
    """Index a small Socrata JSON list by community_code. {} if the source failed."""
    if path is None:
        return {}
    return {row.get("community_code"): row for row in json.loads(path.read_text()) if row.get("community_code")}


def families_with_children_pct(row: dict | None) -> float | None:
    """Share of census families that are couples with children or one-parent families."""
    if not row:
        return None
    total = to_float(row.get("total_census_families"))
    parts = [to_float(row.get(k)) for k in ("married_with_children", "commonlaw_with_children", "one_parent_families")]
    if total is None or total <= 0 or any(p is None for p in parts):
        return None
    return round(100 * sum(parts) / total, 1)


def _file_as_of(url: str, key: str) -> str | None:
    """Last-Modified date for an Alberta workbook. None when the header is missing."""
    try:
        resp = requests.head(url, headers={"User-Agent": USER_AGENT}, timeout=60, allow_redirects=True)
        resp.raise_for_status()
        return parsedate_to_datetime(resp.headers["Last-Modified"]).date().isoformat()
    except Exception as exc:  # noqa: BLE001
        print(f"WARN [{key}] as-of date unavailable: {exc}", file=sys.stderr)
        return None


def source_as_of(refresh: bool) -> dict[str, str | None]:
    """As-of dates: Socrata rowsUpdatedAt, plus each Alberta file's Last-Modified header.

    Cached in data/raw/build/. A metadata failure leaves that date null; it does not
    fail the build, because the data files themselves are the source of truth.
    """
    cache = RAW / "source_as_of.json"
    if cache.exists() and not refresh:
        dates = json.loads(cache.read_text())
        if "diploma" not in dates:
            dates["diploma"] = _file_as_of(SOURCES["diploma"], "diploma")
            cache.write_text(json.dumps(dates, indent=1))
        return dates
    RAW.mkdir(parents=True, exist_ok=True)
    dates: dict[str, str | None] = {}
    for key, dataset_id in SOCRATA_IDS.items():
        try:
            resp = requests.get(f"https://data.calgary.ca/api/views/{dataset_id}.json",
                                headers={"User-Agent": USER_AGENT}, timeout=60)
            resp.raise_for_status()
            updated = resp.json().get("rowsUpdatedAt")
            dates[key] = datetime.fromtimestamp(int(updated), timezone.utc).strftime("%Y-%m-%d") if updated else None
        except Exception as exc:  # noqa: BLE001
            print(f"WARN [{key}] as-of date unavailable: {exc}", file=sys.stderr)
            dates[key] = None
    dates["pat"] = _file_as_of(SOURCES["pat"], "pat")
    dates["diploma"] = _file_as_of(SOURCES["diploma"], "diploma")
    cache.write_text(json.dumps(dates, indent=1))
    return dates


def main() -> int:
    """CLI entry: build web/data/*. Exit 0 on success, 1 on a fatal source error."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true", help="re-download every source")
    args = parser.parse_args()
    paths = {k: fetch(k, args.refresh) for k in SOURCES}

    # --- communities (residential only) ---
    comm_fc = json.loads(paths["communities"].read_text())
    communities = []
    for feat in comm_fc["features"]:
        props = feat.get("properties") or {}
        if props.get("class") != "Residential" or not feat.get("geometry"):
            continue
        geom = shape(feat["geometry"])
        communities.append({"code": props["comm_code"], "name": props["name"].title(),
                            "sector": (props.get("sector") or "").title(), "srg": props.get("srg"),
                            "geom": geom, "prepared": prep(geom), "rep": geom.representative_point()})
    if not communities:
        sys.exit("FATAL no residential communities in boundary data")

    # --- schools + PAT match ---
    pat, pat_years = pat_school_results(paths["pat"])
    pat_by_name: dict = {}
    for (auth, norm), res in pat.items():
        pat_by_name.setdefault(norm, []).append(res)
    schools = []
    for i, row in enumerate(json.loads(paths["schools"].read_text())):
        if not row.get("point"):
            continue
        norm = normalize_name(row.get("name", ""))
        result = pat.get((row.get("board"), norm))
        how = "board+name" if result else None
        if result is None and len(pat_by_name.get(norm, [])) == 1:
            result, how = pat_by_name[norm][0], "name-only"
        lon, lat = row["point"]["coordinates"]
        schools.append({
            # The City file has a mis-encoded en dash ("Hub \u00bf Almadina"); restore it.
            "id": i, "name": (row.get("name") or "").replace("\u00bf", "\u2013"), "board": row.get("board"), "grades": row.get("grades"),
            "address": row.get("address_ab"), "lon": round(lon, 6), "lat": round(lat, 6),
            "elem": row.get("elem") == "Y", "junior": row.get("junior_h") == "Y", "senior": row.get("senior_h") == "Y",
            "pat_code": result.get("code") if result else None, "pat_match": how,
            "g6": (result or {}).get("g6"), "g9": (result or {}).get("g9"),
            "g6_latest": (result or {}).get("g6_latest"), "g9_latest": (result or {}).get("g9_latest"),
            "rank_exam": None, "rank_score": None, "rank_year": None,
            "enrolment": None, "enrolment_year": None,
            "community": None,
        })
    enrol_by_code, enrol_by_name, enrolment_year = load_enrolment(paths["enrolment"])
    name_only: dict[str, list[int]] = {}
    for (bucket, norm), total in enrol_by_name.items():
        name_only.setdefault(norm, []).append(total)
    for s in schools:
        code = str(s.get("pat_code") or "").lstrip("0")
        total = enrol_by_code.get(code) if code else None
        if total is None:
            norm = normalize_name(s["name"])
            total = enrol_by_name.get((board_bucket(s["board"]), norm))
            if total is None and len(name_only.get(norm, [])) == 1:
                total = name_only[norm][0]
        if total is not None:
            s["enrolment"] = total
            s["enrolment_year"] = enrolment_year
    for s in schools:
        pt = Point(s["lon"], s["lat"])
        s["community"] = next((c["code"] for c in communities if c["prepared"].contains(pt)), None)
    for s in schools:
        assign_rank_score(s)
    attach_diploma(schools, diploma_school_results(paths["diploma"]))

    # --- home values (median assessed value, residential with building) ---
    median_value, accounts = {}, {}
    roll_year = None
    if paths["parcels"]:
        parcels = pd.read_csv(paths["parcels"], dtype={"comm_code": str})
        parcels["assessed_value"] = pd.to_numeric(parcels["assessed_value"], errors="coerce")
        parcels = parcels[parcels["assessed_value"] > 0]
        grouped = parcels.groupby("comm_code")["assessed_value"]
        accounts = grouped.size().to_dict()
        # A median over a handful of accounts (e.g. University of Calgary lands)
        # is not a "typical home" price, so small samples are reported as no data.
        median_value = {code: int(round(v, -3)) for code, v in grouped.median().items()
                        if accounts[code] >= MIN_ACCOUNTS_FOR_MEDIAN}

    census_age = index_by_code(paths["census_age"])
    census_families = index_by_code(paths["census_families"])

    out_features = []
    for c in communities:
        age = census_age.get(c["code"])
        props = {
            "code": c["code"], "name": c["name"],
            "home_value": median_value.get(c["code"]),
            "children_pct": to_float(age.get("pop_age_0_to_14_percent")) if age else None,
            "children_count": None if not age or to_float(age.get("pop_age_0_to_14")) is None else int(to_float(age.get("pop_age_0_to_14"))),
            "families_with_children_pct": families_with_children_pct(census_families.get(c["code"])),
        }
        # Simplify to ~10 m: keeps shapes recognisable while shrinking the file a lot.
        geom = c["geom"].simplify(0.0001, preserve_topology=True)
        out_features.append({"type": "Feature", "properties": props,
                             "geometry": json.loads(json.dumps(geom.__geo_interface__))})

    # --- match-rate statistics ---
    pat_level = [s for s in schools if s["elem"] or s["junior"]]
    matched = [s for s in pat_level if s["pat_match"]]
    with_score = [s for s in pat_level if (s.get("g6") or {}).get("acc") is not None or (s.get("g9") or {}).get("acc") is not None]
    calgary_pat = {k for k in pat if "Calgary" in k[0]}
    matched_keys = {(s["board"], normalize_name(s["name"])) for s in matched}
    # A null diploma_latest mixes a name that missed the file with a school
    # whose file row has no published exam rate. The rate is coverage, not a
    # pure name-match rate. An empty senior list leaves the rate unset.
    senior = [s for s in schools if s.get("senior")]
    with_diploma = [s for s in senior if (s.get("diploma_latest") or {}).get("acc") is not None]
    diploma_without = sorted(s["name"] for s in senior if (s.get("diploma_latest") or {}).get("acc") is None)
    stats = {
        "communities_residential": len(out_features),
        "schools_total": len(schools),
        "schools_in_residential_communities": sum(1 for s in schools if s["community"]),
        "schools_elem_or_junior": len(pat_level),
        "pat_matched": len(matched), "pat_match_rate": round(len(matched) / len(pat_level), 3),
        "pat_matched_by": {how: sum(1 for s in matched if s["pat_match"] == how) for how in ("board+name", "name-only")},
        "schools_with_pat_score": len(with_score),
        "schools_ranked_pat6": sum(1 for s in schools if s["rank_exam"] == "pat6" and s["rank_score"] is not None),
        "schools_ranked_pat9": sum(1 for s in schools if s["rank_exam"] == "pat9" and s["rank_score"] is not None),
        "schools_senior": len(senior),
        "schools_with_diploma": len(with_diploma),
        "diploma_result_rate": round(len(with_diploma) / len(senior), 3) if senior else None,
        "diploma_without_result_examples": diploma_without[:25],
        "cbe_cssd_pat_schools": len(calgary_pat),
        "cbe_cssd_pat_schools_matched": len(calgary_pat & matched_keys),
        "communities_with_home_value": sum(1 for f in out_features if f["properties"]["home_value"] is not None),
        "communities_with_children_pct": sum(1 for f in out_features if f["properties"]["children_pct"] is not None),
        "communities_with_families_pct": sum(1 for f in out_features if f["properties"]["families_with_children_pct"] is not None),
        "schools_with_enrolment": sum(1 for s in schools if s["enrolment"] is not None),
        "enrolment_year": enrolment_year,
        "residential_accounts_used": int(sum(accounts.values())) if accounts else 0,
        "unmatched_examples": sorted({s["name"] for s in pat_level if not s["pat_match"]})[:25],
    }
    as_of = source_as_of(args.refresh)

    def source(key: str, url: str, licence: str, note: str | None = None) -> dict:
        record = {"url": url, "as_of": as_of.get(key), "licence": licence}
        if note:
            record["note"] = note
        return record

    meta = {
        "pat_years": pat_years,
        "home_value_basis": "2026 property assessment roll, class RE, property type LI",
        "stats": stats,
        "sources_failed": [k for k, p in paths.items() if p is None],
        "sources": {
            "communities": source("communities", "https://data.calgary.ca/d/surr-xmvs", OGL_CALGARY),
            "schools": source("schools", "https://data.calgary.ca/d/fd9t-tdn2", OGL_CALGARY),
            "pat": source("pat", SOURCES["pat"], LICENCES["pat"], "Grades 6 and 9, latest 3 years present in the file."),
            "diploma": source("diploma", SOURCES["diploma"], LICENCES["diploma"], "Diploma exam mark, not the school-awarded mark. Each school uses its newest year."),
            "parcels": source("parcels", "https://data.calgary.ca/d/4bsw-nn7w", OGL_CALGARY, "2026 roll, class RE, property type LI."),
            "census_age": source("census_age", "https://data.calgary.ca/d/f9wk-wej9", OGL_CALGARY, "2021 census, share of residents age 0-14."),
            "census_families": source("census_families", "https://data.calgary.ca/d/msjx-5ygv", OGL_CALGARY, "2021 census families with children."),
            "enrolment": source("enrolment", "https://data.calgary.ca/d/9qye-mibh", OGL_CALGARY, "Headcount by school for the newest year in the file."),
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "communities.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": out_features}, separators=(",", ":"), allow_nan=False))
    (OUT / "schools.json").write_text(json.dumps(schools, separators=(",", ":"), allow_nan=False))
    (OUT / "meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    print(json.dumps(stats, indent=1))
    print(f"PAT years averaged: {pat_years}; failed sources: {meta['sources_failed'] or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
