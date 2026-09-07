/* Persist an explicit theme choice and otherwise respect the OS preference. */
(() => {
  const storageKey = "secure-commerce-theme";
  const darkMediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
  const preferredTheme = () => {
    try { return localStorage.getItem(storageKey) || (darkMediaQuery.matches ? "dark" : "light"); }
    catch { return darkMediaQuery.matches ? "dark" : "light"; }
  };
  const applyTheme = (theme) => {
    document.documentElement.dataset.theme = theme;
    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      const switchingTo = theme === "dark" ? "light" : "dark";
      button.setAttribute("aria-pressed", String(theme === "dark"));
      button.setAttribute("aria-label", `Switch to ${switchingTo} mode`);
      const label = button.querySelector("[data-theme-label]");
      if (label) label.textContent = `Switch to ${switchingTo}`;
    });
  };
  document.addEventListener("DOMContentLoaded", () => {
    applyTheme(preferredTheme());
    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      button.addEventListener("click", () => {
        const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
        try { localStorage.setItem(storageKey, next); } catch { /* Private browsing can deny storage. */ }
        applyTheme(next);
      });
    });
  });
})();
