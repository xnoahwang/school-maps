# PLAN.md

## Plan (2026-10-05, two-level grade filter)

Mode: `autonomous`. Design notes: the grade control is two dropdowns. The first is the authority, including All. The second lists only the grades that authority actually has.

**Goal.** Replace the single grouped dropdown with a board dropdown and a grade dropdown. All is the first board option. Choosing a board rebuilds the grade options. CBE still offers its published ranges. Other boards offer elementary, junior high, and unknown only when that board has those schools.

**Assumptions.**
- The page still opens on CBE and K–6.
- All grades under one board, or All boards, mixes Grade 6 and Grade 9, so that view is not one ranking. The score stays, with the grade marked beside it.
- High schools stay off the list.

**Out of scope.** Splitting private operators, Diploma scores, the map, commits.

**Done when.** Choosing Catholic shows only Catholic grade options. Choosing All shows every non-high-school group. K–6 is unchanged.

**Pre-flight.** `PLAN.md`, `progress.md`, `README.md`, `web/index.html`, `web/i18n.js`, `web/app.js`, `scripts/screenshot.py`.

**Verify.** Reload the page. Check All, Catholic elementary, and CBE K–6.

## Plan (2026-10-05, authority groups)

Mode: `autonomous`. Design notes: split schools that are not in the CBE directory by the authority the city file names.

**Goal.** Group the grade dropdown by authority: CBE grade ranges, Catholic (CSSD), charter, francophone, other public boards, and private. Inside each non-CBE group, elementary and junior high stay separate so Grade 6 and Grade 9 are not one list.

**Assumptions.**
- Charter means the board name contains “Charter”, plus Calgary Girls' School Society, Calgary Arts Academy Society, Almadina School Society, STEM Innovation Academy Society, and Alberta Classical Academy Ltd.
- Other public boards are Palliser, Pembina Hills, and Prairie Land, matched by “School Division” or “Education Region”.
- Rows with no board are post-secondary campuses and stay off the list.
- High schools stay off the list.

**Out of scope.** Diploma scores, the map, commits.

**Done when.** Catholic elementary and private elementary are different options. K–6 is unchanged.

**Pre-flight.** `PLAN.md`, `progress.md`, `README.md`, `web/i18n.js`, `web/app.js`, `web/index.html`.

**Verify.** Reload the page. Check Catholic elementary, private elementary, and K–6.

## Plan (2026-10-05, note for schools outside the CBE directory)

Mode: `autonomous`. Design notes: the dropdown label “不在 CBE 目录” needs a remark on the page.

**Goal.** Show a short note under the grade dropdown, in English and 简体中文, saying those options are Catholic and private schools. The CBE directory lists only its own schools, so these come from the city list and only have elementary or junior high, not a range such as K–6.

**Out of scope.** Changing which schools are in those groups, the map, commits.

**Done when.** The note is visible on the Chinese page without opening the dropdown.

**Pre-flight.** `PLAN.md`, `web/index.html`, `web/i18n.js`, `web/style.css`.

**Verify.** Reload http://127.0.0.1:8765/?lang=zh and read the note.

## Plan (2026-10-05, one grade control)

Mode: `autonomous`. Design notes: the grade-range dropdown and the K–9 checkboxes overlap. The dropdown is the one that matches how CBE lists a school.

**Goal.** Remove the grade checkboxes. Keep the dropdown of real CBE grade ranges. Split schools that are not in the CBE directory into elementary and junior high, so those two scores are not sorted on one list.

**Assumptions.**
- Program, letter, and search still narrow the selected range.
- A non-CBE school with no grade span and no PAT is listed under “grade unknown”, by name.
- High schools stay off the list.

**Out of scope.** Diploma scores, the map, commits.

**Done when.** No grade checkboxes. K–6 and 4–9 are unchanged. Elementary and junior high outside the CBE directory are separate options.

**Pre-flight.** `PLAN.md`, `progress.md`, `README.md`, `web/index.html`, `web/i18n.js`, `web/app.js`, `web/style.css`.

**Verify.** Reload the page. Check K–6, 4–9, the two non-CBE options, Early French Immersion, and a high-school search.

## Plan (2026-10-05, grade ranges, no high school)

Mode: `autonomous`. Design notes: classify by the grade range a school actually teaches, and drop high schools while Diploma results are not public.

**Goal.** Replace the three exam tabs with the grade ranges published in the CBE directory (K–6, K–5, 6–9, 7–9, and the rest). Rank a range that includes grade 9 on the latest Grade 9 PAT, and a range that includes grade 6 but not grade 9 on the latest Grade 6 PAT. Omit every school that teaches grade 10 or above.

**Assumptions.**
- The default range is K–6.
- Schools that are not in the CBE directory (mostly Catholic and private) stay in their own group. High schools in that group are still omitted.
- A range that reaches neither grade 6 nor grade 9 (K–4, K–3, K–2) is listed by name, with no score.
- Grade checkboxes stop at 9. Program, letter, and search still narrow the selected range.

