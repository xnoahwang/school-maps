# PLAN.md

## Plan

Mode: `autonomous` (from `.cursor/cursor-prime-cloud-mode`). No PR is opened, so the plan lives here.
Design notes: skipped (the brief from Noah was concrete and file-level).

**Goal.** A local prototype in `/workspace/school-map/` that helps immigrant parents in Calgary compare residential communities by nearby school results (Alberta PAT, grade 6 and grade 9) and median assessed home value. It shows a choropleth map, a sortable table, a detail panel, and an English / 简体中文 toggle. `scripts/build_data.py` rebuilds every number from public sources.

**Approach.**
1. `scripts/build_data.py` downloads public sources into `data/raw/` and reuses that cache. It then writes `web/data/communities.geojson`, `web/data/schools.json`, and `web/data/meta.json`.
2. PAT score: for each school and grade, average "% Acc of Enrol" and "% Exc of Enrol" over the non-K&E courses in the latest 3 years that have data (2023–2025). Suppressed `n/a` cells are skipped and never count as 0. School score = 0.5·%acceptable + 0.5·%excellence, on a 0–100 scale.
3. "Nearby schools" approximation for a community: schools inside its boundary, plus the nearest school offering each level (elementary, junior high, senior high) measured from the community's representative point. This is not the official catchment.
4. Community scores: the elementary score is the mean grade-6 score of nearby schools that teach elementary and have PAT data. The junior score is the same idea with grade 9. Missing data stays `null`.
5. Home value: median `assessed_value` of residential accounts that have a building (class RE, property type LI) in the 2026 parcel roll (4bsw-nn7w), grouped by `comm_code`.
6. Value for money: the combined school score's percentile rank minus the home value's percentile rank, rescaled to 0–100 (50 means school quality matches price).
7. Amenities: counts per community of libraries, active transit stops, and parks (park sites whose representative point falls inside the community).
8. `web/`: a static site (Leaflet with Carto/OSM tiles, no API keys), served with `python -m http.server`.
9. `scripts/screenshot.py` uses Playwright Chromium to take the screenshots.

**Assumptions (stated instead of asked).**
- `ab7m-fwn6` is a Socrata *map view* whose API returns empty features. Its backing dataset `surr-xmvs` (Community District Boundaries, same update time) is used instead. `xmep-aasr` and `i9fu-gjqj` are also map views. Their backing datasets are `fd9t-tdn2` (schools) and `kami-qbfh` (parks).
- `p84b-7zbi` (Assessments by Community) contains only roll years 2016–2017. It is too old for house prices, so the 2026 parcel roll `4bsw-nn7w` is used.
- No Diploma school-level XLSX newer than 2015/16 could be found (the alberta.ca URL returns 404, and open.alberta.ca only lists 2015/16). Diploma results are skipped.
- Equity Index `hy6b-89wc` is a map view, and the 2024 release is a file attachment. Skipped as optional.
- Rent: no open per-community source exists. The field `rent` is `null`, and the UI says "not available".

**Out of scope.** Pushing to or creating any GitHub remote. Official catchment designations. Rent estimates. Diploma results. Equity Index. Authentication, backend, and tests beyond the verify script. Committing the `submission/` docs, `data/raw/` (large cached downloads), or `.cursor/cursor-prime-cloud-backups/`. Mandatory TDD, worktrees, and subagent runs.

**Done when.**
- `python scripts/build_data.py` exits 0 and prints counts and the PAT match rate.
- `python scripts/verify.py` passes: output files exist, there are at least 150 residential communities, the PAT match rate is printed, scores are within 0–100 or null, and no suppressed value is turned into 0.
- The site served at `http://localhost:8765/web/` renders, and two screenshots exist in `screenshots/`: the map colored by school score, and a clicked community panel in Chinese.
- Maintainability tier C: file headers and docstrings, a truthful README and AGENTS.md, and `.cursor/rules/project.mdc` filled in.
- A local git commit exists, with no remote.

