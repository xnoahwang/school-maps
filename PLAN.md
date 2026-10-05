# PLAN.md

Older plans and verify receipts are in git history. This file keeps the current record only.

## Plan (2026-10-05, home-community notice)

Mode: `autonomous`. Design notes: skipped. The sentence under a school with no CBE zone is gray 12.5px body text, so it disappears under the school name.

**Goal.** That sentence sits in a tinted callout at the top of the panel, larger and darker than the figure labels.

**Out of scope.** Rewording the sentence, changing the community outline, and a git commit.

**Done when.** On Master's Academy the Chinese sentence is in a visible callout, and Briar Hill’s zone panel has no such callout.

**Scale.** small

**Pre-flight.** `PLAN.md`, `web/app.js`, `web/style.css`, `web/index.html`.

**Verify.** Open the Chinese Master's Academy panel and read the callout.

## Verify (2026-10-05, home-community notice)

On the Chinese Master's Academy panel the sentence is a 15px bold callout on a cream background with an orange bar. Briar Hill’s panel was not given that class.


## Plan (2026-10-05, school community outline)

Mode: `autonomous`. Design notes: skipped. Master's Academy has no CBE attendance zone, so the panel only says so. The school point sits in Garrison Woods (`GAW`).

**Goal.** A school with no published CBE attendance zone draws the community its point falls in, and the panel names that community. A school that already has a zone is unchanged.

**Out of scope.** Inventing an attendance zone, drawing every community a private school might serve, and a git commit.

**Done when.** Opening Master's Academy draws Garrison Woods and the Chinese panel says the outline is the community where the school is, not a CBE zone. A school with no community match still shows the old “no zone” line.

**Scale.** small

**Pre-flight.** `PLAN.md`, `web/app.js`, `web/i18n.js`, `web/style.css`, `web/index.html`, `README.md`, `progress.md`.

**Verify.** Open the Chinese page, search Master's Academy, open its panel, and confirm Garrison Woods is drawn. `node --check web/app.js` and `node --check web/i18n.js`.

## Verify (2026-10-05, school community outline)

`node --check web/app.js` and `node --check web/i18n.js` both exited 0. On the Chinese page, Master's Academy draws Garrison Woods in green and the panel says the outline is the community where the school is. Briar Hill School still shows its CBE attendance zone and walk zone.


## Plan (2026-10-05, cut scores)

Mode: `autonomous`. Design notes: skipped. The score note names the acceptable and excellence rates, and does not say where those lines sit. They are not a fixed 60 and 90.

**Goal.** The score note says the acceptable cut is not a fixed 60 and is often near half the marks, and the excellence cut is not a fixed 90 and is often just above 80 on a test out of 100. Both languages.

**Out of scope.** Publishing a cut score for every subject and year, changing the score formula, and a git commit.

**Done when.** The Chinese score note answers the 60 / 90 question with those approximate lines, and says the exact line moves by subject and year.

**Scale.** small

**Pre-flight.** `PLAN.md`, `web/i18n.js`, `web/style.css`, `web/index.html`.

**Verify.** `node --check web/i18n.js`, then open the Chinese score note and read the two lines.

## Verify (2026-10-05, cut scores)

`node --check web/i18n.js` exited 0. On the Chinese page the score note says the acceptable line is not a fixed 60 and is often near 50 on a test out of 100, and the excellence line is not a fixed 90 and is often just above 80.

## Plan (2026-10-05, acceptable and excellence)

Mode: `autonomous`. Design notes: skipped. The score mark explains the formula and does not say what the two rates are.

**Goal.** The score mark’s note defines the acceptable rate and the excellence rate, in both languages.

**Out of scope.** Changing how the score is calculated, and a git commit.

**Done when.** The Chinese score note says the acceptable rate is the share of enrolled students who met the acceptable standard, and the excellence rate is the share who met the higher standard.

**Scale.** small

**Pre-flight.** `PLAN.md`, `web/i18n.js`, `web/index.html`.

**Verify.** Open the Chinese page and read the score mark’s note.

## Verify (2026-10-05, acceptable and excellence)