**Out of scope.** Diploma scores, the map, CSSD directory, commits.

**Done when.** The page has no high-school tab and no high-school rows. K–6 ranks on Grade 6. 6–9 ranks on Grade 9.

**Pre-flight.** `PLAN.md`, `progress.md`, `README.md`, `web/index.html`, `web/i18n.js`, `web/app.js`, `scripts/screenshot.py`.

**Verify.** Reload the page. K–6, 6–9, and K–4 show the right schools. Searching a high school returns nothing.

## Plan (2026-10-05, CBE directory filters)

Mode: `autonomous`. Design notes: the user wants the public CBE school directory, including its filters, on this page so a parent does not have to leave for cbe.ab.ca.

**Goal.** Load the same public records the [CBE school directory](https://www.cbe.ab.ca/school-directory) uses. Match them onto our schools, add the directory schools the City file does not have, and filter the list by program, grade (K–12), and letter, the way that directory does.

**Assumptions.**
- Source is the public fragment API (`school_profile_fragment` and `program_fragment`), not a scrape of the rendered page. Schools with `hidden` = 1 are omitted, matching the directory.
- Program names marked `hidden-everywhere` are dropped. `hidden-in-search-only` stays on the school row and out of the dropdown.
- A grade checkbox matches a school when that grade falls inside the span the directory uses (the school's own grades plus each program's grades).
- Choosing a program or a grade lists matching schools from every rank tab together. With those filters off, the elementary / junior / high-school tabs work as they do now.
- Name aliases: Alexander Ferguson = Alex Ferguson, Arbour Lake = Arbour Lake Middle, Home Education = Calgary Home Education.
- CSSD programs, lottery, and overflow stay out. This is the CBE directory only.

**Out of scope.** Map, Diploma scores, CSSD directory, principal login ids.

**Done when.** `web/data/cbe_directory.json` contains the directory schools, including Evanston Heights, Piitoayis Family School, and Windsor Park. The page can filter by program and grade. `verify.py` passes.

**Pre-flight.** `scripts/fetch_cbe_directory.py` (new), `scripts/verify.py`, `scripts/build_data.py` (gap text only), `web/app.js`, `web/index.html`, `web/i18n.js`, `web/style.css`, `web/data/cbe_directory.json`, `web/data/meta.json`, `README.md`, `AGENTS.md`, `.cursor/rules/project.mdc`, `PLAN.md`, `progress.md`.

**Verify.** `.venv/Scripts/python scripts/fetch_cbe_directory.py` then `scripts/verify.py`, then the filters in the browser.

## Plan (2026-10-05, school rank list)

Mode: `autonomous`. Design notes: the user wants the map set aside. Rank schools by the latest exam at the highest grade the school offers.

**Goal.** The page opens on a ranked school list. Elementary-only schools use the newest Grade 6 PAT year. Schools that go through grade 9 and do not offer high school use the newest Grade 9 PAT year, not a blend with Grade 6 and not the three-year average. High schools are listed and not scored, because no current Diploma file is public.

**Assumptions.**
- "Latest" means that school's newest year with a published number, shown on the row. It is not the 2023–2025 average already stored as `score6` / `score9`.
- A school that offers high school (including K–12) is in the high-school list. Its Grade 9 result is not used as a substitute score.
- Schools with an unknown grade range are left off the list.
- The map markup stays in the page and is not shown.

**Out of scope.** Map changes, Diploma scraping, CSSD zones, mixing PAT 6 and PAT 9 into one ranking.

**Done when.** `schools.json` has `rank_exam`, `rank_score`, and `rank_year`; `verify.py` passes; the page lists elementary and junior-high schools in score order.

**Pre-flight.** `scripts/build_data.py`, `scripts/verify.py`, `web/index.html`, `web/app.js`, `web/i18n.js`, `web/style.css`, `web/data/schools.json`, `web/data/meta.json`, `README.md`, `PLAN.md`, `progress.md`, `scripts/screenshot.py`.

**Verify.** `.venv/Scripts/python scripts/build_data.py` then `scripts/verify.py`, then the list in the browser.

## Plan (2026-10-05, attendance zones)

Mode: `autonomous`. Design notes: the user asked for schools on by default, and for the map to be divided by CBE attending zone and walking zone rather than by community.

**Goal.** Open with school markers visible. The default map is CBE regular-program attendance areas (the designated zone), with walk zones drawn inside them, so a parent compares zones rather than community polygons. The community view stays available.

**Assumptions.**
- Only the CBE Regular program. Alternative programs (French immersion, IB, bilingual) have different zones and are not the designated regular school.
- CSSD does not publish the same file set here, so Catholic zones are not drawn.
- Zone home value is the median of the community medians whose representative point falls inside the zone, labelled as such.
- Zone files are the KMZ documents the public CBE finder already loads (`/sys/api/query` plus `/documents/...kmz`). They are cached under `data/raw/` and not committed.

**Out of scope.** CSSD zones, alternative-program zones, scraping the finder UI, inventing a boundary where a KMZ is missing.

**Done when.** `scripts/build_zones.py` writes `web/data/zones.geojson`, `verify.py` passes, schools start checked, and the zone view colours elementary attendance areas.

**Pre-flight.** `scripts/build_zones.py` (new), `scripts/verify.py`, `web/index.html`, `web/app.js`, `web/i18n.js`, `web/data/zones.geojson`, `README.md`, `PLAN.md`.

**Verify.** `.venv/Scripts/python scripts/build_zones.py` then `scripts/verify.py`.

## Plan (2026-10-05, next phase)

Mode: `autonomous`. Design notes: skipped — `docs/CURSOR_PROMPT.md` is the file-level brief. The user said go.

**Goal.** Refresh official data to the newest open release, record an as-of date for every source, and add a separate review layer that never mixes into the exam score. Missing sources stay null and are explained.

**Assumptions.**
- A metric goes in the picker even when every value is null (high-school score), with the reason in the panel, README, and `meta.json`.
- Diploma: the public school-level XLSX is still 2015/16 (`education.alberta.ca/.../diploma-multiyear-sch-list-annual.xlsx`). The alberta.ca-style current URL 404s. Per-school 2024/25 PDFs are embargoed for authority use until the embargo is lifted, so they are not downloaded.
- Equity Index 2024 (`i6pu-a35d`) is a PDF/zip blob. `hy6b-89wc` returns no rows. Not parsed from map images.
- Crime: `78gh-n26t` requires a login. `848s-4m4z` ends in 2019 and the methodology was retired. Not used.
- Rent stays null. CMHC is zone-level and there is no community-to-zone crosswalk.
- No 2021 community income or language table on Open Calgary. The 2016 income table is too old to show as current.
- Class size is not in `9qye-mibh` (enrolment by grade, through 2023-2024). The CBE 2025-26 report says it does not include class size.
- Alternative programs, lotteries, and overflow have no single open table. Board HTML is not scraped.
- 2025 vs 2026 home-value change uses the same filter on both rolls: class RE, property type LI, median, at least 50 accounts.
- Context that does exist: 2021 census share of residents age 0–14 (`f9wk-wej9`) and census families with children (`msjx-5ygv`).
- Reviews: `scripts/fetch_reviews.py` exits 0 without API keys and does not write a file. Google stores place id, rating, and count only. Reddit stores id, date, permalink, and a lexicon sentiment, not post text.

**Out of scope.** Paid data, scraping MLS, the CPS dashboard, or Google Maps HTML. User accounts. Deployment. Value-added scores, parent-set weights, address-level lookup, listings, official catchments.

**Done when.**
- `scripts/build_data.py` and `scripts/verify.py` exit 0, with checks for the new fields.
- `meta.json` lists every source with an as-of date (or a gap note when there is no date).
- `fetch_reviews.py` with no keys prints SKIP and exits 0.
- README data table and limitations match what was actually added.
- Screenshots refreshed if Chrome/Playwright can start.

**Scale.** workflow-scale, one pass. **Maintainability tier.** C for `fetch_reviews.py`; B for edits to existing files.

**Pre-flight file list.**
- modify: `PLAN.md`, `scripts/build_data.py`, `scripts/verify.py`, `web/index.html`, `web/app.js`, `web/i18n.js`, `README.md`, `AGENTS.md`, `progress.md`, `.cursor/rules/project.mdc`
- create: `scripts/fetch_reviews.py`
- generated: `web/data/*` (rewritten by the build)
- not committed: `data/raw/`

**Verify.**
```bash
.venv/Scripts/python scripts/build_data.py
.venv/Scripts/python scripts/verify.py
.venv/Scripts/python scripts/fetch_reviews.py
.venv/Scripts/python scripts/screenshot.py
```

## Verify (2026-10-05)

```
$ .venv/Scripts/python scripts/build_data.py
 communities_residential 223, pat_matched 372/423 = 0.879,
 communities_with_home_value 215, communities_with_home_value_prev 214,
 communities_with_children_pct 204, schools_with_enrolment 379 (2023-2024)
 PAT years [2023, 2024, 2025]; failed sources: none
$ .venv/Scripts/python scripts/verify.py
 16 PASS, exit 0
$ .venv/Scripts/python scripts/fetch_reviews.py
 SKIP no GOOGLE_MAPS_API_KEY or REDDIT_CLIENT_ID/REDDIT_CLIENT_SECRET; reviews not written
$ .venv/Scripts/python scripts/screenshot.py
 wrote a_map_school_score_en.png b_community_panel_zh.png
```

Browser check: `http://localhost:8765/?lang=zh&metric=children_pct` coloured the map by the 2021 census share and showed the new metric in the picker.

## Previous plan (prototype, 2026-10-04)

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
