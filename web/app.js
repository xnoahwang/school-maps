/* Wires the ranking page: load the JSON, translate, and connect the controls.
 * Who is listed lives in rank.js. The zone panel lives in zone.js.
 * Points and zoom live in map.js. This file does not recompute PAT scores.
 */
import {
  boardGroup, contactCode, contactKey, displayName, gradeBand, inConfig, isHighSchool,
  listedResult, noteForConfig, passesDirectory, rangeEnds, sortListed,
} from "./rank.js";
import { chooseZones, createZonePanel, esc } from "./zone.js";
import { createMap } from "./map.js";

const I18N = globalThis.I18N;
const params = new URLSearchParams(location.search);
const LANGS = ["en", "zh", "zh-Hant", "fr", "ja", "ko"];
const HTML_LANG = { en: "en", zh: "zh-Hans", "zh-Hant": "zh-Hant", fr: "fr", ja: "ja", ko: "ko" };

function storedLang() {
  const fromUrl = params.get("lang");
  if (LANGS.includes(fromUrl)) return fromUrl;
  // A remembered choice must not replace the English default. ?lang= is the only override.
  try { localStorage.removeItem("school-maps-lang"); } catch (e) { /* private browsing can block storage */ }
  return "en";
}

const state = { lang: storedLang(), query: "", board: "all", grade: "all", program: "all" };
let communities = [], schools = [], zones = [];
let zonesState = "unloaded";
let zonesPromise = null;
let communityProfiles = {};
let assuranceByCode = new Map();

const t = (key) => (I18N[state.lang][key] ?? I18N.en[key] ?? key);
const fmtScore = (v) => v == null ? null : v.toFixed(1);
const orNA = (s) => s == null ? `<span class="na">${t("no_data")}</span>` : s;
const filterOf = () => ({ board: state.board, grade: state.grade, program: state.program, query: state.query });

let notesOpen = false;
function syncNotesMore() {
  const box = document.getElementById("listNotes");
  const body = document.getElementById("listNotesBody");
  const button = document.getElementById("notesMore");
  if (!box || !body || !button) return;
  box.classList.toggle("open", notesOpen);
  button.hidden = !notesOpen && body.scrollHeight <= body.clientHeight + 1;
  button.textContent = t(notesOpen ? "notes_less" : "notes_more");
  button.setAttribute("aria-expanded", notesOpen ? "true" : "false");
}

function applyI18n() {
  document.documentElement.lang = HTML_LANG[state.lang] || "en";
  document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
  const scoreSource = document.getElementById("scoreSource");
  if (scoreSource) scoreSource.setAttribute("aria-label", t("score_source_label"));
  document.getElementById("search").placeholder = t("search_school");
  const langSelect = document.getElementById("lang");
  if (langSelect && langSelect.value !== state.lang) langSelect.value = state.lang;
  document.title = t("title");
  syncNotesMore();
}

function labeledOption(value, key) {
  const option = document.createElement("option");
  option.value = value;
  if (key) {
    option.dataset.label = key;
    option.textContent = t(key);
  } else {
    option.textContent = value;
  }
  return option;
}

function refreshFilterLabels() {
  document.querySelectorAll("#boardFilter option[data-label], #gradeFilter option[data-label]").forEach((option) => {
    option.textContent = t(option.dataset.label);
  });
}

function schoolsInBoard(board) {
  return schools.filter((school) => !isHighSchool(school) && school.board && (board === "all" || boardGroup(school) === board));
}

function fillGradeFilter() {
  const select = document.getElementById("gradeFilter");
  if (!select) return;
  const list = schoolsInBoard(state.board);
  select.replaceChildren();
  select.appendChild(labeledOption("all", "filter_all"));
  if (state.board === "cbe") {
    const labels = new Set(list.map((school) => school.cbe_grades).filter(Boolean));
    [...labels].sort((a, b) => {
      const [al, ah] = rangeEnds(a);
      const [bl, bh] = rangeEnds(b);
      return al - bl || ah - bh || a.localeCompare(b);
    }).forEach((label) => select.appendChild(labeledOption(label)));
    if (list.some((school) => !school.cbe_grades && gradeBand(school) === "elem")) {
      select.appendChild(labeledOption("unlisted", "rank_band_unlisted"));
    }
    if (list.some((school) => !school.cbe_grades && gradeBand(school) === "unknown")) {
      select.appendChild(labeledOption("unknown", "rank_band_unknown"));
    }
  } else {
    if (list.some((school) => gradeBand(school) === "elem")) select.appendChild(labeledOption("elem", "rank_band_elem"));
    if (list.some((school) => gradeBand(school) === "junior")) select.appendChild(labeledOption("junior", "rank_band_junior"));
    if (list.some((school) => gradeBand(school) === "unknown")) select.appendChild(labeledOption("unknown", "rank_band_unknown"));
  }
  if (![...select.options].some((option) => option.value === state.grade)) state.grade = "all";
  select.value = state.grade;
}

