# progress.md

## Current Focus
The ranking list is a left sidebar called the school filter area. The page is a quiet map tool: a white header, the list on the left, and the map on the right. Clicking a row or a point opens that school's card and draws its CBE attendance zone and walk zone. The » control on a row slides in a panel with that zone’s assessed values and, from the City’s 2021 community-profile PDFs, income, housing, language, and racialized-population figures. Each figure has a circled exclamation mark that opens its definition. Crime stays “no data”. The website row links to that school's own site. The card also links to CBE Find a School and says the official source is the final word.

## Completed
- cursor-prime-cloud rules installed (autonomous mode), and the plan recorded in PLAN.md.
- Data pipeline, scoring, verify script, and a bilingual ranking page: board, grade, and program filters, with the list beside the map.
- Clicking a school draws the CBE attendance zone and walk zone from the public finder files.
- CBE directory for phone, website, grades, and programs. Alberta's directory fills a phone or website only when one is missing.
- 2025-to-2026 assessed-value change, 2021 census children and families, school enrolment, source as-of dates.
- Optional review script (`scripts/fetch_reviews.py`) that skips cleanly without API keys.
- Weekly school update (`scripts/update_schools.py`): directory, contacts, and zones, written only when the text changes. Home values and diploma results are not part of it.

## Next Steps
- Show the PAT cohort size (`n_cells`) in the UI, and optionally add a minimum cohort rule.
- CSSD attendance areas, if that board publishes a file the page can use. CBE zones are already drawn.
- Equity Index when the City publishes a community or census-tract table, not only PDF maps.
- Run `fetch_reviews.py` once Google and Reddit keys exist.

## Known Issues
- A school with no CBE zone, including CSSD, charter, and private schools, has no polygon. Community scores still use nearby schools and are not shown on the page.
- Home value is the assessed value, not the market price, and mixes houses with condos. The weekly school update does not refresh it.
- Rent and community crime are not available as open community-level data.
- High schools stay off the list. There is no current diploma file, so they are not ranked or given a grade 10–12 zone.

## Handoff
The zone panel is on the page. Each figure has a definition button, including the PAT acceptable and excellence lines. Verify: open `http://127.0.0.1:8765/?lang=zh`, click `»` on a CBE row, then click a circled exclamation mark. Data check: `.venv\Scripts\python scripts\verify.py`.
