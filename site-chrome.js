/**
 * Shared site chrome — active nav, footer date.
 */
(function () {
  const page = document.body.dataset.page || "";
  if (!page) return;

  const navMap = {
    home: ["index.html", "index.html#", "/mi-data-center-tracker/", "/mi-data-center-tracker/index.html"],
    map: ["map.html"],
    stories: ["stories.html"],
    meetings: ["meetings.html"],
    learn: ["learn.html", "methodology.html", "privacy.html"],
    sponsor: ["sponsorship.html"]
  };

  const match = (href) => {
    if (!href) return false;
    const paths = navMap[page] || [];
    return paths.some(p => href === p || href.endsWith("/" + p.replace(/^\//, "")));
  };

  document.querySelectorAll(".nav-links a, .drawer nav a").forEach(link => {
    const href = link.getAttribute("href") || "";
    if (match(href)) link.classList.add("is-active");
  });

  if (page === "map") {
    document.querySelectorAll('.nav-links a[href="map.html"], .drawer nav a[href="map.html"]').forEach(el => {
      el.classList.add("is-active");
    });
  }
})();