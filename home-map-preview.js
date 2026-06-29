/**
 * Homepage live-map thumbnail — rotates through zoomed views and layer filters.
 */
(function (global) {
  const SVG_SIZE = { w: 1200, h: 720 };
  const GEO = { north: 45.48, south: 41.7, west: -87.02, east: -82.38 };
  const PAD = { left: 92, right: 88, top: 36, bottom: 44 };
  const LAYER_COLORS = {
    projects: "#cf102d",
    moratoria: "#e09820",
    meetings: "#5b9cf5",
    transmission: "#9c5fc9",
    policy: "#22a86a",
    generation: "#64748b"
  };

  const SLIDES = [
    {
      id: "statewide",
      label: "Statewide view",
      kicker: "Every verified pin",
      layers: ["projects", "moratoria", "meetings"],
      view: { x: 0, y: 0, w: 1200, h: 720 },
      bg: ["#dfe8f2", "#c8d6e6"],
      href: "map.html"
    },
    {
      id: "metro",
      label: "Metro Detroit",
      kicker: "Projects & proposals",
      layers: ["projects"],
      view: { x: 560, y: 420, w: 520, h: 300 },
      bg: ["#e8edf4", "#cfd9e8"],
      href: "map.html?lat=42.35&lng=-83.55&zoom=9&layers=projects"
    },
    {
      id: "moratoria",
      label: "Moratoria wave",
      kicker: "Local pauses mapped",
      layers: ["moratoria"],
      view: { x: 0, y: 0, w: 1200, h: 720 },
      bg: ["#f2ebe0", "#e6d4b8"],
      href: "map.html?layers=moratoria"
    },
    {
      id: "saline",
      label: "Saline Township",
      kicker: "Hyperscale campus",
      layers: ["projects"],
      focus: { lat: 42.166, lng: -83.782 },
      view: { x: 720, y: 500, w: 360, h: 210 },
      bg: ["#e4eaf2", "#c5d4e8"],
      href: "map.html?lat=42.166&lng=-83.782&zoom=11&layers=projects"
    },
    {
      id: "grid",
      label: "Power & grid",
      kicker: "Transmission corridors",
      layers: ["transmission"],
      lines: true,
      view: { x: 320, y: 120, w: 640, h: 460 },
      bg: ["#ebe6f2", "#d4c8e6"],
      href: "map.html?layers=transmission"
    },
    {
      id: "west",
      label: "West Michigan",
      kicker: "Community response",
      layers: ["projects", "moratoria"],
      view: { x: 40, y: 220, w: 500, h: 420 },
      bg: ["#e0eaf2", "#c2d4e4"],
      href: "map.html?lat=42.95&lng=-85.75&zoom=8"
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

  function renderPoint(point, layers, focus) {
    if (!layers.has(point.layer || "projects")) return "";
    const [x, y] = project(point.latitude, point.longitude);
    const color = LAYER_COLORS[point.layer] || LAYER_COLORS.projects;
    const focused = focus
      && Math.abs(point.latitude - focus.lat) < 0.08
      && Math.abs(point.longitude - focus.lng) < 0.12;
    const r = focused ? 10.5 : 6.8;
    const glow = focused ? 14 : 9.8;
    const xf = x.toFixed(1);
    const yf = y.toFixed(1);
    if (focused) {
      return `<g class="home-map-preview-pulse" transform="translate(${xf} ${yf})">
<circle r="${glow}" fill="${color}" opacity=".22"/>
<circle r="${r}" fill="${color}" stroke="#fff" stroke-width="1.6"/>
</g>`;
    }
    return `<circle cx="${xf}" cy="${yf}" r="${glow}" fill="${color}" opacity=".2"/>
<circle cx="${xf}" cy="${yf}" r="${r}" fill="${color}" stroke="#fff" stroke-width="1.6"/>`;
  }

  function renderLines(lines, slideId) {
    if (!lines?.length) return "";
    return lines.map((line, i) => {
      const coords = (line.coordinates || [])
        .map(([lat, lng]) => project(lat, lng))
        .map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`)
        .join(" ");
      if (!coords) return "";
      return `<polyline points="${coords}" fill="none" stroke="#9c5fc9" stroke-width="${slideId === "grid" ? 3.2 : 2.4}" stroke-linecap="round" stroke-linejoin="round" opacity=".88"/>`;
    }).join("");
  }

  function renderSlideSvg(slide, data) {
    const { view, bg, id } = slide;
    const layers = new Set(slide.layers);
    const points = (data.map_points || []).filter(
      p => Number.isFinite(p.latitude) && Number.isFinite(p.longitude)
    );
    const pointMarkup = points.map(p => renderPoint(p, layers, slide.focus)).join("");
    const lineMarkup = slide.lines ? renderLines(data.transmission_lines, id) : "";
    const vb = `${view.x} ${view.y} ${view.w} ${view.h}`;

    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${vb}" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
<defs>
<linearGradient id="bg-${id}" x1="0" y1="0" x2="0" y2="1">
<stop offset="0%" stop-color="${bg[0]}"/>
<stop offset="100%" stop-color="${bg[1]}"/>
</linearGradient>
</defs>
<rect x="${view.x}" y="${view.y}" width="${view.w}" height="${view.h}" fill="url(#bg-${id})"/>
<path d="M0,0 L220,0 L180,720 L0,720 Z" fill="#b8cfe0" opacity=".45"/>
<path d="M1020,0 L1200,0 L1200,720 L980,720 Z" fill="#b8cfe0" opacity=".45"/>
<g fill="#e8eef4" stroke="#8fa3b8" stroke-width="1.1" stroke-linejoin="round">${countyMarkup}</g>
<g>${lineMarkup}${pointMarkup}</g>
</svg>`;
  }

  function layerSwatch(slide) {
    const layer = slide.layers[0] || "projects";
    const color = LAYER_COLORS[layer] || LAYER_COLORS.projects;
    return `<span class="home-map-preview-swatch" style="background:${color}"></span>`;
  }

  async function init(options = {}) {
    const root = document.getElementById(options.slidesId || "home-map-preview-slides");
    const link = document.getElementById(options.linkId || "home-map-preview-link");
    const chip = document.getElementById(options.chipId || "home-map-preview-chip");
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

    root.innerHTML = SLIDES.map((slide, i) => `
      <div class="home-map-preview-slide${i === 0 ? " is-active" : ""}" data-slide="${slide.id}" data-href="${slide.href}">
        ${renderSlideSvg(slide, mapData)}
      </div>`).join("");

    if (dotsRoot) {
      dotsRoot.innerHTML = SLIDES.map((_, i) =>
        `<button type="button" class="home-map-preview-dot${i === 0 ? " is-active" : ""}" aria-label="Map view ${i + 1}"></button>`
      ).join("");
    }

    const slides = [...root.querySelectorAll(".home-map-preview-slide")];
    const dots = dotsRoot ? [...dotsRoot.querySelectorAll(".home-map-preview-dot")] : [];
    let index = 0;
    let timer = null;

    const applySlide = next => {
      index = ((next % slides.length) + slides.length) % slides.length;
      const slide = SLIDES[index];
      slides.forEach((el, i) => el.classList.toggle("is-active", i === index));
      dots.forEach((el, i) => el.classList.toggle("is-active", i === index));
      link.href = slide.href;
      if (chip) {
        chip.innerHTML = `${layerSwatch(slide)}<span class="home-map-preview-chip-text"><strong>${slide.label}</strong><span>${slide.kicker}</span></span>`;
      }
      return index;
    };

    const stop = () => {
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
    };

    const start = () => {
      stop();
      if (reducedMotion.matches || slides.length < 2) return;
      timer = setInterval(() => applySlide(index + 1), 3800);
    };

    dots.forEach((dot, i) => {
      dot.addEventListener("click", event => {
        event.preventDefault();
        event.stopPropagation();
        applySlide(i);
        start();
      });
    });

    link.addEventListener("mouseenter", stop);
    link.addEventListener("mouseleave", start);
    link.addEventListener("focusin", stop);
    link.addEventListener("focusout", start);

    reducedMotion.addEventListener("change", () => {
      if (reducedMotion.matches) stop();
      else start();
    });

    applySlide(0);
    start();
  }

  global.HomeMapPreview = { init, SLIDES };
})(window);