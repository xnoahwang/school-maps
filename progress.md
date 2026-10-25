# Status

## Now

Calgary school ranking, marked Prototype. The public page is https://school-maps-beta.vercel.app/. Vercel publishes `web/` when `main` changes. `school-maps-xujun.vercel.app` asks for a Vercel login. The list is on the left and the map is on the right. A row or a point opens the school card and draws the CBE attendance zone and walk zone. The zone file loads the first time a school is selected. A school with no published zone outlines the community where it sits. The » control opens assessed values and 2021 census figures for that zone.

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
- The list is elementary and junior high.

## Check

`.venv\Scripts\python -m pytest`, `.venv\Scripts\python scripts\verify.py`, and `node --test web/rank.test.mjs`. The page is `http://127.0.0.1:8765/`. `?lang=zh` switches to simplified Chinese.
