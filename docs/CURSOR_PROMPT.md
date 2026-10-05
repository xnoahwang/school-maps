# Prompt for a Cursor agent: next phase of the Calgary School & Community Explorer

Copy everything below the line into a Cursor agent chat opened on this repo.

---

You are working in the `school-maps` repo (Calgary School & Community Explorer). Before anything else:

1. Read `docs/PROJECT_BRIEF.md` (why, who, direction, risks), `README.md` (what exists), `AGENTS.md`, and `.cursor/rules/`. Follow the cursor-prime rules already installed in `.cursor/rules/` (plan first, surgical changes, Verify Receipt with exact commands and output, edge-case notes for new public functions, Delta Report, file headers and docstrings, keep README/AGENTS.md truthful). If `.cursor/rules/behavior.mdc` is missing, install https://github.com/xnoahwang/cursor-prime-cloud by following its AGENTS.md first.
2. Write a plan in `PLAN.md` (goal, out of scope, done-when, files to touch, verify commands) before coding.

## Goal

Make the data the **newest and most complete** available, and add a **public review signal** for each school, without breaking the current map.

## Part A: refresh and extend official data

For every source, find the latest release, record its as-of date in `web/data/meta.json`, and cite it (link and licence) in the README. Never invent values; missing means "no data".

- Re-check every source already used (Open Calgary `surr-xmvs`, `fd9t-tdn2`, `4bsw-nn7w`, `kami-qbfh`, `m9y7-ui7j`, `muzh-c9qc`; Alberta PAT multi-year school file) for a newer release.
- Add high schools: find the current school-level **Alberta Diploma exam results and participation rates** (open.alberta.ca or alberta.ca). Add a high-school score with the same rules as PAT.
- Add context where a real open source exists: Calgary Equity Index (`hy6b-89wc` or its latest file), City community profiles (2021 census: income, households with children, languages), class size and enrolment (`9qye-mibh`), and the prior-year assessment roll for a price trend.
- Safety: look for an official downloadable or API version of Calgary Police Service crime by community. If there is none, document that and leave it out. Do not scrape the dashboard.
- Rent: CMHC is zone level only. If you add it, label it as a zone figure and never show it as a community figure.
- Programs: list CBE/CSSD alternative programs (French immersion, bilingual, IB, AP), lottery-only flags, and overflow schools where official pages publish them.

## Part B: school reviews from Reddit and Google Maps

Build an **optional, separate** review layer. It never mixes silently into the exam-based score.

- **Google Maps:** use the official Google Places API (Place Search to find each school's place ID, Place Details for `rating`, `user_ratings_total` and the review snippets the API returns). Read the API key from an environment variable (`GOOGLE_MAPS_API_KEY`), never commit it, and follow Google Maps Platform terms on caching, storage and attribution. If the terms don't allow storing a field, store only the place ID and fetch at runtime, or keep just the rating and count.
- **Reddit:** use the official Reddit API (OAuth app credentials from env vars) to search r/Calgary, r/alberta and r/CalgaryParents (if it exists) for mentions of each school by name. Match conservatively, since many schools share names with streets and communities. Follow Reddit's API terms and rate limits. Store post and comment IDs, dates and permalinks, not full copied text.
- **Scoring:** compute a review score per school, for example a Bayesian-smoothed Google rating plus a sentiment score from matched Reddit comments. Always show the sample size, the date range and a link to the sources. Below a minimum count, show "too few reviews". Write a short methods note in the README explaining the score, its biases, and that reviews are opinions.
- Make the review pipeline a separate script (for example `scripts/fetch_reviews.py`) so the main build runs without API keys.

## Part C: UI

- Add the new metrics (high-school score, review score, context fields) to the metric picker and the community panel, in both EN and 简体中文 (`web/i18n.js`). Chinese is the primary audience.
- Keep the warnings visible: approximate catchments, lotteries, overflow, and test scores reflecting demographics.

## Done when

- `python scripts/build_data.py` and `python scripts/verify.py` pass, with new checks added for every new field.
- `meta.json` lists every source with its as-of date. The README data table and limitations are updated and truthful.
- The review script runs with keys set and is skipped cleanly without them.
- Screenshots are updated (`scripts/screenshot.py`), and you report the commands you ran with their real output.

## Out of scope

Paid data, scraping sites whose terms forbid it (MLS/realtor listings, the CPS dashboard, Google Maps HTML), user accounts, and deployment.
