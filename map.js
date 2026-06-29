/* Michigan Data Center Tracker — map bootstrap */
(function () {
  const escAttr = v => String(v || "").replace(/\\/g, "\\\\").replace(/"/g, '\\"');

  function showBootError(msg) {
    const el = document.getElementById("panel-record-count");
    if (el) el.textContent = msg;
    console.error("[map]", msg);
  }

  async function loadMapData() {
    try {
      const res = await fetch("map-data.json?v=20260701c", { cache: "no-store" });
      if (!res.ok) throw new Error(`map-data.json HTTP ${res.status}`);
      const json = await res.json();
      if (!json.map_points?.length) throw new Error("map-data.json has no map_points");
      return json;
    } catch (err) {
      console.warn("[map] fetch failed, falling back to TRACKER_DATA", err);
      const fallback = window.TRACKER_DATA || {};
      if (fallback.map_points?.length) return fallback;
      throw err;
    }
  }

  async function initMap() {
    if (typeof L === "undefined") {
      showBootError("Map library failed to load");
      return;
    }

    let data;
    try {
      data = await loadMapData();
    } catch (err) {
      showBootError("Data failed to load");
      return;
    }

    const points = (data.map_points || []).filter(p => Number.isFinite(p.latitude) && Number.isFinite(p.longitude));
    const layersMeta = data.map_layers || [];
    const boundaryLayersMeta = data.boundary_layers || [];
    const overlayLayersMeta = data.overlay_layers || [];
    const stories = data.map_stories || [];
    const transmissionLines = data.transmission_lines || [];
    const $ = (sel, root = document) => root.querySelector(sel);
    const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
    const esc = v => String(v || "").replace(/[&<>"']/g, c => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
    }[c]));
    const safeUrl = v => {
      try {
        const u = new URL(String(v || ""), location.href);
        return ["http:", "https:"].includes(u.protocol) ? esc(u.href) : "#";
      } catch {
        return "#";
      }
    };

    const analytics = window.MapAnalytics || {
      init: () => {},
      track: () => {},
      recordAttention: () => {}
    };
    analytics.init({
      plausibleDomain: document.body?.dataset?.plausibleDomain || "",
      endpoint: document.body?.dataset?.analyticsEndpoint || "",
      debug: location.search.includes("analytics=1")
    });

    function layerRow({ id, label, desc, color, count, on, line }) {
      const swatch = line
        ? `class="layer-swatch layer-swatch--line" style="color:${color}"`
        : `class="layer-swatch" style="background:${color}"`;
      return `<button type="button" class="layer-row ${on ? "on" : "off"}" data-layer="${escAttr(id)}" aria-pressed="${on ? "true" : "false"}" title="${esc(desc || label)}"><span ${swatch}></span><span class="layer-name">${esc(label)}</span><span class="layer-count">${count || ""}</span><span class="layer-check" aria-hidden="true"></span></button>`;
    }

    function setLayerRow(btn, on) {
      if (!btn) return;
      btn.classList.toggle("on", on);
      btn.classList.toggle("off", !on);
      btn.setAttribute("aria-pressed", on ? "true" : "false");
    }

    function setLayerRowById(container, id, on) {
      setLayerRow(container?.querySelector(`[data-layer="${escAttr(id)}"]`), on);
    }

    function bindLayerList(container, onToggle) {
      if (!container) return;
      container.addEventListener("click", e => {
        const btn = e.target.closest(".layer-row");
        if (!btn || !container.contains(btn)) return;
        e.preventDefault();
        e.stopPropagation();
        const id = btn.dataset.layer;
        const on = btn.getAttribute("aria-pressed") !== "true";
        setLayerRow(btn, on);
        onToggle(id, on, btn);
      });
    }

    function isMobile() {
      return window.matchMedia("(max-width: 768px)").matches;
    }

    function switchPanelTab(tabId) {
      $$(".panel-tab").forEach(t => {
        const on = t.dataset.tab === tabId;
        t.classList.toggle("active", on);
        t.setAttribute("aria-selected", on ? "true" : "false");
      });
      $$(".panel-pane").forEach(p => { p.hidden = p.id !== `pane-${tabId}`; });
      analytics.track("tab_view", { tab: tabId });
    }

    function updateMobilePanelUi() {
      const sidebar = $("#map-sidebar");
      const chevron = $("#panel-chevron");
      const open = sidebar?.classList.contains("open");
      if (chevron) chevron.textContent = open ? "⌄" : "⌃";
      if (sidebar) sidebar.setAttribute("aria-expanded", open ? "true" : "false");
    }

    function openMobilePanel(tabId) {
      if (!isMobile()) return;
      const sidebar = $("#map-sidebar");
      sidebar?.classList.add("open");
      if (tabId) switchPanelTab(tabId);
      updateMobilePanelUi();
    }

    function toggleMobilePanel(forceOpen) {
      if (!isMobile()) return;
      const sidebar = $("#map-sidebar");
      if (!sidebar) return;
      const shouldOpen = typeof forceOpen === "boolean" ? forceOpen : !sidebar.classList.contains("open");
      sidebar.classList.toggle("open", shouldOpen);
      updateMobilePanelUi();
    }

    const LAYER_COLORS = Object.fromEntries(layersMeta.map(l => [l.id, l.color]));
    const LAYER_LABELS = Object.fromEntries(layersMeta.map(l => [l.id, l.label]));
    const STATUS_COLORS = {
      "Under construction": "#cf102d",
      "Proposed": "#3a7bd5",
      "Under review": "#5b9cf5",
      "Conditionally approved": "#f59e0b",
      "Approved": "#22a86a",
      "Operational": "#10b981",
      "Moratorium": "#e09820",
      "Utility pause": "#9c5fc9",
      "Rejected by planning commission": "#5a6070",
      "Withdrawn": "#374151",
      "Under appeal": "#6b7280",
      "Public meeting": "#5b9cf5",
      "Public signal": "#22a86a",
      "Nuclear": "#c084fc",
      "Coal": "#78716c",
      "Natural gas": "#fb923c",
      "Wind": "#22d3ee",
      "Solar": "#facc15",
      "Hydroelectric": "#60a5fa"
    };
    const pointColor = p => (p.layer === "generation" && STATUS_COLORS[p.status])
      ? STATUS_COLORS[p.status]
      : (LAYER_COLORS[p.layer] || STATUS_COLORS[p.status] || "#cf102d");
    const layerLabel = p => LAYER_LABELS[p.layer] || p.layer || "Record";

    const REGION_COUNTIES = {
      metro_detroit: new Set(["Wayne","Oakland","Macomb","Washtenaw","Livingston","Monroe","Lenawee","St. Clair","Lapeer","Genesee","Hillsdale","Sanilac"]),
      west_michigan: new Set(["Kent","Ottawa","Allegan","Muskegon","Berrien","Cass","Van Buren","Kalamazoo","Barry","Ionia","Montcalm","Mecosta","Newaygo","Oceana","Mason","Lake","Manistee","Benzie","Leelanau"]),
      mid_michigan: new Set(["Ingham","Eaton","Clinton","Jackson","Calhoun","Branch","Shiawassee","Gratiot","Isabella","Clare","Midland","Bay","Saginaw","Tuscola","Huron"]),
      northern_michigan: new Set(["Grand Traverse","Antrim","Charlevoix","Emmet","Cheboygan","Presque Isle","Alpena","Alcona","Iosco","Ogemaw","Oscoda","Crawford","Kalkaska","Missaukee","Wexford","Osceola","Mackinac","Chippewa","Schoolcraft","Delta","Dickinson","Menominee","Marquette","Alger","Baraga","Houghton","Keweenaw","Ontonagon","Gogebic","Iron","Luce"])
    };
    const regionForCounty = county => {
      const c = String(county || "").replace(/ County$/i, "").trim();
      for (const [key, set] of Object.entries(REGION_COUNTIES)) {
        if (set.has(c)) return key;
      }
      return "statewide";
    };

    const params = new URLSearchParams(location.search);
    const initMode = params.get("mode") || "dark";
    const initRegion = params.get("region") || "all";
    const initFilters = params.get("f") ? new Set(params.get("f").split(",")) : null;
    const initLayersRaw = params.get("layers");
    const initLayers = initLayersRaw ? new Set(initLayersRaw.split(",").map(s => s.trim()).filter(Boolean)) : null;
    const initPoint = params.get("point") || "";
    const initStory = params.get("story") || "";
    const initBoundariesRaw = params.get("boundaries");
    const initBoundaries = initBoundariesRaw ? new Set(initBoundariesRaw.split(",").map(s => s.trim()).filter(Boolean)) : null;
    const initOverlaysRaw = params.get("overlays");
    const initOverlays = initOverlaysRaw ? new Set(initOverlaysRaw.split(",").map(s => s.trim()).filter(Boolean)) : null;

    const FOCUSED_LAYER_IDS = ["projects", "moratoria"];
    const OPTIONAL_LAYER_IDS = ["meetings", "transmission", "policy", "generation"];
    const defaultLayers = new Set(
      layersMeta.filter(l => l.default_on !== false).map(l => l.id)
    );
    if (!defaultLayers.size) FOCUSED_LAYER_IDS.forEach(id => defaultLayers.add(id));
    let activeLayers = initLayers?.size ? initLayers : new Set(defaultLayers);

    const defaultBoundaries = new Set(boundaryLayersMeta.filter(b => b.default_on).map(b => b.id));
    let activeBoundaries = initBoundaries?.size ? initBoundaries : new Set(defaultBoundaries);
    const defaultOverlays = new Set(overlayLayersMeta.filter(o => o.default_on).map(o => o.id));
    let activeOverlays = initOverlays?.size ? initOverlays : new Set(defaultOverlays);

    const darkTile = L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", { maxZoom: 19, attribution: '&copy; OSM &copy; CARTO' });
    const dayTile = L.tileLayer("https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png", { maxZoom: 19, attribution: '&copy; OSM &copy; CARTO' });
    const satTile = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", { maxZoom: 19, attribution: '&copy; Esri' });

    const map = L.map("map", { zoomControl: false, scrollWheelZoom: true }).setView([43.4, -85.0], 7);
    L.control.zoom({ position: "bottomright" }).addTo(map);

    let currentMode = ["dark","day","sat"].includes(initMode) ? initMode : "dark";
    const setTileMode = mode => {
      [darkTile, dayTile, satTile].forEach(t => { try { map.removeLayer(t); } catch (_) {} });
      if (mode === "day") dayTile.addTo(map);
      else if (mode === "sat") satTile.addTo(map);
      else darkTile.addTo(map);
      currentMode = mode;
      $$(".tile-btn").forEach(b => b.classList.toggle("active", b.dataset.mode === mode));
    };
    setTileMode(currentMode);
    $$(".tile-btn").forEach(b => b.addEventListener("click", () => {
      setTileMode(b.dataset.mode);
      analytics.track("basemap_change", { mode: b.dataset.mode });
    }));

    const boundaryLayer = L.geoJSON(null, { style: { color: "#cf102d", weight: 2, opacity: 0.55, fillColor: "#cf102d", fillOpacity: 0.04 }, interactive: false }).addTo(map);
    fetch("https://raw.githubusercontent.com/PublicaMundi/MappingAPI/master/data/geojson/us-states.json")
      .then(r => r.json())
      .then(geo => { const mi = geo.features.find(f => f.properties?.name === "Michigan"); if (mi) boundaryLayer.addData(mi); })
      .catch(() => {});

    const boundaryGroups = {}, boundaryLabelGroups = {}, boundaryCache = {}, boundaryLoading = {};
    const overlayGroups = {}, overlayCache = {}, overlayLoading = {};
    const GEO_VERSION = "20260630b";
    const WATER_VERSION = "20260630b";
    const lakeLevelsMeta = data.lake_levels || [];
    const liveMapLinks = data.live_map_links || [];
    const liveWater = {
      lakeLevels: new Map(),
      buoys: new Map(),
      updatedAt: null
    };

    function outerRing(geom) {
      if (!geom) return [];
      if (geom.type === "Polygon") return geom.coordinates[0] || [];
      if (geom.type === "MultiPolygon") return geom.coordinates[0]?.[0] || [];
      return [];
    }

    function featureCenter(geom) {
      const ring = outerRing(geom);
      if (!ring.length) return null;
      let lat = 0, lng = 0;
      ring.forEach(c => { lat += c[1]; lng += c[0]; });
      return [lat / ring.length, lng / ring.length];
    }

    function makeBoundaryPopup(props, meta) {
      const c = meta.color || "#818cf8";
      const title = props.label || props.name || meta.label;
      const sub = props.name && props.label && props.name !== props.label ? props.name : meta.description || "";
      return `<div class="map-popup"><div class="pop-header" style="--status:${c}"><span class="pop-status">${esc(meta.label)}</span><div class="pop-name">${esc(title)}</div>${sub ? `<div class="pop-location">${esc(sub)}</div>` : ""}</div></div>`;
    }

    function boundaryStyle(meta) {
      return () => ({
        color: meta.color,
        weight: meta.id === "townships" ? 0.9 : meta.id === "counties" ? 1.6 : 2.2,
        opacity: meta.id === "townships" ? 0.42 : meta.id === "counties" ? 0.72 : 0.78,
        fillColor: meta.color,
        fillOpacity: meta.id === "congressional" ? 0.07 : 0,
        dashArray: meta.id === "townships" ? "3 4" : null
      });
    }

    async function loadBoundaryGeo(meta) {
      if (boundaryCache[meta.id]) return boundaryCache[meta.id];
      const res = await fetch(`${meta.url}?v=${GEO_VERSION}`, { cache: "force-cache" });
      if (!res.ok) throw new Error(`${meta.url} HTTP ${res.status}`);
      const geo = await res.json();
      boundaryCache[meta.id] = geo;
      return geo;
    }

    async function ensureBoundaryLayer(meta) {
      if (boundaryGroups[meta.id] || boundaryLoading[meta.id]) return boundaryLoading[meta.id];
      boundaryLoading[meta.id] = loadBoundaryGeo(meta).then(geo => {
        const group = L.geoJSON(geo, {
          style: boundaryStyle(meta),
          interactive: true,
          onEachFeature: (feature, layer) => {
            const props = feature.properties || {};
            if (meta.id === "congressional" || meta.id === "counties") {
              layer.bindPopup(makeBoundaryPopup(props, meta), { maxWidth: 280, className: "tracker-popup" });
              layer.bindTooltip(props.name || props.label || meta.label, {
                className: "boundary-tip",
                sticky: true,
                opacity: 0.95
              });
            } else if (meta.id === "townships") {
              layer.bindTooltip(props.label || props.name || "Township", {
                className: "boundary-tip",
                sticky: true,
                opacity: 0.95
              });
            }
          }
        });
        boundaryGroups[meta.id] = group;
        if (meta.id === "congressional") {
          const labelGroup = L.layerGroup();
          geo.features.forEach(f => {
            const center = featureCenter(f.geometry);
            const label = f.properties?.label;
            if (!center || !label) return;
            labelGroup.addLayer(L.marker(center, {
              icon: makeLabelDivIcon("cd-label-wrap", `<span class="cd-label">${esc(label)}</span>`),
              interactive: false
            }));
          });
          boundaryLabelGroups[meta.id] = labelGroup;
        }
        refreshBoundaries();
      }).catch(err => {
        console.warn("[map] boundary load failed", meta.id, err);
        activeBoundaries.delete(meta.id);
        setLayerRowById(boundariesEl, meta.id, false);
      }).finally(() => { delete boundaryLoading[meta.id]; });
      return boundaryLoading[meta.id];
    }

    function refreshBoundaries() {
      boundaryLayersMeta.forEach(meta => {
        const on = activeBoundaries.has(meta.id);
        const minZoom = meta.min_zoom || 0;
        const zoomOk = map.getZoom() >= minZoom;
        const group = boundaryGroups[meta.id];
        const labels = boundaryLabelGroups[meta.id];
        if (on && zoomOk && group) {
          map.addLayer(group);
          if (labels && map.getZoom() >= (meta.label_zoom || 7)) map.addLayer(labels);
          else if (labels) map.removeLayer(labels);
        } else {
          if (group) map.removeLayer(group);
          if (labels) map.removeLayer(labels);
        }
      });
      syncUrl();
    }

    function buoyLive(station) {
      return liveWater.buoys.get(String(station || ""));
    }

    function buoyTempDisplay(station) {
      const live = buoyLive(station);
      return live?.display || "—";
    }

    function makeOverlayPopup(props, meta) {
      const c = meta.color || "#38bdf8";
      const title = props.name || props.label || meta.label;
      const rows = [];
      if (props.code) rows.push(`<div class="pop-row"><span class="pop-label">Code</span><span class="pop-val">${esc(props.code)}</span></div>`);
      if (props.station && meta.live_data === "buoys") {
        rows.push(`<div class="pop-row"><span class="pop-label">Station</span><span class="pop-val">${esc(props.station)}</span></div>`);
        rows.push(`<div class="pop-row"><span class="pop-label">Surface temp</span><span class="pop-val">${esc(buoyTempDisplay(props.station))}</span></div>`);
      }
      if (props.category) {
        const catLbl = meta.category_labels?.[props.category];
        rows.push(`<div class="pop-row"><span class="pop-label">EGLE class</span><span class="pop-val">${esc(props.category)}${catLbl ? ` — ${esc(catLbl)}` : ""}</span></div>`);
      }
      if (props.type) rows.push(`<div class="pop-row"><span class="pop-label">Type</span><span class="pop-val">${esc(props.type)}</span></div>`);
      if (props.operator) rows.push(`<div class="pop-row"><span class="pop-label">Operator</span><span class="pop-val">${esc(props.operator)}</span></div>`);
      if (props.voltage_class) rows.push(`<div class="pop-row"><span class="pop-label">Voltage</span><span class="pop-val">${esc(props.voltage_class)} kV class</span></div>`);
      if (props.owner) rows.push(`<div class="pop-row"><span class="pop-label">Owner</span><span class="pop-val">${esc(props.owner)}</span></div>`);
      if (props.county) rows.push(`<div class="pop-row"><span class="pop-label">County</span><span class="pop-val">${esc(props.county)}</span></div>`);
      const note = props.note || (props.label && props.label !== title ? props.label : "");
      const overlaySrc = meta.source_url && safeUrl(meta.source_url) !== "#" && meta.source_name
        ? `<details class="pop-source-fold"><summary>Data source</summary><a class="pop-source-link" href="${safeUrl(meta.source_url)}" target="_blank" rel="noopener">${esc(meta.source_name)}</a></details>`
        : "";
      return `<div class="map-popup"><div class="pop-header" style="--status:${c}"><span class="pop-status">${esc(meta.label)}</span><div class="pop-name">${esc(title)}</div></div><div class="pop-body">${rows.join("")}${note ? `<p class="pop-note">${esc(note)}</p>` : ""}${overlaySrc}</div></div>`;
    }

    function overlayFeatureStyle(meta, props = {}) {
      const base = {
        color: meta.color,
        weight: meta.geometry_type === "line" ? 2 : 1,
        opacity: meta.geometry_type === "polygon" ? 0.55 : 0.75,
        fillColor: meta.color,
        fillOpacity: meta.geometry_type === "polygon" ? 0.12 : 0
      };
      if (meta.style_by && meta.style_map) {
        const key = props[meta.style_by];
        const s = meta.style_map[key] || {};
        return { ...base, ...s };
      }
      return base;
    }

    async function loadOverlayGeo(meta) {
      if (overlayCache[meta.id]) return overlayCache[meta.id];
      const res = await fetch(`${meta.url}?v=${GEO_VERSION}`, { cache: "force-cache" });
      if (!res.ok) throw new Error(`${meta.url} HTTP ${res.status}`);
      const geo = await res.json();
      overlayCache[meta.id] = geo;
      return geo;
    }

    function overlayIcon(meta) {
      const color = meta.color || "#38bdf8";
      const type = meta.icon_type || "water";
      const svg = {
        water: `<svg class="water-pin" xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24"><path d="M12 2c-3 4-7 7.5-7 12a7 7 0 1014 0C19 9.5 15 6 12 2z" fill="${color}" stroke="#fff" stroke-width="1.4"/></svg>`,
        buoy: `<svg class="buoy-pin" xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8" fill="${color}" stroke="#fff" stroke-width="1.4"/><circle cx="12" cy="12" r="3" fill="#0b0b0d" stroke="#fff" stroke-width="1"/><path d="M12 4v3M12 17v3M4 12h3M17 12h3" stroke="#fff" stroke-width="1.2" stroke-linecap="round"/></svg>`,
        airport: `<svg class="airport-pin" xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24"><path d="M10.5 13.5L3 10l1.5-1.2 6 1.8V4.5L8.5 3v2.2L3 5.5 1.5 4.3 12 2l10.5 2.3L21 5.5l-5.5 1V3L13.5 4.5v7.1l6-1.8L21 10l-7.5 3.5L14 20h-4l-1.5-6.5z" fill="${color}" stroke="#fff" stroke-width="0.8"/></svg>`,
        substation: `<svg class="substation-pin" xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24"><rect x="4" y="5" width="16" height="14" rx="1.5" fill="${color}" stroke="#fff" stroke-width="1.3"/><path d="M13 8l-4 7h3l-1 5 6-9h-3l2-3z" fill="#0b0b0d" stroke="#fff" stroke-width="0.6"/></svg>`
      };
      return L.divIcon({
        html: svg[type] || svg.water,
        className: "map-pin",
        iconSize: [22, 22],
        iconAnchor: [11, 11],
        popupAnchor: [0, -11]
      });
    }

    function bindBuoyLive(layer, props, meta) {
      const label = props.name || props.label || "NOAA buoy";
      const tip = () => `${label} · ${buoyTempDisplay(props.station)} surface`;
      layer.bindTooltip(tip(), { className: "boundary-tip", sticky: true, opacity: 0.95 });
      layer.on("popupopen", () => layer.setPopupContent(makeOverlayPopup(props, meta)));
    }

    function refreshBuoyLiveLayers() {
      const group = overlayGroups.noaa_buoys;
      const meta = overlayLayersMeta.find(o => o.id === "noaa_buoys");
      if (!group || !meta) return;
      group.eachLayer(layer => {
        const props = layer.feature?.properties;
        if (!props?.station) return;
        const label = props.name || props.label || "NOAA buoy";
        layer.setTooltipContent(`${label} · ${buoyTempDisplay(props.station)} surface`);
        if (layer.isPopupOpen?.()) layer.setPopupContent(makeOverlayPopup(props, meta));
      });
    }

    async function ensureOverlayLayer(meta) {
      if (overlayGroups[meta.id] || overlayLoading[meta.id]) return overlayLoading[meta.id];
      overlayLoading[meta.id] = loadOverlayGeo(meta).then(geo => {
        const opts = {
          style: feature => overlayFeatureStyle(meta, feature.properties || {}),
          interactive: true,
          onEachFeature: (feature, layer) => {
            const props = feature.properties || {};
            if (meta.geometry_type === "line") {
              layer.bindPopup(makeOverlayPopup(props, meta), { maxWidth: 300, className: "tracker-popup" });
            } else if (meta.geometry_type === "polygon") {
              layer.bindPopup(makeOverlayPopup(props, meta), { maxWidth: 340, className: "tracker-popup" });
              const tip = meta.category_labels?.[props.category]
                ? `Class ${props.category}: ${meta.category_labels[props.category]}`
                : (props.label || props.category || "Aquifer");
              layer.bindTooltip(tip, { className: "boundary-tip", sticky: true });
            } else if (meta.geometry_type === "point") {
              layer.bindPopup(makeOverlayPopup(props, meta), { maxWidth: 320, className: "tracker-popup" });
              if (meta.live_data === "buoys" && props.station) bindBuoyLive(layer, props, meta);
              else if (props.name || props.label) {
                layer.bindTooltip(props.name || props.label, { className: "boundary-tip", sticky: true, opacity: 0.95 });
              }
            }
          }
        };
        if (meta.geometry_type === "line") {
          opts.className = "tx-grid-glow";
        }
        if (meta.geometry_type === "point") {
          opts.pointToLayer = (feature, latlng) => L.marker(latlng, { icon: overlayIcon(meta), interactive: true });
        }
        overlayGroups[meta.id] = L.geoJSON(geo, opts);
        refreshOverlays();
      }).catch(err => {
        console.warn("[map] overlay load failed", meta.id, err);
        activeOverlays.delete(meta.id);
        setLayerRowById(overlaysEl, meta.id, false);
      }).finally(() => { delete overlayLoading[meta.id]; });
      return overlayLoading[meta.id];
    }

    function refreshOverlays() {
      overlayLayersMeta.forEach(meta => {
        const on = activeOverlays.has(meta.id);
        const minZoom = meta.min_zoom || 0;
        const zoomOk = map.getZoom() >= minZoom;
        const group = overlayGroups[meta.id];
        if (on && zoomOk && group) map.addLayer(group);
        else if (group) map.removeLayer(group);
      });
      syncUrl();
    }

    function makeIcon(color, active = false, layer = "projects", status = "") {
      const size = active ? 28 : 22;
      const shapes = {
        moratoria: `<rect x="5" y="3" width="14" height="14" rx="2" fill="${color}" stroke="#fff" stroke-width="1.5"/>`,
        meetings: `<circle cx="12" cy="10" r="7" fill="${color}" stroke="#fff" stroke-width="1.5"/>`,
        transmission: `<path d="M13 2L8 12h3.5l-1 10 7-12h-3.5L13 2z" fill="${color}" stroke="#fff" stroke-width="1.2"/>`,
        policy: `<polygon points="12,2 15,9 22,9 16.5,13.5 18.5,21 12,17 5.5,21 7.5,13.5 2,9 9,9" fill="${color}" stroke="#fff" stroke-width="1.2"/>`,
        generation: `<rect x="4" y="8" width="16" height="10" rx="2" fill="${color}" stroke="#fff" stroke-width="1.3"/><rect x="10" y="3" width="4" height="6" fill="${color}" stroke="#fff" stroke-width="1.2"/>`
      };
      const genShapes = {
        Nuclear: `<circle cx="12" cy="12" r="2.5" fill="${color}" stroke="#fff" stroke-width="1.2"/><ellipse cx="12" cy="12" rx="9" ry="3.5" fill="none" stroke="${color}" stroke-width="1.4"/><ellipse cx="12" cy="12" rx="9" ry="3.5" fill="none" stroke="${color}" stroke-width="1.4" transform="rotate(60 12 12)"/><ellipse cx="12" cy="12" rx="9" ry="3.5" fill="none" stroke="${color}" stroke-width="1.4" transform="rotate(-60 12 12)"/>`,
        Coal: `<rect x="6" y="10" width="12" height="9" rx="1.5" fill="${color}" stroke="#fff" stroke-width="1.2"/><path d="M9 10V6h6v4" fill="none" stroke="${color}" stroke-width="1.5"/><path d="M8 19v2M12 19v2M16 19v2" stroke="#fff" stroke-width="1.3"/>`,
        "Natural gas": `<path d="M12 3c-2 4-5 6-5 10a5 5 0 0010 0c0-4-3-6-5-10z" fill="${color}" stroke="#fff" stroke-width="1.3"/>`,
        Wind: `<path d="M12 4v16M12 12L6 18M12 12l6 6" stroke="${color}" stroke-width="2" stroke-linecap="round"/><circle cx="12" cy="12" r="2.5" fill="${color}" stroke="#fff" stroke-width="1.2"/>`,
        Solar: `<circle cx="12" cy="12" r="4.5" fill="${color}" stroke="#fff" stroke-width="1.3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9L17 7M7 17l-2.1 2.1" stroke="${color}" stroke-width="1.5" stroke-linecap="round"/>`,
        Hydroelectric: `<path d="M4 14c2-6 6-8 8-8s6 2 8 8H4z" fill="${color}" stroke="#fff" stroke-width="1.3"/><path d="M8 14c1-2 2.5-3 4-3s3 1 4 3" fill="none" stroke="#fff" stroke-width="1.2"/>`
      };
      let inner = shapes[layer];
      if (layer === "generation" && genShapes[status]) inner = genShapes[status];
      if (!inner) inner = `<path d="M12 2c-3.3 0-6 2.5-6 5.6 0 4.2 6 12.4 6 12.4s6-8.2 6-12.4C18 4.5 15.3 2 12 2z" fill="${color}" stroke="#fff" stroke-width="1.5"/><circle cx="12" cy="7.6" r="2.2" fill="#fff" fill-opacity=".9"/>`;
      return L.divIcon({ html: `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 24 24">${inner}</svg>`, className: active ? "map-pin map-pin--active" : "map-pin", iconSize: [size, size], iconAnchor: [size/2, size/2], popupAnchor: [0, -size/2] });
    }

    const dateLabel = value => value ? new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" }).format(new Date(`${value}T12:00:00`)) : "";

    function recordPhase(p) {
      const status = String(p?.status || "");
      const layer = p?.layer || "projects";
      if (layer === "meetings") return "Public process";
      if (layer === "moratoria") return "Local restriction";
      if (layer === "policy") return "Policy signal";
      if (layer === "transmission") return "Grid corridor";
      if (layer === "generation") return "Power generation";
      const map = {
        "Under construction": "Building",
        "Proposed": "Early stage",
        "Under review": "Under review",
        "Conditionally approved": "Approved with conditions",
        "Approved": "Approved",
        "Operational": "Operating",
        "Moratorium": "Moratorium",
        "Utility pause": "Utility pause",
        "Rejected by planning commission": "Rejected",
        "Withdrawn": "Withdrawn",
        "Under appeal": "Appeal",
        "Public meeting": "Public meeting",
        "Public signal": "Public signal"
      };
      return map[status] || status || "Tracked";
    }

    function recordNextActions(p) {
      const actions = [];
      const layer = p?.layer || "";
      const status = String(p?.status || "");
      const when = p?.verified_date ? dateLabel(p.verified_date) : "";
      if (layer === "meetings" && when) actions.push(`Next public step: ${when}`);
      else if (layer === "meetings") actions.push("Check the local agenda for hearing date and materials.");
      if (layer === "moratoria" || status === "Moratorium") actions.push("Watch for township board votes and ordinance updates.");
      if (status === "Proposed" || status === "Under review") actions.push("Track planning commission and zoning hearings.");
      if (status === "Under construction") actions.push("Monitor construction permits and utility filings.");
      if (status === "Rejected by planning commission" || status === "Under appeal") actions.push("Follow appeals, pauses, or revised applications.");
      if (layer === "transmission") actions.push("Review MPSC dockets and corridor route updates.");
      if (layer === "policy") actions.push("Follow capitol hearings and agency rulemaking.");
      if (!actions.length && p?.note) actions.push("Track public filings for the latest update.");
      return actions.slice(0, 2);
    }

    function recordSource(p) {
      const url = String(p?.source_url || "");
      if (!url || safeUrl(url) === "#") return null;
      const label = String(p.source_name || "").trim();
      if (!label) return null;
      return { href: safeUrl(url), label };
    }

    function sourceWorthShowing(p) {
      const src = recordSource(p);
      if (!src) return null;
      const hay = `${src.href} ${src.label}`.toLowerCase();
      if (["meetings", "moratoria", "policy", "transmission"].includes(p.layer)) return src;
      if (/\.gov|michigan\.gov|township|city of|mpsc|egle|legislature/.test(hay)) return src;
      return null;
    }

    function popSourceMarkup(p) {
      const src = sourceWorthShowing(p);
      if (!src) return "";
      return `<details class="pop-source-fold"><summary>Public record</summary><a class="pop-source-link" href="${src.href}" target="_blank" rel="noopener">${esc(src.label)}</a></details>`;
    }

    function makePopup(p) {
      const c = pointColor(p);
      const dateStr = p.verified_date ? dateLabel(p.verified_date) : "";
      const ownerLabel = p.layer === "generation" ? "Operator" : "Developer";
      const capacityLabel = p.layer === "generation" ? "Capacity" : "Scale";
      const phase = recordPhase(p);
      const actions = recordNextActions(p);
      const actionHtml = actions.length
        ? `<div class="pop-actions"><div class="pop-actions-title">What to watch</div><ul>${actions.map(a => `<li>${esc(a)}</li>`).join("")}</ul></div>`
        : "";
      return `<div class="map-popup"><div class="pop-header" style="--status:${c}"><span class="pop-status">${esc(layerLabel(p))}</span><div class="pop-phase">${esc(phase)}</div><div class="pop-name">${esc(p.name)}</div><div class="pop-location">${esc(p.municipality)}, ${esc(p.county)} County</div><div class="pop-status-pill" style="--status:${c}">${esc(p.status)}</div></div><div class="pop-body">${p.developer ? `<div class="pop-row"><span class="pop-label">${ownerLabel}</span><span class="pop-val">${esc(p.developer)}</span></div>` : ""}${p.power_mw ? `<div class="pop-row"><span class="pop-label">${capacityLabel}</span><span class="pop-val">${esc(p.power_mw)} MW</span></div>` : ""}${dateStr ? `<div class="pop-row"><span class="pop-label">Last verified</span><span class="pop-val">${dateStr}</span></div>` : ""}${p.confidence ? `<div class="pop-row"><span class="pop-label">Confidence</span><span class="pop-val">${esc(p.confidence)}</span></div>` : ""}${p.note ? `<p class="pop-note">${esc(p.note)}</p>` : ""}${actionHtml}${popSourceMarkup(p)}</div></div>`;
    }

    function makeLinePopup(line) {
      const src = line.source_url && safeUrl(line.source_url) !== "#" && line.source_name
        ? { href: safeUrl(line.source_url), label: line.source_name }
        : null;
      const srcHtml = src
        ? `<details class="pop-source-fold"><summary>Public record</summary><a class="pop-source-link" href="${src.href}" target="_blank" rel="noopener">${esc(src.label)}</a></details>`
        : "";
      return `<div class="map-popup"><div class="pop-header" style="--status:#9c5fc9"><span class="pop-status">Power & grid · ${esc(line.status)}</span><div class="pop-name">${esc(line.name)}</div><div class="pop-location">${esc((line.counties||[]).join(", "))}</div></div><div class="pop-body"><div class="pop-row"><span class="pop-label">Operator</span><span class="pop-val">${esc(line.operator)}</span></div>${line.note ? `<p class="pop-note">${esc(line.note)}</p>` : ""}${srcHtml}</div></div>`;
    }

    function shortLineLabel(name) {
      const raw = String(name || "").split("(")[0].trim();
      if (/bwl/i.test(raw)) return "BWL South Line";
      if (/oneida/i.test(raw)) return "ITC Oneida–Sabine";
      if (raw.length <= 20) return raw;
      return `${raw.slice(0, 18)}…`;
    }

    function makeLabelDivIcon(className, innerHtml) {
      return L.divIcon({
        className,
        html: innerHtml,
        iconSize: [1, 1],
        iconAnchor: [0, 0]
      });
    }

    const markerLayer = typeof L.markerClusterGroup === "function"
      ? L.markerClusterGroup({
          showCoverageOnHover: false,
          maxClusterRadius: 46,
          spiderfyOnMaxZoom: true,
          zoomToBoundsOnClick: false,
          disableClusteringAtZoom: 12,
          iconCreateFunction: group => {
            const count = group.getChildCount();
            const size = count > 9 ? 40 : 34;
            return L.divIcon({
              html: `<div class="cluster-bubble" style="width:${size}px;height:${size}px"><span>${count}</span></div>`,
              className: "",
              iconSize: [size, size],
              iconAnchor: [size / 2, size / 2]
            });
          }
        })
      : L.layerGroup();
    markerLayer.addTo(map);

    function clusterPoints(cluster) {
      return cluster.getAllChildMarkers()
        .map(m => pointByName.get(m._trackerName))
        .filter(p => p && pointVisible(p))
        .sort((a, b) => a.municipality.localeCompare(b.municipality) || a.name.localeCompare(b.name));
    }

    function clearClusterPeek() {
      const panel = $("#cluster-peek");
      if (!panel) return;
      panel.hidden = true;
      panel.innerHTML = "";
    }

    function renderClusterPeek(clusterPts) {
      const panel = $("#cluster-peek");
      if (!panel || !clusterPts.length) return;
      const preview = clusterPts.slice(0, 6);
      const more = clusterPts.length - preview.length;
      panel.hidden = false;
      panel.innerHTML = `<div class="cluster-peek-title">${clusterPts.length} records here</div><p class="cluster-peek-sub">Zoomed to this area. Pick a record below or tap a pin on the map.</p><div class="cluster-peek-list">${preview.map(p =>
        `<button type="button" data-point="${esc(p.name)}"><span class="dir-dot" style="background:${pointColor(p)}"></span><span><strong>${esc(p.name)}</strong><small>${esc(p.municipality)} · ${esc(p.status)}</small></span></button>`
      ).join("")}</div>${more > 0 ? `<div class="cluster-peek-more">+ ${more} more in list below</div>` : ""}`;
    }

    function handleClusterClick(cluster) {
      const clusterPts = clusterPoints(cluster);
      if (!clusterPts.length) return;
      analytics.track("cluster_click", { count: clusterPts.length, zoom: map.getZoom() });
      clearSelection();
      map.closePopup();
      if (map.getZoom() >= 11 && clusterPts.length <= 10) {
        cluster.spiderfy();
      } else {
        map.fitBounds(cluster.getBounds(), {
          padding: isMobile() ? [72, 24] : [80, 340],
          maxZoom: 12,
          animate: true,
          duration: 0.55
        });
      }
      renderClusterPeek(clusterPts);
      if (isMobile()) openMobilePanel("list");
      else switchPanelTab("list");
    }

    if (markerLayer.on) {
      markerLayer.on("clusterclick", e => {
        L.DomEvent.stopPropagation(e);
        handleClusterClick(e.layer);
      });
    }
    const transmissionGroup = L.layerGroup().addTo(map);
    const markerMap = new Map();
    const pointByName = new Map(points.map(p => [p.name, p]));
    let activeMarker = null, activePointName = null, activeRegion = initRegion;
    const filtersEl = $("#map-filters"), layersStackEl = $("#map-layers-stack"), layersCoreEl = $("#map-layers-core"), layersMoreEl = $("#map-layers-more"), boundariesEl = $("#map-boundaries"), overlaysEl = $("#map-overlays"), dirEl = $("#map-directory"), storiesEl = $("#map-stories");
    function statusesForActiveLayers() {
      return [...new Set(points.filter(p => activeLayers.has(p.layer || "projects")).map(p => p.status))].sort();
    }
    const LOWER_PENINSULA_BOUNDS = L.latLngBounds([41.72, -87.38], [45.68, -82.12]);

    function fitLowerPeninsula({ duration } = {}) {
      const chromePad = lakeLevelsMeta.length ? 28 : 0;
      const opts = isMobile()
        ? { paddingTopLeft: [118, 24 + chromePad], paddingBottomRight: [100, 24], maxZoom: 7 }
        : { paddingTopLeft: [112, 340 + chromePad], paddingBottomRight: [64, 64], maxZoom: 7 };
      if (duration != null) map.flyToBounds(LOWER_PENINSULA_BOUNDS, { ...opts, duration });
      else map.fitBounds(LOWER_PENINSULA_BOUNDS, opts);
    }

    function statCounts(visibleOnly = false) {
      const pool = visibleOnly ? points.filter(pointVisible) : points;
      return {
        total: pool.length,
        moratoria: pool.filter(p => p.layer === "moratoria").length,
        projects: pool.filter(p => p.layer === "projects").length,
        transmission: (activeLayers.has("transmission") ? transmissionLines.length : 0) +
          pool.filter(p => p.layer === "transmission").length,
        meetings: pool.filter(p => p.layer === "meetings").length,
        policy: pool.filter(p => p.layer === "policy").length,
        generation: pool.filter(p => p.layer === "generation").length
      };
    }

    function renderStatsRibbon() {
      const ribbon = $("#map-stats-ribbon");
      const defs = data.stats_ribbon || [];
      if (!ribbon || !defs.length) return;
      const counts = statCounts(true);
      ribbon.innerHTML = defs.map((d, i) => {
        const val = counts[d.value_key] ?? 0;
        const suffix = d.suffix || "";
        const accent = i === 0 ? " stat-inline--accent" : "";
        const sep = i < defs.length - 1 ? `<span class="stat-sep" aria-hidden="true">|</span>` : "";
        return `<span class="stat-inline${accent}"><strong>${val}${suffix}</strong>${esc(d.label)}</span>${sep}`;
      }).join("");
    }

    function renderSponsors() {
      const el = $("#map-sponsors");
      const s = data.sponsors;
      if (!el || !s) return;
      const slots = (s.slots || []).map(slot => {
        const hero = slot.highlight ? " sponsor-slot--hero" : "";
        const filled = slot.status === "filled" && slot.logo_url;
        return `<div class="sponsor-slot${hero}">${filled
          ? `<img src="${esc(slot.logo_url)}" alt="${esc(slot.name)}" style="max-height:36px;margin-bottom:6px">`
          : `<div class="sponsor-slot-tier">${esc(slot.tier)}</div><div class="sponsor-slot-name">${esc(slot.name)}</div><div class="sponsor-slot-tag">${esc(slot.tagline)}</div>`}</div>`;
      }).join("");
      el.innerHTML = `<div class="sponsor-head">Partners</div><div class="sponsor-slots">${slots}</div><a class="sponsor-inquire" href="${safeUrl(s.inquire_url)}">${esc(s.inquire_label || "Inquire")}</a>`;
    }

    function renderSiteLinks() {
      const el = $("#site-nav-grid");
      const links = data.site_links || [];
      if (!el || !links.length) return;
      el.innerHTML = links.map(l =>
        `<a class="site-nav-link" href="${esc(l.href)}"><strong>${esc(l.label)}</strong><small>${esc(l.desc)}</small></a>`
      ).join("");
    }

    function formatLakeLevel(val) {
      if (val == null || !Number.isFinite(val)) return "—";
      return `${val.toFixed(2)} ft`;
    }

    function renderLakeStrip() {
      const el = $("#map-lake-levels");
      if (!el || !lakeLevelsMeta.length) return;
      el.innerHTML = lakeLevelsMeta.map((lake, i) => {
        const live = liveWater.lakeLevels.get(lake.id);
        const display = live?.display || formatLakeLevel(live?.value);
        const sep = i < lakeLevelsMeta.length - 1 ? `<span class="lake-sep" aria-hidden="true">|</span>` : "";
        return `<span class="lake-chip" title="${esc(lake.lake)} — ${esc(lake.name)} gauge"><strong>${esc(display)}</strong>${esc(lake.label)}</span>${sep}`;
      }).join("");
    }

    function renderLiveMapLinks() {
      const el = $("#live-map-links");
      if (!el || !liveMapLinks.length) return;
      el.innerHTML = liveMapLinks.map(l =>
        `<a class="site-nav-link live-map-link" href="${safeUrl(l.href)}" target="_blank" rel="noopener"><strong>${esc(l.label)} ↗</strong><small>${esc(l.desc)}</small></a>`
      ).join("");
    }

    function ingestWaterSnapshot(snapshot) {
      if (!snapshot) return;
      (snapshot.lake_levels || []).forEach(row => {
        if (!row?.id) return;
        liveWater.lakeLevels.set(row.id, row);
      });
      (snapshot.buoys || []).forEach(row => {
        if (!row?.station) return;
        liveWater.buoys.set(String(row.station), row);
      });
      if (snapshot.updated_at) liveWater.updatedAt = snapshot.updated_at;
    }

    async function fetchNoaaLakeLevel(station) {
      const url = `https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=water_level&datum=IGLD&station=${encodeURIComponent(station)}&time_zone=gmt&units=english&format=json&range=1`;
      const res = await fetch(url);
      if (!res.ok) return null;
      const json = await res.json();
      const raw = json?.data?.[0]?.v;
      const val = raw != null ? parseFloat(raw) : null;
      return Number.isFinite(val) ? val : null;
    }

    async function refreshLiveWater({ snapshot = true } = {}) {
      if (snapshot) {
        try {
          const res = await fetch(`water-live.json?v=${WATER_VERSION}`, { cache: "no-store" });
          if (res.ok) ingestWaterSnapshot(await res.json());
        } catch (err) {
          console.warn("[map] water-live.json fetch failed", err);
        }
      }
      await Promise.all(lakeLevelsMeta.map(async lake => {
        if (!lake.station) return;
        try {
          const val = await fetchNoaaLakeLevel(lake.station);
          if (val == null) return;
          liveWater.lakeLevels.set(lake.id, {
            ...lake,
            value: val,
            unit: "ft IGLD",
            display: formatLakeLevel(val)
          });
        } catch (_) {}
      }));
      renderLakeStrip();
      refreshBuoyLiveLayers();
    }

    function renderLegend() {
      const el = $("#map-legend");
      if (!el) return;
      const rows = layersMeta.map(l =>
        `<div class="legend-row"><span class="legend-swatch" style="background:${l.color}"></span>${esc(l.label)}</div>`
      ).join("");
      const txRow = `<div class="legend-row"><span class="legend-line"></span>Transmission corridors</div>`;
      const genRows = ["Nuclear", "Coal", "Natural gas", "Wind", "Solar", "Hydroelectric"].map(s =>
        `<div class="legend-row"><span class="legend-swatch" style="background:${STATUS_COLORS[s] || "#14b8a6"}"></span>${esc(s)}</div>`
      ).join("");
      const boundaryRows = boundaryLayersMeta.map(b =>
        `<div class="legend-row"><span class="legend-line" style="background:${b.color}"></span>${esc(b.label)}</div>`
      ).join("");
      const overlayRows = overlayLayersMeta.map(o => {
        if (o.geometry_type === "point") {
          return `<div class="legend-row"><span class="legend-swatch" style="background:${o.color}"></span>${esc(o.label)}</div>`;
        }
        if (o.geometry_type === "polygon") {
          return `<div class="legend-row"><span class="legend-swatch" style="background:${o.color}"></span>${esc(o.label)}</div>`;
        }
        return `<div class="legend-row"><span class="legend-line" style="background:${o.color}"></span>${esc(o.label)}</div>`;
      }).join("");
      const aqMeta = overlayLayersMeta.find(o => o.id === "aquifers");
      const aquiferRows = aqMeta?.style_map
        ? Object.entries(aqMeta.style_map).map(([k, s]) => {
          const lbl = aqMeta.category_labels?.[k] || "";
          return `<div class="legend-row legend-row--stack"><span class="legend-swatch" style="background:${s.fillColor || s.color}"></span><span><strong>Class ${esc(k)}</strong>${lbl ? `<br><span class="legend-sub">${esc(lbl)}</span>` : ""}</span></div>`;
        }).join("")
        : "";
      const aquiferNote = aquiferRows
        ? `<p class="legend-note">Glacial aquifer colors show EGLE <em>geology</em> — how soil may hold groundwater. Not water quality or safety.</p>`
        : "";
      el.innerHTML = `<div class="map-legend-title">Layers</div>${rows}${txRow}${boundaryRows ? `<div class="map-legend-title" style="margin-top:10px">Boundaries</div>${boundaryRows}` : ""}${overlayRows ? `<div class="map-legend-title" style="margin-top:10px">Water & grid</div>${overlayRows}` : ""}${aquiferRows ? `<div class="map-legend-title" style="margin-top:8px">Glacial aquifer classes</div>${aquiferNote}${aquiferRows}` : ""}<div class="map-legend-title" style="margin-top:10px">Generation types</div>${genRows}`;
    }

    renderSponsors();
    renderSiteLinks();
    renderLiveMapLinks();
    renderLegend();
    renderLakeStrip();
    refreshLiveWater();
    setInterval(() => refreshLiveWater({ snapshot: true }), 15 * 60 * 1000);

    points.forEach(p => {
      const marker = L.marker([p.latitude, p.longitude], { icon: makeIcon(pointColor(p), false, p.layer, p.status), title: p.name });
      marker._trackerName = p.name;
      marker.bindPopup(makePopup(p), { maxWidth: 320, className: "tracker-popup" });
      marker.on("click", () => selectPoint(p.name, false));
      markerMap.set(p.name, marker);
    });

    transmissionLines.forEach(line => {
      if (!line.coordinates?.length) return;
      const isAlt = String(line.id).includes("route-b");
      const poly = L.polyline(line.coordinates, {
        color: isAlt ? "#c084fc" : "#9c5fc9",
        weight: isAlt ? 3 : 4,
        opacity: isAlt ? 0.55 : 0.85,
        dashArray: isAlt ? "10 8" : null,
        className: isAlt ? "" : "tx-glow"
      });
      poly.bindPopup(makeLinePopup(line), { maxWidth: 340 });
      if (line.name) {
        poly.bindTooltip(shortLineLabel(line.name), {
          className: "tx-line-tip",
          sticky: true,
          opacity: 0.94,
          direction: "top"
        });
      }
      transmissionGroup.addLayer(poly);
    });

    function pointVisible(p) {
      const layerOk = activeLayers.has(p.layer || "projects");
      const regionOk = activeRegion === "all" || regionForCounty(p.county) === activeRegion;
      const statusInp = filtersEl?.querySelector(`input[value="${escAttr(p.status)}"]`);
      const statusOk = !statusInp || statusInp.checked;
      return layerOk && regionOk && statusOk;
    }

    function syncUrl() {
      const p = new URLSearchParams();
      if (currentMode !== "dark") p.set("mode", currentMode);
      if (activeRegion !== "all") p.set("region", activeRegion);
      const onStatuses = statusesForActiveLayers().filter(s => filtersEl?.querySelector(`input[value="${escAttr(s)}"]`)?.checked);
      const statusPool = statusesForActiveLayers();
      if (onStatuses.length && onStatuses.length < statusPool.length) p.set("f", onStatuses.join(","));
      const onLayers = [...activeLayers];
      const defaultLayerSet = new Set(layersMeta.filter(l => l.default_on !== false).map(l => l.id));
      const layersAreDefault = onLayers.length === defaultLayerSet.size && onLayers.every(id => defaultLayerSet.has(id));
      if (onLayers.length && onLayers.length < layersMeta.length && !layersAreDefault) p.set("layers", onLayers.join(","));
      const onBoundaries = [...activeBoundaries];
      if (onBoundaries.length) p.set("boundaries", onBoundaries.join(","));
      const onOverlays = [...activeOverlays];
      if (onOverlays.length) p.set("overlays", onOverlays.join(","));
      if (activePointName) p.set("point", activePointName);
      const qs = p.toString();
      history.replaceState(null, "", qs ? `?${qs}` : location.pathname);
    }

    function refreshMarkers() {
      markerLayer.clearLayers();
      const visible = points.filter(pointVisible);
      visible.forEach(p => markerLayer.addLayer(markerMap.get(p.name)));
      const countEl = $("#panel-record-count");
      if (countEl) countEl.textContent = `${visible.length} / ${points.length}`;
      if (dirEl) {
        dirEl.innerHTML = visible.length
          ? [...visible].sort((a, b) => a.municipality.localeCompare(b.municipality)).map(p =>
            `<button type="button" data-point="${esc(p.name)}" class="${activePointName === p.name ? "active" : ""}"><span class="dir-dot" style="background:${pointColor(p)}"></span><strong>${esc(p.name)}</strong><small>${esc(p.municipality)} · ${esc(p.status)}</small></button>`
          ).join("")
          : `<div class="dir-empty">No records match your filters.</div>`;
      }
      if (activeLayers.has("transmission")) map.addLayer(transmissionGroup);
      else map.removeLayer(transmissionGroup);
      renderStatsRibbon();
      syncUrl();
    }

    function fitAll() {
      const latlngs = [];
      points.filter(pointVisible).forEach(p => latlngs.push([p.latitude, p.longitude]));
      if (activeLayers.has("transmission")) transmissionLines.forEach(l => (l.coordinates||[]).forEach(c => latlngs.push(c)));
      if (latlngs.length) map.fitBounds(latlngs, { padding: [50, 50], maxZoom: 8 });
    }

    function renderRecordLayerGroup(el, ids) {
      if (!el) return;
      el.innerHTML = ids.map(id => {
        const l = layersMeta.find(row => row.id === id);
        if (!l) return "";
        const n = points.filter(p => p.layer === l.id).length;
        const on = activeLayers.has(l.id);
        return layerRow({ id: l.id, label: l.label, desc: l.description, color: l.color, count: n, on });
      }).join("");
    }

    function renderRecordLayers() {
      renderRecordLayerGroup(layersCoreEl, FOCUSED_LAYER_IDS);
      renderRecordLayerGroup(layersMoreEl, OPTIONAL_LAYER_IDS.filter(id => layersMeta.some(l => l.id === id)));
    }

    function syncRecordLayerRows() {
      layersStackEl?.querySelectorAll(".layer-row").forEach(btn => {
        setLayerRow(btn, activeLayers.has(btn.dataset.layer));
      });
    }

    function renderStatusFilters() {
      if (!filtersEl) return;
      const statuses = statusesForActiveLayers();
      const isFirst = !filtersEl.querySelector("input");
      const prevInputs = [...filtersEl.querySelectorAll("input")];
      const prevChecked = new Set(prevInputs.filter(i => i.checked).map(i => i.value));
      const prevStatuses = new Set(prevInputs.map(i => i.value));
      filtersEl.innerHTML = statuses.map(s => {
        const checkedOn = isFirst
          ? (!initFilters || initFilters.has(s))
          : (prevStatuses.has(s) ? prevChecked.has(s) : true);
        return `<label class="${checkedOn ? "" : "off"}"><input type="checkbox" value="${esc(s)}" ${checkedOn ? "checked" : ""}><span class="filter-dot" style="background:${STATUS_COLORS[s]||"#cf102d"}"></span><span class="filter-name">${esc(s)}</span><span class="filter-count">${points.filter(p => p.status === s && activeLayers.has(p.layer || "projects")).length}</span></label>`;
      }).join("");
    }

    if (layersStackEl && layersMeta.length) {
      renderRecordLayers();
      bindLayerList(layersStackEl, (id, on) => {
        if (isMobile()) openMobilePanel("layers");
        if (on) activeLayers.add(id); else activeLayers.delete(id);
        analytics.track("layer_toggle", { group: "records", layer: id, on });
        renderStatusFilters();
        refreshMarkers();
      });
    }

    if (boundariesEl && boundaryLayersMeta.length) {
      boundariesEl.innerHTML = boundaryLayersMeta.map(b => {
        const on = activeBoundaries.has(b.id);
        const count = b.id === "townships" ? "1,240" : b.id === "congressional" ? "13" : b.id === "counties" ? "83" : "";
        return layerRow({ id: b.id, label: b.label, desc: b.description, color: b.color, count, on, line: true });
      }).join("");
      bindLayerList(boundariesEl, (id, on) => {
        if (isMobile()) openMobilePanel("layers");
        const meta = boundaryLayersMeta.find(b => b.id === id);
        if (!meta) return;
        if (on) {
          activeBoundaries.add(meta.id);
          ensureBoundaryLayer(meta);
          if (meta.min_zoom && map.getZoom() < meta.min_zoom) {
            map.flyTo(map.getCenter(), meta.min_zoom, { duration: 0.6 });
          }
        } else {
          activeBoundaries.delete(meta.id);
        }
        analytics.track("layer_toggle", { group: "boundaries", layer: id, on });
        refreshBoundaries();
      });
      boundaryLayersMeta.filter(b => activeBoundaries.has(b.id)).forEach(b => ensureBoundaryLayer(b));
      map.on("zoomend", refreshBoundaries);
    }

    if (overlaysEl && overlayLayersMeta.length) {
      const overlayCounts = {
        transmission_grid: "1,737",
        aquifers: "1,388",
        water_wells: "21",
        noaa_buoys: "9",
        airports: "14",
        substations: "15"
      };
      overlaysEl.innerHTML = overlayLayersMeta.map(o => {
        const on = activeOverlays.has(o.id);
        const count = overlayCounts[o.id] || "";
        const line = o.geometry_type === "line";
        return layerRow({ id: o.id, label: o.label, desc: o.description, color: o.color, count, on, line });
      }).join("");
      bindLayerList(overlaysEl, (id, on) => {
        if (isMobile()) openMobilePanel("layers");
        const meta = overlayLayersMeta.find(o => o.id === id);
        if (!meta) return;
        if (on) {
          activeOverlays.add(meta.id);
          ensureOverlayLayer(meta);
          if (meta.min_zoom && map.getZoom() < meta.min_zoom) {
            map.flyTo(map.getCenter(), meta.min_zoom, { duration: 0.6 });
          }
        } else {
          activeOverlays.delete(meta.id);
        }
        analytics.track("layer_toggle", { group: "overlays", layer: id, on });
        refreshOverlays();
      });
      overlayLayersMeta.filter(o => activeOverlays.has(o.id)).forEach(o => ensureOverlayLayer(o));
      map.on("zoomend", refreshOverlays);
    }

    if (filtersEl) {
      renderStatusFilters();
      filtersEl.addEventListener("change", e => {
        const input = e.target.closest("input");
        if (input) analytics.track("filter_change", { type: "status", value: input.value, on: input.checked });
        refreshMarkers();
      });
    }

    if (storiesEl && stories.length) {
      storiesEl.innerHTML = stories.map(s => `<button type="button" class="story-card" data-story="${esc(s.id)}"><span class="story-kicker">${esc(s.kicker)}</span><strong>${esc(s.title)}</strong><small>${esc(s.region)}</small></button>`).join("");
      storiesEl.addEventListener("click", e => { const btn = e.target.closest("[data-story]"); if (btn) openStory(btn.dataset.story); });
    }

    function openStory(id) {
      const story = stories.find(s => s.id === id);
      if (!story) return;
      const panel = $("#story-detail");
      if (panel) { panel.hidden = false; panel.innerHTML = `<div class="story-detail-kicker">${esc(story.kicker)}</div><h3>${esc(story.title)}</h3><p>${esc(story.summary)}</p><div class="story-detail-actions"><a href="${safeUrl(story.source_url)}" target="_blank" rel="noopener">${esc(story.source_name)} ↗</a></div>`; }
      if (isMobile()) openMobilePanel("layers");
      else switchPanelTab("layers");
      if (story.id === "power-water-nexus") {
        ["transmission_grid", "aquifers"].forEach(oid => {
          const meta = overlayLayersMeta.find(o => o.id === oid);
          if (!meta) return;
          activeOverlays.add(oid);
          ensureOverlayLayer(meta);
          setLayerRowById(overlaysEl, oid, true);
        });
        setTimeout(refreshOverlays, 400);
      }
      if (story.fly_to) map.flyTo([story.fly_to.lat, story.fly_to.lng], story.fly_to.zoom || 8, { duration: 0.8 });
    }

    function renderSelectedRecord(p) {
      const panel = $("#selected-record");
      if (!panel) return;
      if (!p) { panel.hidden = true; panel.innerHTML = ""; return; }
      const c = pointColor(p);
      const dateStr = p.verified_date ? dateLabel(p.verified_date) : "";
      const phase = recordPhase(p);
      const actions = recordNextActions(p);
      panel.hidden = false;
      const ownerLabel = p.layer === "generation" ? "Operator" : "Developer";
      const capacityLabel = p.layer === "generation" ? "Capacity" : "Scale";
      const facts = [
        p.developer ? `<div class="record-fact"><span>${ownerLabel}</span><strong>${esc(p.developer)}</strong></div>` : "",
        p.power_mw ? `<div class="record-fact"><span>${capacityLabel}</span><strong>${esc(p.power_mw)} MW</strong></div>` : "",
        dateStr ? `<div class="record-fact"><span>Last verified</span><strong>${dateStr}</strong></div>` : "",
        p.confidence ? `<div class="record-fact"><span>Confidence</span><strong>${esc(p.confidence)}</strong></div>` : ""
      ].filter(Boolean).join("");
      const actionHtml = actions.length
        ? `<div class="record-actions"><div class="record-actions-title">What to watch</div><ul>${actions.map(a => `<li>${esc(a)}</li>`).join("")}</ul></div>`
        : "";
      panel.innerHTML = `<div class="record-card" style="--status:${c}"><div class="record-status">${esc(p.status)}</div><div class="record-phase">${esc(phase)} · ${esc(layerLabel(p))}</div><h2 class="record-name">${esc(p.name)}</h2><div class="record-meta">${esc(p.municipality)}, ${esc(p.county)} County</div>${facts ? `<div class="record-facts">${facts}</div>` : ""}${p.note ? `<p class="record-note">${esc(p.note)}</p>` : ""}${actionHtml}</div>`;
    }

    function clearSelection() {
      if (activeMarker && activePointName) {
        const prev = pointByName.get(activePointName);
        if (prev) activeMarker.setIcon(makeIcon(pointColor(prev), false, prev.layer, prev.status));
      }
      activeMarker = null;
      activePointName = null;
      renderSelectedRecord(null);
      clearClusterPeek();
      $$(".map-directory button.active").forEach(b => b.classList.remove("active"));
    }

    function selectPoint(name, fly = true) {
      const marker = markerMap.get(name), p = pointByName.get(name);
      if (!marker || !p) return;
      clearClusterPeek();
      if (activeMarker && activePointName) { const prev = pointByName.get(activePointName); if (prev) activeMarker.setIcon(makeIcon(pointColor(prev), false, prev.layer, prev.status)); }
      activeMarker = marker; activePointName = name;
      marker.setIcon(makeIcon(pointColor(p), true, p.layer, p.status));
      renderSelectedRecord(p);
      analytics.recordAttention(p.name, p.name, p.layer, p.status);
      $$(".map-directory button").forEach(b => b.classList.toggle("active", b.dataset.point === name));
      if (fly) { map.flyTo(marker.getLatLng(), Math.max(map.getZoom(), 10), { duration: 0.6 }); setTimeout(() => marker.openPopup(), 500); }
      if (isMobile()) openMobilePanel("list");
      else switchPanelTab("list");
      syncUrl();
    }

    function resetMapView({ fit = true } = {}) {
      activeRegion = "all";
      activeLayers = new Set(layersMeta.filter(l => l.default_on !== false).map(l => l.id));
      if (!activeLayers.size) FOCUSED_LAYER_IDS.forEach(id => activeLayers.add(id));
      $$("#map-filters input").forEach(i => { i.checked = true; i.closest("label")?.classList.remove("off"); });
      syncRecordLayerRows();
      renderStatusFilters();
      activeBoundaries = new Set(boundaryLayersMeta.filter(b => b.default_on).map(b => b.id));
      boundariesEl?.querySelectorAll(".layer-row").forEach(btn => setLayerRow(btn, activeBoundaries.has(btn.dataset.layer)));
      refreshBoundaries();
      activeOverlays = new Set(overlayLayersMeta.filter(o => o.default_on).map(o => o.id));
      overlaysEl?.querySelectorAll(".layer-row").forEach(btn => setLayerRow(btn, activeOverlays.has(btn.dataset.layer)));
      refreshOverlays();
      $$(".region-chip").forEach(c => c.classList.toggle("active", c.dataset.region === "all"));
      const storyPanel = $("#story-detail");
      if (storyPanel) { storyPanel.hidden = true; storyPanel.innerHTML = ""; }
      clearSelection();
      clearClusterPeek();
      map.closePopup();
      refreshMarkers();
      if (!isMobile()) switchPanelTab("layers");
      else toggleMobilePanel(false);
      history.replaceState(null, "", location.pathname);
      if (fit) {
        map.invalidateSize();
        fitLowerPeninsula({ duration: 0.7 });
      }
      analytics.track("map_reset");
    }

    $("#show-all")?.addEventListener("click", () => resetMapView());

    $$("#map-reset, #map-reset-top").forEach(btn => btn.addEventListener("click", () => resetMapView()));

    document.addEventListener("keydown", e => {
      if (e.target.matches("input, textarea, select")) return;
      if (e.key === "r" || e.key === "R") { e.preventDefault(); resetMapView(); }
      if (e.key === "/") {
        e.preventDefault();
        if (isMobile()) openMobilePanel("list");
        else switchPanelTab("list");
        $("#map-search")?.focus();
      }
    });

    $$(".region-chip").forEach(chip => {
      chip.classList.toggle("active", chip.dataset.region === activeRegion);
      chip.addEventListener("click", () => {
        activeRegion = chip.dataset.region;
        $$(".region-chip").forEach(c => c.classList.toggle("active", c.dataset.region === activeRegion));
        analytics.track("filter_change", { type: "region", value: activeRegion });
        refreshMarkers();
      });
    });

    $$(".panel-tab").forEach(tab => {
      tab.addEventListener("click", e => {
        e.stopPropagation();
        if (isMobile()) openMobilePanel(tab.dataset.tab);
        else switchPanelTab(tab.dataset.tab);
      });
    });

    dirEl?.addEventListener("click", e => { const btn = e.target.closest("button[data-point]"); if (btn) selectPoint(btn.dataset.point); });
    $("#cluster-peek")?.addEventListener("click", e => {
      const btn = e.target.closest("button[data-point]");
      if (btn) selectPoint(btn.dataset.point);
    });

    const searchEl = $("#map-search"), searchResults = $("#search-results");
    if (searchEl && searchResults) {
      searchEl.addEventListener("input", () => {
        const q = searchEl.value.trim().toLowerCase();
        if (q.length < 2) { searchResults.hidden = true; searchResults.innerHTML = ""; return; }
        const matches = points.filter(p => pointVisible(p) && [p.name,p.municipality,p.county,p.developer||""].some(v => v.toLowerCase().includes(q))).slice(0, 10);
        if (q.length >= 2) analytics.track("search", { query_length: q.length, results: matches.length });
        searchResults.hidden = !matches.length;
        searchResults.innerHTML = matches.map(p => `<button type="button" data-point="${esc(p.name)}"><span class="dir-dot" style="background:${pointColor(p)}"></span><span><strong>${esc(p.name)}</strong><small>${esc(p.municipality)}</small></span></button>`).join("");
      });
        searchResults.addEventListener("click", e => { const btn = e.target.closest("button[data-point]"); if (btn) { selectPoint(btn.dataset.point); searchEl.value = ""; searchResults.hidden = true; } });
    }

    function haversineMi(lat1, lng1, lat2, lng2) {
      const R = 3958.8, toRad = d => d * Math.PI / 180;
      const dLat = toRad(lat2 - lat1), dLng = toRad(lng2 - lng1);
      const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
      return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    }

    function locateNearMe() {
      const btn = $("#map-locate");
      if (!navigator.geolocation) { alert("Geolocation is not available in this browser."); return; }
      if (btn) { btn.textContent = "Locating…"; btn.disabled = true; }
      navigator.geolocation.getCurrentPosition(pos => {
        const { latitude: lat, longitude: lng } = pos.coords;
        const nearby = points.filter(pointVisible).map(p => ({ p, dist: haversineMi(lat, lng, p.latitude, p.longitude) }))
          .sort((a, b) => a.dist - b.dist).slice(0, 5);
        const bounds = L.latLngBounds([[lat, lng]]);
        nearby.forEach(({ p }) => bounds.extend([p.latitude, p.longitude]));
        map.flyToBounds(bounds, { padding: [80, 80], maxZoom: 11, duration: 0.8 });
        if (nearby.length) setTimeout(() => selectPoint(nearby[0].p.name, false), 600);
        if (btn) { btn.textContent = "Near me"; btn.disabled = false; }
      }, () => {
        if (btn) { btn.textContent = "Near me"; btn.disabled = false; }
        alert("Could not access your location. Check browser permissions.");
      }, { enableHighAccuracy: false, timeout: 12000 });
    }

    $("#map-locate")?.addEventListener("click", () => { analytics.track("locate_near_me"); locateNearMe(); });

    async function shareMapView() {
      const url = location.href;
      const title = "Michigan Data Center Tracker — Live Map";
      const text = "Explore Michigan data center proposals, moratoria, and grid corridors.";
      try {
        if (navigator.share) { await navigator.share({ title, text, url }); return; }
      } catch (err) {
        if (err?.name === "AbortError") return;
      }
      try {
        await navigator.clipboard.writeText(url);
        const btn = $("#map-share");
        if (btn) { const orig = btn.textContent; btn.textContent = "Copied!"; setTimeout(() => { btn.textContent = orig; }, 1800); }
      } catch {
        prompt("Copy this link:", url);
      }
    }

    $("#map-share")?.addEventListener("click", () => { analytics.track("share"); shareMapView(); });

    const legendEl = $("#map-legend"), legendToggle = $("#map-legend-toggle");
    legendToggle?.addEventListener("click", () => {
      const hidden = legendEl?.hasAttribute("hidden");
      if (hidden) { legendEl.removeAttribute("hidden"); legendToggle.setAttribute("aria-expanded", "true"); }
      else { legendEl?.setAttribute("hidden", ""); legendToggle.setAttribute("aria-expanded", "false"); }
    });

    $("#copy-link")?.addEventListener("click", shareMapView);

    const sidebar = $("#map-sidebar");
    $("#sidebar-header")?.addEventListener("click", e => {
      if (!isMobile()) return;
      if (e.target.closest("#map-search, .search-results, .panel-search-wrap, .panel-tab")) return;
      toggleMobilePanel();
    });
    $(".panel-grab")?.addEventListener("click", e => {
      e.stopPropagation();
      if (isMobile()) toggleMobilePanel();
    });
    $("#map-search")?.addEventListener("click", e => {
      if (isMobile() && !sidebar?.classList.contains("open")) {
        e.stopPropagation();
        openMobilePanel("list");
      }
    });

    window.addEventListener("resize", updateMobilePanelUi);
    updateMobilePanelUi();

    const updEl = $("#map-updated");
    if (updEl && data.updated_at) updEl.textContent = "Updated " + new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "America/Detroit" }).format(new Date(data.updated_at));

    const ext = data.map_meta?.external_map;
    if (ext) { const link = $("#external-map-link"); if (link) { link.href = ext.url; link.textContent = ext.label; link.hidden = false; } }

    refreshMarkers();
    const applyInitialView = () => {
      map.invalidateSize();
      if (!initStory && !initPoint) fitLowerPeninsula();
    };
    applyInitialView();
    requestAnimationFrame(applyInitialView);
    if (initStory) openStory(initStory);
    else if (initPoint && markerMap.has(initPoint)) selectPoint(initPoint);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => initMap().catch(e => showBootError("Map init error")));
  else initMap().catch(e => showBootError("Map init error"));
})();