`node --check web/i18n.js` exited 0. On the Chinese page the score mark opens a note that defines 达标率 as the share of enrolled students who met the acceptable standard, and 优秀率 as the share who met the higher standard of excellence.

## Plan (2026-10-05, zone communities by overlap)

Mode: `autonomous`. Design notes: skipped. Dr. E.W. Coffin draws an attendance zone and a walk zone, and the panel says no community was matched. The zone sits inside Brentwood, but Brentwood’s representative point is outside the zone, so the list stays empty.

**Goal.** A community is listed when the overlap is at least 10% of the zone or of the community. Coffin’s panel shows Brentwood.

**Out of scope.** Non-regular programs, which still keep an empty list and fall back to the regular zone, and a git commit.

**Done when.** The Coffin regular attendance feature includes Brentwood, and the Chinese panel shows that community.

**Scale.** small

**Pre-flight.** `PLAN.md`, `scripts/build_zones.py`, `scripts/verify.py`, `web/data/zones.geojson`, `web/app.js`, `web/index.html`.

**Verify.** `scripts/verify.py`, then open Dr. E.W. Coffin School’s panel.

## Verify (2026-10-05, zone communities by overlap)

`.venv\Scripts\python.exe scripts\verify.py` → PASS, including “Coffin zone includes Brentwood (BRE)”. The Chinese panel for Dr. E.W. Coffin School lists Brentwood, in the walk zone, assessed $684,000.

## Plan (2026-10-05, details follow the school)

Mode: `autonomous`. Design notes: skipped. The zone panel stays on school A when another school is clicked. A row click still must not open that panel when it is closed.

**Goal.** While the zone panel is open, clicking school B in the list or on the map switches the panel to B. A click while it is closed leaves it closed.

**Out of scope.** Opening the panel from a row click, and a git commit.

**Done when.** Briar Hill’s open panel changes to the next school’s name after that row is clicked, and stays closed after it is closed and another row is clicked.

**Scale.** small

**Pre-flight.** `PLAN.md`, `web/app.js`, `web/index.html`.

**Verify.** In the browser, open one school’s panel, click another row, then close it and click a row again.

## Verify (2026-10-05, details follow the school)

`node --check web/app.js` exited 0. In the Chinese page, the open panel moved from Master’s Academy to Rundle College Elementary School when that row was clicked, and stayed closed after Close when Calgary Classical Academy was clicked.

## Plan (2026-10-05, close button)

Mode: `autonomous`. Design notes: skipped. The zone-panel Close button is white on white, so it disappears into the header.

**Goal.** That button is red with white text.

**Out of scope.** Other buttons, and a git commit.

**Done when.** The open zone panel shows a red Close button with white text.

**Scale.** small

**Pre-flight.** `PLAN.md`, `web/style.css`, `web/index.html`.

**Verify.** Open a zone panel and look at the Close button.

## Verify (2026-10-05, close button)

Browser at `http://127.0.0.1:8765/?lang=en&v=50`. The Briar Hill panel Close button is `rgb(180, 35, 24)` with white text.

## Plan (2026-10-05, racialized-group label)

Mode: `autonomous`. Design notes: skipped. The chip row said “主要群体”, which does not say these are racialized groups.

**Goal.** The label on the page names them as the main racialized groups, in both languages.

**Out of scope.** Changing which groups are listed, and a git commit.

**Done when.** The Chinese Briar Hill panel shows “主要少数族裔” beside those chips.

**Scale.** small

**Pre-flight.** `PLAN.md`, `web/i18n.js`, `web/index.html`.

**Verify.** Open the Chinese Briar Hill panel and read the chip label.

## Verify (2026-10-05, racialized-group label)

Browser at `http://127.0.0.1:8765/?lang=zh&v=49`. Hounsfield Heights/Briar Hill shows “主要少数族裔” beside 华裔 7%、南亚裔 4%、菲律宾裔 4%、拉丁美洲裔 2%.

## Plan (2026-10-05, definition card layer)

Mode: `autonomous`. Design notes: skipped. The map panes sit above the definition card, and the zone drawing is translucent, so the half of the card that crosses onto the map looks faded.

**Goal.** The definition card stays fully opaque, and it opens inside the left sidebar instead of sliding under the map.

