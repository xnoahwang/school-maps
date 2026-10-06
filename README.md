# Calgary school ranking (by PAT)

A local prototype for **immigrant / newcomer parents in Calgary** who know little about how schools and communities compare.

The page opens with a left sidebar, the school filter area, holding the ranking list. The map on the right draws one point for each school in that list. With every filter on All, that is every listed school. A board, grade, program, or search filter draws only the schools still in the list. Click a row, including the school name, to move the map to that school and open its card (official website, phone, address, board, grades, and score). The » control on a row slides in a panel over the list. A circled exclamation mark beside each figure opens a short definition. It lists the communities in that attendance zone, the median and the average of their 2026 assessed values, and the 2021 share of children and of families with children. A school with no published CBE attendance zone instead outlines the community its point falls in, and the panel says that outline is the community where the school is, not an attendance zone. `scripts/fetch_community_profiles.py` reads the City’s 2021 community-profile PDFs (the HTML pages only link to them) and the panel shows, for each community, population, age, 2020 median household income, owner and renter shelter costs, immigrant share, the largest racialized groups, languages spoken most often at home, bachelor’s degree share, and commute mode. Community crime counts are not in those PDFs, so that row says no data and links to the [Calgary Police community safety dashboard](https://www.calgarypolice.ca/transparency-and-accountability/community-safety-dashboard---monthly-snapshot.html). Click a point for the same card. The map then draws that school's CBE attendance zone, and the walk zone inside it. A regular program is used when the school has one; otherwise the program zone CBE publishes is used. The website row on the card links to that school's own site. A CBE school uses the site CBE publishes. Under that, every card links to CBE Find a School and says the official source is the final word. The school name itself is plain text. A missing website, phone, address, or zone is "no data".

- CBE schools are grouped by the grade range CBE publishes (K–6, 7–9, and the rest). Other schools are grouped by authority: Catholic, charter, francophone, other public boards, and private.
- A range that includes grade 9 is ranked on its **latest Grade 9 PAT** year. A range that includes grade 6 but not grade 9 is ranked on its **latest Grade 6 PAT** year.
- High schools are left off the list. There is no current school-level Diploma file, so they are not ranked and their grade 10–12 zones are not built.
- With the grade filter on All, Grade 6 and Grade 9 are separate lists. Grade 6 comes first, then Grade 9. Rank numbers start again for each exam, and the score cell names the grade.

The score is (% acceptable + % excellence) / 2 for that one year. It is not the three-year average used for the community figures in the tables below. Schools with no published result stay at the bottom and are not numbered. Hovering a score shows the two rates with the percent mark after the number, for example 达标率 96.5%. The circle beside the score heading opens this explanation and links to Alberta's [PAT results page](https://www.alberta.ca/provincial-achievement-tests#jumplinks-3), under Multiyear results (by school).

Filters are board, grade, and program. Each opens on All. Board and grade sit on one row. CBE grade options are the ranges that board publishes, such as K–6 and 7–9. Other schools use elementary, junior high, or unknown. The list can also filter by a CBE program name. `scripts/fetch_cbe_directory.py` refreshes the [CBE school directory](https://www.cbe.ab.ca/school-directory) (phone, address, website, grade span, and programs). Catholic, charter, francophone, and private schools are not in that directory, so their grade is the city's elementary or junior-high label. A phone or website the directory does not already have comes from Alberta's [school directory](https://open.alberta.ca/opendata/alberta-education-schools-and-authorities). `scripts/fetch_ab_contacts.py` refreshes that file. It does not invent a site the file left blank.

The page opens in English as Calgary school ranking (by PAT). The same title is 卡尔加里学校排名（按PAT）, 卡爾加里學校排名（按PAT）, Classement des écoles de Calgary (par PAT), カルガリー学校ランキング（PAT順）, and 캘거리 학교 순위 (PAT 기준). The menu also offers 简体中文, 繁體中文, Français, 日本語, and 한국어. CSSD zones are not drawn. Always confirm the designated school with the [CBE School Finder](https://www.cbe.ab.ca/find-a-school) and the [CSSD School Finder](https://www.cssd.ab.ca/schools).

Community scores, home values, amenities, and the optional review score are still built by the pipeline. They are not shown on this page. Their definitions are in the tables below.

Status: prototype. Code and comments are in English.

## Run

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # Windows: .venv\Scripts\pip
.venv/bin/python scripts/build_data.py          # optional: downloads into data/raw/ (cached), rewrites web/data/
python3 -m http.server 8765 -d web               # then open http://localhost:8765/
```

`web/data/` is committed, so the map runs with only the last command.

URL parameter (optional): `?lang=` with `en`, `zh`, `zh-Hant`, `fr`, `ja`, or `ko`. Without it, the page is English.

`build_data.py --refresh` re-downloads every source. Without it, files already in `data/raw/` are reused.

Reviews are optional and never required for the map:

```bash
# PowerShell. Skip (exit 0) when these are unset.
$env:GOOGLE_MAPS_API_KEY = "..."
$env:REDDIT_CLIENT_ID = "..."
$env:REDDIT_CLIENT_SECRET = "..."
.venv/Scripts/python scripts/fetch_reviews.py
```

## School data update

The page reads the JSON already in `web/data/`. It does not call CBE when you open it.

`scripts/update_schools.py` refreshes the CBE directory, Alberta phone and website file, and CBE zones. A file is replaced only when the new text differs. A source that fails or comes back empty keeps the file on disk. Home values are not downloaded. High-school diploma results are not fetched.

On this computer the update is scheduled weekly, Sunday at 09:00 local time, and runs after a missed start once the machine is on. Register it again with:

```bash
.venv/bin/python scripts/update_schools.py --install-task
```

The log is `data/raw/update_schools.log` (not committed).

## Verify

```bash
.venv/bin/python scripts/build_data.py && .venv/bin/python scripts/fetch_cbe_directory.py && .venv/bin/python scripts/fetch_ab_contacts.py && .venv/bin/python scripts/verify.py && .venv/bin/python scripts/fetch_reviews.py
```

On Windows, use `.venv\Scripts\python` instead of `.venv/bin/python`. `verify.py` exits 0 when the data checks pass. `fetch_reviews.py` exits 0 when the API keys are unset.

## How the numbers are made (simple on purpose)

| Field | Definition |
|---|---|
| School PAT % acceptable / % excellence | "% Acc of Enrol" and "% Exc of Enrol" from the Alberta PAT school multi-year file. Averaged over every regular course in the grade (Knowledge & Employability courses excluded) and over the latest **3 years with data (2023, 2024, 2025)**. Suppressed `n/a` cells are skipped and never counted as 0. |
| School score (0–100) | (% acceptable + % excellence) / 2 |
| Rank score | The same formula on the **newest year only**, for the exam at the school's top grade: Grade 6 PAT (`rank_exam=pat6`), Grade 9 PAT (`pat9`), or Diploma (`diploma`, currently null). See `rank_score` and `rank_year` on each school. |
| Community elementary / junior score | Mean of grade 6 (or grade 9) school scores across the community's nearby schools that offer that level and have PAT data |
| Community school score | Mean of the elementary and junior scores. If only one exists, that one is used. |
| Home value | Median `assessed_value` of residential accounts with a building (class RE, property type LI) in the 2026 roll. Shown as no data when the community has fewer than 50 such accounts. |
| Value for money (0–100) | (school-score percentile − home-value percentile + 100) / 2. 50 means the price matches the school results; above 50 means better schools than the price suggests. |
| Amenities | Counts of libraries, ACTIVE transit stops, and park sites (by representative point) inside the community boundary |
| Rent | **Not available.** No open per-community rent data exists (CMHC publishes by zone only), so the field is `null` and nothing is estimated. A zone figure is not shown as a community figure. |
| Children 0–14 | 2021 census share of household population age 0–14 (`f9wk-wej9`). |
| Families with children | 2021 census: (married with children + common-law with children + one-parent families) / census families (`msjx-5ygv`). |
| Assessed-value change | Percent change from the 2025 median to the 2026 median. Both use class RE, property type LI, and at least 50 accounts. |
| Enrolment | Headcount from Open Calgary `9qye-mibh` for the newest school year in that file (2023–2024 as of this build). This is not class size. |
| High-school score | **Not available.** No current school-level Diploma file. See Limitations. |
| Review score (0–100) | Optional. Bayesian-smoothed Google rating (prior 3.7, weight 10, then scaled from 1–5 onto 0–100). When a school also has at least 3 matched Reddit posts, 30% of the score is a word-list sentiment of those titles. Under 5 Google ratings and 3 Reddit posts, the UI says "too few reviews". Reviews are opinions, biased toward people who post, and are never mixed into the exam score. Google review text is not stored. Reddit stores post id, date and permalink only. |

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
| 2025 assessments | [4ur7-wsgc Historical Property Assessments (Parcel)](https://data.calgary.ca/d/4ur7-wsgc), roll year 2025, same RE/LI filter, median by community. | OGL – City of Calgary |
| 2021 census age | [f9wk-wej9 Population and Dwellings by Community](https://data.calgary.ca/d/f9wk-wej9) | OGL – City of Calgary |
| 2021 census families | [msjx-5ygv Families and Households by Community](https://data.calgary.ca/d/msjx-5ygv) | OGL – City of Calgary |
| Enrolment | [9qye-mibh School Enrolment Data](https://data.calgary.ca/d/9qye-mibh). Newest year in the file, not class size. | OGL – City of Calgary |
| CBE school directory | [cbe.ab.ca/school-directory](https://www.cbe.ab.ca/school-directory). Phone, address, website, grades, and programs. | CBE public pages |
| Alberta school contacts | [Schools and authorities](https://open.alberta.ca/opendata/alberta-education-schools-and-authorities), file as of 2026-10-04. Phone and website only, and only when the school does not already have them. | OGL – Alberta |
| CBE attendance and walk zones | KMZ files loaded by the public [CBE School Finder](https://www.cbe.ab.ca/find-a-school). `scripts/build_zones.py` writes `web/data/zones.geojson`. | CBE public pages |
| Basemap | © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors (ODbL), standard tile server. For anything beyond prototype traffic, follow the OSM tile usage policy or self-host. | ODbL |

As-of dates for the Open Calgary and PAT downloads are in `web/data/meta.json` (`sources.*.as_of`). The Alberta contacts file date is in `web/data/ab_contacts.json`. Sources that were checked and not used are in `meta.json → gaps`.

## Limitations

- Clicking a school draws the attendance area and walk zone CBE publishes. With the program filter on All, a school that has a regular program uses that zone; otherwise it uses the program zone CBE publishes. A chosen program uses that program's zone when the school has one. Schools with no CBE zone, including CSSD, charter, and private schools, show "no data" and no polygon. CSSD zones are not in the file. The community scores in the data still treat nearby schools as an approximation, and that choropleth is not on this page.
- PAT data covers grades 6 and 9 only. Schools that end before grade 6 (for example K–4) have no PAT score. **High-school Diploma results are not included**: no school-level Diploma XLSX newer than 2015/16 was found (the alberta.ca URL returns 404, and open.alberta.ca lists only 2015/16). Current per-school multiyear PDFs are embargoed for school-authority use until Alberta lifts the embargo, so they are not downloaded.
- PAT match: 372 of 423 elementary or junior-high schools in the City list (87.9%) are matched by board and normalised name. 299 of the 322 CBE/CSSD-named schools in the PAT file (92.9%) are matched. Most unmatched City schools are K–4/K–5 schools or private schools that do not appear in the PAT file. See `web/data/meta.json → stats`.
- Small cohorts make PAT averages noisy. The number of non-suppressed cells is kept per school (`n_cells` in `schools.json`) but not yet shown in the UI.
- Assessed value is not the same as market price, and the median mixes houses and condos.
- Calgary Equity Index is not included. The 2024 release (`i6pu-a35d`) is a PDF/zip, and `hy6b-89wc` returns no rows.
- Community crime is not included. `78gh-n26t` requires a login. The open table `848s-4m4z` ends in 2019 and its methodology was retired.
- 2021 census income and language by community were not found on Open Calgary. The 2016 income table was not used because it is too old to present as current.
- Class size is not published in `9qye-mibh` or in the CBE 2025–26 enrolment report. CBE programs come from the public directory API. CSSD programs, lottery-only flags, and overflow schools are still not listed.
- Test scores reflect demographics as much as teaching quality. They are only one input for families. Reviews, when loaded, are opinions and are labelled separately.

## Layout

```
scripts/build_data.py   data pipeline (download + cache + scoring) -> web/data/
scripts/build_zones.py  CBE attendance and walk zones, per published program -> web/data/zones.geojson
scripts/verify.py       data sanity checks
scripts/fetch_cbe_directory.py  CBE directory -> web/data/cbe_directory.json
scripts/fetch_ab_contacts.py  Alberta school phone and website -> web/data/ab_contacts.json
scripts/update_schools.py  refresh directory, contacts, and zones; write only if changed
scripts/fetch_reviews.py  optional Google/Reddit reviews -> web/data/reviews.json (skips without keys)
scripts/fetch_community_profiles.py  2021 census fields from City profile PDFs -> web/data/community_profiles.json
web/index.html, app.js, i18n.js, style.css   static front end (Leaflet via unpkg CDN)
web/data/               generated, committed so the site runs without a rebuild
data/raw/               download cache (large, not committed)
PLAN.md                 current plan / verify record
progress.md             working log
```
