# Decisions

The page is a Calgary school ranking for elementary and junior high, scored on the newest PAT year. The header says Prototype because the page covers Calgary.

These choices are already in the code:

- Grade 10 and above is not ranked. Diploma results are not in the public file this page uses.
- A missing number stays blank. It is not stored or shown as zero.
- Catholic, charter, francophone, and private schools stay on the list when they have a grade 6 or grade 9 PAT. Schools outside the CBE have no attendance polygon, so the map outlines the community the school sits in.
- The old community colouring map is not part of the page. Community school scores, value for money, amenity counts, and the 2025-to-2026 assessed-value change are not built.
- Market rent, crime, class size, and an equity index are not shown. The zone panel uses the 2026 assessed value and the 2021 census figures that were actually published.
- The browser only reads files in `web/`. Python scripts build those files beforehand.

Check the data with:

```bash
.venv/bin/python -m pytest
.venv/bin/python scripts/verify.py
node --test web/rank.test.mjs
```

On Windows, use `.venv\Scripts\python`. Open `http://127.0.0.1:8765/` after `python3 -m http.server 8765 -d web`. The public page is https://school-maps-beta.vercel.app/. Vercel publishes `web/` from `main`, with no install and no build.
