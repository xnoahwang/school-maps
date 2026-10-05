"""Build the front-end data for the Calgary school-community map.

Responsibility: download public sources into data/raw/ (cached; delete a file
to refetch), join them, compute transparent per-community scores, and write
compact JSON/GeoJSON into web/data/. It does NOT serve or render anything.

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
RAW = ROOT / "data" / "raw"
OUT = ROOT / "web" / "data"

SOCRATA = "https://data.calgary.ca/resource"
SOURCES = {
    # ab7m-fwn6 is a map *view* whose API returns empty features; surr-xmvs is
    # the backing dataset (same name/update time) so we read that instead.
    "communities": f"{SOCRATA}/surr-xmvs.geojson?$limit=5000",
    "schools": f"{SOCRATA}/fd9t-tdn2.json?$limit=5000",
    "pat": "https://www.alberta.ca/system/files/custom_downloaded_images/ed-pat-multiyear-sch-list.xlsx",
    # p84b-7zbi (Assessments by Community) only holds 2016-2017, so we take the
    # current parcel roll and compute medians ourselves.
    "parcels": (f"{SOCRATA}/4bsw-nn7w.csv?$select=comm_code,comm_name,assessed_value"
                "&$where=assessment_class='RE' AND property_type='LI'&$limit=2000000"),
    "libraries": f"{SOCRATA}/m9y7-ui7j.json?$limit=5000",
    "transit": f"{SOCRATA}/muzh-c9qc.json?$select=stop_name,status,point&$limit=100000",
    "parks": f"{SOCRATA}/kami-qbfh.geojson?$select=site_name,the_geom&$limit=100000",
    # assessed_value is text in this dataset, so a Socrata median() is
    # alphabetical and wrong. Download the rows and take the median in pandas.
    "parcels_2025": (f"{SOCRATA}/4ur7-wsgc.csv?$select=comm_code,assessed_value"
                     "&$where=roll_year='2025' AND assessment_class='RE' AND property_type='LI'"
                     "&$limit=2000000"),
    "census_age": (f"{SOCRATA}/f9wk-wej9.json?$select=community_code,pop_age_0_to_14,"
                   "pop_age_0_to_14_percent,total_pop_household&$limit=5000"),
    "census_families": (f"{SOCRATA}/msjx-5ygv.json?$select=community_code,total_census_families,"
                        "married_with_children,commonlaw_with_children,one_parent_families&$limit=5000"),
    "enrolment": f"{SOCRATA}/9qye-mibh.json?$limit=20000",
}
RAW_FILES = {
    "communities": "communities.geojson", "schools": "schools.json", "pat": "pat.xlsx",
    "parcels": "parcels_res.csv", "libraries": "libraries.json",
    "transit": "transit.json", "parks": "parks.geojson",
    "parcels_2025": "parcels_2025.csv", "census_age": "census_age.json",
    "census_families": "census_families.json", "enrolment": "enrolment.json",
}
# Socrata view ids, used only to read rowsUpdatedAt. Not all of these are downloaded.
SOCRATA_IDS = {
    "communities": "surr-xmvs", "schools": "fd9t-tdn2", "parcels": "4bsw-nn7w",
    "libraries": "m9y7-ui7j", "transit": "muzh-c9qc", "parks": "kami-qbfh",
    "parcels_2025": "4ur7-wsgc", "census_age": "f9wk-wej9",
    "census_families": "msjx-5ygv", "enrolment": "9qye-mibh",
}
LICENCES = {
    "pat": "https://open.alberta.ca/licence",
}
OGL_CALGARY = "https://data.calgary.ca/d/Open-Data-Terms/u45n-7awa"
REQUIRED = {"communities", "schools", "pat"}
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
        "n_cells": len(acc),
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
    """Set the one exam score used to rank this school.

    Elementary-only schools use the latest Grade 6 PAT. Schools that continue
    through grade 9 and do not offer high school use the latest Grade 9 PAT,
    even when they also have a Grade 6 result. High schools would use Diploma
    results; that file is not open, so `rank_score` stays None. Writes
    `rank_exam` (`pat6`, `pat9`, `diploma`, or None), `rank_score`, and
    `rank_year`. A missing or suppressed result stays None, never 0.
    """
    if school["senior"]:
        school["rank_exam"] = "diploma"
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


def school_score(result: dict | None) -> float | None:
    """0-100 school score = mean of % acceptable and % excellence (both of enrolled).

    Excellence is ~20-50% while acceptable is ~70-95%, so the blend rewards
    both a high floor and a strong top end. None if either part is missing.
    """
    if not result or result.get("acc") is None or result.get("exc") is None:
        return None
    return round((result["acc"] + result["exc"]) / 2, 1)


def mean_or_none(values) -> float | None:
    """Mean of the non-None values, or None when there are none."""
    vals = [v for v in values if v is not None]
    return round(sum(vals) / len(vals), 1) if vals else None


def percentile_ranks(values: dict) -> dict:
    """Map key -> percentile rank (0-100) among non-None values; None stays None."""
    present = sorted(v for v in values.values() if v is not None)
    if len(present) < 2:
        return {k: (50.0 if v is not None else None) for k, v in values.items()}
    def rank(v):
        below = sum(1 for p in present if p < v)
        equal = sum(1 for p in present if p == v)
        return 100 * (below + (equal - 1) / 2) / (len(present) - 1)
    return {k: (round(rank(v), 1) if v is not None else None) for k, v in values.items()}


def approx_km(lon1, lat1, lon2, lat2) -> float:
    """Equirectangular distance in km; accurate to <1% at city scale."""
    x = math.radians(lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    y = math.radians(lat2 - lat1)
    return 6371 * math.hypot(x, y)


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
    Names are recovered from earlier years that share that code. This is
    enrolment, not class size. Returns ({}, {}, None) when the source is missing.
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


def load_prior_medians(path: Path | None) -> dict[str, int]:
    """Community code -> 2025 median assessed value, same LI filter as the 2026 roll.

    The download stores assessed_value as text. It is parsed numerically here.
    Samples under MIN_ACCOUNTS_FOR_MEDIAN are dropped, matching the current roll.
    """
    if path is None:
        return {}
    frame = pd.read_csv(path, dtype={"comm_code": str})
    # Socrata CSV exports this column with thousands separators ("547,000").
    frame["assessed_value"] = pd.to_numeric(
        frame["assessed_value"].astype(str).str.replace(",", "", regex=False), errors="coerce")
    frame = frame[frame["assessed_value"] > 0]
    grouped = frame.groupby("comm_code")["assessed_value"]
    counts = grouped.size()
    return {code: int(round(value, -3)) for code, value in grouped.median().items()
            if counts[code] >= MIN_ACCOUNTS_FOR_MEDIAN}


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


def source_as_of(refresh: bool) -> dict[str, str | None]:
    """As-of dates: Socrata rowsUpdatedAt, plus the PAT file's Last-Modified header.

    Cached in data/raw/. A metadata failure leaves that date null; it does not
    fail the build, because the data files themselves are the source of truth.
    """
    cache = RAW / "source_as_of.json"
    if cache.exists() and not refresh:
        return json.loads(cache.read_text())
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
    try:
        resp = requests.head(SOURCES["pat"], headers={"User-Agent": USER_AGENT}, timeout=60, allow_redirects=True)
        resp.raise_for_status()
        dates["pat"] = parsedate_to_datetime(resp.headers["Last-Modified"]).date().isoformat()
    except Exception as exc:  # noqa: BLE001
        print(f"WARN [pat] as-of date unavailable: {exc}", file=sys.stderr)
        dates["pat"] = None
    cache.write_text(json.dumps(dates, indent=1))
    return dates


def load_points(path: Path | None, kind: str) -> list[Point] | None:
    """Read point features for amenity counts; None if the source failed."""
    if path is None:
        return None
    if kind == "transit":
        rows = json.loads(path.read_text())
        return [Point(r["point"]["coordinates"]) for r in rows
                if r.get("point") and r.get("status", "ACTIVE").upper() == "ACTIVE"]
    if kind == "libraries":
        rows = json.loads(path.read_text())
        return [Point(float(r["location"]["longitude"]), float(r["location"]["latitude"]))
                for r in rows if r.get("location", {}).get("latitude")]
    if kind == "parks":
        feats = json.loads(path.read_text())["features"]
        return [shape(f["geometry"]).representative_point() for f in feats if f.get("geometry")]
    raise ValueError(kind)


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
            "score6": school_score((result or {}).get("g6")) if row.get("elem") == "Y" else None,
            "score9": school_score((result or {}).get("g9")) if row.get("junior_h") == "Y" else None,
            "rank_exam": None, "rank_score": None, "rank_year": None,
            # Diploma school-level results newer than 2015/16 are not open data. See meta.gaps.
            "g12": None, "score12": None,
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

    prior_value = load_prior_medians(paths["parcels_2025"])
    census_age = index_by_code(paths["census_age"])
    census_families = index_by_code(paths["census_families"])

    # --- amenities ---
    amenity_points = {k: load_points(paths[k], k) for k in ("libraries", "transit", "parks")}

    # --- per-community aggregation ---
    out_features, school_cut = [], {}
    for c in communities:
        inside = [s for s in schools if s["community"] == c["code"]]
        nearby = {s["id"]: "inside" for s in inside}
        rx, ry = c["rep"].x, c["rep"].y
        for level in ("elem", "junior", "senior"):
            cands = [s for s in schools if s[level]]
            if cands:
                nearest = min(cands, key=lambda s: approx_km(rx, ry, s["lon"], s["lat"]))
                nearby.setdefault(nearest["id"], f"nearest_{level}")
        near_list = [schools[i] for i in nearby]
        elem_score = mean_or_none(s["score6"] for s in near_list)
        junior_score = mean_or_none(s["score9"] for s in near_list)
        combined = mean_or_none([elem_score, junior_score])
        senior_score = mean_or_none(s["score12"] for s in near_list)
        enrol_vals = [s["enrolment"] for s in near_list if s["enrolment"] is not None]
        age = census_age.get(c["code"])
        current = median_value.get(c["code"])
        previous = prior_value.get(c["code"])
        change = None if current is None or previous is None or previous == 0 else round(100 * (current - previous) / previous, 1)
        amen = {}
        for k, pts in amenity_points.items():
            amen[k] = None if pts is None else sum(1 for p in pts if c["prepared"].contains(p))
        props = {
            "code": c["code"], "name": c["name"], "sector": c["sector"], "srg": c["srg"],
            "elem_score": elem_score, "junior_score": junior_score, "school_score": combined,
            "senior_score": senior_score,
            "home_value": current, "home_value_prev": previous, "home_value_change_pct": change,
            "home_accounts": accounts.get(c["code"]),
            "rent": None,  # CMHC is zone-level only; no community crosswalk, so not estimated
            "children_pct": to_float(age.get("pop_age_0_to_14_percent")) if age else None,
            "children_count": None if not age or to_float(age.get("pop_age_0_to_14")) is None else int(to_float(age.get("pop_age_0_to_14"))),
            "families_with_children_pct": families_with_children_pct(census_families.get(c["code"])),
            "enrolment": int(sum(enrol_vals)) if enrol_vals else None,
            "libraries": amen["libraries"], "transit_stops": amen["transit"], "parks": amen["parks"],
            "nearby": [{"id": i, "why": why,
                        "km": round(approx_km(rx, ry, schools[i]["lon"], schools[i]["lat"]), 2)}
                       for i, why in nearby.items()],
        }
        # Simplify to ~10 m: keeps shapes recognisable while shrinking the file a lot.
        geom = c["geom"].simplify(0.0001, preserve_topology=True)
        out_features.append({"type": "Feature", "properties": props,
                             "geometry": json.loads(json.dumps(geom.__geo_interface__))})
        school_cut.update({i: schools[i] for i in nearby})

    # value for money: school-percentile minus price-percentile, rescaled 0..100
    school_pct = percentile_ranks({f["properties"]["code"]: f["properties"]["school_score"] for f in out_features})
    price_pct = percentile_ranks({f["properties"]["code"]: f["properties"]["home_value"] for f in out_features})
    for f in out_features:
        code = f["properties"]["code"]
        sp, pp = school_pct[code], price_pct[code]
        f["properties"]["school_pct"], f["properties"]["price_pct"] = sp, pp
        f["properties"]["value_score"] = None if sp is None or pp is None else round((sp - pp + 100) / 2, 1)

    # --- match-rate statistics ---
    pat_level = [s for s in schools if s["elem"] or s["junior"]]
    matched = [s for s in pat_level if s["pat_match"]]
    with_score = [s for s in pat_level if s["score6"] is not None or s["score9"] is not None]
    calgary_pat = {k for k in pat if "Calgary" in k[0]}
    matched_keys = {(s["board"], normalize_name(s["name"])) for s in matched}
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
        "cbe_cssd_pat_schools": len(calgary_pat),
        "cbe_cssd_pat_schools_matched": len(calgary_pat & matched_keys),
        "communities_with_school_score": sum(1 for f in out_features if f["properties"]["school_score"] is not None),
        "communities_with_home_value": sum(1 for f in out_features if f["properties"]["home_value"] is not None),
        "communities_with_home_value_prev": sum(1 for f in out_features if f["properties"]["home_value_prev"] is not None),
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
        "home_value_prev_basis": "2025 historical roll (4ur7-wsgc), same class RE and property type LI filter",
        "stats": stats,
        "sources_failed": [k for k, p in paths.items() if p is None],
        "gaps": [
            {"field": "senior_score", "reason": "No school-level Diploma XLSX newer than 2015/16 is on open.alberta.ca. The alberta.ca current-file URL returns 404. Per-school 2024/25 multiyear PDFs are embargoed for school-authority use until the embargo is lifted, so they are not used."},
            {"field": "equity_index", "reason": "The 2024 Calgary Equity Index (i6pu-a35d) is a PDF/zip blob, not a community table. hy6b-89wc returns no rows."},
            {"field": "crime", "reason": "Community Crime Statistics (78gh-n26t) requires a logged-in session. The open table 848s-4m4z ends in 2019 and its methodology was retired, so it is not shown as current safety."},
            {"field": "rent", "reason": "CMHC publishes rent by zone only. There is no community-to-zone crosswalk, so a zone figure is not shown as a community figure."},
            {"field": "income", "reason": "Open Calgary has no 2021 census income-by-community table. The 2016 table (wj3a-wgmh) is too old to present as current."},
            {"field": "languages", "reason": "Open Calgary has no 2021 census language-by-community table."},
            {"field": "class_size", "reason": "9qye-mibh is enrolment by grade through 2023-2024, not class size. The CBE 2025-26 enrolment report states it does not include class size."},
            {"field": "programs", "reason": "CBE programs come from the public school-directory API (web/data/cbe_directory.json). CSSD programs, lottery-only flags, and overflow schools are still not included."},
        ],
        "sources": {
            "communities": source("communities", "https://data.calgary.ca/d/surr-xmvs", OGL_CALGARY),
            "schools": source("schools", "https://data.calgary.ca/d/fd9t-tdn2", OGL_CALGARY),
            "pat": source("pat", SOURCES["pat"], LICENCES["pat"], "Grades 6 and 9, latest 3 years present in the file."),
            "parcels": source("parcels", "https://data.calgary.ca/d/4bsw-nn7w", OGL_CALGARY, "2026 roll, class RE, property type LI."),
            "parcels_2025": source("parcels_2025", "https://data.calgary.ca/d/4ur7-wsgc", OGL_CALGARY, "2025 roll, same RE/LI filter, median by community."),
            "census_age": source("census_age", "https://data.calgary.ca/d/f9wk-wej9", OGL_CALGARY, "2021 census, share of residents age 0-14."),
            "census_families": source("census_families", "https://data.calgary.ca/d/msjx-5ygv", OGL_CALGARY, "2021 census families with children."),
            "enrolment": source("enrolment", "https://data.calgary.ca/d/9qye-mibh", OGL_CALGARY, "Headcount by school for the newest year in the file. Not class size."),
            "libraries": source("libraries", "https://data.calgary.ca/d/m9y7-ui7j", OGL_CALGARY),
            "transit": source("transit", "https://data.calgary.ca/d/muzh-c9qc", OGL_CALGARY),
            "parks": source("parks", "https://data.calgary.ca/d/kami-qbfh", OGL_CALGARY),
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "communities.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": out_features}, separators=(",", ":"), allow_nan=False))
    (OUT / "schools.json").write_text(json.dumps(schools, separators=(",", ":"), allow_nan=False))
    (OUT / "meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False, allow_nan=False))
    print(json.dumps(stats, indent=1))
    print(f"PAT years averaged: {pat_years}; failed sources: {meta['sources_failed'] or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
