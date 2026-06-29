(() => {
  const data = window.TRACKER_DATA || {};
  const $ = (selector, scope = document) => scope.querySelector(selector);
  const $$ = (selector, scope = document) => [...scope.querySelectorAll(selector)];
  const escapeHtml = (value = "") => String(value).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  }[c]));
  const safeUrl = value => {
    try {
      const url = new URL(String(value || ""), window.location.href);
      return ["http:", "https:"].includes(url.protocol) ? escapeHtml(url.href) : "#";
    } catch {
      return "#";
    }
  };
  const dateLabel = (value, relative = false) => {
    if (!value) return "";
    const d = new Date(value.includes("T") ? value : `${value}T12:00:00`);
    if (relative) {
      const diffMs = Date.now() - d.getTime();
      const diffMin = Math.floor(diffMs / 60000);
      const diffHr = Math.floor(diffMs / 3600000);
      const diffDay = Math.floor(diffMs / 86400000);
      if (diffMin < 60) return diffMin <= 1 ? "Just now" : `${diffMin} min ago`;
      if (diffHr < 24) return diffHr === 1 ? "1 hour ago" : `${diffHr} hours ago`;
      if (diffDay === 1) return "Yesterday";
      if (diffDay < 7) return `${diffDay} days ago`;
    }
    return new Intl.DateTimeFormat("en-US", { month: "long", day: "numeric" })
      .format(d);
  };
  const isNew = value => {
    if (!value) return false;
    const d = new Date(value.includes("T") ? value : `${value}T12:00:00`);
    return (Date.now() - d.getTime()) < 72 * 3600000; // within 3 days
  };
  const updatedLabel = value => {
    if (!value) return "Update time unavailable";
    return new Intl.DateTimeFormat("en-US", {
      month: "long", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit",
      timeZone: "America/Detroit", timeZoneName: "short"
    }).format(new Date(value));
  };
  const external = `<span class="external" aria-hidden="true">↗</span>`;
  const labelExternalLinks = () => {
    $$('a[target="_blank"]').forEach(link => {
      if (link.querySelector(".new-window-note")) return;
      const note = document.createElement("span");
      note.className = "sr-only new-window-note";
      note.textContent = " (opens in a new tab)";
      link.append(note);
    });
  };
  const emptyState = (title, body) => `
    <div class="empty-state">
      <span class="empty-mark"></span>
      <div><strong>${escapeHtml(title)}</strong><p>${escapeHtml(body)}</p></div>
    </div>`;

  const edition = window.HomeStats?.formatEditionDate?.() || null;
  if (edition) {
    const updatedAtEl = $("#updated-at");
    if (updatedAtEl) updatedAtEl.textContent = edition.short;
    const footerEl = $("#footer-updated");
    if (footerEl) {
      footerEl.textContent = edition.short;
      footerEl.setAttribute("datetime", edition.iso);
    }
  }

  $("#status-grid").innerHTML = (data.status || []).map(item => `
    <a class="status-card" href="${safeUrl(item.source_url)}" target="_blank" rel="noopener">
      <span>${escapeHtml(item.label)}</span>
      <strong>${escapeHtml(item.value)}</strong>
      <small>${escapeHtml(item.detail)}</small>
      <em>${escapeHtml(item.source_name)} ${external}</em>
    </a>`).join("");

  const latest = data.latest_developments || [];
  if ($("#latest-grid")) {
    $("#latest-grid").innerHTML = latest.length
      ? latest.map((item, index) => `
        <article class="story-card ${index === 0 ? "story-card-lead" : ""}">
          <a href="${safeUrl(item.source_url)}" target="_blank" rel="noopener">
            <div class="story-meta">
              <span>${escapeHtml(item.topic)}</span>
              <span>${escapeHtml(item.region)}</span>
            </div>
            <h3>${escapeHtml(item.headline)} ${external}</h3>
            ${index < 3 ? `<p>${escapeHtml(item.summary)}</p>` : ""}
            <footer><span>${escapeHtml(item.source_name)}</span><time datetime="${escapeHtml(item.published_date)}">${dateLabel(item.published_date)}</time></footer>
          </a>
        </article>`).join("")
      : emptyState("No verified headlines loaded", "The tracker will not publish placeholder headlines.");
  }

  const meetings = data.meetings || [];
  const meetingNote = `<p class="meeting-section-note">Agendas and livestreams are added as local governments publish them. Not all meetings have data center items on the agenda.</p>`;
  $("#meeting-list").innerHTML = meetings.length
    ? meetingNote + meetings.map(item => {
      const dt = new Date(item.start);
      const day = new Intl.DateTimeFormat("en-US", { weekday: "short", timeZone: "America/Detroit" }).format(dt);
      const date = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", timeZone: "America/Detroit" }).format(dt);
      const time = new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit", timeZone: "America/Detroit" }).format(dt);
      const hasLinks = item.agenda_url || item.watch_url;
      return `<article class="meeting-card">
        <div class="meeting-date"><strong>${day}</strong><span>${date}</span><em>${time}</em></div>
        <div class="meeting-copy"><span>${escapeHtml(item.county)}</span><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.location || "Location listed in source")}</p></div>
        <div class="meeting-actions">
          ${item.agenda_url ? `<a href="${safeUrl(item.agenda_url)}" target="_blank" rel="noopener">Agenda ${external}</a>` : ""}
          ${item.watch_url ? `<a class="watch" href="${safeUrl(item.watch_url)}" target="_blank" rel="noopener">Watch ${external}</a>` : ""}
          ${!hasLinks ? `<span class="agenda-pending">Agenda pending</span>` : ""}
        </div>
      </article>`;
    }).join("")
    : emptyState("No upcoming meeting is verified in the current feed", "When an agenda or official notice is available, it will appear here with a direct source link.");

  const platformClass = t => ({ social: "tag-social", official: "tag-official", news: "tag-news" }[t] || "tag-social");
  const renderPublicSources = posts => {
    if (!posts.length) {
      $("#public-grid").innerHTML = emptyState("No verified public posts loaded", "Exact post links will appear here when verified.");
      return;
    }
    $("#public-grid").innerHTML = `
      <p class="public-disclaimer">Summaries are written by the tracker based on public posts and statements. Not verbatim quotes.</p>
      ${posts.slice(0, 6).map(post => `<a class="public-card" href="${safeUrl(post.post_url)}" target="_blank" rel="noopener">
        ${isNew(post.posted_at) ? `<span class="new-badge">New</span>` : ""}
        <div class="public-source">
          <strong>${escapeHtml(post.account_name)}</strong>
          <span class="public-tag ${platformClass(post.platform_type)}">${escapeHtml(post.platform)}</span>
        </div>
        <p>${escapeHtml(post.text)}</p>
        <footer><time datetime="${escapeHtml(post.posted_at)}">${dateLabel(post.posted_at, true)}</time></footer>
      </a>`).join("")}`;
    labelExternalLinks();
  };
  renderPublicSources(data.public_sources || []);
  const pubUpdatedEl = document.getElementById("public-updated-time");
  if (pubUpdatedEl && edition) {
    pubUpdatedEl.textContent = edition.short;
    pubUpdatedEl.setAttribute("datetime", edition.iso);
  }

  const feedUrl = data.feeds?.public_monitor_url;
  if (feedUrl) {
    fetch(feedUrl, { headers: { Accept: "application/json" } })
      .then(response => {
        if (!response.ok) throw new Error(`Feed returned ${response.status}`);
        return response.json();
      })
      .then(payload => {
        const items = Array.isArray(payload) ? payload : payload.items;
        if (Array.isArray(items)) renderPublicSources(items.filter(item =>
          item && item.account_name && item.platform && item.text && item.post_url && item.context_note
        ));
      })
      .catch(() => {
        const notice = document.createElement("p");
        notice.className = "feed-notice";
        notice.textContent = "Live social feed is temporarily unavailable; showing the latest editorial snapshot.";
        $("#public-grid").before(notice);
      });
  }

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const regionNames = {
    statewide: "Your top stories",
    metro_detroit: "Metro Detroit / SE Michigan",
    west_michigan: "West Michigan",
    mid_michigan: "Mid-Michigan",
    northern_michigan: "Northern Michigan"
  };
  const regionTabLabels = {
    statewide: "Top stories",
    metro_detroit: "Metro Detroit",
    west_michigan: "West Michigan",
    mid_michigan: "Mid-Michigan",
    northern_michigan: "Northern Mich."
  };
  const slideBase = "assets/across-michigan-slides/";
  const regionVisuals = {
    statewide: {
      slides: [
        `${slideBase}pictured-rocks.jpg`,
        `${slideBase}mackinac-bridge.jpg`,
        `${slideBase}03-grand-ledge-water-town.jpg`,
        `${slideBase}grand-rapids.jpg`,
        `${slideBase}06-capitol-wide.jpg`,
        `${slideBase}05-jackson-downtown.jpg`,
        `${slideBase}detroit.jpg`,
        `${slideBase}04-lansing-skyline.jpg`,
        `${slideBase}07-capitol-dome.jpg`
      ],
      image: `${slideBase}pictured-rocks.jpg`,
      caption: "One state, many local decisions"
    },
    metro_detroit: {
      slides: [`${slideBase}detroit.jpg`, `${slideBase}06-capitol-wide.jpg`],
      image: `${slideBase}detroit.jpg`,
      caption: "Detroit, Ann Arbor and Southeast Michigan"
    },
    west_michigan: {
      slides: [`${slideBase}grand-rapids.jpg`, `${slideBase}03-grand-ledge-water-town.jpg`],
      image: `${slideBase}grand-rapids.jpg`,
      caption: "Grand Rapids, Holland, lakeshore, Kalamazoo and Battle Creek"
    },
    mid_michigan: {
      slides: [
        `${slideBase}04-lansing-skyline.jpg`,
        `${slideBase}07-capitol-dome.jpg`,
        `${slideBase}05-jackson-downtown.jpg`,
        `${slideBase}06-capitol-wide.jpg`
      ],
      image: `${slideBase}04-lansing-skyline.jpg`,
      caption: "Lansing, Jackson, Mount Pleasant and the Tri-Cities"
    },
    northern_michigan: {
      slides: [
        `${slideBase}mackinac-bridge.jpg`,
        `${slideBase}pictured-rocks.jpg`,
        `${slideBase}03-grand-ledge-water-town.jpg`
      ],
      image: `${slideBase}mackinac-bridge.jpg`,
      caption: "Cadillac, Houghton Lake, Traverse City, Mackinac City and the U.P."
    }
  };
  const regional = data.regional_watch || {};
  const tabs = Object.keys(regionNames);
  $("#region-tabs").innerHTML = tabs.map((key, i) => {
    const label = regionTabLabels[key];
    const full = regionNames[key];
    return `<button id="region-tab-${key}" type="button" role="tab" data-region="${key}" aria-controls="region-panel" aria-selected="${i === 0}" tabindex="${i === 0 ? "0" : "-1"}" title="${escapeHtml(full)}" aria-label="${escapeHtml(full)}">${escapeHtml(label)}</button>`;
  }).join("");

  let regionSlideshowTimer = null;
  const stopRegionSlideshow = () => {
    if (regionSlideshowTimer) {
      clearInterval(regionSlideshowTimer);
      regionSlideshowTimer = null;
    }
  };
  const setRegionSlide = (container, index) => {
    const slides = $$(".region-visual-slide", container);
    const dots = $$(".region-visual-dot", container);
    if (!slides.length) return;
    const next = ((index % slides.length) + slides.length) % slides.length;
    slides.forEach((slide, i) => slide.classList.toggle("is-active", i === next));
    dots.forEach((dot, i) => dot.classList.toggle("is-active", i === next));
    return next;
  };
  const startRegionSlideshow = container => {
    stopRegionSlideshow();
    if (!container || reducedMotion.matches) return;
    const slides = $$(".region-visual-slide", container);
    if (slides.length < 2) return;
    let index = setRegionSlide(container, 0);
    regionSlideshowTimer = setInterval(() => {
      index = setRegionSlide(container, index + 1);
    }, 4500);
  };
  const renderRegionCaption = (key, visual) => `<div class="region-visual-caption">
      <span class="region-visual-kicker">${escapeHtml(regionTabLabels[key] || "Michigan")}</span>
      <strong class="region-visual-title">${escapeHtml(visual.caption)}</strong>
    </div>`;
  const renderRegionVisual = (key, visual) => {
    const caption = renderRegionCaption(key, visual);
    if (visual.slides?.length) {
      const slideMarkup = visual.slides.map((src, i) =>
        `<img class="region-visual-slide${i === 0 ? " is-active" : ""}" src="${escapeHtml(src)}" alt="" loading="${i === 0 ? "eager" : "lazy"}" decoding="async" aria-hidden="true">`
      ).join("");
      const dots = visual.slides.length > 1
        ? `<div class="region-visual-dots" aria-hidden="true">${visual.slides.map((_, i) =>
            `<span class="region-visual-dot${i === 0 ? " is-active" : ""}"></span>`
          ).join("")}</div>`
        : "";
      return `<div class="region-visual region-visual--slideshow">
          <div class="region-visual-slides" aria-hidden="true">${slideMarkup}</div>
          <div class="region-visual-scrim" aria-hidden="true"></div>
          ${caption}
          ${dots}
        </div>`;
    }
    return `<div class="region-visual" style="--region-image:url('${escapeHtml(visual.image)}')">
        <div class="region-visual-scrim" aria-hidden="true"></div>
        ${caption}
      </div>`;
  };

  function renderRegion(key) {
    $$("#region-tabs button").forEach(btn => {
      const selected = btn.dataset.region === key;
      btn.setAttribute("aria-selected", selected ? "true" : "false");
      btn.setAttribute("tabindex", selected ? "0" : "-1");
    });
    $("#region-panel").setAttribute("aria-labelledby", `region-tab-${key}`);
    const indexes = regional[key] || [];
    const items = indexes.map(index => latest[index]).filter(Boolean);
    const visual = regionVisuals[key];
    stopRegionSlideshow();
    $("#region-panel").innerHTML = renderRegionVisual(key, visual) + (items.length
      ? items.map(item => `<a href="${safeUrl(item.source_url)}" target="_blank" rel="noopener">
          <span class="region-topic">${escapeHtml(item.region)}</span>
          <strong>${escapeHtml(item.headline)}</strong>
          <small>${escapeHtml(item.source_name)} · ${dateLabel(item.published_date)} ${external}</small>
        </a>`).join("")
      : emptyState(`No verified ${regionNames[key]} item loaded`, "This region remains visible so a future verified update drops into the same layout."));
    startRegionSlideshow($(".region-visual--slideshow", $("#region-panel")));
  }
  $("#region-tabs").addEventListener("click", event => {
    const button = event.target.closest("button[data-region]");
    if (button) renderRegion(button.dataset.region);
  });
  $("#region-tabs").addEventListener("keydown", event => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    const buttons = $$("#region-tabs button");
    const current = buttons.indexOf(document.activeElement);
    if (current < 0) return;
    event.preventDefault();
    const next = event.key === "Home" ? 0
      : event.key === "End" ? buttons.length - 1
      : (current + (event.key === "ArrowRight" ? 1 : -1) + buttons.length) % buttons.length;
    buttons[next].focus();
    renderRegion(buttons[next].dataset.region);
  });
  renderRegion("statewide");

  const mapPoints = data.map_points || [];
  const counts = mapPoints.reduce((acc, point) => {
    acc[point.status] = (acc[point.status] || 0) + 1;
    return acc;
  }, {});
  $("#map-promo-stats").innerHTML = `
    <div><strong>${mapPoints.length}</strong><span>Verified map records loaded</span></div>
    <div><strong>${counts.Moratorium || 0}</strong><span>Moratoria in current map feed</span></div>
    <div><strong>${mapPoints.filter(p => p.confidence === "Confirmed").length}</strong><span>Confirmed by official or direct source</span></div>`;

  const drawer = $("#site-drawer");
  const shade = $(".drawer-shade");
  const menu = $(".menu-button");
  let lastFocused = null;
  const setDrawer = open => {
    if (open) lastFocused = document.activeElement;
    drawer.classList.toggle("open", open);
    shade.classList.toggle("open", open);
    drawer.setAttribute("aria-hidden", String(!open));
    menu.setAttribute("aria-expanded", String(open));
    document.body.classList.toggle("drawer-open", open);
    if (open) $(".drawer-close").focus();
    else if (lastFocused instanceof HTMLElement) lastFocused.focus();
  };
  $$("[data-drawer-open]").forEach(el => el.addEventListener("click", () => setDrawer(true)));
  $$("[data-drawer-close]").forEach(el => el.addEventListener("click", () => setDrawer(false)));
  $$(".drawer a").forEach(el => el.addEventListener("click", () => setDrawer(false)));
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && drawer.classList.contains("open")) setDrawer(false);
    if (event.key !== "Tab" || !drawer.classList.contains("open")) return;
    const focusable = $$('a[href], button:not([disabled])', drawer).filter(el => el.offsetParent !== null);
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });

  const video = $(".masthead-video");
  if (video && window.matchMedia("(prefers-reduced-motion: reduce)").matches) video.pause();

  const briefingForm = $("#briefing-form");
  if (briefingForm) {
    const action = data.newsletter?.form_action || "";
    const message = $("#briefing-message");
    if (action) briefingForm.action = action;
    briefingForm.addEventListener("submit", event => {
      const email = $("#briefing-email");
      if (!email.checkValidity()) {
        event.preventDefault();
        message.textContent = "Please enter a valid email address.";
        email.focus();
        return;
      }
      if (!action) {
        event.preventDefault();
        message.textContent = "Mailchimp connection is being finalized. Your address was not submitted yet.";
        return;
      }
      message.textContent = "Opening the secure signup confirmation…";
    });
  }

  labelExternalLinks();
})();