function fillBoardFilter() {
  const select = document.getElementById("boardFilter");
  if (!select) return;
  select.replaceChildren();
  ["all", "cbe", "cssd", "charter", "franco", "other_public", "private"].forEach((group) => {
    if (group !== "all" && !schoolsInBoard(group).length) return;
    const key = group === "all" ? "filter_all" : "group_" + group;
    select.appendChild(labeledOption(group, key));
  });
  if (![...select.options].some((option) => option.value === state.board)) state.board = "all";
  select.value = state.board;
  fillGradeFilter();
}

function fillProgramFilter(names) {
  const select = document.getElementById("programFilter");
  if (!select) return;
  const current = state.program;
  select.replaceChildren();
  const all = document.createElement("option");
  all.value = "all";
  all.textContent = t("filter_all_programs");
  select.appendChild(all);
  (names || []).forEach((name) => {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    select.appendChild(option);
  });
  select.value = current === "all" || (names || []).includes(current) ? current : "all";
  state.program = select.value;
}

function mergeDirectory(directory) {
  if (!directory || !Array.isArray(directory.schools)) return;
  const byId = new Map(schools.map((s) => [s.id, s]));
  directory.schools.forEach((row) => {
    const fields = {
      cbe_name: row.name, cbe_code: row.code, phone: row.phone, website: row.website, address: row.address,
      grade_min: row.grade_min, grade_max: row.grade_max, cbe_grades: row.grades,
      cbe_programs: row.programs, program_names: row.program_names,
    };
    const lat = Number(row.lat), lon = Number(row.lon);
    const hasPoint = Number.isFinite(lat) && Number.isFinite(lon);
    if (row.school_id != null && byId.has(row.school_id)) {
      const school = byId.get(row.school_id);
      Object.assign(school, fields);
      if (hasPoint && !Number.isFinite(Number(school.lat))) {
        school.lat = lat;
        school.lon = lon;
      }
      return;
    }
    schools.push({
      id: "cbe-" + (row.code || row.name), name: row.name, board: "The Calgary School Division",
      grades: row.grades, rank_exam: row.rank_exam, rank_score: null, rank_year: null, cbe_only: true,
      lat: hasPoint ? lat : null, lon: hasPoint ? lon : null,
      ...fields,
    });
  });
  const listedPrograms = new Set();
  schools.forEach((school) => {
    if (isHighSchool(school)) return;
    (school.program_names || []).forEach((name) => listedPrograms.add(name));
  });
  fillProgramFilter([...listedPrograms].sort((a, b) => a.localeCompare(b)));
  fillBoardFilter();
}

function mergeContacts(payload) {
  const rows = (payload && payload.schools) || [];
  const byKey = new Map();
  const ambiguous = new Set();
  const byCode = new Map();
  rows.forEach((row) => {
    const code = contactCode(row.code);
    if (code) byCode.set(code, row);
    if (!row.key || ambiguous.has(row.key)) return;
    const prev = byKey.get(row.key);
    if (!prev) {
      byKey.set(row.key, row);
      return;
    }
    if ((prev.website || "") !== (row.website || "") || (prev.phone || "") !== (row.phone || "")) {
      byKey.delete(row.key);
      ambiguous.add(row.key);
    }
  });
  schools.forEach((school) => {
    const row = byCode.get(contactCode(school.pat_code)) || byKey.get(contactKey(school.name));
    if (!row) return;
    if (!school.phone && row.phone) school.phone = row.phone;
    if (!school.website && row.website) school.website = row.website;
  });
}

function rateShown(value) {
  return value == null || value === "" ? "–" : `${value}%`;
}
function rateText(labelKey, value) {
  return `${t(labelKey)} ${rateShown(value)}`;
}

