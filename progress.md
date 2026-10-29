# Status

## Now

Calgary school ranking, marked Prototype. The page has elementary, junior high, and high-school lists. A school that teaches more than one level appears on each list with that level's score. High schools use the diploma exam file dated 2025-11-14, through the 2025 year. The public page is https://school-maps-beta.vercel.app/. Vercel publishes `web/` when `main` changes. `school-maps-xujun.vercel.app` asks for a Vercel login. The list is on the left and the map is on the right. The columns are rank, school, score, acceptable, and excellence. English and French headers are Acc. and Exc. The line under a school name is the board, the full grade range, and the exam year. A row or a point opens the school card and draws the CBE attendance zone and walk zone. The zone file loads the first time a school is selected. A school with no published zone outlines the community where it sits. The » control opens assessed values and 2021 census figures for that zone.

On a phone, portrait asks you to turn sideways. The page cannot lock the phone. After the first landscape, turning back keeps that layout until a refresh. A short touch near a point selects the school. A card that is cut off shows a double arrow until it is scrolled to the end.

The page was built with AI in Cursor, using the cursor-prime standard described in the README.

## In the product

- Ranking in English, 简体中文, 繁體中文, Français, 日本語, and 한국어. Board, grade, and program filters sit with the list.
- CBE directory for phone, website, grades, and programs. Alberta's directory fills a phone or website only when one is missing.
- 2026 assessed value, 2021 census children and families, school enrolment, and source dates.
- Optional weekly refresh of the directory, contacts, and zones. Home values are not part of that refresh.
- Download cache is one directory per script under `data/raw/`, and that cache is not published.

## Limits

- A school with no CBE zone outlines the community its point falls in. That outline is not an attendance zone.
- Home value is the assessed value, not the market price, and mixes houses with condos.
- High school uses the diploma exam mark, not the school-awarded mark. A school with no published result for that list stays at the bottom and is not numbered.
- A phone must be sideways. Refreshing while it is upright shows the turn prompt again.

## Check

`.venv\Scripts\python -m pytest`, `.venv\Scripts\python scripts\verify.py`, and `node --test web/rank.test.mjs`. The page is `http://127.0.0.1:8765/`. `?lang=zh` switches to simplified Chinese.
