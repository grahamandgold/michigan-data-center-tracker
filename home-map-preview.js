/**
 * Homepage map preview — clean statewide thumbnail, minimal motion.
 */
(function (global) {
  const SVG_SIZE = { w: 1200, h: 720 };
  const GEO = { north: 45.48, south: 41.7, west: -87.02, east: -82.38 };
  const PAD = { left: 92, right: 88, top: 36, bottom: 44 };
  const MAP_BG = ["#dfe8f2", "#c8d6e6"];
  const COUNTY_FILL = "#e8eef4";
  const COUNTY_STROKE = "#8fa3b8";
  const LAYER_COLORS = {
    projects: "#cf102d",
    moratoria: "#c97d10",
    meetings: "#3b6fb6",
    transmission: "#7c4f9e",
    policy: "#1f8a55",
    generation: "#0f9a8d"
  };

  const SLIDE_DEFS = [
    {
      id: "state-overview",
      layers: ["projects", "moratoria", "meetings"],
      zoom: "state",
      href: "map.html?layers=projects,moratoria,meetings"
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

  function stateView() {
    return { x: 36, y: 18, w: SVG_SIZE.w - 72, h: SVG_SIZE.h - 42 };
  }

  function buildSlides(data) {
    const points = (data.map_points || []).filter(
      p => Number.isFinite(p.latitude) && Number.isFinite(p.longitude)
    );
    if (!points.length) return [];

    return SLIDE_DEFS.map(def => ({
      ...def,
      view: stateView()
    }));
  }

  function renderDot(point, layers, index = 0) {
    if (!layers.has(point.layer || "projects")) return "";
    const [x, y] = project(point.latitude, point.longitude);
    const color = LAYER_COLORS[point.layer] || LAYER_COLORS.projects;
    const r = point.layer === "moratoria" ? 5 : 4;
    const delay = ((index * 0.38) % 2.4).toFixed(2);
    return `<circle class="home-map-preview-pulse" style="animation-delay:${delay}s" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${r}" fill="${color}" stroke="#fff" stroke-width="1.4" opacity=".92"/>`;
  }

  function renderSlideSvg(slide, data) {
    const { view, id } = slide;
    const layers = new Set(slide.layers);
    const points = (data.map_points || []).filter(
      p => Number.isFinite(p.latitude) && Number.isFinite(p.longitude)
    );
    const pointMarkup = points.map((p, i) => renderDot(p, layers, i)).join("");
    const vb = `${view.x} ${view.y} ${view.w} ${view.h}`;
    const countyLayer = countyMarkup
      ? `<g fill="${COUNTY_FILL}" stroke="${COUNTY_STROKE}" stroke-width="1" stroke-linejoin="round">${countyMarkup}</g>`
      : "";

    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${vb}" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
<defs>
<linearGradient id="bg-${id}" x1="0" y1="0" x2="0" y2="1">
<stop offset="0%" stop-color="${MAP_BG[0]}"/>
<stop offset="100%" stop-color="${MAP_BG[1]}"/>
</linearGradient>
</defs>
<rect x="${view.x}" y="${view.y}" width="${view.w}" height="${view.h}" fill="url(#bg-${id})"/>
${countyLayer}
<g>${pointMarkup}</g>
</svg>`;
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

    root.innerHTML = slides.map((slide, i) =>
      `<div class="home-map-preview-slide${i === 0 ? " is-active" : ""}" data-slide="${slide.id}" data-href="${slide.href}">
        ${renderSlideSvg(slide, mapData)}
      </div>`
    ).join("");

    if (dotsRoot) {
      if (slides.length < 2) {
        dotsRoot.innerHTML = "";
        dotsRoot.hidden = true;
      } else {
        dotsRoot.hidden = false;
        dotsRoot.innerHTML = slides.map((_, i) =>
          `<button type="button" class="home-map-preview-dot${i === 0 ? " is-active" : ""}" aria-label="Map view ${i + 1}"></button>`
        ).join("");
      }
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
      }, 7000);
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

    document.addEventListener("visibilitychange", () => {
      tabVisible = !document.hidden;
      if (canRotate()) schedule();
      else stop();
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

  global.HomeMapPreview = { init, SLIDE_DEFS };
})(window);