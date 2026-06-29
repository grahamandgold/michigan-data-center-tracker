/**
 * Homepage stats — reads the same map-data.json as map.js.
 * Keep stat logic here so index.html and future pages stay in sync with the map.
 */
(function (global) {
  const DEFAULT_FOCUS = ["projects", "moratoria"];

  function getDefaultLayers(mapLayers) {
    const fromMeta = (mapLayers || []).filter(l => l.default_on !== false).map(l => l.id);
    return fromMeta.length ? fromMeta : DEFAULT_FOCUS.slice();
  }

  function computeStats(data) {
    const points = (data.map_points || []).filter(
      p => Number.isFinite(p.latitude) && Number.isFinite(p.longitude)
    );
    const focus = new Set(getDefaultLayers(data.map_layers));
    const focused = points.filter(p => focus.has(p.layer || "projects"));

    const byLayer = layer => points.filter(p => p.layer === layer).length;
    const focusedByLayer = layer => focused.filter(p => p.layer === layer).length;
    const projects = points.filter(p => p.layer === "projects");
    const countyCount = layer => new Set(
      points.filter(p => p.layer === layer && p.county).map(p => p.county)
    ).size;

    return {
      total: focused.length,
      projects: focusedByLayer("projects"),
      moratoria: focusedByLayer("moratoria"),
      all_records: points.length,
      all_projects: byLayer("projects"),
      all_moratoria: byLayer("moratoria"),
      meetings: byLayer("meetings"),
      transmission: byLayer("transmission"),
      policy: byLayer("policy"),
      generation: byLayer("generation"),
      proposed: projects.filter(p => p.status === "Proposed").length,
      under_construction: projects.filter(p => p.status === "Under construction").length,
      approved: projects.filter(p => /approved/i.test(p.status || "")).length,
      project_counties: countyCount("projects"),
      moratoria_counties: countyCount("moratoria"),
      transmission_lines: (data.transmission_lines || []).length
    };
  }

  function statItemValid(item) {
    if (!item || !item.label) return false;
    const value = item.value;
    if (value === undefined || value === null || value === "") return false;
    if (typeof value === "number" && value <= 0) return false;
    return true;
  }

  function dedupeStatItems(items) {
    const seen = new Set();
    return items.filter(item => {
      if (!statItemValid(item)) return false;
      const key = `${item.value}|${item.label}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  function isNumericStatValue(value) {
    return /^[\d,]+$/.test(String(value).replace(/\+/g, ""));
  }

  const COMPACT_FOLD_MQ = "(max-width: 900px)";

  function isCompactFold(root = document) {
    return root.defaultView?.matchMedia(COMPACT_FOLD_MQ).matches ?? false;
  }

  /** Three fixed numbers on small screens — no rotation, short labels. */
  function buildMobileUtilityStats(counts) {
    return [
      [{ value: counts.all_records, label: "Records" }],
      [{ value: counts.projects, label: "Sites" }],
      [{ value: counts.moratoria, label: "Pauses" }]
    ];
  }

  function buildUtilityRotations(counts, industryStats = []) {
    const industryByColumn = [[], [], []];
    industryStats.forEach(stat => {
      const col = Math.min(2, Math.max(0, Number(stat.column) || 0));
      industryByColumn[col].push({
        value: stat.value,
        label: stat.label,
        source: stat.source || "",
        source_url: stat.source_url || ""
      });
    });

    return [
      dedupeStatItems([
        { value: counts.total, label: "On map now" },
        { value: counts.all_records, label: "Sourced records" },
        { value: counts.generation, label: "Generation nodes" },
        { value: counts.meetings, label: "Public hearings" },
        { value: counts.transmission, label: "Grid proposals" },
        { value: counts.policy, label: "Policy signals" },
        ...industryByColumn[0]
      ]),
      dedupeStatItems([
        { value: counts.projects, label: "Data center sites" },
        { value: counts.proposed, label: "Proposed" },
        { value: counts.under_construction, label: "Under construction" },
        { value: counts.approved, label: "Approved" },
        { value: counts.project_counties, label: "Counties tracked" },
        ...industryByColumn[1]
      ]),
      dedupeStatItems([
        { value: counts.moratoria, label: "Moratoria" },
        { value: counts.moratoria_counties, label: "Communities paused" },
        { value: counts.transmission_lines, label: "Grid corridors" },
        { value: counts.policy, label: "Capitol watch" },
        ...industryByColumn[2]
      ])
    ].filter(column => column.length > 0);
  }

  function scrambleDigits(len) {
    return Array.from({ length: Math.max(len, 1) }, () => Math.floor(Math.random() * 10)).join("");
  }

  function clearStatTimers(el) {
    if (!el) return;
    if (el._utilityFlicker) {
      window.clearInterval(el._utilityFlicker);
      el._utilityFlicker = null;
    }
    if (el._utilitySwap) {
      window.clearTimeout(el._utilitySwap);
      el._utilitySwap = null;
    }
    if (el._utilityLand) {
      window.clearTimeout(el._utilityLand);
      el._utilityLand = null;
    }
  }

  function startUtilityStatRotator(columns, options = {}) {
    const interval = options.interval || 3400;
    const stagger = options.stagger || 420;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const timers = [];

    const apply = (column, item) => {
      if (!column || !item) return;
      const el = column.el || column;
      const num = el.querySelector(".utility-stat-num");
      const label = el.querySelector(".utility-stat-label");
      if (!num || !label) return;

      const nextValue = String(item.value);
      const nextLabel = item.label;
      if (num.textContent === nextValue && label.textContent === nextLabel) return;

      clearStatTimers(el);
      el.classList.remove("utility-stat--land", "utility-stat--flip", "utility-stat--zap");

      if (reducedMotion.matches) {
        num.textContent = nextValue;
        label.textContent = nextLabel;
        return;
      }

      el.classList.add("utility-stat--zap");
      num.classList.toggle("utility-stat-num--compact", nextValue.length > 4);
      if (item.source) {
        const title = item.source_url
          ? `${nextLabel} — Source: ${item.source}`
          : `${nextLabel} — ${item.source}`;
        el.setAttribute("title", title);
      } else {
        el.removeAttribute("title");
      }
      if (isNumericStatValue(nextValue)) {
        const len = nextValue.replace(/,/g, "").length;
        let flickers = 0;
        el._utilityFlicker = window.setInterval(() => {
          num.textContent = scrambleDigits(len);
          flickers += 1;
          if (flickers >= 6) {
            window.clearInterval(el._utilityFlicker);
            el._utilityFlicker = null;
          }
        }, 30);
      }

      el._utilitySwap = window.setTimeout(() => {
        if (el._utilityFlicker) {
          window.clearInterval(el._utilityFlicker);
          el._utilityFlicker = null;
        }
        num.textContent = nextValue;
        label.textContent = nextLabel;
        el.classList.remove("utility-stat--zap");
        el.classList.add("utility-stat--land");
        el._utilityLand = window.setTimeout(() => {
          el.classList.remove("utility-stat--land");
          el._utilityLand = null;
        }, 360);
        el._utilitySwap = null;
      }, 220);
    };

    const stop = () => {
      timers.forEach(id => {
        window.clearInterval(id);
        window.clearTimeout(id);
      });
      timers.length = 0;
      columns.forEach(column => clearStatTimers(column.el));
    };

    columns.forEach((column, columnIndex) => {
      const rotation = column.rotation || [];
      if (rotation.length < 2) {
        if (rotation[0]) apply(column, rotation[0]);
        return;
      }

      let index = 0;
      apply(column, rotation[0]);

      if (reducedMotion.matches) return;

      const tick = () => {
        index = (index + 1) % rotation.length;
        apply(column, rotation[index]);
      };
      const startDelay = columnIndex * stagger;
      const starter = window.setTimeout(() => {
        timers.push(window.setInterval(tick, interval));
      }, startDelay);
      timers.push(starter);
    });

    reducedMotion.addEventListener("change", () => {
      stop();
      if (!reducedMotion.matches) startUtilityStatRotator(columns, options);
    });

    return { stop };
  }

  function mountContextFacts(facts, root = document, options = {}) {
    const strip = root.getElementById("context-strip");
    const factEl = root.getElementById("context-strip-fact");
    if (!strip || !factEl) return null;
    if (!facts.length || (options.mobile !== false && isCompactFold(root))) {
      strip.hidden = true;
      return null;
    }
    strip.hidden = false;

    const interval = options.interval || 8500;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let index = 0;
    let timer = null;

    const esc = (value = "") => String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");

    const render = fact => {
      const cite = fact.source
        ? fact.source_url
          ? `<cite><a href="${esc(fact.source_url)}" target="_blank" rel="noopener">${esc(fact.source)}</a></cite>`
          : `<cite>${esc(fact.source)}</cite>`
        : "";
      factEl.innerHTML = `${esc(fact.text)} ${cite}`.trim();
    };

    const stop = () => {
      if (timer) {
        window.clearInterval(timer);
        timer = null;
      }
    };

    const start = () => {
      stop();
      if (reducedMotion.matches || facts.length < 2) return;
      timer = window.setInterval(() => {
        index = (index + 1) % facts.length;
        factEl.classList.remove("is-visible");
        window.setTimeout(() => {
          render(facts[index]);
          factEl.classList.add("is-visible");
        }, 280);
      }, interval);
    };

    render(facts[0]);
    factEl.classList.add("is-visible");
    start();
    reducedMotion.addEventListener("change", start);
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) stop();
      else start();
    });

    return { stop };
  }

  function mountUtilityStats(counts, options = {}, root = document) {
    const industryStats = options.industryStats || [];
    const rotations = isCompactFold(root)
      ? buildMobileUtilityStats(counts)
      : buildUtilityRotations(counts, industryStats);
    const slots = [
      root.getElementById("utility-stat-0"),
      root.getElementById("utility-stat-1"),
      root.getElementById("utility-stat-2")
    ];

    const columns = slots
      .map((el, i) => (el && rotations[i] ? { el, rotation: rotations[i] } : null))
      .filter(Boolean);

    const rotator = startUtilityStatRotator(columns);
    const compact = isCompactFold(root);
    rotator._compact = compact;
    return rotator;
  }

  let foldControllers = { utility: null, context: null };

  function mountHomeFold(mapData, root = document) {
    foldControllers.utility?.stop();
    foldControllers.context?.stop();
    const counts = computeStats(mapData);
    foldControllers.utility = mountUtilityStats(counts, { industryStats: mapData.industry_stats || [] }, root);
    foldControllers.context = mountContextFacts(mapData.context_facts || [], root);
    return foldControllers;
  }

  function watchHomeFold(mapData, root = document) {
    mountHomeFold(mapData, root);
    const mq = root.defaultView?.matchMedia(COMPACT_FOLD_MQ);
    if (!mq) return foldControllers;
    const onChange = () => mountHomeFold(mapData, root);
    mq.addEventListener("change", onChange);
    return foldControllers;
  }

  function formatUpdated(iso) {
    if (!iso) return null;
    try {
      return new Intl.DateTimeFormat("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        timeZone: "America/Detroit"
      }).format(new Date(iso));
    } catch {
      return null;
    }
  }

  /** Magazine-style edition date — defaults to today in Michigan time. */
  function formatEditionDate(iso) {
    const d = iso
      ? new Date(iso.includes("T") ? iso : `${iso}T12:00:00`)
      : new Date();
    const detroit = { timeZone: "America/Detroit" };
    const fmt = opts => new Intl.DateTimeFormat("en-US", { ...opts, ...detroit }).format(d);
    return {
      iso: new Intl.DateTimeFormat("en-CA", { year: "numeric", month: "2-digit", day: "2-digit", ...detroit }).format(d),
      weekday: fmt({ weekday: "long" }),
      short: fmt({ month: "long", day: "numeric", year: "numeric" }),
      compact: fmt({ month: "short", day: "numeric", year: "numeric" }),
      stripLine: fmt({ weekday: "short", month: "short", day: "numeric", year: "numeric" })
    };
  }

  function applyEditionDate(root = document) {
    const edition = formatEditionDate();
    const set = (id, text, attr) => {
      const el = root.getElementById(id);
      if (!el) return;
      el.textContent = text;
      if (attr) el.setAttribute("datetime", attr);
    };
    set("utility-timestamp", edition.stripLine, edition.iso);
    set("footer-updated", edition.short, edition.iso);
    set("public-updated-time", edition.short, edition.iso);
    return edition;
  }

  function ribbonStats(data, counts) {
    const defs = data.stats_ribbon || [];
    return defs.map((d, i) => ({
      label: d.label,
      value: counts[d.value_key] ?? 0,
      suffix: d.suffix || "",
      accent: i === 0
    }));
  }

  async function loadMapData(url) {
    const res = await fetch(url || "map-data.json", { cache: "no-store" });
    if (!res.ok) throw new Error(`map-data.json HTTP ${res.status}`);
    const json = await res.json();
    if (!json.map_points?.length) throw new Error("map-data.json has no map_points");
    return json;
  }

  global.HomeStats = {
    DEFAULT_FOCUS,
    getDefaultLayers,
    computeStats,
    buildUtilityRotations,
    buildMobileUtilityStats,
    isCompactFold,
    mountHomeFold,
    watchHomeFold,
    mountContextFacts,
    mountUtilityStats,
    startUtilityStatRotator,
    formatUpdated,
    formatEditionDate,
    applyEditionDate,
    ribbonStats,
    loadMapData
  };
})(window);