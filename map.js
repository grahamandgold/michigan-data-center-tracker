(() => {
  const data = window.TRACKER_DATA || {};
  const points = (data.map_points || []).filter(point => Number.isFinite(point.latitude) && Number.isFinite(point.longitude));
  const esc = value => String(value || "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[c]));
  const safeUrl = value => {
    try {
      const url = new URL(String(value || ""), window.location.href);
      return ["http:", "https:"].includes(url.protocol) ? esc(url.href) : "#";
    } catch {
      return "#";
    }
  };
  const colors = {
    "Under construction": "#cf102d",
    "Proposed": "#1e5f91",
    "Moratorium": "#df8b16",
    "Utility pause": "#7851a9",
    "Rejected by planning commission": "#555963",
    "Approved": "#278050"
  };
  const map = L.map("map", { zoomControl: true, scrollWheelZoom: false }).setView([44.55, -85.45], 6);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: "© OpenStreetMap contributors"
  }).addTo(map);

  const layers = new Map();
  const markers = new Map();
  const statuses = [...new Set(points.map(point => point.status))];
  statuses.forEach(status => layers.set(status, L.layerGroup().addTo(map)));

  const popup = point => `
    <article class="map-popup">
      <span>${esc(point.status)} · ${esc(point.confidence)}</span>
      <h2>${esc(point.name)}</h2>
      <p>${esc(point.municipality)}, ${esc(point.county)} County</p>
      ${point.developer ? `<p><strong>Developer:</strong> ${esc(point.developer)}</p>` : ""}
      ${point.power_mw ? `<p><strong>Reported scale:</strong> ${esc(point.power_mw)} MW</p>` : ""}
      <p class="map-popup-note">${esc(point.note)}</p>
      <a href="${safeUrl(point.source_url)}" target="_blank" rel="noopener">Open ${esc(point.source_name)} source ↗</a>
    </article>`;

  points.forEach(point => {
    const marker = L.circleMarker([point.latitude, point.longitude], {
      radius: 9,
      weight: 3,
      color: "#fff",
      fillColor: colors[point.status] || "#cf102d",
      fillOpacity: 1
    }).bindPopup(popup(point));
    marker.addTo(layers.get(point.status));
    markers.set(point.name, marker);
  });

  const filters = document.querySelector("#map-filters");
  filters.innerHTML = statuses.map(status => `
    <label><input type="checkbox" value="${esc(status)}" checked>
      <i style="--marker:${colors[status] || "#cf102d"}"></i>
      <span>${esc(status)}</span>
      <em>${points.filter(point => point.status === status).length}</em>
    </label>`).join("");
  filters.addEventListener("change", event => {
    if (!event.target.matches("input")) return;
    const layer = layers.get(event.target.value);
    if (event.target.checked) layer.addTo(map); else map.removeLayer(layer);
  });
  document.querySelector("#show-all").addEventListener("click", () => {
    filters.querySelectorAll("input").forEach(input => {
      input.checked = true;
      layers.get(input.value).addTo(map);
    });
  });

  const directory = document.querySelector("#map-directory");
  directory.innerHTML = points.map(point => `
    <button type="button" data-point="${esc(point.name)}">
      <span style="--marker:${colors[point.status] || "#cf102d"}"></span>
      <strong>${esc(point.name)}</strong>
      <small>${esc(point.municipality)} · ${esc(point.status)}</small>
    </button>`).join("");
  directory.addEventListener("click", event => {
    const button = event.target.closest("button[data-point]");
    if (!button) return;
    const marker = markers.get(button.dataset.point);
    const status = points.find(point => point.name === button.dataset.point)?.status;
    const input = [...filters.querySelectorAll("input")].find(item => item.value === status);
    if (input && !input.checked) {
      input.checked = true;
      layers.get(status).addTo(map);
    }
    map.setView(marker.getLatLng(), 9, { animate: true });
    marker.openPopup();
  });
  document.querySelector("#map-updated").textContent = `Updated ${new Intl.DateTimeFormat("en-US", {
    month: "long", day: "numeric", year: "numeric", timeZone: "America/Detroit"
  }).format(new Date(data.updated_at))}`;
})();