const SURVEY_FIELDS = [
  ["survey_quality", "education_quality"],
  ["survey_parents", "parental_involvement"],
  ["survey_engagement", "learning_engagement"],
  ["survey_citizenship", "citizenship"],
  ["survey_safe", "safe_caring"],
  ["survey_supports", "access_supports"],
];
function applyAssurance(payload) {
  assuranceByCode = new Map();
  ((payload && payload.schools) || []).forEach((row) => {
    if (row && row.code) assuranceByCode.set(contactCode(row.code), row);
  });
}
function surveyHtml(school) {
  const row = assuranceByCode.get(contactCode(school.cbe_code));
  if (!row) return "";
  const any = SURVEY_FIELDS.some(([, field]) => row[field] != null);
  const title = row.report
    ? `<a href="${esc(row.report)}" target="_blank" rel="noopener">${esc(t("survey_title"))}</a>`
    : esc(t("survey_title"));
  const year = row.year ? ` <span class="na">${esc(String(row.year))}</span>` : "";
  if (!any) return `<div class="survey"><div>${title}${year}</div><div class="na">${t("no_data")}</div></div>`;
  const lines = SURVEY_FIELDS.map(([key, field]) => {
    const value = row[field];
    const shown = value == null ? `<span class="na">${t("no_data")}</span>` : `${esc(Number(value).toFixed(1))}%`;
    return `<div><span class="k">${esc(t(key))}</span>${shown}</div>`;
  }).join("");
  return `<div class="survey"><div>${title}${year}</div>${lines}<div class="note">${esc(t("survey_note"))}</div></div>`;
}
function schoolPopupHtml(school) {
  const result = listedResult(school);
  const name = displayName(school);
  const phoneDigits = String(school.phone || "").replace(/[^\d+]/g, "");
  const phone = phoneDigits
    ? `<a href="tel:${esc(phoneDigits)}">${esc(school.phone)}</a>`
    : `<span class="na">${t("no_data")}</span>`;
  let siteHost = school.website || "";
  try { siteHost = new URL(school.website).host.replace(/^www\./, ""); } catch (e) { /* keep the stored text */ }
  const site = school.website
    ? `<a href="${esc(school.website)}" target="_blank" rel="noopener">${esc(siteHost)}</a>`
    : `<span class="na">${t("no_data")}</span>`;
  const address = school.address ? esc(school.address) : `<span class="na">${t("no_data")}</span>`;
  let zoneLine = "";
  if (zonesState === "failed") {
    zoneLine = `<div><span class="k">${esc(t("attendance_zone"))}</span><span class="na">${esc(t("zone_load_failed"))}</span></div>`;
  } else if (zonesState === "ready" && !chooseZones(school, zones, state.program).attendance.length) {
    zoneLine = `<div><span class="k">${esc(t("attendance_zone"))}</span><span class="na">${t("no_data")}</span></div>`;
  }
  const exam = result.exam === "pat9" ? t("grade9") : result.exam === "pat6" ? t("grade6") : "";
  const score = result.score == null
    ? t("no_data")
    : `${fmtScore(result.score)}${exam ? " · " + exam : ""}${result.year ? " · " + result.year : ""}`;
  const programs = (school.program_names || []).filter(Boolean);
  const programLine = programs.length ? `<div><span class="k">${esc(t("filter_program"))}</span>${esc(programs.join(", "))}</div>` : "";
  const enrol = school.enrolment == null ? "" : `<div><span class="k">${esc(t("enrolment"))}</span>${Number(school.enrolment).toLocaleString()}</div>`;
  const official = `<div class="official"><a href="https://www.cbe.ab.ca/find-a-school" target="_blank" rel="noopener">${esc(t("cbe_finder"))}</a><div class="note">${esc(t("official_note"))}</div></div>`;
  return `<div class="school-pop"><strong>${esc(name)}</strong>
    <div><span class="k">${esc(t("website"))}</span>${site}</div>
    <div><span class="k">${esc(t("phone"))}</span>${phone}</div>
    <div><span class="k">${esc(t("address"))}</span>${address}</div>
    ${zoneLine}
    <div><span class="k">${esc(t("board"))}</span>${esc(school.board || "–")}</div>
    <div><span class="k">${esc(t("grades"))}</span>${esc(school.cbe_grades || school.grades || "–")}</div>
    <div><span class="k">${esc(t("col_score"))}</span>${esc(score)}</div>
    ${enrol}${programLine}${surveyHtml(school)}${official}</div>`;
}

const dataUrl = (name) => "data/" + name + "?v=" + encodeURIComponent(globalThis.ASSET_VERSION || "");

function ensureZones() {
  if (zonesState === "ready") return Promise.resolve(zonesState);
  if (zonesState === "loading" && zonesPromise) return zonesPromise;
  zonesState = "loading";
  zonesPromise = fetch(dataUrl("zones.geojson")).then((response) => {
    if (!response.ok) throw new Error("zones.geojson " + response.status);
    return response.json();
  }).then((fc) => {
    zones = (fc && fc.features) || [];
    zonesState = "ready";
    return zonesState;
  }).catch(() => {
    zones = [];
    zonesState = "failed";
    zonesPromise = null;
    return zonesState;
  });
  return zonesPromise;
}

