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
  const dateLabel = value => {
    if (!value) return "";
    return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" })
      .format(new Date(`${value}T12:00:00`));
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

  const updated = updatedLabel(data.updated_at);
  $("#updated-at").textContent = `Updated ${updated}`;
  $("#footer-updated").textContent = `Last editorial update: ${updated}`;

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
        <div class="public-source">
          <strong>${escapeHtml(post.account_name)}</strong>
          <span class="public-tag ${platformClass(post.platform_type)}">${escapeHtml(post.platform)}</span>
        </div>
        <p>${escapeHtml(post.text)}</p>
        <footer><time>${escapeHtml(post.posted_at)}</time>${external}</footer>
      </a>`).join("")}`;
    labelExternalLinks();
  };
  renderPublicSources(data.public_sources || []);

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

  const regionNames = {
    statewide: "Your top stories",
    metro_detroit: "Metro Detroit / SE Michigan",
    west_michigan: "West Michigan",
    mid_michigan: "Mid-Michigan",
    northern_michigan: "Northern Michigan"
  };
  const regionVisuals = {
    statewide: { image: "pictured-rocks.jpg", label: "Your top stories", caption: "One state, many local decisions" },
    metro_detroit: { image: "detroit.jpg", label: "Metro Detroit / SE Michigan", caption: "Detroit, Ann Arbor and Southeast Michigan" },
    west_michigan: { image: "grand-rapids.jpg", label: "West Michigan", caption: "Grand Rapids, Holland, lakeshore, Kalamazoo and Battle Creek" },
    mid_michigan: { image: "michigan night view.jpg", label: "Mid-Michigan", caption: "Lansing, Jackson, Mount Pleasant and the Tri-Cities" },
    northern_michigan: { image: "mackinac-bridge.jpg", label: "Northern Michigan", caption: "Cadillac, Houghton Lake, Traverse City, Mackinac City and the U.P." }
  };
  const regional = data.regional_watch || {};
  const tabs = Object.keys(regionNames);
  $("#region-tabs").innerHTML = tabs.map((key, i) => `<button id="region-tab-${key}" type="button" role="tab" data-region="${key}" aria-controls="region-panel" aria-selected="${i === 0}" tabindex="${i === 0 ? "0" : "-1"}">${regionNames[key]}</button>`).join("");

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
    const visualCard = key === "statewide"
      ? `<div class="region-visual region-visual-video">
          <video autoplay muted loop playsinline preload="auto" aria-hidden="true">
            <source src="across-michigan-hero-web.mp4" type="video/mp4">
          </video>
          <strong>${escapeHtml(visual.caption)}</strong>
        </div>`
      : `<div class="region-visual" style="--region-image:url('${escapeHtml(visual.image)}')">
          <strong>${escapeHtml(visual.caption)}</strong>
        </div>`;
    $("#region-panel").innerHTML = visualCard + (items.length
      ? items.map(item => `<a href="${safeUrl(item.source_url)}" target="_blank" rel="noopener">
          <span class="region-topic">${escapeHtml(item.region)}</span>
          <strong>${escapeHtml(item.headline)}</strong>
          <small>${escapeHtml(item.source_name)} · ${dateLabel(item.published_date)} ${external}</small>
        </a>`).join("")
      : emptyState(`No verified ${regionNames[key]} item loaded`, "This region remains visible so a future verified update drops into the same layout."));
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
