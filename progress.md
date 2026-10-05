# progress.md

## Current Focus
MVP prototype complete (local only).

## Completed
- cursor-prime-cloud rules installed (autonomous mode), and the plan recorded in PLAN.md.
- Data pipeline, scoring, verify script, static bilingual front end, and screenshots.

## Next Steps
- Diploma results for high schools, once a current school-level file is found.
- Show the PAT cohort size (`n_cells`) in the UI, and optionally add a minimum cohort rule.
- Official attendance-area data from CBE/CSSD, if they publish it or agree to share it.
- Context layers: Equity Index and census newcomer share.

## Known Issues
- Catchment is approximated. Home value is the assessed value, not the market price, and mixes houses with condos.
- Rent is not available.

## Handoff
Verify: `.venv/bin/python scripts/build_data.py && .venv/bin/python scripts/verify.py && .venv/bin/python scripts/screenshot.py`
