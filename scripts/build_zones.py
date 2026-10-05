"""Download CBE regular-program attendance areas and walk zones.

Responsibility: turn the KMZ files already published by the CBE Find a School
tool into web/data/zones.geojson. It does not scrape the finder page. CSSD
zones and alternative-program zones (French immersion, IB, bilingual) are out
of scope. Run after scripts/build_data.py, because community home values and
school scores are read from web/data/.

Run:  .venv/bin/python scripts/build_zones.py
"""
from __future__ import annotations

import json
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from xml.etree import ElementTree as ET

import requests
from shapely.geometry import Polygon, shape
from shapely.ops import unary_union
from shapely.prepared import prep
from shapely.validation import make_valid

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_data import normalize_name, percentile_ranks  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "cbe_kmz"
OUT = ROOT / "web" / "data"
CBE = "https://www.cbe.ab.ca"
QUERY = CBE + "/sys/api/query?structureKeys={key}&pageSize=300&ignoreCurrentSite=true"
REGULAR_FRAGMENT = "fragment://9d06f92c-6f9e-42bb-a2ce-890215738ecc"
KML_NS = "{http://www.opengis.net/kml/2.2}"
USER_AGENT = "school-maps prototype (CBE public zone files)"


def fetch_rows(structure_key: str) -> list[dict]:
    """All fragments for one CBE structure key. Raises if the API is not JSON."""
    resp = requests.get(QUERY.format(key=structure_key), headers={"User-Agent": USER_AGENT}, timeout=120)
    resp.raise_for_status()
    payload = resp.json()
    rows = payload.get("Rows") or []
    if not rows:
        raise RuntimeError(f"no rows for {structure_key}")
    return rows


def parse_coords(text: str) -> list[tuple[float, float]]:
    """KML coordinate string to (lon, lat) pairs. Empty or short rings return []."""
    points = []
    for token in (text or "").split():
        parts = token.split(",")
        if len(parts) >= 2:
            points.append((float(parts[0]), float(parts[1])))
    return points


def polygons_from_kml(text: str) -> list[Polygon]:
    """Every Polygon in a KML document, holes included. Invalid rings are dropped."""
    root = ET.fromstring(text)
    found = []
    for poly in root.iter(f"{KML_NS}Polygon"):
        outer = poly.find(f".//{KML_NS}outerBoundaryIs/{KML_NS}LinearRing/{KML_NS}coordinates")
        if outer is None:
            continue
        shell = parse_coords(outer.text or "")
        if len(shell) < 4:
            continue
        holes = []
        for inner in poly.findall(f".//{KML_NS}innerBoundaryIs/{KML_NS}LinearRing/{KML_NS}coordinates"):
            ring = parse_coords(inner.text or "")
            if len(ring) >= 4:
                holes.append(ring)
        try:
            found.append(Polygon(shell, holes))
        except Exception:
            continue
    return found


def load_kmz(path: Path):
    """Union of polygons in a KMZ or raw KML file. None when the file has no polygon."""
    raw = path.read_bytes()
    if raw[:2] == b"PK":
        with zipfile.ZipFile(path) as archive:
            name = next((n for n in archive.namelist() if n.lower().endswith(".kml")), None)
            if name is None:
                return None
            text = archive.read(name).decode("utf-8", errors="replace")
    else:
        text = raw.decode("utf-8", errors="replace")
    parts = [g for g in polygons_from_kml(text) if not g.is_empty]
    if not parts:
        return None
    geom = unary_union(parts)
    if not geom.is_valid:
        geom = make_valid(geom)
    return geom.simplify(0.00012, preserve_topology=True)


def download(url_path: str) -> Path | None:
    """Cache one CBE document under data/raw/cbe_kmz. None on HTTP failure."""
    RAW.mkdir(parents=True, exist_ok=True)
    name = url_path.rstrip("/").split("/")[-1] or "zone.kmz"
    dest = RAW / name
    if dest.exists() and dest.stat().st_size > 500:
        return dest
    try:
        resp = requests.get(CBE + url_path, headers={"User-Agent": USER_AGENT}, timeout=60)
        resp.raise_for_status()
        if len(resp.content) < 500:
            return None
        dest.write_bytes(resp.content)
        return dest
    except Exception as exc:  # noqa: BLE001
        print(f"WARN zone download {url_path}: {exc}", file=sys.stderr)
        return None


def grade_band(low: int, high: int) -> str:
    """elem / junior / senior from the program grade span. K is 0."""
    if high <= 6:
        return "elem"
    if low >= 10:
        return "senior"
    if low >= 7:
        return "junior"
    return "junior" if high >= 7 else "elem"