**Out of scope.** Map tile opacity, zone colors, and a git commit.

**Done when.** Clicking the walk-zone mark on Briar Hill shows a solid card, and a point on that card hits the card rather than the map canvas.

**Scale.** small

**Pre-flight.** `PLAN.md`, `web/style.css`, `web/app.js`, `web/index.html`.

**Verify.** Open the English Briar Hill panel, click the walk-zone mark, and check the card in the browser.

## Verify (2026-10-05, definition card layer)

Browser at `http://127.0.0.1:8765/?lang=en&v=48`. The walk-zone card stays inside the left sidebar (`right` 552, sidebar edge 560) at `z-index: 2000`. Points across the card hit `#termPop`, not the map canvas. The school card on the map stays solid.

## Plan (2026-10-05, metric definitions)

Mode: `autonomous`. Design notes: skipped. The ranking score column already uses a circled exclamation that opens a definition.

**Goal.** Every figure in the zone panel has the same circled mark. Clicking it opens a short definition and clicking it again, clicking elsewhere, or pressing Escape closes it.

**Out of scope.** New data, crime counts, and a git commit.

**Done when.** Briar Hill’s Chinese panel shows the mark beside household income, and the popover says it is the 2020 median, before tax.

**Scale.** small

**Pre-flight.** `PLAN.md`, `web/app.js`, `web/style.css`, `web/i18n.js`, `web/index.html`, `README.md`, `progress.md`.

**Verify.** `node --check web/app.js` and `node --check web/i18n.js`, then open the Chinese Briar Hill panel and click the income mark.

## Verify (2026-10-05, metric definitions)

`node --check web/app.js` and `node --check web/i18n.js` both exited 0. Browser at `http://127.0.0.1:8765/?lang=zh&v=46`: Briar Hill’s panel has a circled mark on every summary tile and community figure. The household-income mark opens “2020 年全年家庭总收入的中位数，税前。2021 年人口普查。” A second click closes it.

## Plan (2026-10-05, zone panel layout)

Mode: `autonomous`. Design notes: skipped. The census lines were one wrapped sentence per community.

**Goal.** The zone panel reads as a short summary, then one card per community: a two-column fact grid, then chips for the largest racialized groups and home languages.

**Out of scope.** Changing which census fields are stored, crime figures, and a git commit.

**Done when.** Briar Hill’s panel shows Hounsfield Heights as labeled facts, not one middot sentence.

**Scale.** small

**Pre-flight.** `PLAN.md`, `web/app.js`, `web/style.css`, `web/i18n.js`, `web/index.html`.

**Verify.** Open the Chinese panel for Briar Hill and read the community card.

## Verify (2026-10-05, zone panel layout)

Browser at `http://127.0.0.1:8765/?lang=zh&v=45`: Briar Hill opens with four summary tiles, then Hounsfield Heights/Briar Hill as a two-column fact grid. Racialized groups and home languages are chips under the numbers.

## Plan (2026-10-05, community profile PDFs)

## Plan (2026-10-05, community profile PDFs)

Mode: `autonomous`. Design notes: skipped. The profile HTML pages do not hold the census tables. Those tables are the 2021 City PDFs, one per community.

**Goal.** `scripts/fetch_community_profiles.py` downloads those PDFs and writes the fields a parent uses. The zone panel shows them for each community in the attendance zone.

**Fields.** Population, share aged 0–14 and 65+, 2020 median household income, owner/renter share, median monthly shelter cost, share spending 30% or more on shelter, immigrant share, racialized-population share and the largest groups, languages spoken most often at home, share with a bachelor’s degree or higher, and the share who drive or take transit to work. Each figure stays null when the parser cannot read it.

**Left out.** Religion, marital status, the age pyramid, industry, occupation, admission category, mobility, dwelling age, and the May 2021 unemployment rate. Crime is not in these PDFs.

**Out of scope.** Averaging racialized groups across a zone, the weekly school updater, and a git commit.

**Done when.** Dalhousie parses to population 8,530 and household income $85,000, and the Briar Hill panel shows those census lines for its communities.

**Scale.** small

