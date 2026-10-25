/* CBE attendance zones and the slide-in panel.
 * Picks the published polygon for a school and fills assessed values and
 * census figures. Does not rank schools and does not own the map.
 * A school with no zone is reported as such; the map module draws the outline.
 */
import { contactCode, contactKey, displayName } from "./rank.js";

export function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"
  }[ch]));
}

/** Zones whose school code or name matches this school. Empty when none do. */
export function zonesForSchool(school, zones) {
  if (!school) return [];
  const code = contactCode(school.cbe_code);
  if (code) return zones.filter((f) => contactCode(f.properties.school_code) === code);
  const key = contactKey(school.cbe_name || school.name);
  if (!key) return [];
  return zones.filter((f) => contactKey(f.properties.name) === key);
}

/**
 * Attendance polygons for the selected program, plus their walk zones.
 * program "all" prefers Regular. A program with no polygon keeps the unfiltered set.
 */
export function chooseZones(school, zones, program) {
  const matched = zonesForSchool(school, zones);
  let attendance = matched.filter((f) => f.properties.kind === "attendance" && f.properties.band !== "senior");
  if (!attendance.length) attendance = matched.filter((f) => f.properties.kind === "attendance");
  if (program !== "all") {
    const filtered = attendance.filter((f) => f.properties.program === program);
    if (filtered.length) attendance = filtered;
  } else {
    const regular = attendance.filter((f) => f.properties.program === "Regular");
    if (regular.length) attendance = regular;
  }
  const codes = new Set(attendance.map((f) => f.properties.code));
  const walks = matched.filter((f) => f.properties.kind === "walk" && codes.has(f.properties.code));
  const programs = [...new Set(attendance.map((f) => f.properties.program))];
  return { attendance, walks, program: programs.join(" · ") };
}

/**
 * Communities listed on the chosen zone. An empty program list falls back to
 * that school's regular zone, and fromRegular tells the panel to say so.
 */
export function zoneFacts(school, zones, communities, program) {
  const matched = zonesForSchool(school, zones);
  const picked = chooseZones(school, zones, program);
  const withPlaces = (features) => features.filter((f) => (f.properties.places || []).length);
  let features = withPlaces(picked.attendance);
  let fromRegular = false;
  if (!features.length) {
    features = withPlaces(matched.filter((f) => f.properties.kind === "attendance" && f.properties.program === "Regular" && f.properties.band !== "senior"));
    fromRegular = features.length > 0;
  }
  const byCode = new Map();
  features.forEach((f) => (f.properties.places || []).forEach((place) => {
    if (!byCode.has(place.code)) byCode.set(place.code, place);
  }));
  const communityByCode = new Map(communities.map((f) => [f.properties.code, f.properties]));
  const rows = [...byCode.values()].map((place) => ({
    ...place,
    community: communityByCode.get(place.code) || null,
  })).sort((a, b) => a.name.localeCompare(b.name));
  return { hasZone: picked.attendance.length > 0, fromRegular, rows };
}

/** The community polygon stored on the school, or null when the code is missing. */
export function homeCommunity(school, communities) {
  const code = school && school.community;
  if (!code) return null;
  return communities.find((f) => f.properties.code === code) || null;
}

