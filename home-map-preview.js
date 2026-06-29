/**
 * Homepage live-map thumbnail — rotates through layer-focused views with filters + legend.
 */
(function (global) {
  const SVG_SIZE = { w: 1200, h: 720 };
  const GEO = { north: 45.48, south: 41.7, west: -87.02, east: -82.38 };
  const PAD = { left: 92, right: 88, top: 36, bottom: 44 };
  const MAP_BG = ["#1a2a42", "#0c121c"];
  const COUNTY_FILL = "#243a56";
  const COUNTY_STROKE = "#4d7394";
  const PREVIEW_ASPECT = 2.2;
  const LAYER_COLORS = {
    projects: "#cf102d",
    moratoria: "#e09820",
    meetings: "#5b9cf5",
    transmission: "#9c5fc9",
    policy: "#22a86a",
    generation: "#14b8a6"
  };
  const LAYER_META = {
    projects: { label: "Data center sites", short: "Sites" },
    moratoria: { label: "Moratoria & pauses", short: "Moratoria" },
    meetings: { label: "Public meetings", short: "Meetings" },
    transmission: { label: "Grid proposals", short: "Grid" },
    policy: { label: "Capitol & policy", short: "Policy" },
    generation: { label: "Power generation", short: "Power" }
  };

  const DRIFT_CLASSES = ["ne", "sw", "nw", "se", "ctr"];

  const SLIDE_DEFS = [
    {
      id: "full-tracker",
      label: "Full tracker",
      kickerFn: c => `${c.projects + c.moratoria + c.meetings} records statewide`,
      layers: ["projects", "moratoria", "meetings"],
      zoom: "state",
      wide: true,
      labels: false,
      href: "map.html?layers=projects,moratoria,meetings"
    },
    {
      id: "zoom-se-moratoria",
      label: "Moratoria & pauses",
      kicker: "Oakland · Wayne · Macomb",
      layers: ["moratoria", "projects"],
      swatchLayer: "moratoria",
      fit: p => p.longitude > -83.72 && p.latitude > 42.18 && p.latitude < 42.82,
      tight: true,
      labels: false,
      maxView: { w: 320, h: 250 },
      focus: { lat: 42.52, lng: -83.42 },
      href: "map.html?lat=42.52&lng=-83.42&zoom=10&layers=moratoria,projects"
    },
    {
      id: "zoom-wixom",
      label: "Public meetings",
      kicker: "Wixom · Lyon · Pittsfield",
      layers: ["meetings", "moratoria", "projects"],
      swatchLayer: "meetings",
      fit: p => p.longitude > -83.78 && p.longitude < -83.35 && p.latitude > 42.2 && p.latitude < 42.58,
      tight: true,
      labels: false,
      maxView: { w: 290, h: 230 },
      focus: { lat: 42.525, lng: -83.536 },
      href: "map.html?lat=42.525&lng=-83.536&zoom=11&layers=meetings,moratoria,projects"
    },
    {
      id: "zoom-saline",
      label: "Data center sites",
      kicker: "Saline · Pittsfield · Ypsilanti",
      layers: ["projects", "moratoria"],
      swatchLayer: "projects",
      fit: p => p.longitude > -84.05 && p.longitude < -83.55 && p.latitude > 42.05 && p.latitude < 42.35,
      tight: true,
      labels: false,
      maxView: { w: 300, h: 240 },
      focus: { lat: 42.2, lng: -83.75 },
      href: "map.html?lat=42.2&lng=-83.75&zoom=10&layers=projects,moratoria"
    },
    {
      id: "zoom-google",
      label: "Data center sites",
      kicker: "Van Buren · Allen Park corridor",
      layers: ["projects", "moratoria"],
      swatchLayer: "projects",
      fit: p => p.longitude > -83.65 && p.longitude < -83.15 && p.latitude > 42.15 && p.latitude < 42.48,
      tight: true,
      labels: false,
      maxView: { w: 280, h: 220 },
      focus: { lat: 42.232, lng: -83.486 },
      href: "map.html?lat=42.23&lng=-83.49&zoom=11&layers=projects,moratoria"
    },
    {
      id: "zoom-west",
      label: "Moratoria & pauses",
      kicker: "Kent · Ottawa · Muskegon",
      layers: ["moratoria", "projects"],
      swatchLayer: "moratoria",
      fit: p => p.longitude < -85.1 && p.latitude > 42.65,
      tight: true,
      labels: false,
      maxView: { w: 340, h: 270 },
      href: "map.html?lat=43.05&lng=-85.75&zoom=9&layers=moratoria,projects"
    },
    {
      id: "zoom-capitol",
      label: "Capitol & policy",
      kicker: "Lansing · East Lansing",
      layers: ["policy", "meetings", "moratoria"],
      swatchLayer: "policy",
      fit: p => p.longitude > -84.75 && p.longitude < -84.35 && p.latitude > 42.55 && p.latitude < 42.82,
      tight: true,
      labels: false,
      maxView: { w: 300, h: 240 },
      focus: { lat: 42.73, lng: -84.55 },
      href: "map.html?lat=42.73&lng=-84.55&zoom=10&layers=policy,meetings,moratoria"
    },
    {
      id: "zoom-grid",
      label: "Grid proposals",
      kicker: "Corridors · plants · sites",
      layers: ["transmission", "generation", "projects"],
      swatchLayer: "transmission",
      lines: true,
      fit: p => ["transmission", "generation", "projects"].includes(p.layer)
        && p.longitude > -86.2 && p.latitude > 42.35 && p.latitude < 43.1,
      tight: true,
      labels: false,
      maxView: { w: 380, h: 300 },
      href: "map.html?lat=42.68&lng=-84.9&zoom=9&layers=transmission,generation,projects"
    },
    {
      id: "zoom-wind",
      label: "Power generation",
      kicker: "Gratiot · Muskegon · Cross Winds",
      layers: ["generation"],
      swatchLayer: "generation",
      fit: p => p.layer === "generation"
        && ((p.longitude < -84.5 && p.latitude > 43.0) || p.name.includes("Wind") || p.name.includes("Solar")),
      tight: true,
      labels: false,
      maxView: { w: 400, h: 310 },
      href: "map.html?lat=43.2&lng=-85.1&zoom=9&layers=generation"
    },
    {
      id: "all-layers",
      label: "Six map layers",
      kickerFn: (_, total) => `Toggle anything · ${total} records`,
      layers: ["projects", "moratoria", "meetings", "transmission", "policy", "generation"],
      lines: true,
      zoom: "state",
      wide: true,
      labels: false,
      href: "map.html"
    }
  ];

  let countyMarkup = "";
  let countyPromise = null;

  function project(lat, lng) {
    const innerW = SVG_SIZE.w - PAD.left - PAD.right;
    const innerH = SVG_SIZE.h - PAD.top - PAD.bottom;
    const x = PAD.left + ((lng - GEO.west) / (GEO.east - GEO.west)) * innerW;
    const y = PAD.top + ((GEO.north - lat) / (GEO.north - GEO.south)) * innerH;
    return [x, y];
  }

  function iconInner(layer, color, status = "") {
    const shapes = {
      moratoria: `<rect x="5" y="5" width="14" height="14" rx="2.2" fill="${color}" stroke="#fff" stroke-width="1.6"/>`,
      meetings: `<circle cx="12" cy="12" r="7.2" fill="${color}" stroke="#fff" stroke-width="1.6"/>`,
      transmission: `<path d="M12 2.5L7.5 12.5H11l-1 9.5 6.5-11.5H13.5L12 2.5z" fill="${color}" stroke="#fff" stroke-width="1.3"/>`,
      policy: `<polygon points="12,2.5 15,9.5 22,9.5 16.5,14 18.5,21.5 12,17.5 5.5,21.5 7.5,14 2,9.5 9,9.5" fill="${color}" stroke="#fff" stroke-width="1.2"/>`,
      generation: `<rect x="4" y="9" width="16" height="10" rx="2" fill="${color}" stroke="#fff" stroke-width="1.3"/><rect x="10" y="4" width="4" height="6.5" fill="${color}" stroke="#fff" stroke-width="1.2"/>`
    };
    const genShapes = {
      Nuclear: `<circle cx="12" cy="12" r="2.4" fill="${color}" stroke="#fff" stroke-width="1.1"/><ellipse cx="12" cy="12" rx="8.5" ry="3.2" fill="none" stroke="${color}" stroke-width="1.3"/><ellipse cx="12" cy="12" rx="8.5" ry="3.2" fill="none" stroke="${color}" stroke-width="1.3" transform="rotate(60 12 12)"/><ellipse cx="12" cy="12" rx="8.5" ry="3.2" fill="none" stroke="${color}" stroke-width="1.3" transform="rotate(-60 12 12)"/>`,
      Wind: `<path d="M12 4v16M12 12L6.5 18M12 12l5.5 6" stroke="${color}" stroke-width="2" stroke-linecap="round"/><circle cx="12" cy="12" r="2.4" fill="${color}" stroke="#fff" stroke-width="1.2"/>`,
      Solar: `<circle cx="12" cy="12" r="4.5" fill="${color}" stroke="#fff" stroke-width="1.2"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3" stroke="${color}" stroke-width="1.4" stroke-linecap="round"/>`
    };
    if (layer === "generation" && genShapes[status]) return genShapes[status];
    if (shapes[layer]) return shapes[layer];
    return `<path d="M12 2.2c-3.2 0-5.8 2.4-5.8 5.4 0 4 5.8 11.8 5.8 11.8s5.8-7.8 5.8-11.8c0-3-2.6-5.4-5.8-5.4z" fill="${color}" stroke="#fff" stroke-width="1.5"/><circle cx="12" cy="7.5" r="2" fill="#fff" fill-opacity=".92"/>`;
  }

  function layerCounts(mapData) {
    const counts = { projects: 0, moratoria: 0, meetings: 0, transmission: 0, policy: 0, generation: 0 };
    (mapData.map_points || []).forEach(p => {
      const layer = p.layer || "projects";
      if (layer in counts) counts[layer] += 1;
    });
    return counts;
  }

  function loadCountyMarkup() {
    if (countyMarkup) return Promise.resolve(countyMarkup);
    if (countyPromise) return countyPromise;
    countyPromise = fetch("home-map-preview.svg?v=20260701p")
      .then(res => {
        if (!res.ok) throw new Error(`preview svg ${res.status}`);
        return res.text();
      })
      .then(text => {
        const match = text.match(/<g fill="#e8eef4"[^>]*>([\s\S]*?)<\/g>/);
        countyMarkup = match ? match[1] : "";
        return countyMarkup;
      })
      .catch(() => {
        countyMarkup = "";
        return countyMarkup;
      });
    return countyPromise;
  }

  function clampViewBox(x, y, w, h) {
    w = Math.max(180, Math.min(w, SVG_SIZE.w));
    h = Math.max(140, Math.min(h, SVG_SIZE.h));
    x = Math.max(0, Math.min(x, SVG_SIZE.w - w));
    y = Math.max(0, Math.min(y, SVG_SIZE.h - h));
    return { x, y, w, h };
  }

  function stateView(count = 0) {
    return { x: 36, y: 18, w: SVG_SIZE.w - 72, h: SVG_SIZE.h - 42, count };
  }

  function normalizeViewAspect(view, aspect = PREVIEW_ASPECT) {
    let { x, y, w, h, count } = view;
    const ratio = w / h;
    if (ratio > aspect * 1.05) {
      const newH = w / aspect;
      y -= (newH - h) / 2;
      h = newH;
    } else if (ratio < aspect * 0.78) {
      const newW = h * aspect;
      x -= (newW - w) / 2;
      w = newW;
    }
    return { ...clampViewBox(x, y, w, h), count };
  }

  function computeView(points, slide) {
    const layers = new Set(slide.layers);
    const filtered = points.filter(p => {
      if (!layers.has(p.layer || "projects")) return false;
      return slide.fit ? slide.fit(p) : true;
    });

    if (slide.zoom === "state") return stateView(filtered.length);
    if (!filtered.length) return stateView(0);

    const coords = filtered.map(p => project(p.latitude, p.longitude));
    const xs = coords.map(c => c[0]);
    const ys = coords.map(c => c[1]);

    let minX = Math.min(...xs);
    let maxX = Math.max(...xs);
    let minY = Math.min(...ys);
    let maxY = Math.max(...ys);

    const spanX = Math.max(maxX - minX, 1);
    const spanY = Math.max(maxY - minY, 1);
    const padFactor = slide.tight ? 0.16 : slide.wide ? 0.09 : 0.12;
    const padX = Math.max(spanX * padFactor, slide.tight ? 22 : slide.wide ? 36 : 28);
    const padY = Math.max(spanY * padFactor, slide.tight ? 18 : slide.wide ? 30 : 24);

    let w = spanX + padX * 2;
    let h = spanY + padY * 2;

    if (slide.minView) {
      w = Math.max(w, slide.minView.w);
      h = Math.max(h, slide.minView.h);
    }
    if (slide.maxView) {
      w = Math.min(w, slide.maxView.w);
      h = Math.min(h, slide.maxView.h);
    }

    const cx = (minX + maxX) / 2;
    const cy = (minY + maxY) / 2;
    return { ...clampViewBox(cx - w / 2, cy - h / 2, w, h), count: filtered.length };
  }

  function expandViewForLines(view, lines, slide) {
    if (!lines?.length) return view;
    const pts = lines.flatMap(l => (l.coordinates || []).map(([lat, lng]) => project(lat, lng)));
    if (!pts.length) return view;
    const xs = pts.map(p => p[0]);
    const ys = pts.map(p => p[1]);
    const minX = Math.min(...xs, view.x);
    const minY = Math.min(...ys, view.y);
    const maxX = Math.max(...xs, view.x + view.w);
    const maxY = Math.max(...ys, view.y + view.h);
    const spanX = Math.max(maxX - minX, 1);
    const spanY = Math.max(maxY - minY, 1);
    const padX = Math.max(spanX * (slide.wide ? 0.08 : 0.1), 24);
    const padY = Math.max(spanY * (slide.wide ? 0.08 : 0.1), 20);
    let w = spanX + padX * 2;
    let h = spanY + padY * 2;
    if (slide?.minView) {
      w = Math.max(w, slide.minView.w);
      h = Math.max(h, slide.minView.h);
    }
    if (slide?.maxView) {
      w = Math.min(w, slide.maxView.w);
      h = Math.min(h, slide.maxView.h);
    }
    const cx = (minX + maxX) / 2;
    const cy = (minY + maxY) / 2;
    return { ...view, ...clampViewBox(cx - w / 2, cy - h / 2, w, h) };
  }

  function buildSlides(data) {
    const points = (data.map_points || []).filter(
      p => Number.isFinite(p.latitude) && Number.isFinite(p.longitude)
    );
    const counts = layerCounts(data);
    const total = points.length;

    return SLIDE_DEFS.map(def => {
      const kicker = def.kickerFn ? def.kickerFn(counts, total) : def.kicker;
      let view = computeView(points, def);
      if (def.lines) view = expandViewForLines(view, data.transmission_lines, def);
      view = normalizeViewAspect(view, def.aspect || PREVIEW_ASPECT);
      return { ...def, kicker, view };
    }).filter(slide => slide.view.count > 0 || slide.lines);
  }

  function townName(point) {
    if (point.municipality) {
      return String(point.municipality)
        .replace(/\s+(Township|City|Charter Township|Village)$/i, "")
        .trim();
    }
    const name = String(point.name || "");
    const patterns = [
      /^(?:City of |Township of |Village of )?([A-Za-z .'-]+?)\s+(?:moratorium|Planning|board|Commission|hearing|meeting|campus|Google|proposal|Project)/i,
      /^([A-Za-z .'-]+?)\s+Township\b/i,
      /^([A-Za-z .'-]+?)\s+(?:Nuclear|Power Plant|Generating|Wind|Solar|Energy Center|Solar Park)/i,
      /^([A-Za-z .'-]+?)\s+(?:Metrobloks|Solstice|Meta|Microsoft|Franklin|Deep Green)/i,
      /^([A-Za-z .'-]+?)-area\b/i,
      /^([A-Za-z .'-]+)\s+County\b/i
    ];
    for (const pattern of patterns) {
      const match = name.match(pattern);
      if (match?.[1]) return match[1].replace(/ Township$/, "").trim();
    }
    if (point.county) return String(point.county).replace(/ County$/, "").trim();
    return "";
  }

  function shouldShowLabels(slide, view) {
    if (slide.labels === false) return false;
    if (slide.labels === true || slide.tight) return true;
    return view.w < 480;
  }

  function renderTownLabels(points, layers, view, slide) {
    if (!shouldShowLabels(slide, view)) return "";
    const scale = SVG_SIZE.w / Math.max(view.w, 180);
    const fontSize = Math.min(12, Math.max(7.5, 7.2 * Math.pow(scale, 0.28)));
    const placed = [];
    const offsets = [[11, -9], [11, 15], [-11, -9], [-52, 12], [0, -15], [0, 18], [14, 2], [-58, -4]];
    const rows = [];

    points.forEach(point => {
      if (!layers.has(point.layer || "projects")) return;
      if (slide.fit && !slide.fit(point)) return;
      const text = townName(point);
      if (!text || text.length > 22) return;
      const [x, y] = project(point.latitude, point.longitude);
      if (x < view.x + 8 || x > view.x + view.w - 8 || y < view.y + 8 || y > view.y + view.h - 8) return;

      let lx = x + 11;
      let ly = y - 9;
      for (const [dx, dy] of offsets) {
        const tx = x + dx;
        const ty = y + dy;
        const clash = placed.some(p => Math.hypot(p.x - tx, p.y - ty) < Math.max(34, text.length * 3.8));
        if (!clash) {
          lx = tx;
          ly = ty;
          break;
        }
      }
      placed.push({ x: lx, y: ly });
      const textAnchor = lx < x ? "end" : "start";
      rows.push(`<text x="${lx.toFixed(1)}" y="${ly.toFixed(1)}" text-anchor="${textAnchor}" fill="rgba(255,255,255,.78)" stroke="rgba(6,10,16,.72)" stroke-width="2.4" paint-order="stroke">${text}</text>`);
    });

    if (!rows.length) return "";
    return `<g class="home-map-labels" font-family="-apple-system,BlinkMacSystemFont,system-ui,sans-serif" font-size="${fontSize.toFixed(1)}" font-weight="600" letter-spacing=".05em">${rows.join("")}</g>`;
  }

  function markerSize(view) {
    const scale = SVG_SIZE.w / Math.max(view.w, 200);
    return Math.min(22, Math.max(11, Math.round(11 * Math.pow(scale, 0.38))));
  }

  function renderMarker(point, layers, focus, view) {
    if (!layers.has(point.layer || "projects")) return "";
    const [x, y] = project(point.latitude, point.longitude);
    const color = LAYER_COLORS[point.layer] || LAYER_COLORS.projects;
    const focused = focus
      && Math.abs(point.latitude - focus.lat) < 0.08
      && Math.abs(point.longitude - focus.lng) < 0.12;
    const base = markerSize(view);
    const size = focused ? base + 4 : base;
    const glow = focused ? base * 0.85 : base * 0.68;
    const inner = iconInner(point.layer, color, point.status);
    const cls = focused ? ' class="home-map-preview-pulse"' : "";
    const cx = (size / 2).toFixed(1);
    return `<g transform="translate(${(x - size / 2).toFixed(1)} ${(y - size / 2).toFixed(1)})"${cls}>
<circle cx="${cx}" cy="${cx}" r="${(glow * 1.55).toFixed(1)}" fill="${color}" opacity=".1"/>
<circle cx="${cx}" cy="${cx}" r="${glow}" fill="${color}" opacity=".32"/>
<circle cx="${cx}" cy="${cx}" r="${(glow * 0.42).toFixed(1)}" fill="#fff" opacity=".55"/>
<svg x="0" y="0" width="${size}" height="${size}" viewBox="0 0 24 24" aria-hidden="true">${inner}</svg>
</g>`;
  }

  function lineInView(coords, view) {
    const pad = 24;
    const left = view.x - pad;
    const right = view.x + view.w + pad;
    const top = view.y - pad;
    const bottom = view.y + view.h + pad;
    return coords.some(([x, y]) => x >= left && x <= right && y >= top && y <= bottom);
  }

  function renderLines(lines, view) {
    if (!lines?.length) return "";
    const scale = Math.max(1.1, Math.min(2.8, SVG_SIZE.w / Math.max(view.w, 220)));
    const stroke = (3.8 * scale).toFixed(1);
    const halo = (1.4 * scale).toFixed(1);
    return lines.map(line => {
      const projected = (line.coordinates || []).map(([lat, lng]) => project(lat, lng));
      if (!lineInView(projected, view)) return "";
      const coords = projected.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
      if (!coords) return "";
      return `<polyline points="${coords}" fill="none" stroke="${LAYER_COLORS.transmission}" stroke-width="${(parseFloat(stroke) * 1.35).toFixed(1)}" stroke-linecap="round" stroke-linejoin="round" opacity=".22"/>
<polyline points="${coords}" fill="none" stroke="${LAYER_COLORS.transmission}" stroke-width="${stroke}" stroke-linecap="round" stroke-linejoin="round" opacity=".92"/>
<polyline points="${coords}" fill="none" stroke="#e9d5ff" stroke-width="${halo}" stroke-linecap="round" stroke-linejoin="round" opacity=".45"/>`;
    }).join("");
  }

  function renderSlideSvg(slide, data) {
    const { view, id } = slide;
    const layers = new Set(slide.layers);
    const points = (data.map_points || []).filter(
      p => Number.isFinite(p.latitude) && Number.isFinite(p.longitude)
    );
    const pointMarkup = points.map(p => renderMarker(p, layers, slide.focus, view)).join("");
    const labelMarkup = renderTownLabels(points, layers, view, slide);
    const lineMarkup = slide.lines ? renderLines(data.transmission_lines, view) : "";
    const vb = `${view.x} ${view.y} ${view.w} ${view.h}`;
    const isTight = slide.tight || view.w < 500;
    const tint = slide.layers.includes("moratoria") && !slide.layers.includes("projects")
      ? `<rect x="${view.x}" y="${view.y}" width="${view.w}" height="${view.h}" fill="rgba(224,152,32,.06)"/>`
      : slide.layers.includes("moratoria") && slide.layers.includes("projects")
        ? `<rect x="${view.x}" y="${view.y}" width="${view.w}" height="${view.h}" fill="rgba(207,16,45,.03)"/>`
        : "";

    const showCounties = !isTight && (slide.wide || view.w >= 620);
    const countyLayer = showCounties
      ? `<g fill="${COUNTY_FILL}" stroke="${COUNTY_STROKE}" stroke-width="1" stroke-linejoin="round" opacity=".92">${countyMarkup}</g>`
      : "";
    const gridOpacity = isTight ? ".22" : ".55";
    const vignetteInner = isTight ? "rgba(125,211,252,.08)" : "rgba(125,211,252,.14)";
    const vignetteOuter = isTight ? "rgba(0,0,0,.28)" : "rgba(0,0,0,.42)";

    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${vb}" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
<defs>
<linearGradient id="bg-${id}" x1="0" y1="0" x2="0" y2="1">
<stop offset="0%" stop-color="${MAP_BG[0]}"/>
<stop offset="100%" stop-color="${MAP_BG[1]}"/>
</linearGradient>
<radialGradient id="vignette-${id}" cx="50%" cy="44%" r="68%">
<stop offset="0%" stop-color="${vignetteInner}"/>
<stop offset="55%" stop-color="rgba(0,0,0,0)"/>
<stop offset="100%" stop-color="${vignetteOuter}"/>
</radialGradient>
<pattern id="grid-${id}" width="28" height="28" patternUnits="userSpaceOnUse">
<path d="M28 0H0V28" fill="none" stroke="rgba(125,211,252,.07)" stroke-width=".6"/>
</pattern>
</defs>
<rect x="${view.x}" y="${view.y}" width="${view.w}" height="${view.h}" fill="url(#bg-${id})"/>
<rect x="${view.x}" y="${view.y}" width="${view.w}" height="${view.h}" fill="url(#grid-${id})" opacity="${gridOpacity}"/>
${showCounties ? `<path d="M0,0 L220,0 L180,720 L0,720 Z" fill="#0a1018" opacity=".55"/>
<path d="M1020,0 L1200,0 L1200,720 L980,720 Z" fill="#0a1018" opacity=".55"/>` : ""}
${countyLayer}
${tint}
<g>${lineMarkup}${pointMarkup}</g>
<rect x="${view.x}" y="${view.y}" width="${view.w}" height="${view.h}" fill="url(#vignette-${id})"/>
${labelMarkup}
</svg>`;
  }

  function layerSwatch(slide) {
    const layer = slide.swatchLayer || slide.layers[0] || "projects";
    const color = LAYER_COLORS[layer] || LAYER_COLORS.projects;
    const inner = iconInner(layer, color);
    return `<span class="home-map-preview-swatch home-map-preview-swatch--icon" style="color:${color}"><svg viewBox="0 0 24 24" aria-hidden="true">${inner}</svg></span>`;
  }

  function renderDockLayers(slide) {
    if (slide.layers.length > 3) {
      return `<span class="home-map-preview-layer home-map-preview-layer--stack"><i></i>${slide.layers.length} layers</span>`;
    }
    return slide.layers.map(id => {
      const meta = LAYER_META[id] || { short: id };
      const color = LAYER_COLORS[id] || LAYER_COLORS.projects;
      return `<span class="home-map-preview-layer" style="--layer:${color}"><i></i>${meta.short}</span>`;
    }).join("") + (slide.lines
      ? `<span class="home-map-preview-layer home-map-preview-layer--line"><i></i>Grid</span>`
      : "");
  }

  async function init(options = {}) {
    const root = document.getElementById(options.slidesId || "home-map-preview-slides");
    const link = document.getElementById(options.linkId || "home-map-preview-link");
    const chip = document.getElementById(options.chipId || "home-map-preview-chip");
    const filters = document.getElementById(options.filtersId || "home-map-preview-filters");
    const dotsRoot = document.getElementById(options.dotsId || "home-map-preview-dots");
    if (!root || !link) return;

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let mapData = options.mapData || null;

    try {
      await loadCountyMarkup();
      if (!mapData) {
        const version = options.mapVersion || "20260701w";
        mapData = await global.HomeStats.loadMapData(`map-data.json?v=${version}`);
      }
    } catch (err) {
      console.error("[home-map-preview]", err);
      root.innerHTML = `<img src="home-map-preview.svg?v=20260701p" width="1200" height="720" alt="" loading="lazy" decoding="async">`;
      return;
    }

    const slides = buildSlides(mapData);
    if (!slides.length) return;

    root.innerHTML = slides.map((slide, i) => {
      const drift = DRIFT_CLASSES[i % DRIFT_CLASSES.length];
      return `<div class="home-map-preview-slide home-map-preview-slide--drift-${drift}${i === 0 ? " is-active" : ""}" data-slide="${slide.id}" data-href="${slide.href}">
        ${renderSlideSvg(slide, mapData)}
      </div>`;
    }).join("");

    if (dotsRoot) {
      dotsRoot.innerHTML = slides.map((_, i) =>
        `<button type="button" class="home-map-preview-dot${i === 0 ? " is-active" : ""}" aria-label="Map view ${i + 1}"></button>`
      ).join("");
    }

    const slideEls = [...root.querySelectorAll(".home-map-preview-slide")];
    const dots = dotsRoot ? [...dotsRoot.querySelectorAll(".home-map-preview-dot")] : [];
    const canHover = window.matchMedia("(hover: hover) and (pointer: fine)");
    let index = 0;
    let timer = null;
    let paused = false;
    let tabVisible = !document.hidden;
    let inView = true;

    const applySlide = next => {
      index = ((next % slideEls.length) + slideEls.length) % slideEls.length;
      const slide = slides[index];
      slideEls.forEach((el, i) => el.classList.toggle("is-active", i === index));
      dots.forEach((el, i) => el.classList.toggle("is-active", i === index));
      link.href = slide.href;
      if (chip) chip.innerHTML = "";
      if (filters) filters.innerHTML = "";
      return index;
    };

    const stop = () => {
      if (timer) {
        clearTimeout(timer);
        timer = null;
      }
    };

    const canRotate = () => !paused && tabVisible && inView && !reducedMotion.matches && slideEls.length >= 2;

    const schedule = () => {
      stop();
      if (!canRotate()) return;
      timer = setTimeout(() => {
        applySlide(index + 1);
        schedule();
      }, 4200);
    };

    const start = () => {
      paused = false;
      schedule();
    };

    const pause = () => {
      paused = true;
      stop();
    };

    dots.forEach((dot, i) => {
      dot.addEventListener("click", event => {
        event.preventDefault();
        event.stopPropagation();
        applySlide(i);
        start();
      });
    });

    const onMouseEnter = () => pause();
    const onMouseLeave = () => start();
    const bindHover = () => {
      link.removeEventListener("mouseenter", onMouseEnter);
      link.removeEventListener("mouseleave", onMouseLeave);
      if (canHover.matches) {
        link.addEventListener("mouseenter", onMouseEnter);
        link.addEventListener("mouseleave", onMouseLeave);
      }
    };
    bindHover();
    canHover.addEventListener("change", bindHover);

    link.addEventListener("focusin", event => {
      if (event.target !== link) return;
      pause();
    });
    link.addEventListener("focusout", event => {
      if (event.target !== link) return;
      start();
    });

    document.addEventListener("visibilitychange", () => {
      tabVisible = !document.hidden;
      if (canRotate()) schedule();
      else stop();
    });

    window.addEventListener("pageshow", event => {
      if (event.persisted) schedule();
    });

    if ("IntersectionObserver" in window) {
      const observer = new IntersectionObserver(entries => {
        inView = Boolean(entries[0]?.isIntersecting);
        if (canRotate()) schedule();
        else stop();
      }, { threshold: 0.2 });
      observer.observe(link);
    }

    reducedMotion.addEventListener("change", () => {
      if (reducedMotion.matches) stop();
      else schedule();
    });

    applySlide(0);
    start();
  }

  global.HomeMapPreview = { init, SLIDE_DEFS, LAYER_META };
})(window);