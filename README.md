# Calgary School & Community Explorer (prototype)

A local prototype for **immigrant / newcomer parents in Calgary** who know little about how schools and communities compare. It shows every residential community as a choropleth map and a sortable list, coloured by one of these metrics:

- **School score**: Alberta Provincial Achievement Test (PAT) results of the community's *nearby* schools. Grade 6 (elementary) and grade 9 (junior high) are scored separately and combined.
- **Median assessed home value**: 2026 City of Calgary property assessment roll.
- **Value for money**: the school score compared with the price.

Click a community to see its nearby schools (board, grades, PAT % acceptable / % excellence and the years they come from), its home value, amenity counts, and source links. The UI switches between English and 简体中文.

> ⚠️ **Catchments are approximated.** Official attendance areas are not open data. "Nearby schools" means schools located inside the community, plus the nearest elementary, junior high, and senior high school by straight-line distance. Always confirm the designated school with the [CBE School Finder](https://www.cbe.ab.ca/find-a-school) and the [CSSD School Finder](https://www.cssd.ab.ca/schools).

Status: prototype. Code and comments are in English.

**Read first:** [`docs/PROJECT_BRIEF.md`](docs/PROJECT_BRIEF.md) explains why this exists, who it is for, how it differs from FamilyRoost, and the roadmap. [`docs/CURSOR_PROMPT.md`](docs/CURSOR_PROMPT.md) is the ready-to-use prompt for the next development phase (fresher data, plus Reddit and Google Maps reviews).

## Run

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # Windows: .venv\Scripts\pip
.venv/bin/python scripts/build_data.py          # optional: downloads into data/raw/ (cached), rewrites web/data/
python3 -m http.server 8765 -d web               # then open http://localhost:8765/

`web/data/` is committed, so the map runs with only the last command.
```

URL parameters (optional): `?lang=zh`, `?metric=school_score|elem_score|junior_score|home_value|value_score`, `?community=VAR` (community code).

`build_data.py --refresh` re-downloads every source. Without it, files already in `data/raw/` are reused.

## Verify

```bash
.venv/bin/python scripts/build_data.py    # prints counts + PAT match rate, exit 0
.venv/bin/python scripts/verify.py        # PASS/FAIL data checks, exit 0 when all pass
.venv/bin/python scripts/screenshot.py    # serves web/ on :8765, writes screenshots/*.png (needs Chrome or `playwright install chromium`)
```

## How the numbers are made (simple on purpose)

| Field | Definition |
|---|---|
| School PAT % acceptable / % excellence | "% Acc of Enrol" and "% Exc of Enrol" from the Alberta PAT school multi-year file. Averaged over every regular course in the grade (Knowledge & Employability courses excluded) and over the latest **3 years with data (2023, 2024, 2025)**. Suppressed `n/a` cells are skipped and never counted as 0. |
| School score (0–100) | (% acceptable + % excellence) / 2 |
| Community elementary / junior score | Mean of grade 6 (or grade 9) school scores across the community's nearby schools that offer that level and have PAT data |
| Community school score | Mean of the elementary and junior scores. If only one exists, that one is used. |
| Home value | Median `assessed_value` of residential accounts with a building (class RE, property type LI) in the 2026 roll. Shown as no data when the community has fewer than 50 such accounts. |
| Value for money (0–100) | (school-score percentile − home-value percentile + 100) / 2. 50 means the price matches the school results; above 50 means better schools than the price suggests. |
| Amenities | Counts of libraries, ACTIVE transit stops, and park sites (by representative point) inside the community boundary |
| Rent | **Not available.** No open per-community rent data exists (CMHC publishes by zone only), so the field is `null` and nothing is estimated. |

Any missing input gives "no data" (grey), never zero. A real published 0.0 (for example, a small specialised school) is kept as published.

## Data sources and licences

| Data | Source | Licence |
|---|---|---|
| Community boundaries (residential only) | [surr-xmvs Community District Boundaries](https://data.calgary.ca/d/surr-xmvs). The `ab7m-fwn6` map view returns empty features through the API, so its backing dataset is used. | [Open Government Licence – City of Calgary](https://data.calgary.ca/d/Open-Data-Terms/u45n-7awa) |
| Schools (location, board, grades) | [fd9t-tdn2 Schools](https://data.calgary.ca/d/fd9t-tdn2). `xmep-aasr` "Schools in Communities" is a map view whose API returns empty rows. | same |
| PAT results by school | [Alberta Education ed-pat-multiyear-sch-list.xlsx](https://www.alberta.ca/system/files/custom_downloaded_images/ed-pat-multiyear-sch-list.xlsx) | [Open Government Licence – Alberta](https://open.alberta.ca/licence) |
| Home values | [4bsw-nn7w Current Year Property Assessments (Parcel)](https://data.calgary.ca/d/4bsw-nn7w). `p84b-7zbi` "Assessments by Community" only covers 2016–2017, so it is not used. | OGL – City of Calgary |
| Libraries | [m9y7-ui7j](https://data.calgary.ca/d/m9y7-ui7j) | OGL – City of Calgary |
| Transit stops | [muzh-c9qc](https://data.calgary.ca/d/muzh-c9qc) | OGL – City of Calgary |
| Parks | [kami-qbfh Parks Sites](https://data.calgary.ca/d/kami-qbfh). This is the dataset behind the `i9fu-gjqj` map view. | OGL – City of Calgary |
| Basemap | © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors (ODbL), standard tile server. For anything beyond prototype traffic, follow the OSM tile usage policy or self-host. | ODbL |

## Limitations

- **The catchment is an approximation**, not the official CBE or CSSD designation. Programs of choice, French immersion, and Catholic eligibility are not modelled.
- PAT data covers grades 6 and 9 only. Schools that end before grade 6 (for example K–4) have no PAT score. **High-school Diploma results are not included**: no school-level Diploma XLSX newer than 2015/16 was found (the alberta.ca URL returns 404, and open.alberta.ca lists only 2015/16).
- PAT match: 372 of 423 elementary or junior-high schools in the City list (87.9%) are matched by board and normalised name. 299 of the 322 CBE/CSSD-named schools in the PAT file (92.9%) are matched. Most unmatched City schools are K–4/K–5 schools or private schools that do not appear in the PAT file. See `web/data/meta.json → stats`.
- Small cohorts make PAT averages noisy. The number of non-suppressed cells is kept per school (`n_cells` in `schools.json`) but not yet shown in the UI.
- Assessed value is not the same as market price, and the median mixes houses and condos.
- Calgary Equity Index and census context are not included (the Equity Index `hy6b-89wc` is a map view, and its 2024 release is a file attachment).
- Test scores reflect demographics as much as teaching quality. They are only one input for families.

## Layout

```
scripts/build_data.py   data pipeline (download + cache + scoring) -> web/data/
scripts/verify.py       data sanity checks
scripts/screenshot.py   headless screenshots -> screenshots/
web/index.html, app.js, i18n.js, style.css   static front end (Leaflet via unpkg CDN)
web/data/               generated, committed so the site runs without a rebuild
data/raw/               download cache (large, not committed)
PLAN.md                 plan / verify record (cursor-prime-cloud autonomous mode)
docs/PROJECT_BRIEF.md   why / who / direction / risks
docs/CURSOR_PROMPT.md   prompt for the next Cursor agent phase
```