export function medianOf(nums) {
  if (!nums.length) return null;
  const sorted = [...nums].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

export function meanOf(nums) {
  if (!nums.length) return null;
  return nums.reduce((sum, n) => sum + n, 0) / nums.length;
}

/** Population-weighted share of children across the zone's communities. Null if none qualify. */
export function weightedChildren(rows) {
  let population = 0;
  let children = 0;
  rows.forEach(({ community }) => {
    if (!community || community.children_pct == null || community.children_count == null || community.children_pct <= 0) return;
    population += community.children_count / (community.children_pct / 100);
    children += community.children_count;
  });
  return population ? (children / population) * 100 : null;
}

const GROUP_KEYS = {
  "South Asian": "group_south_asian", Chinese: "group_chinese", Black: "group_black",
  Filipino: "group_filipino", Arab: "group_arab", "Latin American": "group_latin",
  "Southeast Asian": "group_southeast_asian", "West Asian": "group_west_asian",
  Korean: "group_korean", Japanese: "group_japanese",
};
const LANG_KEYS = {
  Mandarin: "lang_mandarin", "Yue (Cantonese)": "lang_yue", Cantonese: "lang_yue",
  "Tagalog (Pilipino, Filipino)": "lang_tagalog", Korean: "lang_korean", Spanish: "lang_spanish",
  "Punjabi (Panjabi)": "lang_punjabi", Hindi: "lang_hindi", Arabic: "lang_arabic",
  Urdu: "lang_urdu", Vietnamese: "lang_vietnamese", "Iranian Persian": "lang_persian",
  Russian: "lang_russian", Ukrainian: "lang_ukrainian", German: "lang_german",
  Portuguese: "lang_portuguese", Polish: "lang_polish", Italian: "lang_italian",
  Gujarati: "lang_gujarati", Tamil: "lang_tamil", Bengali: "lang_bengali",
  Nepali: "lang_nepali", Japanese: "lang_japanese",
};

/**
 * The slide-in panel. deps supplies live data and the translator:
 * zones(), communities(), profiles(), program(), schools(), t(key), orNA(html), closeTerm().
 * Returns open/close/fill. panelSchoolId() is null while the panel is closed.
 */
export function createZonePanel(deps) {
  const t = (key) => deps.t(key);
  let panelSchoolId = null;

  function moneyFull(value) {
    return value == null ? null : "$" + Math.round(value).toLocaleString("en-CA");
  }
  function pct1(value) {
    return value == null ? null : value.toFixed(1) + "%";
  }
  function profileFor(name) {
    return deps.profiles()[contactKey(name)] || null;
  }
  function termMark(key) {
    return `<button type="button" class="source-mark" data-term="${esc(key)}" aria-expanded="false" aria-label="${esc(t("term_label"))}">!</button>`;
  }
  function fact(key, value) {
    if (value == null || value === "") return "";
    return `<div><dt><span>${esc(t(key))}</span>${termMark(key)}</dt><dd>${esc(String(value))}</dd></div>`;
  }
  function pctNum(value) {
    return value == null ? null : value + "%";
  }
  function moneyMonth(amount) {
    return amount == null ? null : moneyFull(amount) + t("fact_month");
  }
  function tenureValue(share, cost) {
    if (share == null) return null;
    return cost == null ? pctNum(share) : `${pctNum(share)} · ${moneyMonth(cost)}`;
  }
  function chipRow(label, items, keys, minimum) {
    const chips = (items || [])
      .filter((item) => item.pct != null && item.pct >= minimum)
      .sort((a, b) => b.pct - a.pct)
      .slice(0, 4)
      .map((item) => `${keys[item.name] ? t(keys[item.name]) : item.name} ${item.pct}%`);
    if (!chips.length) return "";
    return `<div class="chip-row"><span class="term-line"><span>${esc(t(label))}</span>${termMark(label)}</span>${chips.map((chip) => `<b>${esc(chip)}</b>`).join("")}</div>`;
  }
  function censusFacts(profile, families) {
    const row = profile || {};
    return [
      fact("fact_income", row.median_household_income == null ? null : moneyFull(row.median_household_income)),
      fact("fact_pop", row.population == null ? null : Number(row.population).toLocaleString("en-CA")),
      fact("fact_young", pctNum(row.age_0_14_pct)),
      fact("fact_older", pctNum(row.age_65_plus_pct)),
      fact("fact_families", families == null ? null : pct1(families)),
      fact("fact_own", tenureValue(row.owner_pct, row.shelter_owner)),
      fact("fact_rent", tenureValue(row.renter_pct, row.shelter_renter)),
      fact("fact_burden", pctNum(row.shelter_30_pct)),
      fact("fact_immigrant", pctNum(row.immigrant_pct)),
      fact("fact_racialized", pctNum(row.racialized_pct)),
      fact("fact_english", pctNum(row.english_home_pct)),
      fact("fact_degree", pctNum(row.bachelor_pct)),
      fact("fact_drive", pctNum(row.drive_pct)),
      fact("fact_transit", pctNum(row.transit_pct)),
    ].join("");
  }
  function censusExtra(profile) {
    if (!profile) return "";
    const pdf = profile.pdf ? `<a href="${esc(profile.pdf)}" target="_blank" rel="noopener">${esc(t("census_pdf"))}</a>` : "";
    return `${chipRow("fact_groups", profile.racialized, GROUP_KEYS, 2)}${chipRow("fact_languages", profile.home_languages, LANG_KEYS, 1)}${pdf}`;
  }
  function summaryTile(labelKey, valueHtml, termKey) {
    const key = termKey || labelKey;
    return `<div><span class="term-line"><span>${esc(t(labelKey))}</span>${termMark(key)}</span><b>${valueHtml}</b></div>`;
  }
  function zoneLinks() {
    return `<div class="stat"><a href="https://www.calgary.ca/communities/profiles.html" target="_blank" rel="noopener">${esc(t("profile_link"))}</a></div>
      <p class="note">${esc(t("census_next"))}</p>`;
  }
  function fillZonePanel(id) {
    const school = deps.schools().find((s) => String(s.id) === String(id));
    const title = document.getElementById("zonePanelTitle");
    const body = document.getElementById("zonePanelBody");
    if (!school || !title || !body) return;
    deps.closeTerm();
    title.textContent = displayName(school);
    const facts = zoneFacts(school, deps.zones(), deps.communities(), deps.program());
    if (!facts.hasZone && !facts.rows.length) {
      const home = homeCommunity(school, deps.communities());
      if (!home) {
        body.innerHTML = `<p>${esc(t("zone_none"))}</p>${zoneLinks()}`;
        return;
      }
      const place = home.properties;
      const profile = profileFor(place.name);
      const families = place.families_with_children_pct;
      const headFacts = fact("fact_value", moneyFull(place.home_value) || t("no_data"));
      const ethnicityRow = profile ? "" : `<div class="stat"><span class="term-line"><span>${esc(t("ethnicity"))}</span>${termMark("fact_racialized")}</span><b>${esc(t("no_data"))}</b></div>`;
      body.innerHTML = `<p class="zone-callout">${esc(t("zone_home_only"))}</p>
        <ul class="zone-places"><li class="place-card"><div class="place-head"><strong>${esc(place.name)}</strong></div><dl class="metrics">${headFacts}${censusFacts(profile, families)}</dl>${censusExtra(profile)}</li></ul>
        ${ethnicityRow}
        ${zoneLinks()}`;
      return;
    }
    if (!facts.rows.length) {
      body.innerHTML = `<p>${esc(t("zone_no_places"))}</p>${zoneLinks()}`;
      return;
    }
    const values = facts.rows.map((row) => row.home_value).filter((value) => value != null);
    const familyRates = facts.rows.map((row) => row.community && row.community.families_with_children_pct).filter((value) => value != null);
    const regularNote = facts.fromRegular ? `<p class="note">${esc(t("zone_from_regular"))}</p>` : "";
    const hasProfile = facts.rows.some((row) => profileFor(row.name));
    const communityRows = facts.rows.map((row) => {
      const families = row.community ? row.community.families_with_children_pct : null;
      const where = row.in_walk ? t("zone_walk") : t("zone_bus");
      const profile = profileFor(row.name);
      const headFacts = fact("fact_value", moneyFull(row.home_value) || t("no_data"));
      return `<li class="place-card"><div class="place-head"><strong>${esc(row.name)}</strong><span class="place-status"><span class="place-tag">${esc(where)}</span>${termMark("walk_zone")}</span></div><dl class="metrics">${headFacts}${censusFacts(profile, families)}</dl>${censusExtra(profile)}</li>`;
    }).join("");
    const ethnicityRow = hasProfile ? "" : `<div class="stat"><span class="term-line"><span>${esc(t("ethnicity"))}</span>${termMark("fact_racialized")}</span><b>${esc(t("no_data"))}</b></div>`;
    body.innerHTML = `${regularNote}
      <div class="zone-summary">
        ${summaryTile("summary_median", deps.orNA(moneyFull(medianOf(values))))}
        ${summaryTile("summary_mean", deps.orNA(moneyFull(meanOf(values))))}
        ${summaryTile("fact_young", deps.orNA(pct1(weightedChildren(facts.rows))), "summary_young")}
        ${summaryTile("fact_families", deps.orNA(pct1(meanOf(familyRates))), "summary_families")}
      </div>
      <p class="place-kicker">${esc(t("zone_places"))}</p>
      <ul class="zone-places">${communityRows}</ul>
      ${ethnicityRow}
      ${zoneLinks()}`;
  }
  function openZonePanel(id) {
    panelSchoolId = String(id);
    fillZonePanel(id);
    const panel = document.getElementById("zonePanel");
    const body = document.getElementById("zonePanelBody");
    if (body) body.scrollTop = 0;
    panel.classList.add("open");
    panel.setAttribute("aria-hidden", "false");
  }
  function closeZonePanel() {
    panelSchoolId = null;
    const panel = document.getElementById("zonePanel");
    if (!panel) return;
    panel.classList.remove("open");
    panel.setAttribute("aria-hidden", "true");
  }
  return {
    fillZonePanel, openZonePanel, closeZonePanel,
    panelSchoolId: () => panelSchoolId,
  };
}
