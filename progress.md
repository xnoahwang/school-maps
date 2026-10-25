# progress.md

## Current Focus
The page is the Calgary school ranking. The header pill says Prototype. The list is on the left and the map is on the right. Clicking a row or a point opens that school's card and draws its CBE attendance zone and walk zone. A school with no published zone outlines the community where the school sits. The » control on a row slides in a panel with that zone’s 2026 assessed values and, from the City’s 2021 community-profile PDFs, income, housing, language, and racialized-population figures. Rule text is cursor-prime v0.3.3. `.cursor/cursor-prime-cloud-mode` is `interactive`.

## Completed
- cursor-prime v0.3.3 rules, with Plan Gate waiting for `GO`.
- Data pipeline, scoring, verify script, and a ranking page in English, 简体中文, 繁體中文, Français, 日本語, and 한국어. Board, grade, and program filters sit with the list beside the map.
- Clicking a school draws the CBE attendance zone and walk zone from the public finder files.
- CBE directory for phone, website, grades, and programs. Alberta's directory fills a phone or website only when one is missing.
- 2026 assessed value, 2021 census children and families, school enrolment, source as-of dates.
- Weekly school update (`scripts/update_schools.py`): directory, contacts, and zones, written only when the text changes. Home values are not part of it.
- Download cache is one directory per script under `data/raw/`. Probe scripts are deleted and gitignored.

## Next Steps
- None queued. Do not push until asked.

## Known Issues
- A school with no CBE zone, including CSSD, charter, and private schools, outlines the community its point falls in.
- Home value is the assessed value, not the market price, and mixes houses with condos. The weekly school update does not refresh it.
- The list is elementary and junior high.

## Handoff
The page is Calgary School Ranking (by PAT). The header pill is Prototype. A CBE school card shows the Assurance survey from that school's improvement report. It opens in English. The header menu is English, 简体中文, 繁體中文, Français, 日本語, and 한국어. A `?lang=` code still switches the page. Verify: `.venv\Scripts\python scripts\verify.py`. Open `http://127.0.0.1:8765/` and `http://127.0.0.1:8765/?lang=zh`.
