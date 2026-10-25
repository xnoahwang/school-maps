/* Front-end logic for Calgary school ranking (by PAT).
 * The page that opens is the school ranking list beside the map. Scores come
 * from web/data/ and are displayed, not recalculated, except when a CBE grade
 * range calls for the other exam's latest-year block. Clicking a school draws
 * its CBE zone from zones.geojson. A school with no CBE zone outlines the
 * community its point falls in. Optional URL param: ?lang=fr
 */
(function () {
  "use strict";
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
  let communities = [], schools = [], zones = [], schoolLayer;
  let communityProfiles = {};
  let assuranceByCode = new Map();
  let pickedZoneLayer = null, pickedWalkLayer = null;

  const t = (key) => (I18N[state.lang][key] ?? I18N.en[key] ?? key);
  const fmtScore = (v) => v == null ? null : v.toFixed(1);
  const orNA = (s) => s == null ? `<span class="na">${t("no_data")}</span>` : s;

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

  // The grade and ranking notes are long. Keep about two lines until more is clicked.
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

  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"
  }[ch]));

  // City grades are bands, not numbers. Used when a school is not in the CBE directory.
  function citySpan(grades) {
    if (!grades || grades === "Unknown") return null;
    let low = null, high = null;
    const add = (a, b) => { low = low == null ? a : Math.min(low, a); high = high == null ? b : Math.max(high, b); };
    for (const part of grades.split("/")) {
      const name = part.trim();
      if (name === "Elementary") add(0, 6);
      else if (name === "Junior High") add(7, 9);
      else if (name === "Senior High") add(10, 12);
    }
    return low == null ? null : [low, high];
  }

  function schoolSpan(school) {
    if (school.grade_min != null && school.grade_max != null) return [school.grade_min, school.grade_max];
    return citySpan(school.grades);
  }

  function displayName(school) {
    return school.cbe_name || school.name;
  }

  // Grade 10 and above stays off the list. This ranking is elementary and junior high.
  function isHighSchool(school) {
    if (school.senior) return true;
    const span = schoolSpan(school);
    return !!(span && span[1] >= 10);
  }

  function rangeEnds(label) {
    const [low, high] = String(label).split("-");
    const num = (part) => part === "K" ? 0 : Number(part);
    return [num(low), high == null ? num(low) : num(high)];
  }

  // Which published exam this grade range actually writes. Not a new score: the latest-year block is already in the data.
  function examForSpan(span) {
    if (!span || span[1] >= 10) return null;
    if (span[1] >= 9 && span[0] <= 9) return "pat9";
    if (span[1] >= 6 && span[0] <= 6) return "pat6";
    return null;
  }

  function blockScore(block) {
    if (!block || block.acc == null || block.exc == null) return null;
    return Math.round((block.acc + block.exc) / 2 * 10) / 10;
  }

  // CBE ranges use the published span. Schools outside that directory fall back to the city grade band.
  function listedExam(school) {
    const fromSpan = examForSpan(schoolSpan(school));
    if (school.cbe_grades) return fromSpan;
    if (fromSpan) return fromSpan;
    if (school.rank_exam === "pat6" || school.rank_exam === "pat9") return school.rank_exam;
    return null;
  }

  function listedResult(school) {
    const exam = listedExam(school);
    const block = exam === "pat9" ? school.g9_latest : exam === "pat6" ? school.g6_latest : null;
    // Prefer the score the pipeline already rounded. Recompute only when the CBE grade range calls for the other exam.
    if (exam && school.rank_exam === exam) return { score: school.rank_score, year: school.rank_year, exam, detail: block };
    const fromBlock = blockScore(block);
    if (fromBlock != null) return { score: fromBlock, year: block.year || null, exam, detail: block };
    return { score: null, year: null, exam, detail: null };
  }

  // These authorities run Calgary public charter schools. Their legal names do not contain "Charter".
  const CHARTER_BOARDS = new Set([
    "Calgary Girls' School Society",
    "Calgary Arts Academy Society",
    "Almadina School Society",
    "STEM Innovation Academy Society",
    "Alberta Classical Academy Ltd.",
  ]);

  function boardGroup(school) {
    const board = school.board || "";
    if (!board) return null;
    if (board === "The Calgary School Division") return "cbe";
    if (board === "The Calgary Roman Catholic Separate School Division") return "cssd";
    if (board === "The Southern Francophone Education Region") return "franco";
    if (board.includes("Charter") || CHARTER_BOARDS.has(board)) return "charter";
    if (board.includes("School Division") || board.includes("Education Region")) return "other_public";
    return "private";
  }

  function gradeBand(school) {
    const exam = listedExam(school);
    if (exam === "pat6") return "elem";
    if (exam === "pat9") return "junior";
    return "unknown";
  }

  function inConfig(school) {
    if (isHighSchool(school) || !school.board) return false;
    if (state.board !== "all" && boardGroup(school) !== state.board) return false;
    if (state.grade === "all") return true;
    if (state.grade === "elem") return gradeBand(school) === "elem";
    if (state.grade === "junior") return gradeBand(school) === "junior";
    if (state.grade === "unlisted") return !school.cbe_grades && gradeBand(school) === "elem";
    if (state.grade === "unknown") {
      if (state.board === "cbe") return !school.cbe_grades && gradeBand(school) === "unknown";
      return gradeBand(school) === "unknown";
    }
    return school.cbe_grades === state.grade;
  }

  function noteForConfig() {
    if (state.grade === "all") return "rank_note_all";
    if (state.grade === "junior") return "rank_note_pat9";
    if (state.grade === "elem" || state.grade === "unlisted") return "rank_note_pat6";
    if (state.grade === "unknown") return "rank_note_unknown";
    const exam = examForSpan(rangeEnds(state.grade));
    if (exam === "pat9") return "rank_note_pat9";
    if (exam === "pat6") return "rank_note_pat6";
    return "rank_note_noscore";
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

  function passesDirectory(school) {
    if (state.program !== "all" && !(school.program_names || []).includes(state.program)) return false;
    const q = state.query.toLowerCase();
    if (!q) return true;
    const programs = (school.program_names || []).join(" ");
    return (displayName(school) + " " + school.name + " " + (school.board || "") + " " + programs).toLowerCase().includes(q);
  }

  function renderRank() {
    refreshFilterLabels();
    const rows = schools.filter((s) => inConfig(s) && passesDirectory(s));
    const mixed = state.grade === "all";
    const shown = rows.map((s) => ({ school: s, result: listedResult(s) }));
    const examOrder = { pat6: 0, pat9: 1 };
    shown.sort((a, b) => {
      if (mixed && (a.result.exam || "") !== (b.result.exam || "")) {
        return (examOrder[a.result.exam] ?? 2) - (examOrder[b.result.exam] ?? 2);
      }
      if (a.result.score == null && b.result.score == null) return displayName(a.school).localeCompare(displayName(b.school));
      if (a.result.score == null) return 1;
      if (b.result.score == null) return -1;
      return b.result.score - a.result.score || displayName(a.school).localeCompare(displayName(b.school));
    });
    const placeByExam = {};
    let scored = 0;
    // A slash is a real separator, as in Elementary/Junior, so the cell may break there.
    const withBreak = (value) => esc(value).replaceAll("/", "/\u200b");
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
      const nameShown = displayName(s);
      const name = withBreak(nameShown);
      const examTag = mixed && result.exam ? ` <span class="small">${esc(t(result.exam === "pat9" ? "grade9" : "grade6"))}</span>` : "";
      return `<tr data-id="${esc(s.id)}" class="${String(s.id) === pickedId ? "sel" : ""}"><td class="num">${rank}</td><td>${name}</td>
        <td>${esc(s.board || "–")}</td><td>${withBreak(s.cbe_grades || s.grades || "–")}</td>
        <td class="num score" title="${esc(tip)}">${orNA(fmtScore(result.score))}${examTag}</td><td class="num">${result.year || "–"}</td>
        <td class="more"><button type="button" class="more-btn" data-more="${esc(s.id)}" aria-label="${esc(t("more_zone"))}">»</button></td></tr>`;
    }).join("");
    const allPrograms = document.querySelector("#programFilter option[value=all]");
    if (allPrograms) allPrograms.textContent = t("filter_all_programs");
    const filtered = state.program !== "all" || state.query;
    document.getElementById("rankNote").textContent = t(filtered ? "rank_note_filter" : noteForConfig())
      .replace("{n}", String(rows.length))
      .replace("{scored}", String(scored));
    syncNotesMore();
    if (panelSchoolId && !shown.some(({ school }) => String(school.id) === panelSchoolId)) closeZonePanel();
    else if (panelSchoolId) fillZonePanel(panelSchoolId);
    renderRankMap();
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
        // City coordinates stay. The directory point fills a school the city file did not locate.
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

  // Same rules as build_data.normalize_name, so a name match uses the key the contact file stored.
  const NAME_STOP = new Set(["the", "school", "of", "and", "campus"]);
  function contactKey(name) {
    let text = String(name || "").toLowerCase().replace(/&/g, " and ");
    text = text.replace(/\bst\.?\s/g, "saint ");
    text = text.replace(/[^a-z0-9 ]+/g, " ");
    return text.split(/\s+/).filter((word) => word && !NAME_STOP.has(word)).join(" ");
  }
  function contactCode(value) {
    const text = String(value == null ? "" : value).replace(/\.0$/, "").trim();
    if (!text) return "";
    return text.replace(/^0+/, "") || "0";
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
      // The exam code is the same Alberta school code. A shared name (two St. Matthew schools) is not guessed.
      const row = byCode.get(contactCode(school.pat_code)) || byKey.get(contactKey(school.name));
      if (!row) return;
      if (!school.phone && row.phone) school.phone = row.phone;
      if (!school.website && row.website) school.website = row.website;
    });
  }

  // The percent mark follows the number: 达标率 96.5%. A missing rate stays a dash.
  function rateShown(value) {
    return value == null || value === "" ? "–" : `${value}%`;
  }

  function rateText(labelKey, value) {
    return `${t(labelKey)} ${rateShown(value)}`;
  }

  // Same schools as the ranking list. A later filter replaces the points and leaves the view where it is.
  let rankMapFitted = false;
  let pickedId = null;
  let panelSchoolId = null;
  const markerById = new Map();
  let focusToken = 0;
  function schoolPoint(school) {
    const lat = Number(school.lat), lon = Number(school.lon);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
    if (Math.abs(lat) > 90 || Math.abs(lon) > 180) return null;
    return [lat, lon];
  }
  function pointStyle(school, picked) {
    const result = listedResult(school);
    return {
      radius: picked ? 8 : 5, weight: picked ? 3 : 1,
      color: picked ? "#f5a623" : "#12355b",
      fillColor: result.score == null ? "#ffffff" : "#12355b", fillOpacity: 0.9,
    };
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
    const zone = chooseZones(school);
    const zoneLine = zone.attendance.length
      ? ""
      : `<div><span class="k">${esc(t("attendance_zone"))}</span><span class="na">${t("no_data")}</span></div>`;
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
  // pinToTop is for a map click: the sticky header was covering the row, so it never looked like the first one.
  function revealRankRow(id, pinToTop) {
    const tr = document.querySelector(`#rankTable tbody tr[data-id="${CSS.escape(id)}"]`);
    if (!tr) return;
    const scroller = document.getElementById("rankScroll");
    const head = document.querySelector("#rankTable thead");
    const headH = head ? head.getBoundingClientRect().height : 0;
    const row = tr.getBoundingClientRect();
    const box = scroller.getBoundingClientRect();
    const top = box.top + headH;
    if (pinToTop || row.top < top || row.bottom > box.bottom) scroller.scrollTop += row.top - top;
  }
  function restylePicked(nextId) {
    if (pickedId && pickedId !== nextId && markerById.has(pickedId)) {
      const prev = schools.find((s) => String(s.id) === pickedId);
      if (prev) markerById.get(pickedId).setStyle(pointStyle(prev, false));
    }
    pickedId = nextId;
    document.querySelectorAll("#rankTable tbody tr").forEach((tr) => {
      tr.classList.toggle("sel", tr.dataset.id === nextId);
    });
    const school = schools.find((s) => String(s.id) === nextId);
    const marker = markerById.get(nextId);
    if (school && marker) marker.setStyle(pointStyle(school, true));
  }
  function zonesForSchool(school) {
    if (!school) return [];
    const code = contactCode(school.cbe_code);
    if (code) return zones.filter((f) => contactCode(f.properties.school_code) === code);
    const key = contactKey(school.cbe_name || school.name);
    if (!key) return [];
    return zones.filter((f) => contactKey(f.properties.name) === key);
  }
  function chooseZones(school) {
    const matched = zonesForSchool(school);
    let attendance = matched.filter((f) => f.properties.kind === "attendance" && f.properties.band !== "senior");
    if (!attendance.length) attendance = matched.filter((f) => f.properties.kind === "attendance");
    if (state.program !== "all") {
      const filtered = attendance.filter((f) => f.properties.program === state.program);
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
  function medianOf(nums) {
    if (!nums.length) return null;
    const sorted = [...nums].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
  }
  function meanOf(nums) {
    if (!nums.length) return null;
    return nums.reduce((sum, n) => sum + n, 0) / nums.length;
  }
  // Community lists are stored only on regular-program zones. A program zone with
  // an empty list falls back to that school's regular zone, and the panel says so.
  function zoneFacts(school) {
    const matched = zonesForSchool(school);
    const picked = chooseZones(school);
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
  // Private and other non-CBE schools have no attendance zone. The city file
  // already records which community the school point falls in.
  function homeCommunity(school) {
    const code = school && school.community;
    if (!code) return null;
    return communities.find((f) => f.properties.code === code) || null;
  }
  function weightedChildren(rows) {
    let population = 0;
    let children = 0;
    rows.forEach(({ community }) => {
      if (!community || community.children_pct == null || community.children_count == null || community.children_pct <= 0) return;
      population += community.children_count / (community.children_pct / 100);
      children += community.children_count;
    });
    return population ? (children / population) * 100 : null;
  }
  function moneyFull(value) {
    return value == null ? null : "$" + Math.round(value).toLocaleString("en-CA");
  }
  function pct1(value) {
    return value == null ? null : value.toFixed(1) + "%";
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
  function profileFor(name) {
    return communityProfiles[contactKey(name)] || null;
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
  function fillZonePanel(id) {
    const school = schools.find((s) => String(s.id) === String(id));
    const title = document.getElementById("zonePanelTitle");
    const body = document.getElementById("zonePanelBody");
    if (!school || !title || !body) return;
    closeTerm();
    title.textContent = displayName(school);
    const facts = zoneFacts(school);
    if (!facts.hasZone && !facts.rows.length) {
      const home = homeCommunity(school);
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
        ${summaryTile("summary_median", orNA(moneyFull(medianOf(values))))}
        ${summaryTile("summary_mean", orNA(moneyFull(meanOf(values))))}
        ${summaryTile("fact_young", orNA(pct1(weightedChildren(facts.rows))), "summary_young")}
        ${summaryTile("fact_families", orNA(pct1(meanOf(familyRates))), "summary_families")}
      </div>
      <p class="place-kicker">${esc(t("zone_places"))}</p>
      <ul class="zone-places">${communityRows}</ul>
      ${ethnicityRow}
      ${zoneLinks()}`;
  }
  function zoneLinks() {
    return `<div class="stat"><a href="https://www.calgary.ca/communities/profiles.html" target="_blank" rel="noopener">${esc(t("profile_link"))}</a></div>
      <p class="note">${esc(t("census_next"))}</p>`;
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
  function programLabel(name) {
    return name === "Regular" ? t("program_regular") : name;
  }
  function clearSchoolZone() {
    if (pickedZoneLayer) { pickedZoneLayer.remove(); pickedZoneLayer = null; }
    if (pickedWalkLayer) { pickedWalkLayer.remove(); pickedWalkLayer = null; }
    const box = document.getElementById("zoneKey");
    if (box) box.hidden = true;
  }
  function drawSchoolZone(school) {
    clearSchoolZone();
    const picked = chooseZones(school);
    const box = document.getElementById("zoneKey");
    if (!picked.attendance.length) {
      const home = homeCommunity(school);
      if (!home) return false;
      const homeStyle = { color: "#0f6b4c", weight: 2, fillColor: "#1f8a5b", fillOpacity: 0.22 };
      pickedZoneLayer = L.geoJSON(home, { pane: "zonePane", style: homeStyle }).addTo(map);
      if (box) {
        box.innerHTML = `<div class="zone-program">${esc(home.properties.name)}</div><div><i class="home"></i>${esc(t("zone_home_community"))}</div>`;
        box.hidden = false;
      }
      return true;
    }
    const areaStyle = { color: "#12355b", weight: 2, fillColor: "#2f6fad", fillOpacity: 0.28 };
    const walkStyle = { color: "#c45c26", weight: 2.5, dashArray: "6 4", fillColor: "#f5a623", fillOpacity: 0.2 };
    pickedZoneLayer = L.geoJSON({ type: "FeatureCollection", features: picked.attendance }, { pane: "zonePane", style: areaStyle }).addTo(map);
    if (picked.walks.length) {
      pickedWalkLayer = L.geoJSON({ type: "FeatureCollection", features: picked.walks }, { pane: "zonePane", style: walkStyle }).addTo(map);
    }
    if (box) {
      const title = picked.program.split(" · ").map((name) => esc(programLabel(name))).join(" · ");
      box.innerHTML = `<div class="zone-program">${title}</div><div><i class="area"></i>${esc(t("attendance_zone"))}</div><div><i class="walk"></i>${esc(t("walk_zone"))}</div>`;
      box.hidden = false;
    }
    return true;
  }
  function schoolZoneBounds() {
    const layers = [pickedZoneLayer, pickedWalkLayer].filter(Boolean);
    if (!layers.length) return null;
    let bounds = layers[0].getBounds();
    layers.slice(1).forEach((layer) => { bounds = bounds.extend(layer.getBounds()); });
    return bounds.isValid() ? bounds : null;
  }
  // Row clicks and point clicks share this. The list name is plain text; the website link lives on the map card.
  function focusSchool(id, pinToTop) {
    const key = String(id);
    // » is what opens the panel. Once it is open, the next school click keeps it and switches it.
    if (panelSchoolId && panelSchoolId !== key) openZonePanel(key);
    const school = schools.find((s) => String(s.id) === key);
    const marker = markerById.get(key);
    const token = ++focusToken;
    restylePicked(key);
    revealRankRow(key, pinToTop);
    if (!school || !marker) { clearSchoolZone(); return; }
    const drawn = drawSchoolZone(school);
    const bounds = drawn ? schoolZoneBounds() : null;
    const point = schoolPoint(school);
    const open = () => { if (token === focusToken && markerById.get(key) === marker) marker.openPopup(); };
    if (bounds) {
      const view = map.getBounds();
      if (view.contains(bounds) && bounds.contains(map.getCenter())) open();
      else {
        map.once("moveend", open);
        map.flyToBounds(bounds, { padding: [28, 28], maxZoom: 14, duration: 0.45 });
      }
      return;
    }
    if (!point) return;
    const latlng = L.latLng(point);
    const zoom = Math.max(map.getZoom(), 15);
    const there = map.getZoom() >= 15 && map.getCenter().distanceTo(latlng) < 40;
    if (there) open();
    else {
      map.once("moveend", open);
      map.flyTo(latlng, zoom, { duration: 0.45 });
    }
  }
  function renderRankMap() {
    if (!map) return;
    map.invalidateSize();
    if (schoolLayer) schoolLayer.remove();
    markerById.clear();
    const rows = schools.filter((s) => inConfig(s) && passesDirectory(s) && schoolPoint(s));
    schoolLayer = L.layerGroup(rows.map((s) => {
      const marker = L.circleMarker(schoolPoint(s), pointStyle(s, String(s.id) === pickedId))
        .bindPopup(schoolPopupHtml(s), { maxWidth: 300, autoPan: true, autoPanPadding: [12, 12] });
      marker.off("click");
      marker.on("click", () => focusSchool(s.id, true));
      markerById.set(String(s.id), marker);
      return marker;
    })).addTo(map);
    if (!rankMapFitted && rows.length) {
      rankMapFitted = true;
      map.fitBounds(L.latLngBounds(rows.map((s) => schoolPoint(s))), { padding: [28, 28], maxZoom: 13 });
    }
    if (pickedId) {
      const still = rows.find((s) => String(s.id) === pickedId);
      if (still) drawSchoolZone(still);
      else clearSchoolZone();
    }
  }

  function rerenderAll() {
    applyI18n();
    renderRank();
  }

  let map;
  // map-zoom.mdc: scale the picture already on screen. The default wheel handler
  // waits out wheelDebounceTime, then setZoomAround. While an animation is
  // running, _tryAnimatedZoom returns without retargeting, so the next notch
  // waits; a zoom that fails the animation test hits _resetView and flashes.
  function latLngAt(containerPoint) {
    const zoom = map._animatingZoom ? map._animateToZoom : map.getZoom();
    const center = map._animatingZoom ? map._animateToCenter : map.getCenter();
    const centerPx = map.project(center, zoom);
    const half = map.getSize().divideBy(2);
    return map.unproject(centerPx.add(containerPoint.subtract(half)), zoom);
  }
  function centerKeeping(anchor, containerPoint, zoom) {
    const half = map.getSize().divideBy(2);
    const anchorPx = map.project(anchor, zoom);
    return map.unproject(anchorPx.subtract(containerPoint.subtract(half)), zoom);
  }
  map = L.map("map", {
    preferCanvas: true,
    zoomSnap: 0,
    zoomDelta: 1,
    scrollWheelZoom: false,
    wheelPxPerZoomLevel: 60
  }).setView([51.045, -114.07], 11);
  map.createPane("zonePane");
  map.getPane("zonePane").style.zIndex = 350;
  const zoneKey = document.createElement("div");
  zoneKey.id = "zoneKey";
  zoneKey.hidden = true;
  map.getContainer().appendChild(zoneKey);
  // Leaflet ends a zoom animation on a 250ms timer. A later notch in the same
  // gesture must retarget that animation; letting the timer commit mid-gesture
  // reloads the tiles. Commit only after the wheel has been quiet.
  let wheelActive = false;
  let pendingZoom = null;
  let settleTimer = 0;
  const finishZoom = map._onZoomTransitionEnd.bind(map);
  map._onZoomTransitionEnd = function () {
    if (wheelActive) return;
    finishZoom();
  };
  function retarget(center, zoom) {
    map._animateToCenter = center;
    map._animateToZoom = zoom;
    map._animateZoom(center, zoom, false, true);
  }
  map.getContainer().addEventListener("wheel", (event) => {
    if (event.ctrlKey) return;
    event.preventDefault();
    const delta = L.DomEvent.getWheelDelta(event);
    const from = map._animatingZoom ? map._animateToZoom : map.getZoom();
    const target = map._limitZoom(from + delta / map.options.wheelPxPerZoomLevel);
    if (target === from) return;
    const mouse = map.mouseEventToContainerPoint(event);
    const center = centerKeeping(latLngAt(mouse), mouse, target);
    wheelActive = true;
    clearTimeout(settleTimer);
    settleTimer = setTimeout(() => {
      wheelActive = false;
      if (map._animatingZoom) finishZoom();
    }, 280);
    if (map._animatingZoom) {
      pendingZoom = null;
      retarget(center, target);
    } else if (map._smoothZoomPending) {
      pendingZoom = { center, zoom: target };
    } else {
      map._smoothZoomPending = true;
      map.once("zoomanim", () => {
        map._smoothZoomPending = false;
        if (!pendingZoom) return;
        const next = pendingZoom;
        pendingZoom = null;
        retarget(next.center, next.zoom);
      });
      map.setZoomAround(mouse, target, { animate: true });
    }
  }, { passive: false });
  // Standard OSM tiles: free, no API key (Carto's keyless basemaps now show an "API key required" watermark).
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19, opacity: 0.6 }).addTo(map);

  const dataUrl = (name) => "data/" + name + "?v=20261006d";
  Promise.all(["communities.geojson", "schools.json", "cbe_directory.json", "ab_contacts.json"].map((name) => fetch(dataUrl(name)).then((r) => {
    if (!r.ok) throw new Error(name + " " + r.status); return r.json(); })))
    .then(([fc, sch, directory, contacts]) => {
      communities = fc.features; schools = sch;
      mergeDirectory(directory);
      mergeContacts(contacts);
      const zonesPromise = fetch(dataUrl("zones.geojson")).then((r) => r.ok ? r.json() : { features: [] }).catch(() => ({ features: [] }));
      const profilesPromise = fetch(dataUrl("community_profiles.json")).then((r) => r.ok ? r.json() : null).catch(() => null);
      const assurancePromise = fetch(dataUrl("assurance.json")).then((r) => r.ok ? r.json() : null).catch(() => null);
      return Promise.all([zonesPromise, profilesPromise, assurancePromise]);
    })
    .then(([zoneFc, profiles, assurance]) => {
      if (!communities.length) return;
      zones = (zoneFc && zoneFc.features) || [];
      communityProfiles = (profiles && profiles.communities) || {};
      applyAssurance(assurance);
      rerenderAll();
      document.body.dataset.ready = "1";
    })
    .catch((err) => {
      const note = document.getElementById("rankNote");
      if (note) note.textContent = "Failed to load data: " + err.message;
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
    closeZonePanel();
  });
  document.getElementById("zonePanelClose").addEventListener("click", () => closeZonePanel());
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
    if (more) openZonePanel(tr.dataset.id);
    focusSchool(tr.dataset.id);
  });
})();
