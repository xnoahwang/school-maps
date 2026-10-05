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
SCORE_KEYS = ("elem_score", "junior_score", "school_score", "value_score")


def run_checks() -> list[tuple[str, bool, str]]:
    """Return (check name, passed, detail) tuples; missing files fail the first check."""
    files = [DATA / n for n in ("communities.geojson", "schools.json", "meta.json")]
    missing = [f.name for f in files if not f.exists()]
    if missing:
        return [("output files exist", False, f"missing {missing}; run scripts/build_data.py")]
    feats = json.loads(files[0].read_text())["features"]
    schools = json.loads(files[1].read_text())
    stats = json.loads(files[2].read_text())["stats"]
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
    return out


if __name__ == "__main__":
    results = run_checks()
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}  ({detail})")
    sys.exit(0 if all(ok for _, ok, _ in results) else 1)
