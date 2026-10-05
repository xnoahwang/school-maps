# Project Brief: Calgary School & Community Explorer

> Why this project exists, who it is for, and where it is going.
> Written from the owner's (Noah Wang's) conversations while building the first prototype, October 2026.
> Read this before changing scope. `README.md` describes what is built today; this file describes the intent.

## 1. Why

Immigrant and newcomer parents arriving in Calgary usually know nothing about which schools are strong or which communities are good places to raise children. Many are willing to **move to a specific community so their child gets a good designated school**, but the information they would need is scattered across the City of Calgary, Alberta Education, two school boards, the Fraser Institute, real-estate sites, and word of mouth. It is mostly in English and mostly organised around "I already have an address."

This project puts that information in one place, in their language, and answers the question they actually ask.

## 2. Target users

- **Primary:** immigrant / newcomer parents (Chinese-speaking first) with school-age or soon-school-age children who are choosing where to rent or buy in Calgary.
- They are willing to pay more in rent or price for a better school, but want to know whether the premium is worth it.
- They do not know the local vocabulary (CBE vs CSSD, catchment / designated school, PAT, Diploma, programs of choice, lotteries, overflow).

## 3. The core idea: reverse the usual flow

Most tools work from **address → schools** ("I live here, which school is mine?").
This project works from **good schools → where to live** ("I want good schools; which communities, and eventually which addresses, should I move to?").

The product shows:

- A **map plus a sortable list** of every residential community (the map style is like the HydraHerder risk map: colour by a metric, click for details).
- For each community, the **schools that serve it**, with their results, plus the **community itself**: home prices, amenities, and later safety, demographics and reviews.
- **Bilingual UI, Simplified Chinese first**, English second, with plain explanations of the local education system.

## 4. How this differs from FamilyRoost (and why it is not a copy)

[FamilyRoost.ca](https://familyroost.ca) is the closest existing tool (address lookup of catchment schools in 5 Alberta cities, a "Roost Rating" from PAT 3-year means + the Alberta Education Assurance Measures survey + its own research, a paid Family+ tier). We learn from it, but we are deliberately targeted at a different job:

| | FamilyRoost | This project |
|---|---|---|
| Starting point | An address | A goal ("good schools within my budget") → communities → addresses |
| Unit shown | Schools for one address | Communities ranked, with their schools |
| Community dimensions | Not the focus | Price, value for money, amenities; later safety, demographics, reviews |
| Fairness of school score | Raw outcomes | Planned: value-added score adjusted for neighbourhood income |
| Audience | General English-speaking families | Immigrant parents, Chinese first, with education-system explainers |
| Weights | Fixed rating | Planned: separate school and community scores, parent-set weights |

Do not copy FamilyRoost's text, ratings, data, or UI. Build from primary public sources.

## 5. Data: newest and most complete, always cited

Rule: use the **latest available release** of every source, record its date in `web/data/meta.json`, cite it in the README, and show "no data" rather than inventing or zero-filling.

Used in the prototype (see README for links and licences):

- Community boundaries: Open Calgary `surr-xmvs` (residential communities, 223).
- Schools: Open Calgary `fd9t-tdn2` (506 schools).
- Alberta PAT school multi-year results (grades 6 and 9, latest 3 years: 2023–2025).
- 2026 property assessment roll: Open Calgary `4bsw-nn7w`.
- Parks `kami-qbfh`, libraries `m9y7-ui7j`, transit stops `muzh-c9qc`.

Known candidates not yet used (verify each before relying on it):

- Alberta Diploma exam results and participation rates (open.alberta.ca), for high schools. The school-level file found so far was out of date, so look for a newer one.
- Alberta Education Assurance Measure results. School-level figures appear in CBE/CSSD school results reports (PDFs).
- Alberta class size data (open.alberta.ca); Calgary school enrolment (Open Calgary `9qye-mibh`).
- Fraser Institute report cards. The Alberta secondary edition is current (2025, 2023/24 data); the newest Alberta elementary edition found was 2024. Use only as a cited reference, not as an input we republish.
- City community profiles (2021 census), civic census `s7f7-3gjj` (2019), Calgary Equity Index `hy6b-89wc`, prior assessment years `4ur7-wsgc` (trend), traffic incidents `35ra-9556`, playground and school zones.
- Calgary Police Service Community Safety Dashboard (monthly crime by community). It is a dashboard, not a download, so look for an official export or API before using it.
- CMHC rental market data (zone level only; never present a zone figure as a community figure).
- CBE / CSSD program information: alternative programs (French immersion, Spanish/Mandarin bilingual, IB, AP), lottery deadlines, overflow schools, transportation eligibility.
- Public reviews of schools (Reddit, Google Maps) through official APIs and within terms of service, turned into a separate, clearly labelled review signal. See `docs/CURSOR_PROMPT.md`.

## 6. Direction / roadmap ideas

1. **Better catchments:** use official designated-school lookups where permitted, flag overflow schools and lottery-only programs, and stop approximating where possible.
2. **High schools:** add Diploma results and participation rates.
3. **Fair school score:** a value-added score that adjusts results for neighbourhood income or the Equity Index, so schools are not ranked purely by demographics.
4. **Two scores, parent-set weights:** a school score and a community score (price, safety, amenities, commute, reviews), combined with weights each parent chooses.
5. **Reviews:** a review score from Reddit and Google Maps, shown separately with sample size and dates.
6. **Address level:** score an address (its actual designated schools plus its surroundings), compare addresses, and save a shortlist.
7. **Listings:** connect a good community / address to real rental or sale listings (through a licensed feed or partner, never scraping MLS).
8. **Explainers:** Chinese-first guides to CBE vs CSSD, registration, programs of choice, lotteries, and bussing.

## 7. Risks and honesty rules

- **Catchments change** and schools go on overflow. A community's "school" today may not be the school a new resident gets. Always link the official school finders.
- **Lotteries:** alternative programs are not guaranteed by address.
- **Test scores reflect demographics** as much as teaching. Say so in the UI.
- **Missing data:** crime and rent are not available at community level as open data yet. Show gaps, never fill them with guesses.
- **Assessed value is not market price.**
- **Reviews are noisy and biased.** Show counts and dates, and never treat them as fact. Respect each platform's terms; store only what the terms allow.
- **Licences:** cite every dataset, follow OGL terms, and follow the OSM tile policy beyond prototype traffic.
