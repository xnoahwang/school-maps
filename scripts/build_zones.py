"""Download CBE attendance areas and walk zones.

Responsibility: turn the KMZ files published by the CBE Find a School tool
into web/data/zones.geojson, one attendance polygon and one walk zone per
program that publishes them. A community is included when the overlap is at
least 10% of the zone or of the community, not only when the community's
representative point falls inside. Grade 10–12 zones are skipped. Community
lists are stored on the regular program. Run after scripts/build_data.py.
"""
from __future__ import annotations

import json
import re
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from xml.etree import ElementTree as ET

import requests
from shapely.geometry import Polygon, shape
from shapely.ops import unary_union
from shapely.validation import make_valid

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_data import normalize_name  # noqa: E402
from store import write_if_changed  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "cbe_kmz"
OUT = ROOT / "web" / "data"
CBE = "https://www.cbe.ab.ca"
QUERY = CBE + "/sys/api/query?structureKeys={key}&pageSize=300&ignoreCurrentSite=true"
REGULAR_FRAGMENT = "fragment://9d06f92c-6f9e-42bb-a2ce-890215738ecc"
KML_NS = "{http://www.opengis.net/kml/2.2}"
USER_AGENT = "school-maps prototype (CBE public zone files)"
# A boundary sliver can be a few percent of one side and almost nothing of the other.
OVERLAP_SHARE = 0.10


def places_for_zone(zone_geom, walk_geom, communities: list[dict]) -> list[dict]:
    """Communities this attendance zone covers, with a walk-zone flag.

    The community's representative point is often outside a zone that only
    covers part of that community. A community counts when the overlap is at
    least 10% of the zone or of the community. in_walk is true when the walk
    zone covers at least half of that overlap. Returns [] for an empty zone.
    """
    zone_area = zone_geom.area
    if zone_area <= 0:
        return []
    places = []
    for community in communities:
        geom = community["geom"]
        if geom.is_empty or geom.area <= 0 or not zone_geom.intersects(geom):
            continue
        try:
            overlap = zone_geom.intersection(geom)
        except Exception:
            continue
        if overlap.is_empty or overlap.area <= 0:
            continue
        if overlap.area / zone_area < OVERLAP_SHARE and overlap.area / geom.area < OVERLAP_SHARE:
            continue
        in_walk = False
        if walk_geom is not None and not walk_geom.is_empty:
            try:
                walked = walk_geom.intersection(overlap)
            except Exception:
                walked = None
            in_walk = walked is not None and not walked.is_empty and walked.area >= overlap.area * 0.5
        places.append({
            "code": community["code"], "name": community["name"],
            "home_value": community["home_value"], "in_walk": in_walk,
        })
    places.sort(key=lambda place: place["name"])
    return places


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


def download(url_path: str, refresh: bool = False) -> Path | None:
    """Cache one CBE document under data/raw/cbe_kmz. None on HTTP failure.

    A cached file is reused unless refresh is set. On refresh, identical
    bytes are left in place. A failed refresh keeps the cache when it exists.
    """
    RAW.mkdir(parents=True, exist_ok=True)
    name = url_path.rstrip("/").split("/")[-1] or "zone.kmz"
    dest = RAW / name
    cached = dest.exists() and dest.stat().st_size > 500
    if cached and not refresh:
        return dest
    try:
        resp = requests.get(CBE + url_path, headers={"User-Agent": USER_AGENT}, timeout=60)
        resp.raise_for_status()
        if len(resp.content) < 500:
            return dest if cached else None
        if cached and dest.read_bytes() == resp.content:
            return dest
        dest.write_bytes(resp.content)
        return dest
    except Exception as exc:  # noqa: BLE001
        print(f"WARN zone download {url_path}: {exc}", file=sys.stderr)
        return dest if cached else None


def grade_band(low: int, high: int) -> str:
    """elem / junior / senior from the program grade span. K is 0."""
    if high <= 6:
        return "elem"
    if low >= 10:
        return "senior"
    if low >= 7:
        return "junior"
    return "junior" if high >= 7 else "elem"


