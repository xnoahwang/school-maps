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
}
RAW_FILES = {
    "communities": "communities.geojson", "schools": "schools.json", "pat": "pat.xlsx",
    "parcels": "parcels_res.csv", "libraries": "libraries.json",
    "transit": "transit.json", "parks": "parks.geojson",
}
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


def pat_school_results(xlsx: Path) -> tuple[dict, list[int]]:
    """Compute per-school PAT multi-year averages for grades 6 and 9.

    For each (authority, school, grade) we average '% Acc of Enrol' and
    '% Exc of Enrol' over all regular courses (K&E courses excluded: a separate,
    alternative program) in the latest PAT_YEARS_TO_AVERAGE years that have any
    data in the file. Suppressed cells ('n/a') are skipped, not zeroed.
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
        acc = [v for y in used for v in grp[f"{y} Sch % Acc of Enrol"].map(to_float) if pd.notna(v)]
        exc = [v for y in used for v in grp[f"{y} Sch % Exc of Enrol"].map(to_float) if pd.notna(v)]
        years_present = [y for y in used if grp[f"{y} Sch % Acc of Enrol"].map(to_float).notna().any()]
        entry = results.setdefault((auth, normalize_name(school)), {"code": code, "pat_name": school})
        entry[f"g{grade}"] = {
            "acc": round(sum(acc) / len(acc), 1) if acc else None,
            "exc": round(sum(exc) / len(exc), 1) if exc else None,
            "n_cells": len(acc),
            "years": years_present,
        }
    return results, used


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
            "score6": school_score((result or {}).get("g6")) if row.get("elem") == "Y" else None,
            "score9": school_score((result or {}).get("g9")) if row.get("junior_h") == "Y" else None,
            "community": None,
        })
    for s in schools:
        pt = Point(s["lon"], s["lat"])
        s["community"] = next((c["code"] for c in communities if c["prepared"].contains(pt)), None)

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
        amen = {}
        for k, pts in amenity_points.items():
            amen[k] = None if pts is None else sum(1 for p in pts if c["prepared"].contains(p))
        props = {
            "code": c["code"], "name": c["name"], "sector": c["sector"], "srg": c["srg"],
            "elem_score": elem_score, "junior_score": junior_score, "school_score": combined,
            "home_value": median_value.get(c["code"]), "home_accounts": accounts.get(c["code"]),
            "rent": None,  # no open per-community rent source; deliberately not estimated
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
        "cbe_cssd_pat_schools": len(calgary_pat),
        "cbe_cssd_pat_schools_matched": len(calgary_pat & matched_keys),
        "communities_with_school_score": sum(1 for f in out_features if f["properties"]["school_score"] is not None),
        "communities_with_home_value": sum(1 for f in out_features if f["properties"]["home_value"] is not None),
        "residential_accounts_used": int(sum(accounts.values())) if accounts else 0,
        "unmatched_examples": sorted({s["name"] for s in pat_level if not s["pat_match"]})[:25],
    }
    meta = {
        "pat_years": pat_years, "home_value_basis": "2026 property assessment roll, class RE, property type LI",
        "stats": stats,
        "sources_failed": [k for k, p in paths.items() if p is None],
        "sources": {
            "communities": "https://data.calgary.ca/d/surr-xmvs",
            "schools": "https://data.calgary.ca/d/fd9t-tdn2",
            "pat": SOURCES["pat"],
            "parcels": "https://data.calgary.ca/d/4bsw-nn7w",
            "libraries": "https://data.calgary.ca/d/m9y7-ui7j",
            "transit": "https://data.calgary.ca/d/muzh-c9qc",
            "parks": "https://data.calgary.ca/d/kami-qbfh",
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
