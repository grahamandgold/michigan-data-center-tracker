try { history.scrollRestoration = 'manual'; } catch (e) {}
window.addEventListener('load', function () { if (!location.hash) setTimeout(function () { window.scrollTo(0, 0); }, 60); });
(function () {
  var KEY = "mdct-theme";
  var root = document.documentElement;

  function stored() {
    try {
      return localStorage.getItem(KEY);
    } catch (e) {
      return null;
    }
  }

  function resolve() {
    var t = stored();
    return t === "light" || t === "dark" ? t : "dark";
  }

  function metaColor(theme) {
    var el = document.querySelector('meta[name="theme-color"]');
    if (el) el.setAttribute("content", theme === "light" ? "#faf9f5" : "#100f0e");
  }

  function syncButtons(theme) {
    var light = theme === "light";
    document.querySelectorAll(".mdct-theme-btn").forEach(function (btn) {
      btn.setAttribute("aria-pressed", light ? "true" : "false");
      btn.title = light ? "Switch to dark mode" : "Switch to light mode";
      btn.setAttribute("aria-label", light ? "Switch to dark mode" : "Switch to light mode");
      var icon = btn.querySelector(".mdct-theme-icon");
      var label = btn.querySelector(".mdct-theme-label");
      if (icon) icon.textContent = light ? "☾" : "☀";
      if (label) label.textContent = light ? "Dark" : "Light";
    });
  }

  function apply(theme) {
    if (theme !== "light" && theme !== "dark") theme = "dark";
    root.dataset.theme = theme;
    try {
      localStorage.setItem(KEY, theme);
    } catch (e) {}
    metaColor(theme);
    syncButtons(theme);
    try {
      window.dispatchEvent(new CustomEvent("mdct-theme-change", { detail: { theme: theme } }));
      window.postMessage({ type: "__dc_theme", theme: theme }, "*");
    } catch (e) {}
  }

  function toggle() {
    apply(root.dataset.theme === "light" ? "dark" : "light");
  }

  apply(resolve());

  window.MDCTTheme = { get: function () { return root.dataset.theme; }, set: apply, toggle: toggle };

  document.addEventListener("click", function (e) {
    var btn = e.target.closest(".mdct-theme-btn");
    if (!btn) return;
    e.preventDefault();
    toggle();
  });
})();