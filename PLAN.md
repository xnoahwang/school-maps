# PLAN.md

Older plans and verify receipts are in git history. This file keeps the current record only.

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
