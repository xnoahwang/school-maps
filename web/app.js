/* Front-end logic for the Calgary School & Community Explorer.
 * Loads web/data/*.json produced by scripts/build_data.py, draws the Leaflet
 * choropleth, the sortable community table and the detail panel, and handles
 * the EN/中文 toggle. It never computes scores itself; it only displays them.
 * Optional URL params: ?lang=zh&metric=home_value&community=<CODE>
 */
(function () {
  "use strict";
  const params = new URLSearchParams(location.search);
  const state = { lang: params.get("lang") === "zh" ? "zh" : "en", metric: params.get("metric") || "school_score",
                  sortKey: "school_score", sortAsc: false, selected: params.get("community"), query: "" };
  let communities = [], schools = [], meta = {}, geoLayer, schoolLayer, legend;
  const NO_DATA_COLOR = "#c8ced6";
  // Red→yellow→green "risk map" ramp: green = better schools / better value.
  const RAMP_GOOD = ["#d7191c", "#fdae61", "#ffffbf", "#a6d96a", "#1a9641"];
  // Price is not good/bad, so it gets a neutral sequential ramp.
  const RAMP_PRICE = ["#f2f0f7", "#cbc9e2", "#9e9ac8", "#756bb1", "#54278f"];

  const t = (key) => (I18N[state.lang][key] ?? I18N.en[key] ?? key);
  const fmtMoney = (v) => v == null ? null : "$" + Math.round(v / 1000).toLocaleString() + "k";
  const fmtScore = (v) => v == null ? null : v.toFixed(1);
  const fmt = (key, v) => key === "home_value" ? fmtMoney(v) : fmtScore(v);
  const orNA = (s) => s == null ? `<span class="na">${t("no_data")}</span>` : s;

  /** Quintile breaks over non-null values; returns [] when there is no data. */
  function breaks(key) {
    const vals = communities.map((c) => c.properties[key]).filter((v) => v != null).sort((a, b) => a - b);
    if (!vals.length) return [];
    return [0.2, 0.4, 0.6, 0.8].map((q) => vals[Math.floor(q * (vals.length - 1))]);
  }
  function colorFor(key, v, brk) {
    if (v == null || !brk.length) return NO_DATA_COLOR;
    const ramp = key === "home_value" ? RAMP_PRICE : RAMP_GOOD;
    let i = 0; while (i < brk.length && v > brk[i]) i++;
    return ramp[i];
  }

  function applyI18n() {
    document.documentElement.lang = state.lang === "zh" ? "zh-CN" : "en";
    document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
    document.getElementById("search").placeholder = t("search");
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
      const ramp = state.metric === "home_value" ? RAMP_PRICE : RAMP_GOOD;
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
    const rows = communities.map((f) => f.properties).filter((p) => !q || p.name.toLowerCase().includes(q));
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

  function patLine(label, r) {
    if (!r || r.acc == null) return "";
    return `<div class="pat">${label}: ${t("pat_acc")} <b>${r.acc}</b> · ${t("pat_exc")} <b>${r.exc ?? "–"}</b>
      <span class="small">(${r.years.join(", ")})</span></div>`;
  }

  function renderPanel() {
    const panel = document.getElementById("panel");
    const f = communities.find((c) => c.properties.code === state.selected);
    if (!f) { panel.innerHTML = `<p class="hint">${t("click_hint")}</p>`; return; }
    const p = f.properties;
    const schoolHtml = p.nearby.map((n) => {
      const s = schools[n.id];
      const pats = (s.elem ? patLine(t("grade6"), s.g6) : "") + (s.junior ? patLine(t("grade9"), s.g9) : "");
      const needsPat = s.elem || s.junior;
      return `<div class="school"><b>${s.name}</b> <span class="small">· ${t("why_" + n.why)} · ${n.km} ${t("km")}</span>
        <div class="meta">${t("board")}: ${s.board || "–"} · ${t("grades")}: ${s.grades || "–"}</div>
        ${pats || (needsPat ? `<div class="pat na">${t("pat_none")}</div>` : `<div class="pat na">${t("senior_note")}</div>`)}</div>`;
    }).join("");
    const src = meta.sources || {};
    panel.innerHTML = `<h2>${p.name}</h2><div class="small">${t("sector")}: ${p.sector} · ${p.code}</div>
      <div class="kpis">
        <div class="kpi">${t("school_score")}<b>${orNA(fmtScore(p.school_score))}</b></div>
        <div class="kpi">${t("m_value_score")}<b>${orNA(fmtScore(p.value_score))}</b></div>
        <div class="kpi">${t("elem_score")}<b>${orNA(fmtScore(p.elem_score))}</b></div>
        <div class="kpi">${t("junior_score")}<b>${orNA(fmtScore(p.junior_score))}</b></div>
        <div class="kpi" style="grid-column:span 2">${t("home_value")}<b>${orNA(p.home_value == null ? null : "$" + p.home_value.toLocaleString())}</b>
          <span class="small">${p.home_accounts ? p.home_accounts.toLocaleString() + " " + t("accounts") : ""}</span></div>
        <div class="kpi" style="grid-column:span 2">${t("rent")}: <span class="na">${t("rent_na")}</span></div>
      </div>
      <div><b>${t("amenities")}</b>: ${t("libraries")} ${orNA(p.libraries)} · ${t("transit")} ${orNA(p.transit_stops)} · ${t("parks")} ${orNA(p.parks)}</div>
      <h3>${t("nearby")}</h3>${schoolHtml}
      <p class="small">${t("method").replace("{years}", (meta.pat_years || []).join("–"))}</p>
      <p class="small"><b>${t("sources")}</b>: <a href="${src.pat}" target="_blank">Alberta Education PAT</a> ·
        <a href="${src.schools}" target="_blank">Calgary Schools</a> · <a href="${src.communities}" target="_blank">Community boundaries</a> ·
        <a href="${src.parcels}" target="_blank">2026 Property Assessments</a> · <a href="${src.libraries}" target="_blank">Libraries</a> ·
        <a href="${src.transit}" target="_blank">Transit stops</a> · <a href="${src.parks}" target="_blank">Parks</a></p>`;
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

  function rerenderAll() { applyI18n(); geoLayer.setStyle(styleFeature); renderLegend(); renderTable(); renderPanel(); renderSchools(); }

  const map = L.map("map", { preferCanvas: true }).setView([51.045, -114.07], 11);
  // Standard OSM tiles: free, no API key (Carto's keyless basemaps now show an "API key required" watermark).
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19, opacity: 0.6 }).addTo(map);

  Promise.all(["data/communities.geojson", "data/schools.json", "data/meta.json"].map((u) => fetch(u).then((r) => {
    if (!r.ok) throw new Error(u + " " + r.status); return r.json(); })))
    .then(([fc, sch, m]) => {
      communities = fc.features; schools = sch; meta = m;
      document.getElementById("metric").value = state.metric;
      geoLayer = L.geoJSON(fc, { style: styleFeature, onEachFeature: (f, layer) => {
        layer.on("click", () => select(f.properties.code, false));
        layer.bindTooltip(() => `${f.properties.name}: ${fmt(state.metric, f.properties[state.metric]) ?? t("no_data")}`, { sticky: true });
      } }).addTo(map);
      map.fitBounds(geoLayer.getBounds());
      rerenderAll();
      if (state.selected) select(state.selected, true);
      document.body.dataset.ready = "1";
    })
    .catch((err) => { document.getElementById("panel").innerHTML = `<p class="na">Failed to load data: ${err.message}. Run scripts/build_data.py first.</p>`; });

  document.getElementById("metric").addEventListener("change", (e) => { state.metric = e.target.value; rerenderAll(); });
  document.getElementById("showSchools").addEventListener("change", renderSchools);
  document.getElementById("lang").addEventListener("click", () => { state.lang = state.lang === "en" ? "zh" : "en"; rerenderAll(); });
  document.getElementById("search").addEventListener("input", (e) => { state.query = e.target.value; renderTable(); });
  document.querySelector("#commTable thead").addEventListener("click", (e) => {
    const key = e.target.dataset.key; if (!key) return;
    state.sortAsc = state.sortKey === key ? !state.sortAsc : key === "name";
    state.sortKey = key; renderTable();
  });
  document.querySelector("#commTable tbody").addEventListener("click", (e) => {
    const tr = e.target.closest("tr"); if (tr) select(tr.dataset.code, true);
  });
})();