**Pre-flight.** `PLAN.md`, `requirements.txt`, `scripts/fetch_community_profiles.py`, `scripts/verify.py`, `web/data/community_profiles.json`, `web/app.js`, `web/i18n.js`, `web/style.css`, `web/index.html`, `README.md`, `AGENTS.md`, `progress.md`, `.cursor/rules/project.mdc`.

**Verify.** Run the fetch script against the local Dalhousie PDF and the published PDFs, then `scripts/verify.py`, then open the Chinese panel for Briar Hill.

## Verify (2026-10-05, community profile PDFs)

`scripts/fetch_community_profiles.py` → `updated community_profiles.json: 205 profiles, 18 missing`.

The local Dalhousie PDF parses to population 8,530, household income $85,000, racialized population 38%, English at home 78%.

`scripts/verify.py` → PASS, including `Dalhousie profile matches the 2021 PDF (pop 8530 income 85000)`.

Browser at `http://127.0.0.1:8765/?lang=zh&v=43`: Briar Hill’s panel shows Hounsfield Heights/Briar Hill income $111,000 and St. Andrews Heights income $117,000, with age, shelter, immigrant, racialized groups, home language, degree, and commute lines. Crime still says 无数据.

## Plan (2026-10-05, police link)

## Plan (2026-10-05, police link)

Mode: `autonomous`. Design notes: skipped. The old crime-statistics URL returns 404 after the CPS site move.

**Goal.** The zone panel’s police link opens the live Community Safety Dashboard page.

**Out of scope.** Scraping crime counts into the panel.

**Done when.** The link target is `community-safety-dashboard---monthly-snapshot.html`, which loads.

**Scale.** trivial-but-multi-line

**Pre-flight.** `PLAN.md`, `web/app.js`, `web/index.html`, `README.md`.

**Verify.** Fetch the new URL and confirm the panel href matches it.

## Verify (2026-10-05, police link)

The panel href is `https://www.calgarypolice.ca/transparency-and-accountability/community-safety-dashboard---monthly-snapshot.html`. That page loads as “Community Safety Dashboard – Monthly Snapshot”, with a View Dashboard control. The old `crime-statistics.html` path is the 404.

## Plan (2026-10-05, zone detail panel)

Mode: `autonomous`. Design notes: skipped. The `»` control is the only way into the panel. A row click still only selects the school.

**Goal.** Each ranking row has a `»` control. It slides a panel in from the right edge of the left sidebar, and the close control slides it back out. The panel shows the communities in that school's attendance zone: the median and the average of their 2026 assessed values, the 2021 share of children and of families with children, and links for crime and ethnic origin.

**Out of scope.** Inventing sale prices, crime counts, or ethnic shares. Scraping the community-profile HTML. Diploma results, high schools, and a git commit.

**Done when.** Opening and closing the panel animates, a CBE school with a regular zone shows assessed-value figures from `zones.geojson`, and crime and ethnic origin say no data with an official link.

**Scale.** small

**Pre-flight.** `PLAN.md`, `web/index.html`, `web/app.js`, `web/style.css`, `web/i18n.js`, `README.md`, `progress.md`.

**Verify.** Open the Chinese ranking page, open the panel from a row, close it, and confirm a row click still does not open the panel.

## Verify (2026-10-05, zone detail panel)

`node --check web/app.js` and `node --check web/i18n.js` exited 0.

Browser at `http://127.0.0.1:8765/?lang=zh&v=41`: the `»` control on Briar Hill School slid the panel over the list. It showed a $882,000 median and average of the two community assessments (Hounsfield Heights/Briar Hill $744,000, St. Andrews Heights $1,020,000), children 13.7%, families with children 51.6%, and “无数据” for crime and ethnic origin with the City profile and police dashboard links. Close moved the panel to x=560. Clicking the school name left the panel closed. Master’s Academy, which has no CBE zone, says there is no published attendance zone. The year column stayed visible and the list had no horizontal overflow.

## Plan (2026-10-05, weekly school update)

Mode: `autonomous`. Design notes: skipped. School files stay stale until a script runs. Home values and high-school diploma results stay out of this update.

