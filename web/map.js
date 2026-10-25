/* School points, attendance polygons, and wheel zoom.
 * Scales the tiles already on screen. Does not rank schools or fill the panel.
 * Leaflet is loaded by index.html as globalThis.L before this module runs.
 */
import { inConfig, listedResult, passesDirectory } from "./rank.js";
import { chooseZones, esc, homeCommunity } from "./zone.js";

const L = globalThis.L;

export function schoolPoint(school) {
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

/**
 * deps: schools(), zones(), zonesState(), ensureZones(), communities(),
 * program(), filter() for the list, t(key), popupHtml(school),
 * openZonePanel(id), panelSchoolId().
 * Returns render(), focusSchool(id, pinToTop), pickedId(), and the Leaflet map.
 */
export function createMap(deps) {
  const t = (key) => deps.t(key);
  let schoolLayer;
  let rankMapFitted = false;
  let pickedId = null;
  let pickedZoneLayer = null;
  let pickedWalkLayer = null;
  const markerById = new Map();
  let focusToken = 0;

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
  // map-zoom.mdc: scale the picture already on screen. Resetting the view
  // on each wheel notch flashes the basemap.
  const map = L.map("map", {
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
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19, opacity: 0.6 }).addTo(map);

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
    // An empty list before the file loads is not "this school has no zone".
    if (deps.zonesState() !== "ready") return false;
    const picked = chooseZones(school, deps.zones(), deps.program());
    const box = document.getElementById("zoneKey");
    if (!picked.attendance.length) {
      const home = homeCommunity(school, deps.communities());
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
      const prev = deps.schools().find((s) => String(s.id) === pickedId);
      if (prev) markerById.get(pickedId).setStyle(pointStyle(prev, false));
    }
    pickedId = nextId;
    document.querySelectorAll("#rankTable tbody tr").forEach((tr) => {
      tr.classList.toggle("sel", tr.dataset.id === nextId);
    });
    const school = deps.schools().find((s) => String(s.id) === nextId);
    const marker = markerById.get(nextId);
    if (school && marker) marker.setStyle(pointStyle(school, true));
  }
  function focusSchool(id, pinToTop) {
    const key = String(id);
    const openId = deps.panelSchoolId();
    if (openId && openId !== key) deps.openZonePanel(key);
    const school = deps.schools().find((s) => String(s.id) === key);
    const marker = markerById.get(key);
    const token = ++focusToken;
    restylePicked(key);
    revealRankRow(key, pinToTop);
    if (!school || !marker) { clearSchoolZone(); return; }
    // Draw only after the zone file settles. A later click moves focusToken,
    // so the first school's polygon is dropped.
    const show = () => {
      if (token !== focusToken) return;
      const current = markerById.get(key);
      const currentSchool = deps.schools().find((s) => String(s.id) === key);
      if (!current || !currentSchool) return;
      current.setPopupContent(deps.popupHtml(currentSchool));
      const drawn = drawSchoolZone(currentSchool);
      const bounds = drawn ? schoolZoneBounds() : null;
      const point = schoolPoint(currentSchool);
      const open = () => { if (token === focusToken && markerById.get(key) === current) current.openPopup(); };
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
    };
    const status = deps.zonesState();
    if (status === "ready" || status === "failed") show();
    else deps.ensureZones().then(show);
  }
  function render() {
    if (!map) return;
    map.invalidateSize();
    if (schoolLayer) schoolLayer.remove();
    markerById.clear();
    const filter = deps.filter();
    const rows = deps.schools().filter((s) => inConfig(s, filter) && passesDirectory(s, filter) && schoolPoint(s));
    schoolLayer = L.layerGroup(rows.map((s) => {
      const marker = L.circleMarker(schoolPoint(s), pointStyle(s, String(s.id) === pickedId))
        .bindPopup(deps.popupHtml(s), { maxWidth: 300, autoPan: true, autoPanPadding: [12, 12] });
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
  return { map, render, focusSchool, pickedId: () => pickedId };
}
