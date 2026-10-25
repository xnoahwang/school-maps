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
PCT_KEYS = ("children_pct", "families_with_children_pct")
# Retired community-map fields. They must stay off community properties so the
# old colouring scores cannot sneak back. Enrolment on a school record is not
# this check.
MAP_FIELDS = ("elem_score", "junior_score", "school_score", "value_score", "school_pct", "price_pct",
              "libraries", "transit_stops", "parks", "nearby", "home_value_prev", "home_value_change_pct", "enrolment")


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
    map_left = [p["code"] for p in props if any(k in p for k in MAP_FIELDS)]
    out.append(("communities are boundaries and census figures", not map_left, f"{len(map_left)} with map fields"))
    # A real published 0.0 is allowed. A score still has to name the years it came from.
    fabricated = [s["name"] for s in schools for g in ("g6", "g9", "g6_latest", "g9_latest")
                  if s.get(g) and s[g].get("acc") is not None and not s[g].get("years")]
    out.append(("every PAT value names the years it came from", not fabricated, f"{len(fabricated)} unbacked"))
    orphan = [s["name"] for s in schools if "score6" in s or "score9" in s]
    out.append(("schools do not store a community-map score", not orphan, f"{len(orphan)}"))
    out.append(("PAT match rate reported", "pat_match_rate" in stats,
                f"{stats.get('pat_matched')}/{stats.get('schools_elem_or_junior')} = {stats.get('pat_match_rate')}"))
    with_value = sum(1 for p in props if p["home_value"])
    out.append(("home values present for >=90% communities", with_value >= 0.9 * len(props), f"{with_value}/{len(props)}"))
    pct_bad = [(p["code"], k, p.get(k)) for p in props for k in PCT_KEYS
               if p.get(k) is not None and not 0 <= p[k] <= 100]
    out.append(("census percents within 0-100 or null", not pct_bad, f"{len(pct_bad)} out of range"))
    with_children = sum(1 for p in props if p.get("children_pct") is not None)
    out.append(("children 0-14 share present for >=80% communities", with_children >= 0.8 * len(props),
                f"{with_children}/{len(props)}"))
    enrol_bad = [s["name"] for s in schools if s.get("enrolment") is not None and s["enrolment"] < 0]
    out.append(("enrolment non-negative when present", not enrol_bad, f"{len(enrol_bad)} negative"))
    out.append(("enrolment matched for >=100 schools", stats.get("schools_with_enrolment", 0) >= 100,
                f"{stats.get('schools_with_enrolment')} in {stats.get('enrolment_year')}"))
    dated = [k for k, v in (meta.get("sources") or {}).items() if isinstance(v, dict) and v.get("as_of")]
    out.append(("every downloaded source has an as-of date", len(dated) >= 7, f"{len(dated)} dated"))
    leftover = [p["code"] for p in props if "senior_score" in p or "rent" in p]
    cell_counts = [s["name"] for s in schools for g in ("g6", "g9", "g6_latest", "g9_latest")
                   if s.get(g) and "n_cells" in s[g]]
    diploma_rows = [s["name"] for s in schools if s.get("rank_exam") == "diploma" or "g12" in s or "score12" in s]
    out.append(("no stored diploma, rent, or cohort-count fields",
                not leftover and not cell_counts and not diploma_rows and not meta.get("gaps"),
                f"{len(leftover)} communities, {len(cell_counts)} cells, {len(diploma_rows)} schools"))
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
        coffin = next((f for f in regular if "coffin" in f["properties"].get("name", "").lower()
                       and f["properties"].get("band") == "elem"), None)
        coffin_codes = [p.get("code") for p in (coffin or {}).get("properties", {}).get("places") or []]
        out.append(("Coffin zone includes Brentwood", coffin_codes == ["BRE"], ", ".join(coffin_codes) or "none"))
        scored_zones = [f["properties"].get("code") for f in zfeats if any(k in f["properties"] for k in ("school_score", "elem_score", "junior_score", "value_score"))]
        out.append(("zones are not coloured by a score", not scored_zones, f"{len(scored_zones)}"))
    ranked = [s for s in schools if "rank_exam" in s]
    out.append(("every school has a rank exam field", len(ranked) == len(schools), f"{len(ranked)}/{len(schools)}"))
    bad_rank = [s["name"] for s in schools if s.get("rank_score") is not None and not 0 <= s["rank_score"] <= 100]
    out.append(("rank scores within 0-100 or null", not bad_rank, f"{len(bad_rank)} out of range"))
    pat6 = [s for s in schools if s.get("rank_exam") == "pat6"]
    pat9 = [s for s in schools if s.get("rank_exam") == "pat9"]
    high = [s for s in schools if s.get("senior")]
    out.append(("elementary rank is grade 6 only", all(s["elem"] and not s["junior"] and not s["senior"] for s in pat6), f"{len(pat6)}"))
    out.append(("junior rank is grade 9, not high school", all(s["junior"] and not s["senior"] for s in pat9), f"{len(pat9)}"))
    out.append(("high schools are not ranked",
                all(s.get("rank_exam") is None and s.get("rank_score") is None for s in high) and len(high) >= 40,
                f"{len(high)}"))
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
    profiles_path = DATA / "community_profiles.json"
    if not profiles_path.exists():
        out.append(("community profiles exist", False, "missing community_profiles.json; run scripts/fetch_community_profiles.py"))
        return out
    profiles = json.loads(profiles_path.read_text(encoding="utf-8")).get("communities") or {}
    out.append(("community profiles cover most communities", len(profiles) >= 150, f"{len(profiles)}"))
    dalhousie = profiles.get("dalhousie") or {}
    out.append(("Dalhousie profile matches the 2021 PDF",
                dalhousie.get("population") == 8530 and dalhousie.get("median_household_income") == 85000
                and dalhousie.get("racialized_pct") == 38 and dalhousie.get("english_home_pct") == 78,
                f"pop {dalhousie.get('population')} income {dalhousie.get('median_household_income')}"))
    pct_fields = ("age_0_14_pct", "age_65_plus_pct", "shelter_30_pct", "immigrant_pct", "owner_pct",
                  "renter_pct", "racialized_pct", "english_home_pct", "bachelor_pct", "drive_pct", "transit_pct")
    bad_profile = [name for name, row in profiles.items()
                   if any(row.get(key) is not None and not 0 <= row[key] <= 100 for key in pct_fields)
                   or (row.get("population") is not None and row["population"] <= 0)
                   or (row.get("median_household_income") is not None and row["median_household_income"] <= 0)]
    out.append(("profile counts stay positive and percents stay in range", not bad_profile, f"{len(bad_profile)} bad"))
    assurance_path = DATA / "assurance.json"
    if not assurance_path.exists():
        out.append(("assurance survey exists", False, "missing assurance.json; run scripts/fetch_assurance.py"))
        return out
    assurance = json.loads(assurance_path.read_text(encoding="utf-8")).get("schools") or []
    survey_fields = ("education_quality", "parental_involvement", "learning_engagement",
                     "citizenship", "safe_caring", "access_supports")
    dal = next((row for row in assurance if row.get("name") == "Dalhousie School"), {})
    out.append(("Dalhousie Assurance survey matches the Fall 2025 table",
                dal.get("education_quality") == 89.7 and dal.get("parental_involvement") == 74.9
                and dal.get("year") == 2025,
                f"quality {dal.get('education_quality')} parents {dal.get('parental_involvement')}"))
    bad_survey = [row.get("name") for row in assurance if any(
        row.get(key) is not None and not 0 <= row[key] <= 100 for key in survey_fields)]
    with_quality = sum(1 for row in assurance if row.get("education_quality") is not None)
    out.append(("assurance percents stay in range", not bad_survey, f"{len(bad_survey)} bad"))
    out.append(("assurance survey covers most CBE schools", with_quality >= 100, f"{with_quality} with education quality"))
    return out


if __name__ == "__main__":
    results = run_checks()
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}  ({detail})")
    sys.exit(0 if all(ok for _, ok, _ in results) else 1)