**Goal.** A weekly task refreshes the CBE directory, Alberta contacts, and CBE zones. A file is replaced only when the new text differs. A failed or empty fetch keeps the file on disk. High schools stay off the list, and grade 10–12 zones are not built.

**Out of scope.** Home values, diploma scores, CSSD zones, commits.

**Done when.** `update_schools.py` reports unchanged or updated for the directory, a Windows task exists for Sunday 09:00, and the program filter does not offer a program that only high schools teach.

**Scale.** small

**Pre-flight.** `PLAN.md`, `scripts/store.py`, `scripts/update_schools.py`, `scripts/fetch_cbe_directory.py`, `scripts/fetch_ab_contacts.py`, `scripts/build_zones.py`, `web/app.js`, `web/index.html`, `README.md`, `AGENTS.md`, `progress.md`, `.cursor/rules/project.mdc`.

**Verify.** Run the directory update, confirm the scheduled task, and check the program list in the browser.

## Verify (2026-10-05, weekly school update)

`.venv\Scripts\python scripts\fetch_cbe_directory.py` → `unchanged cbe_directory.json`.

Scheduled task `school-maps-school-update` is Ready, weekly, Sunday 09:00 local (`DaysOfWeek` 1).

`scripts\build_zones.py` from cache → `updated zones.geojson`, attendance 303, regular 211, walk 300. The missing A.E. Cross walk file stayed a warning and was not invented.

Browser at `http://127.0.0.1:8765/?lang=zh&v=39`: the program list has no Alternative High School, IB Diploma, or Outreach. `scripts\verify.py` passed, including `211 regular`.

## Plan (2026-10-05, drop screenshots)

Mode: `autonomous`. Design notes: skipped. Screenshots are a record of the page, not something the page needs.

**Goal.** Remove the screenshot script, the images, and Playwright. Verify no longer mentions them.

**Out of scope.** The data pipeline, commits.

**Done when.** No file under `scripts/` or `screenshots/` produces or stores a screenshot, and the docs' verify command does not call `screenshot.py`.

**Scale.** small

**Pre-flight.** `PLAN.md`, `README.md`, `progress.md`, `AGENTS.md`, `.cursor/rules/project.mdc`, `requirements.txt`, `scripts/screenshot.py`, `screenshots/a_school_rank_pat6_en.png`, `screenshots/b_school_rank_pat9_zh.png`.

**Verify.** Search the repo for `screenshot` and `playwright`.

## Verify (2026-10-05, drop screenshots)

`scripts/screenshot.py` and `screenshots/` are gone. A search for `screenshot` and `playwright` finds those words only in this plan.

## Plan (2026-10-05, docs match the page)

Mode: `autonomous`. Design notes: skipped. The ranking page, CBE zones, three filters, and the percent format are in the code. The README still says there are two filters and that every catchment is an approximation.

**Goal.** README, progress, AGENTS, and the project rule describe the page that opens: a ranking list, three filters, a CBE zone on click, and rates written as 达标率 96.5%.

**Out of scope.** Scoring code, rebuilding data, screenshots, commits, the cursor-prime-cloud section of `AGENTS.md`.

**Done when.** The README no longer says the page has two filters, and the catchment note distinguishes a published CBE zone from the community approximation.

**Scale.** small

**Pre-flight.** `PLAN.md`, `README.md`, `progress.md`, `AGENTS.md`, `.cursor/rules/project.mdc`, `web/app.js` (file header only).

**Verify.** Read the edited sections and search for the stale "two filters" line.

## Verify (2026-10-05, docs match the page)

The README now lists board, grade, and program filters, separate Grade 6 and Grade 9 ranks, and the published CBE zone. A search for "two filters" finds that phrase only in this plan. PAT match counts in the README match `web/data/meta.json` (372 of 423, 299 of 322).

## Current

The page is a school ranking list beside a map. Board, grade, and program filters open on All, with board and grade on one row. Grade 6 and Grade 9 are separate rankings when the grade filter is All. Clicking a school draws its published CBE attendance zone and walk zone. The card links to the school's own site, then to CBE Find a School, and says the official source is the final word. Score tips read as 达标率 96.5%.
