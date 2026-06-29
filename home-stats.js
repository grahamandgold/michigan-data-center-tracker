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
      generation: byLayer("generation")
    };
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
      compact: fmt({ month: "short", day: "numeric", year: "numeric" })
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
    set("utility-weekday", edition.weekday);
    set("utility-timestamp", edition.short, edition.iso);
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
    formatUpdated,
    formatEditionDate,
    applyEditionDate,
    ribbonStats,
    loadMapData
  };
})(window);