**Max iterations.** 8. **Scale.** single-context. **Maintainability tier.** C.

**Pre-flight file list.**
- create `PLAN.md`, `README.md`, `requirements.txt`, `progress.md`
- create `scripts/build_data.py`, `scripts/verify.py`, `scripts/screenshot.py`
- create `web/index.html`, `web/app.js`, `web/style.css`, `web/i18n.js`
- generated: `web/data/communities.geojson`, `web/data/schools.json`, `web/data/meta.json`, `screenshots/*.png`
- modify: `AGENTS.md` (outside the cursor-prime-cloud markers only), create `.cursor/rules/project.mdc`
- cache (not committed): `data/raw/*`
- installed by cursor-prime-cloud (committed unmodified): `.cursor/rules/*`, `.cursor/commands/*`, `.cursor/cursor-prime-cloud-*`

**Pattern grounding.** Greenfield, with no existing code conventions. Established conventions:
- Python 3 standard library plus requests, pandas, openpyxl, and shapely.
- snake_case names, a module docstring header, and docstrings on public functions.
- Errors: a failed optional source logs a warning and sets the related fields to null. A failed required source (boundaries, schools, PAT) aborts with a non-zero exit.
- Front end: vanilla JS, no build step.
- Recorded in `AGENTS.md` and `.cursor/rules/project.mdc`.

**Verify.**
```bash
.venv/bin/python scripts/build_data.py
.venv/bin/python scripts/verify.py
.venv/bin/python scripts/screenshot.py   # starts http.server itself, writes screenshots/
git status --short && git remote -v      # remote list must be empty
```

**Edge cases.**
- `build_data.py`: if the raw cache is missing it downloads. If a download fails, a required source exits 1 and an optional source becomes null fields plus a warning. Malformed numbers or `n/a` are parsed as None. Scale: about 570k parcel rows streamed through pandas, which takes a few seconds.
- `verify.py`: missing output means FAIL with a message and exit 1.
- `screenshot.py`: if the port is busy or Chromium is missing, it raises with the reason.
- Front end: a missing metric shows "no data" in gray, never 0.

## Verify

Run on 2026-10-04, box local time (MDT).

```
$ bash /tmp/cpc/install.sh --mode autonomous /workspace/school-map   # re-run after the AGENTS.md project section was added
[cursor-prime-cloud] Updated: 0  Unchanged: 13
$ .venv/bin/python scripts/build_data.py
 "communities_residential": 223, "schools_total": 506, "schools_elem_or_junior": 423,
 "pat_matched": 372, "pat_match_rate": 0.879 (board+name 366, name-only 6),
 "cbe_cssd_pat_schools": 322, "cbe_cssd_pat_schools_matched": 299,
 "communities_with_school_score": 218, "communities_with_home_value": 215
PAT years averaged: [2023, 2024, 2025]; failed sources: none
$ .venv/bin/python scripts/verify.py
PASS  output files exist  (3 files)
PASS  >=150 residential communities  (223)
PASS  scores within 0-100 or null  (0 out of range)
PASS  every PAT value backed by >=1 non-suppressed cell  (0 unbacked)
PASS  no school score without PAT data  (0)
PASS  PAT match rate reported  (372/423 = 0.879)
PASS  rent left null (no source)  (all null)
PASS  home values present for >=90% communities  (215/223)
$ .venv/bin/python scripts/screenshot.py
wrote a_map_school_score_en.png b_community_panel_zh.png
```

Changes made during the build, beyond the original plan:
- Fixed a NaN bug: pandas `map` returns NaN rather than None. The JSON writer now uses `allow_nan=False`.
- Medians with fewer than 50 accounts are now treated as no data. University of Calgary showed $13.9M from a handful of accounts.
- Carto keyless tiles showed an "API key required" watermark, so the map now uses standard OSM tiles.
- Restored the mis-encoded "¿" in the City's school names.
- The verify check was changed from "no zero scores" to "every value is backed by a real cell". Dr. Oakley School genuinely publishes 0.0.