const zonePanel = createZonePanel({
  t, orNA,
  schools: () => schools,
  zones: () => zones,
  zonesState: () => zonesState,
  ensureZones,
  communities: () => communities,
  profiles: () => communityProfiles,
  program: () => state.program,
  closeTerm: () => closeTerm(),
});

const mapView = createMap({
  t,
  schools: () => schools,
  zones: () => zones,
  zonesState: () => zonesState,
  ensureZones,
  communities: () => communities,
  program: () => state.program,
  filter: filterOf,
  popupHtml: schoolPopupHtml,
  openZonePanel: (id) => zonePanel.openZonePanel(id),
  panelSchoolId: () => zonePanel.panelSchoolId(),
  syncZonePanel: () => {
    const id = zonePanel.panelSchoolId();
    if (id) zonePanel.fillZonePanel(id);
  },
});

function renderRank() {
  refreshFilterLabels();
  const filter = filterOf();
  const rows = schools.filter((s) => inConfig(s, filter) && passesDirectory(s, filter));
  const mixed = state.grade === "all";
  const shown = sortListed(rows.map((s) => ({ school: s, result: listedResult(s) })), mixed);
  const placeByExam = {};
  let scored = 0;
  const withBreak = (value) => esc(value).replaceAll("/", "/\u200b");
  const picked = mapView.pickedId();
  document.querySelector("#rankTable tbody").innerHTML = shown.map(({ school: s, result }) => {
    let rank = "–";
    if (result.score != null) {
      scored += 1;
      const key = mixed ? (result.exam || "") : "one";
      placeByExam[key] = (placeByExam[key] || 0) + 1;
      rank = String(placeByExam[key]);
    }
    const detail = result.detail;
    const tip = detail && detail.acc != null ? `${rateText("pat_acc", detail.acc)} · ${rateText("pat_exc", detail.exc)}` : "";
    const name = withBreak(displayName(s));
    const examTag = mixed && result.exam ? ` <span class="small">${esc(t(result.exam === "pat9" ? "grade9" : "grade6"))}</span>` : "";
    return `<tr data-id="${esc(s.id)}" class="${String(s.id) === picked ? "sel" : ""}"><td class="num">${rank}</td><td>${name}</td>
      <td>${esc(s.board || "–")}</td><td>${withBreak(s.cbe_grades || s.grades || "–")}</td>
      <td class="num score" title="${esc(tip)}">${orNA(fmtScore(result.score))}${examTag}</td><td class="num">${result.year || "–"}</td>
      <td class="more"><button type="button" class="more-btn" data-more="${esc(s.id)}" aria-label="${esc(t("more_zone"))}">»</button></td></tr>`;
  }).join("");
  const allPrograms = document.querySelector("#programFilter option[value=all]");
  if (allPrograms) allPrograms.textContent = t("filter_all_programs");
  const filtered = state.program !== "all" || state.query;
  document.getElementById("rankNote").textContent = t(filtered ? "rank_note_filter" : noteForConfig(filter))
    .replace("{n}", String(rows.length))
    .replace("{scored}", String(scored));
  syncNotesMore();
  const panelId = zonePanel.panelSchoolId();
  if (panelId && !shown.some(({ school }) => String(school.id) === panelId)) zonePanel.closeZonePanel();
  else if (panelId) zonePanel.fillZonePanel(panelId);
  mapView.render();
}

function rerenderAll() {
  applyI18n();
  renderRank();
}

Promise.all(["communities.geojson", "schools.json", "cbe_directory.json", "ab_contacts.json"].map((name) => fetch(dataUrl(name)).then((r) => {
  if (!r.ok) throw new Error(name + " " + r.status); return r.json(); })))
  .then(([fc, sch, directory, contacts]) => {
    communities = fc.features; schools = sch;
    mergeDirectory(directory);
    mergeContacts(contacts);
    const profilesPromise = fetch(dataUrl("community_profiles.json")).then((r) => r.ok ? r.json() : null).catch(() => null);
    const assurancePromise = fetch(dataUrl("assurance.json")).then((r) => r.ok ? r.json() : null).catch(() => null);
    return Promise.all([profilesPromise, assurancePromise]);
  })
  .then(([profiles, assurance]) => {
    if (!communities.length) return;
    communityProfiles = (profiles && profiles.communities) || {};
    applyAssurance(assurance);
    rerenderAll();
    document.body.dataset.ready = "1";
  })
  .catch((err) => {
    const note = document.getElementById("rankNote");
    if (!note) return;
    const detail = err && err.message ? String(err.message) : "";
    note.textContent = t("load_failed").replace("{detail}", detail).trim();
  });

