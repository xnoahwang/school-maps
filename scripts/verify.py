"""Sanity checks on the built front-end data (web/data/*).

Responsibility: prove build_data.py produced complete, in-range output and did
not turn suppressed/missing values into zeros. Prints PASS/FAIL per check and
exits 1 on any failure. Does not download anything.

Run:  .venv/bin/python scripts/verify.py
"""
import json
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "web" / "data"
SCORE_KEYS = ("elem_score", "junior_score", "school_score", "value_score", "senior_score")
PCT_KEYS = ("children_pct", "families_with_children_pct")


def run_checks() -> list[tuple[str, bool, str]]:
    """Return (check name, passed, detail) tuples; missing files fail the first check."""
    files = [DATA / n for n in ("communities.geojson", "schools.json", "meta.json")]
    missing = [f.name for f in files if not f.exists()]
    if missing:
        return [("output files exist", False, f"missing {missing}; run scripts/build_data.py")]
    feats = json.loads(files[0].read_text())["features"]
    schools = json.loads(files[1].read_text())
    meta = json.loads(files[2].read_text())
    stats = meta["stats"]
    props = [f["properties"] for f in feats]
    out = [("output files exist", True, "3 files")]
    out.append((">=150 residential communities", len(props) >= 150, f"{len(props)}"))
    bad = [(p["code"], k, p[k]) for p in props for k in SCORE_KEYS if p[k] is not None and not 0 <= p[k] <= 100]
    out.append(("scores within 0-100 or null", not bad, f"{len(bad)} out of range"))
    # A real published 0.0 is allowed (e.g. a small specialised school); what must
    # never happen is a value that does not come from at least one non-suppressed cell.
    fabricated = [s["name"] for s in schools for g in ("g6", "g9")
                  if s.get(g) and s[g]["acc"] is not None and s[g]["n_cells"] == 0]
    out.append(("every PAT value backed by >=1 non-suppressed cell", not fabricated, f"{len(fabricated)} unbacked"))
    orphan = [s["name"] for s in schools for g, k in (("g6", "score6"), ("g9", "score9"))
              if s[k] is not None and not (s.get(g) and s[g]["acc"] is not None)]
    out.append(("no school score without PAT data", not orphan, f"{len(orphan)}"))
    out.append(("PAT match rate reported", "pat_match_rate" in stats,
                f"{stats.get('pat_matched')}/{stats.get('schools_elem_or_junior')} = {stats.get('pat_match_rate')}"))
    out.append(("rent left null (no source)", all(p["rent"] is None for p in props), "all null"))
    with_value = sum(1 for p in props if p["home_value"])
    out.append(("home values present for >=90% communities", with_value >= 0.9 * len(props), f"{with_value}/{len(props)}"))
    pct_bad = [(p["code"], k, p.get(k)) for p in props for k in PCT_KEYS
               if p.get(k) is not None and not 0 <= p[k] <= 100]
    out.append(("census percents within 0-100 or null", not pct_bad, f"{len(pct_bad)} out of range"))
    with_children = sum(1 for p in props if p.get("children_pct") is not None)
    out.append(("children 0-14 share present for >=80% communities", with_children >= 0.8 * len(props),
                f"{with_children}/{len(props)}"))
    with_prev = sum(1 for p in props if p.get("home_value_prev"))
    out.append(("2025 home values present for >=80% communities", with_prev >= 0.8 * len(props), f"{with_prev}/{len(props)}"))
    change_bad = [p["code"] for p in props if p.get("home_value_change_pct") is not None and abs(p["home_value_change_pct"]) > 80]
    out.append(("home-value change within +/-80% or null", not change_bad, f"{len(change_bad)} extreme"))
    out.append(("senior_score null until a current Diploma file exists",
                all(p.get("senior_score") is None for p in props), "all null"))
    enrol_bad = [s["name"] for s in schools if s.get("enrolment") is not None and s["enrolment"] < 0]
    out.append(("enrolment non-negative when present", not enrol_bad, f"{len(enrol_bad)} negative"))
    out.append(("enrolment matched for >=100 schools", stats.get("schools_with_enrolment", 0) >= 100,
                f"{stats.get('schools_with_enrolment')} in {stats.get('enrolment_year')}"))
    dated = [k for k, v in (meta.get("sources") or {}).items() if isinstance(v, dict) and v.get("as_of")]
    out.append(("every downloaded source has an as-of date", len(dated) >= 11, f"{len(dated)} dated"))
    out.append(("gaps recorded for sources that were not used", len(meta.get("gaps") or []) >= 6, f"{len(meta.get('gaps') or [])} gaps"))
    zone_path = DATA / "zones.geojson"
    if not zone_path.exists():
        out.append(("CBE attendance zones exist", False, "missing zones.geojson; run scripts/build_zones.py"))
    else:
        zfeats = json.loads(zone_path.read_text(encoding="utf-8"))["features"]
        attendance = [f for f in zfeats if f.get("properties", {}).get("kind") == "attendance"]
        walks = [f for f in zfeats if f.get("properties", {}).get("kind") == "walk"]
        elem = [f for f in attendance if f["properties"].get("band") == "elem"]
        regular = [f for f in attendance if f["properties"].get("program") == "Regular"]
        out.append(("CBE regular attendance zones", len(regular) >= 80, f"{len(regular)} regular of {len(attendance)}"))
        out.append(("CBE walk zones", len(walks) >= 50, f"{len(walks)}"))
        out.append(("elementary attendance zones", len(elem) >= 40, f"{len(elem)}"))
    ranked = [s for s in schools if "rank_exam" in s]
    out.append(("every school has a rank exam field", len(ranked) == len(schools), f"{len(ranked)}/{len(schools)}"))
    bad_rank = [s["name"] for s in schools if s.get("rank_score") is not None and not 0 <= s["rank_score"] <= 100]
    out.append(("rank scores within 0-100 or null", not bad_rank, f"{len(bad_rank)} out of range"))
    pat6 = [s for s in schools if s.get("rank_exam") == "pat6"]
    pat9 = [s for s in schools if s.get("rank_exam") == "pat9"]
    diploma = [s for s in schools if s.get("rank_exam") == "diploma"]
    out.append(("elementary rank is grade 6 only", all(s["elem"] and not s["junior"] and not s["senior"] for s in pat6), f"{len(pat6)}"))
    out.append(("junior rank is grade 9, not high school", all(s["junior"] and not s["senior"] for s in pat9), f"{len(pat9)}"))
    out.append(("high-school rank is diploma and unscored", all(s["senior"] and s.get("rank_score") is None for s in diploma) and len(diploma) >= 40, f"{len(diploma)}"))
    years = set(meta.get("pat_years") or [])
    bad_year = [s["name"] for s in schools if s.get("rank_year") is not None and s["rank_year"] not in years]
    missing_year = [s["name"] for s in schools if s.get("rank_score") is not None and s.get("rank_year") is None]
    out.append(("rank year is a PAT year when the score exists", not bad_year and not missing_year, f"{len(bad_year)} bad, {len(missing_year)} missing"))
    n6 = sum(1 for s in pat6 if s.get("rank_score") is not None)
    n9 = sum(1 for s in pat9 if s.get("rank_score") is not None)
    out.append(("enough latest-year PAT ranks", n6 >= 100 and n9 >= 80, f"pat6 {n6}, pat9 {n9}"))
    directory_path = DATA / "cbe_directory.json"
    if not directory_path.exists():
        out.append(("CBE directory file", False, "missing cbe_directory.json"))
        return out
    directory = json.loads(directory_path.read_text(encoding="utf-8"))
    dschools = directory.get("schools") or []
    dnames = {s.get("name") for s in dschools}
    needed = {"Evanston Heights School", "Piitoayis Family School", "Windsor Park School"}
    out.append(("CBE directory has the schools missing from the City file", needed <= dnames, f"{len(dnames)} schools"))
    programs = set(directory.get("programs") or [])
    out.append(("CBE program filter includes Regular and Early French Immersion",
                {"Regular", "Early French Immersion"} <= programs and "Knowledge & Employability (K&E)" not in programs,
                f"{len(programs)} programs"))
    bad_span = [s.get("name") for s in dschools
                if s.get("grade_min") is not None and s.get("grade_max") is not None and s["grade_min"] > s["grade_max"]]
    out.append(("CBE grade spans are ordered", not bad_span, f"{len(bad_span)} reversed"))
    return out


if __name__ == "__main__":
    results = run_checks()
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}  ({detail})")
    sys.exit(0 if all(ok for _, ok, _ in results) else 1)
