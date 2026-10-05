# progress.md

## Current Focus
The ranking list opens with both filters on All. The A–Z letter row is gone. The filters stay put while the school rows scroll. The score heading still has a circle that opens Alberta's PAT results page.

## Completed
- cursor-prime-cloud rules installed (autonomous mode), and the plan recorded in PLAN.md.
- Data pipeline, scoring, verify script, static bilingual front end, and screenshots.
- 2025-to-2026 assessed-value change, 2021 census children and families, school enrolment, source as-of dates.
- Optional review script (`scripts/fetch_reviews.py`) that skips cleanly without API keys.

## Next Steps
- Diploma results for high schools, once a current school-level file is public.
- Show the PAT cohort size (`n_cells`) in the UI, and optionally add a minimum cohort rule.
- Official attendance-area data from CBE/CSSD, if they publish it or agree to share it.
- Equity Index when the City publishes a community or census-tract table, not only PDF maps.
- Run `fetch_reviews.py` once Google and Reddit keys exist.

## Known Issues
- Catchment is approximated. Home value is the assessed value, not the market price, and mixes houses with condos.
- Rent and community crime are not available as open community-level data.
- High-school score is null for every community until a current Diploma file exists.

## Handoff
Verify: `.venv/Scripts/python scripts/build_data.py && .venv/Scripts/python scripts/verify.py && .venv/Scripts/python scripts/fetch_reviews.py && .venv/Scripts/python scripts/screenshot.py`
