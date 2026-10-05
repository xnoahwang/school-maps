/* Front-end logic for the Calgary School & Community Explorer.
 * Loads web/data/*.json produced by scripts/build_data.py, draws the Leaflet
 * choropleth, the sortable community table and the detail panel, and handles
 * the EN/中文 toggle. It never computes scores itself; it only displays them.
 * Optional URL params: ?lang=zh&metric=home_value&community=<CODE>
 */
(function () {
  "use strict";
  const params = new URLSearchParams(location.search);
  const RANK_FIRST = document.body.classList.contains("rank-first");
  const state = { lang: params.get("lang") === "zh" ? "zh" : "en", metric: params.get("metric") || "school_score",
                  sortKey: "school_score", sortAsc: false, selected: params.get("zone") || params.get("community"), query: "",
                  unit: params.get("unit") === "community" ? "community" : "zone", band: params.get("band") || "elem",
                  config: "K-6", program: "all", letter: "all" };
  let communities = [], schools = [], zones = [], viewFeatures = [], meta = {}, geoLayer, walkLayer, schoolLayer, legend;
  const NO_DATA_COLOR = "#c8ced6";
  // Red→yellow→green "risk map" ramp: green = better schools / better value.
  const RAMP_GOOD = ["#d7191c", "#fdae61", "#ffffbf", "#a6d96a", "#1a9641"];
  // Price is not good/bad, so it gets a neutral sequential ramp.
  const RAMP_PRICE = ["#f2f0f7", "#cbc9e2", "#9e9ac8", "#756bb1", "#54278f"];
  // Context metrics are not "better/worse" the way a school score is.
  const NEUTRAL = new Set(["home_value", "home_value_change_pct", "children_pct", "families_with_children_pct"]);

  const t = (key) => (I18N[state.lang][key] ?? I18N.en[key] ?? key);
  const fmtMoney = (v) => v == null ? null : "$" + Math.round(v / 1000).toLocaleString() + "k";
  const fmtScore = (v) => v == null ? null : v.toFixed(1);
  const fmt = (key, v) => {
    if (v == null) return null;
    if (key === "home_value" || key === "home_value_prev") return fmtMoney(v);
    if (key === "home_value_change_pct") return (v > 0 ? "+" : "") + v.toFixed(1) + "%";
    if (key === "children_pct" || key === "families_with_children_pct") return v.toFixed(1) + "%";
    return fmtScore(v);
  };
  const orNA = (s) => s == null ? `<span class="na">${t("no_data")}</span>` : s;

  /** Quintile breaks over non-null values; returns [] when there is no data. */
  function breaks(key) {
    const vals = viewFeatures.map((c) => c.properties[key]).filter((v) => v != null).sort((a, b) => a - b);
    if (!vals.length) return [];
    return [0.2, 0.4, 0.6, 0.8].map((q) => vals[Math.floor(q * (vals.length - 1))]);
  }
  function colorFor(key, v, brk) {
    if (v == null || !brk.length) return NO_DATA_COLOR;
    const ramp = NEUTRAL.has(key) ? RAMP_PRICE : RAMP_GOOD;
    let i = 0; while (i < brk.length && v > brk[i]) i++;
    return ramp[i];
  }

  function applyI18n() {
    document.documentElement.lang = state.lang === "zh" ? "zh-CN" : "en";
    document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
    document.getElementById("search").placeholder = RANK_FIRST ? t("search_school") : (state.unit === "zone" ? t("search_zone") : t("search"));
    document.getElementById("lang").textContent = t("lang_btn");
    document.title = t("title");
  }

  function styleFeature(f) {
    const brk = breaks(state.metric);
    const sel = f.properties.code === state.selected;
    return { fillColor: colorFor(state.metric, f.properties[state.metric], brk), fillOpacity: 0.72,
             color: sel ? "#000" : "#ffffff", weight: sel ? 3 : 0.8 };
  }

  function renderLegend() {
    if (legend) legend.remove();
    legend = L.control({ position: "bottomright" });
    legend.onAdd = () => {
      const div = L.DomUtil.create("div", "legend");
      const brk = breaks(state.metric);
      const ramp = NEUTRAL.has(state.metric) ? RAMP_PRICE : RAMP_GOOD;
      if (!brk.length) {
        div.innerHTML = `<b>${t("m_" + state.metric)}</b><br><i style="background:${NO_DATA_COLOR}"></i>${t("no_data")}`;
        return div;
      }
      const edges = [null, ...brk, null];
      let html = `<b>${t("m_" + state.metric)}</b><br>`;
      ramp.forEach((c, i) => {
        const lo = edges[i] == null ? "" : fmt(state.metric, edges[i]);
        const hi = edges[i + 1] == null ? "" : fmt(state.metric, edges[i + 1]);
        html += `<i style="background:${c}"></i>${lo || "≤"} ${lo && hi ? "–" : ""} ${hi || "+"}<br>`;
      });
      html += `<i style="background:${NO_DATA_COLOR}"></i>${t("no_data")}`;
      div.innerHTML = html;
      return div;
    };
    legend.addTo(map);
  }

  function renderTable() {
    const tbody = document.querySelector("#commTable tbody");
    const q = state.query.toLowerCase();
    const rows = viewFeatures.map((f) => f.properties).filter((p) => {
      if (!q) return true;
      const places = (p.places || []).map((x) => x.name).join(" ");
      return (p.name + " " + places).toLowerCase().includes(q);
    });
    const k = state.sortKey, dir = state.sortAsc ? 1 : -1;
    rows.sort((a, b) => {
      if (k === "name") return dir * a.name.localeCompare(b.name);
      if (a[k] == null) return 1; if (b[k] == null) return -1;  // no-data always last
      return dir * (a[k] - b[k]);
    });
    const brk = breaks(state.metric);
    tbody.innerHTML = rows.map((p) => `<tr data-code="${p.code}" class="${p.code === state.selected ? "sel" : ""}">
      <td><span class="chip" style="background:${colorFor(state.metric, p[state.metric], brk)}"></span>${p.name}</td>
      <td class="num">${orNA(fmtScore(p.school_score))}</td><td class="num">${orNA(fmtMoney(p.home_value))}</td>
      <td class="num">${orNA(fmtScore(p.value_score))}</td></tr>`).join("");
    document.querySelectorAll("#commTable th").forEach((th) => {
      th.classList.toggle("sorted", th.dataset.key === k); th.classList.toggle("asc", th.dataset.key === k && state.sortAsc);
    });
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

  // Grade 10 and above is high school. Diploma results are not public, so those schools stay off the list.
  function isHighSchool(school) {
    if (school.senior || school.rank_exam === "diploma") return true;
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

  function outsideBucket(school) {
    if (school.cbe_grades || isHighSchool(school)) return null;
    const exam = listedExam(school);
    if (exam === "pat9") return "other_junior";
    if (exam === "pat6") return "other_elem";
    return "other_unknown";
  }

  function inConfig(school) {
    if (isHighSchool(school)) return false;
    if (state.config === "other_elem" || state.config === "other_junior" || state.config === "other_unknown") {
      return outsideBucket(school) === state.config;
    }
    return school.cbe_grades === state.config;
  }

  function noteForConfig() {
    if (state.config === "other_elem") return "rank_note_other_elem";
    if (state.config === "other_junior") return "rank_note_other_junior";
    if (state.config === "other_unknown") return "rank_note_unknown";
    const span = rangeEnds(state.config);
    const exam = examForSpan(span);
    if (exam === "pat9") return "rank_note_pat9";
    if (exam === "pat6") return "rank_note_pat6";
    return "rank_note_noscore";
  }

  function fillGradeConfig() {
    const labels = new Set();
    schools.forEach((school) => {
      if (!isHighSchool(school) && school.cbe_grades) labels.add(school.cbe_grades);
    });
    const select = document.getElementById("gradeConfig");
    if (!select) return;
    select.replaceChildren();
    [...labels].sort((a, b) => {
      const [al, ah] = rangeEnds(a);
      const [bl, bh] = rangeEnds(b);
      return al - bl || ah - bh || a.localeCompare(b);
    }).forEach((label) => {
      const option = document.createElement("option");
      option.value = label;
      option.textContent = label;
      select.appendChild(option);
    });
    ["other_elem", "other_junior", "other_unknown"].forEach((value) => {
      if (!schools.some((school) => outsideBucket(school) === value)) return;
      const option = document.createElement("option");
      option.value = value;
      option.textContent = t("config_" + value);
      select.appendChild(option);
    });
    if (![...select.options].some((option) => option.value === state.config)) state.config = "K-6";
    select.value = state.config;
  }

  function passesDirectory(school) {
    if (state.program !== "all" && !(school.program_names || []).includes(state.program)) return false;
    if (state.letter !== "all" && displayName(school).trim().charAt(0).toUpperCase() !== state.letter) return false;
    const q = state.query.toLowerCase();
    if (!q) return true;
    const programs = (school.program_names || []).join(" ");
    return (displayName(school) + " " + school.name + " " + (school.board || "") + " " + programs).toLowerCase().includes(q);
  }

  function renderRank() {
    document.querySelectorAll("#letterFilters button").forEach((btn) => btn.classList.toggle("on", btn.dataset.letter === state.letter));
    ["other_elem", "other_junior", "other_unknown"].forEach((value) => {
      const option = document.querySelector("#gradeConfig option[value=" + value + "]");
      if (option) option.textContent = t("config_" + value);
    });
    const rows = schools.filter((s) => inConfig(s) && passesDirectory(s));
    const shown = rows.map((s) => ({ school: s, result: listedResult(s) }));
    shown.sort((a, b) => {
      if (a.result.score == null && b.result.score == null) return displayName(a.school).localeCompare(displayName(b.school));
      if (a.result.score == null) return 1;
      if (b.result.score == null) return -1;
      return b.result.score - a.result.score || displayName(a.school).localeCompare(displayName(b.school));
    });
    let place = 0;
    document.querySelector("#rankTable tbody").innerHTML = shown.map(({ school: s, result }) => {
      const rank = result.score == null ? "–" : String(++place);
      const detail = result.detail;
      const tip = detail && detail.acc != null ? `${t("pat_acc")} ${detail.acc} · ${t("pat_exc")} ${detail.exc}` : "";
      const nameShown = displayName(s);
      const name = s.website ? `<a href="${esc(s.website)}" target="_blank" rel="noopener">${esc(nameShown)}</a>` : esc(nameShown);
      const extra = [s.phone, (s.cbe_programs || []).map((p) => p.label).join(", ")].filter(Boolean).join(" · ");
      return `<tr><td class="num">${rank}</td><td>${name}${extra ? `<div class="small">${esc(extra)}</div>` : ""}</td>
        <td>${esc(s.board || "–")}</td><td>${esc(s.cbe_grades || s.grades || "–")}</td>
        <td class="num" title="${esc(tip)}">${orNA(fmtScore(result.score))}</td><td class="num">${result.year || "–"}</td></tr>`;
    }).join("");
    const allPrograms = document.querySelector("#programFilter option[value=all]");
    if (allPrograms) allPrograms.textContent = t("filter_all_programs");
    const allLetters = document.querySelector("#letterFilters button[data-letter=all]");
    if (allLetters) allLetters.textContent = t("filter_all");
    const filtered = state.program !== "all" || state.letter !== "all" || state.query;
    document.getElementById("rankNote").textContent = t(filtered ? "rank_note_filter" : noteForConfig())
      .replace("{n}", String(rows.length))
      .replace("{scored}", String(place));
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
        cbe_name: row.name, phone: row.phone, website: row.website, address: row.address,
        grade_min: row.grade_min, grade_max: row.grade_max, cbe_grades: row.grades,
        cbe_programs: row.programs, program_names: row.program_names,
      };
      if (row.school_id != null && byId.has(row.school_id)) {
        Object.assign(byId.get(row.school_id), fields);
        return;
      }
      schools.push({
        id: "cbe-" + (row.code || row.name), name: row.name, board: "The Calgary School Division",
        grades: row.grades, rank_exam: row.rank_exam, rank_score: null, rank_year: null, cbe_only: true,
        ...fields,
      });
    });
    fillProgramFilter(directory.programs);
    fillGradeConfig();
  }

  function sourceHref(entry) {
    if (!entry) return "#";
    return typeof entry === "string" ? entry : (entry.url || "#");
  }

  function reviewLine(review) {
    if (!review) return `<div class="pat na">${t("reviews_missing")}</div>`;
    if (review.too_few || review.review_score == null) {
      const n = (review.google && review.google.count) || 0;
      const posts = (review.reddit && review.reddit.n) || 0;
      return `<div class="pat na">${t("too_few")} <span class="small">(${t("google_n")} ${n}, ${t("reddit_n")} ${posts})</span></div>`;
    }
    const g = review.google;
    const range = review.date_range ? review.date_range.join(" – ") : "";
    const google = g && g.rating != null ? `${t("google_rating")} ${g.rating} (${g.count})` : t("google_na");
    return `<div class="pat">${t("review_score")}: <b>${fmtScore(review.review_score)}</b> · ${google}
      <span class="small">${t("reddit_n")} ${(review.reddit && review.reddit.n) || 0}${range ? " · " + range : ""}</span></div>`;
  }

  function attachReviews(payload) {
    const byId = (payload && payload.schools) || {};
    schools.forEach((s) => { s.review = byId[String(s.id)] || null; });
    communities.forEach((f) => {
      const scores = f.properties.nearby.map((n) => schools[n.id] && schools[n.id].review)
        .filter((r) => r && r.review_score != null && !r.too_few).map((r) => r.review_score);
      f.properties.review_score = scores.length
        ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length * 10) / 10 : null;
    });
  }

  function patLine(label, r) {
    if (!r || r.acc == null) return "";
    return `<div class="pat">${label}: ${t("pat_acc")} <b>${r.acc}</b> · ${t("pat_exc")} <b>${r.exc ?? "–"}</b>
      <span class="small">(${r.years.join(", ")})</span></div>`;
  }

  function renderPanel() {
    const panel = document.getElementById("panel");
    const f = viewFeatures.find((c) => c.properties.code === state.selected);
    if (!f) { panel.innerHTML = `<p class="hint">${t("click_hint")}</p>`; return; }
    const p = f.properties;
    if (state.unit === "zone") {
      const places = (p.places || []).map((pl) => `<div class="school"><b>${pl.name}</b>
        <span class="small">${orNA(fmtMoney(pl.home_value))} · ${pl.in_walk ? t("in_walk") : t("bus_zone")}</span></div>`).join("");
      panel.innerHTML = `<h2>${p.name}</h2><div class="small">CBE Regular · ${p.grades || ""}</div>
        <div class="kpis">
          <div class="kpi">${t("school_score")}<b>${orNA(fmtScore(p.school_score))}</b></div>
          <div class="kpi">${t("m_value_score")}<b>${orNA(fmtScore(p.value_score))}</b></div>
          <div class="kpi" style="grid-column:span 2">${t("home_value")}<b>${orNA(fmtMoney(p.home_value))}</b>
            <span class="small">${t("zone_home_note")}</span></div>
        </div>
        <p class="small">${t("zone_note")}</p>
        <h3>${t("zone_places")}</h3>${places || `<p class="na">${t("no_data")}</p>`}
        <p class="small"><a href="https://www.cbe.ab.ca/find-a-school" target="_blank">${t("cbe_finder")}</a></p>`;
      return;
    }
    const schoolHtml = p.nearby.map((n) => {
      const s = schools[n.id];
      const pats = (s.elem ? patLine(t("grade6"), s.g6) : "") + (s.junior ? patLine(t("grade9"), s.g9) : "");
      const needsPat = s.elem || s.junior;
      const enrol = s.enrolment == null ? "" : `<div class="meta">${t("enrolment")}: ${s.enrolment.toLocaleString()} <span class="small">(${s.enrolment_year || ""})</span></div>`;
      const review = reviewLine(s.review);
      return `<div class="school"><b>${s.name}</b> <span class="small">· ${t("why_" + n.why)} · ${n.km} ${t("km")}</span>
        <div class="meta">${t("board")}: ${s.board || "–"} · ${t("grades")}: ${s.grades || "–"}</div>
        ${enrol}
        ${pats || (needsPat ? `<div class="pat na">${t("pat_none")}</div>` : `<div class="pat na">${t("senior_note")}</div>`)}
        ${review}</div>`;
    }).join("");
    const src = meta.sources || {};
    panel.innerHTML = `<h2>${p.name}</h2><div class="small">${t("sector")}: ${p.sector} · ${p.code}</div>
      <div class="kpis">
        <div class="kpi">${t("school_score")}<b>${orNA(fmtScore(p.school_score))}</b></div>
        <div class="kpi">${t("m_value_score")}<b>${orNA(fmtScore(p.value_score))}</b></div>
        <div class="kpi">${t("elem_score")}<b>${orNA(fmtScore(p.elem_score))}</b></div>
        <div class="kpi">${t("junior_score")}<b>${orNA(fmtScore(p.junior_score))}</b></div>
        <div class="kpi">${t("senior_score")}<b>${orNA(fmtScore(p.senior_score))}</b>
          <span class="small">${p.senior_score == null ? t("diploma_gap") : ""}</span></div>
        <div class="kpi">${t("review_score")}<b>${orNA(fmtScore(p.review_score))}</b></div>
        <div class="kpi" style="grid-column:span 2">${t("home_value")}<b>${orNA(p.home_value == null ? null : "$" + p.home_value.toLocaleString())}</b>
          <span class="small">${p.home_accounts ? p.home_accounts.toLocaleString() + " " + t("accounts") : ""}
          ${p.home_value_change_pct == null ? "" : " · " + t("m_home_value_change_pct") + " " + fmt("home_value_change_pct", p.home_value_change_pct)}</span></div>
        <div class="kpi">${t("m_children_pct")}<b>${orNA(fmt("children_pct", p.children_pct))}</b></div>
        <div class="kpi">${t("m_families_with_children_pct")}<b>${orNA(fmt("families_with_children_pct", p.families_with_children_pct))}</b></div>
        <div class="kpi" style="grid-column:span 2">${t("rent")}: <span class="na">${t("rent_na")}</span></div>
        <div class="kpi" style="grid-column:span 2">${t("safety")}: <span class="na">${t("safety_na")}</span></div>
      </div>
      <p class="small">${t("programs_na")}</p>
      <p class="small">${t("review_method")}</p>
      <div><b>${t("amenities")}</b>: ${t("libraries")} ${orNA(p.libraries)} · ${t("transit")} ${orNA(p.transit_stops)} · ${t("parks")} ${orNA(p.parks)}</div>
      <h3>${t("nearby")}</h3>${schoolHtml}
      <p class="small">${t("method").replace("{years}", (meta.pat_years || []).join("–"))}</p>
      <p class="small"><b>${t("sources")}</b>: <a href="${sourceHref(src.pat)}" target="_blank">Alberta Education PAT</a> ·
        <a href="${sourceHref(src.schools)}" target="_blank">Calgary Schools</a> · <a href="${sourceHref(src.communities)}" target="_blank">Community boundaries</a> ·
        <a href="${sourceHref(src.parcels)}" target="_blank">2026 Property Assessments</a> · <a href="${sourceHref(src.parcels_2025)}" target="_blank">2025 assessments</a> ·
        <a href="${sourceHref(src.census_age)}" target="_blank">2021 census</a> · <a href="${sourceHref(src.enrolment)}" target="_blank">Enrolment</a> ·
        <a href="${sourceHref(src.libraries)}" target="_blank">Libraries</a> ·
        <a href="${sourceHref(src.transit)}" target="_blank">Transit stops</a> · <a href="${sourceHref(src.parks)}" target="_blank">Parks</a></p>`;
  }

  function select(code, zoom) {
    state.selected = code;
    geoLayer.setStyle(styleFeature);
    renderTable(); renderPanel();
    if (zoom) {
      const layer = geoLayer.getLayers().find((l) => l.feature.properties.code === code);
      if (layer) map.fitBounds(layer.getBounds(), { maxZoom: 13, padding: [60, 60] });
    }
  }

  function renderSchools() {
    if (schoolLayer) schoolLayer.remove();
    if (!document.getElementById("showSchools").checked) return;
    schoolLayer = L.layerGroup(schools.map((s) => {
      const sc = s.score6 ?? s.score9;
      return L.circleMarker([s.lat, s.lon], { radius: 4, weight: 1, color: "#12355b",
        fillColor: sc == null ? "#ffffff" : "#12355b", fillOpacity: 0.9 })
        .bindTooltip(`${s.name}<br>${s.board || ""}<br>${s.grades || ""}` +
          (s.score6 != null ? `<br>${t("grade6")}: ${s.score6}` : "") + (s.score9 != null ? `<br>${t("grade9")}: ${s.score9}` : ""));
    })).addTo(map);
  }

  function syncView() {
    document.getElementById("bandWrap").hidden = state.unit !== "zone";
    document.getElementById("walkWrap").hidden = state.unit !== "zone";
    if (state.unit === "zone" && zones.length) {
      viewFeatures = zones.filter((f) => f.properties.kind === "attendance" && f.properties.band === state.band);
    } else {
      viewFeatures = communities;
    }
    const nameTh = document.querySelector('#commTable th[data-key="name"]');
    if (nameTh) nameTh.dataset.i18n = state.unit === "zone" && zones.length ? "col_zone" : "col_name";
  }

  function renderGeo(fit) {
    if (geoLayer) geoLayer.remove();
    if (walkLayer) walkLayer.remove();
    geoLayer = L.geoJSON(viewFeatures, { style: styleFeature, onEachFeature: (f, layer) => {
      layer.on("click", () => select(f.properties.code, false));
      layer.bindTooltip(() => `${f.properties.name}: ${fmt(state.metric, f.properties[state.metric]) ?? t("no_data")}`, { sticky: true });
    } }).addTo(map);
    if (state.unit === "zone" && document.getElementById("showWalk").checked) {
      const keys = new Set(viewFeatures.map((f) => f.properties.code));
      const walks = zones.filter((f) => f.properties.kind === "walk" && keys.has(f.properties.code));
      walkLayer = L.geoJSON(walks, {
        style: { color: "#12355b", weight: 1.6, fillColor: "#ffffff", fillOpacity: 0.35, dashArray: "5 4" },
        onEachFeature: (f, layer) => layer.on("click", () => select(f.properties.code, false)),
      }).addTo(map);
    }
    if (fit && viewFeatures.length) map.fitBounds(geoLayer.getBounds());
  }

  function rerenderAll() {
    applyI18n();
    if (RANK_FIRST) { renderRank(); return; }
    syncView(); if (geoLayer) geoLayer.setStyle(styleFeature); renderLegend(); renderTable(); renderPanel(); renderSchools();
  }

  let map;
  if (!RANK_FIRST) {
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
  }

  const dataUrl = (name) => "data/" + name + "?v=20261005f";
  Promise.all(["communities.geojson", "schools.json", "meta.json", "cbe_directory.json"].map((name) => fetch(dataUrl(name)).then((r) => {
    if (!r.ok) throw new Error(name + " " + r.status); return r.json(); })))
    .then(([fc, sch, m, directory]) => {
      communities = fc.features; schools = sch; meta = m;
      mergeDirectory(directory);
      communities.forEach((f) => { f.properties.review_score = null; });
      document.getElementById("metric").value = state.metric;
      document.getElementById("unit").value = state.unit;
      document.getElementById("band").value = state.band;
      if (RANK_FIRST) return [{ features: [] }, null];
      return Promise.all([
        fetch(dataUrl("zones.geojson")).then((r) => r.ok ? r.json() : { features: [] }).catch(() => ({ features: [] })),
        fetch(dataUrl("reviews.json")).then((r) => r.ok ? r.json() : null).catch(() => null),
      ]);
    })
    .then(([zoneFc, reviews]) => {
      if (!communities.length) return;
      zones = (zoneFc && zoneFc.features) || [];
      if (state.unit === "zone" && !zones.length) state.unit = "community";
      attachReviews(reviews);
      if (RANK_FIRST) {
        rerenderAll();
      } else {
        syncView();
        renderGeo(true);
        rerenderAll();
        if (state.selected) select(state.selected, true);
      }
      document.body.dataset.ready = "1";
    })
    .catch((err) => { document.getElementById("panel").innerHTML = `<p class="na">Failed to load data: ${err.message}. Run scripts/build_data.py first.</p>`; });

  document.getElementById("metric").addEventListener("change", (e) => { state.metric = e.target.value; rerenderAll(); });
  document.getElementById("unit").addEventListener("change", (e) => {
    state.unit = e.target.value; state.selected = null; syncView(); renderGeo(true); rerenderAll();
  });
  document.getElementById("band").addEventListener("change", (e) => {
    state.band = e.target.value; state.selected = null; syncView(); renderGeo(true); rerenderAll();
  });
  document.getElementById("showSchools").addEventListener("change", renderSchools);
  document.getElementById("showWalk").addEventListener("change", () => { renderGeo(false); renderSchools(); });
  document.getElementById("lang").addEventListener("click", () => { state.lang = state.lang === "en" ? "zh" : "en"; rerenderAll(); });
  document.getElementById("gradeConfig").addEventListener("change", (e) => {
    state.config = e.target.value;
    renderRank();
  });
  if (RANK_FIRST) {
    const letters = document.getElementById("letterFilters");
    ["all", ..."ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("")].forEach((letter) => {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.letter = letter;
      button.textContent = letter === "all" ? t("filter_all") : letter;
      letters.appendChild(button);
    });
    letters.addEventListener("click", (e) => {
      const letter = e.target.dataset && e.target.dataset.letter;
      if (!letter || e.target.disabled) return;
      state.letter = letter;
      renderRank();
    });
    document.getElementById("programFilter").addEventListener("change", (e) => {
      state.program = e.target.value;
      renderRank();
    });
  }
  document.getElementById("search").addEventListener("input", (e) => {
    state.query = e.target.value;
    if (RANK_FIRST) renderRank(); else renderTable();
  });
  document.querySelector("#commTable thead").addEventListener("click", (e) => {
    const key = e.target.dataset.key; if (!key) return;
    state.sortAsc = state.sortKey === key ? !state.sortAsc : key === "name";
    state.sortKey = key; renderTable();
  });
  document.querySelector("#commTable tbody").addEventListener("click", (e) => {
    const tr = e.target.closest("tr"); if (tr) select(tr.dataset.code, true);
  });
})();