def main() -> int:
    """CLI entry. Exit 0 when zones.geojson is written, 1 when the API fails."""
    schools_path = OUT / "schools.json"
    communities_path = OUT / "communities.geojson"
    if not schools_path.exists() or not communities_path.exists():
        print("FAIL run scripts/build_data.py first", file=sys.stderr)
        return 1

    city_schools = json.loads(schools_path.read_text(encoding="utf-8"))
    by_name: dict[str, dict] = {}
    for school in city_schools:
        board = (school.get("board") or "").lower()
        if "calgary school division" not in board:
            continue
        by_name.setdefault(normalize_name(school["name"]), school)

    communities = []
    for feat in json.loads(communities_path.read_text(encoding="utf-8"))["features"]:
        geom = shape(feat["geometry"])
        props = feat["properties"]
        communities.append({"code": props["code"], "name": props["name"],
                            "home_value": props.get("home_value"), "rep": geom.representative_point(),
                            "prep": None, "geom": geom})

    rows = fetch_rows("school_profile_fragment")
    jobs = []
    for row in rows:
        data = row.get("data") or {}
        profile = data.get("profile") or {}
        if str(profile.get("hidden") or "0") not in ("0", "no", ""):
            continue
        for program in data.get("programs") or []:
            if program.get("programFragment") != REGULAR_FRAGMENT:
                continue
            low = int(program.get("programLowGrade") or 0)
            high = int(program.get("programHighGrade") or 0)
            jobs.append({
                "name": profile.get("schoolname") or row.get("title"),
                "school_code": str(profile.get("schoolcode") or ""),
                "low": low, "high": high, "band": grade_band(low, high),
                "overlay": program.get("overlay") or "",
                "walkzone": program.get("walkzone") or "",
            })

    paths: dict[str, Path | None] = {}
    urls = sorted({u for job in jobs for u in (job["overlay"], job["walkzone"]) if u})
    with ThreadPoolExecutor(max_workers=8) as pool:
        future = {pool.submit(download, url): url for url in urls}
        for done in as_completed(future):
            paths[future[done]] = done.result()
    print(f"zone files: {sum(1 for p in paths.values() if p)}/{len(urls)}")

    features = []
    skipped = 0
    for job in jobs:
        attendance_path = paths.get(job["overlay"])
        if attendance_path is None:
            skipped += 1
            continue
        attendance = load_kmz(attendance_path)
        if attendance is None or attendance.is_empty:
            skipped += 1
            continue
        walk = None
        walk_path = paths.get(job["walkzone"])
        if walk_path is not None:
            walk = load_kmz(walk_path)
        matched = by_name.get(normalize_name(job["name"]))
        score6 = matched.get("score6") if matched else None
        score9 = matched.get("score9") if matched else None
        band_score = score6 if job["band"] == "elem" else score9 if job["band"] == "junior" else None
        prepared = attendance if attendance.geom_type == "Polygon" else attendance
        try:
            prepared_geom = prepared.buffer(0) if not prepared.is_valid else prepared
        except Exception:
            prepared_geom = attendance
        ready = prep(prepared_geom)
        walk_ready = None
        if walk is not None and not walk.is_empty:
            walk_ready = prep(walk.buffer(0) if not walk.is_valid else walk)
        places = []
        for community in communities:
            if not ready.contains(community["rep"]):
                continue
            in_walk = bool(walk_ready and walk_ready.contains(community["rep"]))
            places.append({"code": community["code"], "name": community["name"],
                           "home_value": community["home_value"], "in_walk": in_walk})
        values = [p["home_value"] for p in places if p["home_value"]]
        values.sort()
        home = values[len(values) // 2] if values else None
        code = f"{job['school_code']}-{job['low']}-{job['high']}"
        base = {
            "code": code, "name": job["name"], "school_code": job["school_code"],
            "program": "Regular", "low": job["low"], "high": job["high"], "band": job["band"],
            "grades": f"K-{job['high']}" if job["low"] == 0 else f"{job['low']}-{job['high']}",
            "school_score": band_score, "elem_score": score6, "junior_score": score9,
            "senior_score": None, "home_value": home, "places": places,
            "source": "https://www.cbe.ab.ca/find-a-school",
        }
        features.append({"type": "Feature", "properties": {**base, "kind": "attendance"},
                         "geometry": json.loads(json.dumps(prepared_geom.__geo_interface__))})
        if walk is not None and not walk.is_empty:
            features.append({"type": "Feature", "properties": {**base, "kind": "walk", "places": []},
                             "geometry": json.loads(json.dumps(walk.__geo_interface__))})

    attendance = [f for f in features if f["properties"]["kind"] == "attendance"]
    for band in ("elem", "junior", "senior"):
        group = [f for f in attendance if f["properties"]["band"] == band]
        scores = {f["properties"]["code"]: f["properties"]["school_score"] for f in group}
        prices = {f["properties"]["code"]: f["properties"]["home_value"] for f in group}
        school_pct = percentile_ranks(scores)
        price_pct = percentile_ranks(prices)
        for feat in group:
            code = feat["properties"]["code"]
            sp, pp = school_pct[code], price_pct[code]
            feat["properties"]["value_score"] = None if sp is None or pp is None else round((sp - pp + 100) / 2, 1)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "zones.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":"), allow_nan=False),
        encoding="utf-8")
    print(f"attendance {len(attendance)} walk {sum(1 for f in features if f['properties']['kind']=='walk')} skipped {skipped}")
    return 0 if len(attendance) >= 80 else 1


if __name__ == "__main__":
    sys.exit(main())