document.getElementById("lang").addEventListener("change", (e) => {
  const next = e.target.value;
  if (!LANGS.includes(next)) return;
  state.lang = next;
  const url = new URL(location.href);
  url.searchParams.set("lang", next);
  history.replaceState(null, "", url);
  rerenderAll();
});
document.getElementById("boardFilter").addEventListener("change", (e) => {
  state.board = e.target.value;
  fillGradeFilter();
  renderRank();
});
document.getElementById("gradeFilter").addEventListener("change", (e) => {
  state.grade = e.target.value;
  renderRank();
});
document.getElementById("programFilter").addEventListener("change", (e) => {
  state.program = e.target.value;
  renderRank();
});

const scoreSource = document.getElementById("scoreSource");
const scoreSourcePop = document.getElementById("scoreSourcePop");
function placeScoreSource() {
  const mark = scoreSource.getBoundingClientRect();
  const pop = scoreSourcePop.getBoundingClientRect();
  let left = mark.right - pop.width;
  left = Math.max(8, Math.min(left, window.innerWidth - pop.width - 8));
  let top = mark.bottom + 6;
  if (top + pop.height > window.innerHeight - 8) top = Math.max(8, mark.top - pop.height - 6);
  scoreSourcePop.style.left = left + "px";
  scoreSourcePop.style.top = top + "px";
}
function setScoreSource(open) {
  scoreSourcePop.hidden = !open;
  scoreSource.setAttribute("aria-expanded", open ? "true" : "false");
  if (open) placeScoreSource();
}
scoreSource.addEventListener("click", (e) => {
  e.stopPropagation();
  closeTerm();
  setScoreSource(scoreSourcePop.hidden);
});
scoreSourcePop.addEventListener("click", (e) => e.stopPropagation());
const termPop = document.getElementById("termPop");
let termButton = null;
function closeTerm() {
  if (!termPop) return;
  termPop.hidden = true;
  if (termButton) termButton.setAttribute("aria-expanded", "false");
  termButton = null;
}
function openTerm(button) {
  setScoreSource(false);
  if (termButton && termButton !== button) termButton.setAttribute("aria-expanded", "false");
  termButton = button;
  termPop.textContent = t("term_" + button.dataset.term);
  termPop.hidden = false;
  button.setAttribute("aria-expanded", "true");
  const mark = button.getBoundingClientRect();
  const pop = termPop.getBoundingClientRect();
  const paneRight = document.getElementById("listPane").getBoundingClientRect().right - 8;
  let left = mark.left;
  if (left + pop.width > paneRight) left = paneRight - pop.width;
  left = Math.max(8, Math.min(left, window.innerWidth - pop.width - 8));
  let top = mark.bottom + 6;
  if (top + pop.height > window.innerHeight - 8) top = Math.max(8, mark.top - pop.height - 6);
  termPop.style.left = left + "px";
  termPop.style.top = top + "px";
}
document.getElementById("zonePanelBody").addEventListener("click", (e) => {
  const button = e.target.closest("[data-term]");
  if (!button) return;
  e.stopPropagation();
  if (termButton === button) closeTerm();
  else openTerm(button);
});
termPop.addEventListener("click", (e) => e.stopPropagation());
document.getElementById("zonePanelBody").addEventListener("scroll", () => closeTerm());
document.addEventListener("click", () => { setScoreSource(false); closeTerm(); });
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  setScoreSource(false);
  if (termPop && !termPop.hidden) { closeTerm(); return; }
  zonePanel.closeZonePanel();
});
document.getElementById("zonePanelClose").addEventListener("click", () => zonePanel.closeZonePanel());
document.getElementById("notesMore").addEventListener("click", (e) => {
  e.stopPropagation();
  notesOpen = !notesOpen;
  syncNotesMore();
});
window.addEventListener("resize", syncNotesMore);
document.getElementById("rankScroll").addEventListener("scroll", () => { if (!scoreSourcePop.hidden) placeScoreSource(); });
document.getElementById("search").addEventListener("input", (e) => {
  state.query = e.target.value;
  renderRank();
});
document.querySelector("#rankTable tbody").addEventListener("click", (e) => {
  if (e.target.closest("a")) return;
  const more = e.target.closest("[data-more]");
  const tr = e.target.closest("tr");
  if (!tr || !tr.dataset.id) return;
  if (more) zonePanel.openZonePanel(tr.dataset.id);
  mapView.focusSchool(tr.dataset.id);
});