def program_names() -> dict[str, str]:
    """Map a CBE program fragment id to its display name.

    Returns {} when the program list cannot be read. Callers then keep only
    the regular program, whose fragment id is already known.
    """
    try:
        rows = fetch_rows("program_fragment")
    except Exception as exc:  # noqa: BLE001
        print(f"WARN program names: {exc}", file=sys.stderr)
        return {}
    names = {}
    for row in rows:
        programs = (row.get("data") or {}).get("programs") or {}
        name = (programs.get("name") or "").strip()
        if name and row.get("id"):
            names[str(row["id"])] = name
    return names


def main(refresh: bool = False) -> int:
    """CLI entry. Exit 0 when zones.geojson is current, 1 when the API fails.

    refresh re-downloads each zone file and keeps it when the bytes match.
    Grade 10–12 zones are not built. The page ranks elementary and junior high.
    """
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
    names = program_names()
    jobs = []
    for row in rows:
        data = row.get("data") or {}
        profile = data.get("profile") or {}
        if str(profile.get("hidden") or "0") not in ("0", "no", ""):
            continue
        for program in data.get("programs") or []:
            fragment = str(program.get("programFragment") or "").replace("fragment://", "")
            program_name = names.get(fragment)
            if not program_name and program.get("programFragment") == REGULAR_FRAGMENT:
                program_name = "Regular"
            if not program_name or not program.get("overlay"):
                continue
            low = int(program.get("programLowGrade") or 0)
            high = int(program.get("programHighGrade") or 0)
            band = grade_band(low, high)
            if band == "senior":
                continue
            jobs.append({
                "name": profile.get("schoolname") or row.get("title"),
                "school_code": str(profile.get("schoolcode") or ""),
                "program": program_name,
                "low": low, "high": high, "band": band,
                "overlay": program.get("overlay") or "",
                "walkzone": program.get("walkzone") or "",
            })

    paths: dict[str, Path | None] = {}
    urls = sorted({u for job in jobs for u in (job["overlay"], job["walkzone"]) if u})
    with ThreadPoolExecutor(max_workers=8) as pool:
        future = {pool.submit(download, url, refresh): url for url in urls}
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
        prepared = attendance if attendance.geom_type == "Polygon" else attendance
        try:
            prepared_geom = prepared.buffer(0) if not prepared.is_valid else prepared
        except Exception:
            prepared_geom = attendance
        places = []
        home = None
        # Community lists are stored on the regular program. Another program with an
        # empty list falls back to that school's regular zone.
        if job["program"] == "Regular":
            places = places_for_zone(prepared_geom, walk if walk is not None and not walk.is_empty else None, communities)
            values = sorted(p["home_value"] for p in places if p["home_value"])
            home = values[len(values) // 2] if values else None
        code = f"{job['school_code']}-{job['low']}-{job['high']}"
        if job["program"] != "Regular":
            slug = re.sub(r"[^a-z0-9]+", "-", job["program"].lower()).strip("-")
            code = f"{code}-{slug}"
        base = {
            "code": code, "name": job["name"], "school_code": job["school_code"],
            "program": job["program"], "low": job["low"], "high": job["high"], "band": job["band"],
            "grades": f"K-{job['high']}" if job["low"] == 0 else f"{job['low']}-{job['high']}",
            "home_value": home, "places": places,
            "source": "https://www.cbe.ab.ca/find-a-school",
        }
        features.append({"type": "Feature", "properties": {**base, "kind": "attendance"},
                         "geometry": json.loads(json.dumps(prepared_geom.__geo_interface__))})
        if walk is not None and not walk.is_empty:
            features.append({"type": "Feature", "properties": {**base, "kind": "walk", "places": []},
                             "geometry": json.loads(json.dumps(walk.__geo_interface__))})

    attendance = [f for f in features if f["properties"]["kind"] == "attendance"]
    regular = [f for f in attendance if f["properties"]["program"] == "Regular"]

    text = json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":"), allow_nan=False)
    write_if_changed(OUT / "zones.geojson", text)
    print(f"attendance {len(attendance)} regular {len(regular)} walk {sum(1 for f in features if f['properties']['kind']=='walk')} skipped {skipped}")
    return 0 if len(regular) >= 80 else 1


if __name__ == "__main__":
    sys.exit(main())
