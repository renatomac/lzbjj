/* Shared live filtering for CRM management tables.
 * Uses GET requests, debounces text input, and replaces only the result region.
 */
(function () {
  "use strict";
  function setup(form) {
    const targetId = form.dataset.liveTarget;
    const target = document.getElementById(targetId);
    const message = form.querySelector("[data-filter-feedback]");
    const clear = form.querySelector("[data-clear-filters]");
    const count = document.querySelector("[data-results-count]");
    if (!target) return;
    let timer, controller, serial = 0;
    const defaults = Array.from(form.elements).filter(el => el.name && el.type !== "hidden");
    function buildUrl() {
      const url = new URL(form.action || location.href, location.href);
      const params = new URLSearchParams();
      defaults.forEach(el => {
        if (el.name && el.value.trim()) params.set(el.name, el.value.trim());
      });
      url.search = params.toString();
      return url;
    }
    async function refresh() {
      const url = buildUrl();
      const current = ++serial;
      if (controller) controller.abort();
      controller = new AbortController();
      if (message) message.textContent = "Updating…";
      try {
        const response = await fetch(url, {
          credentials: "same-origin",
          signal: controller.signal,
          headers: {"X-Requested-With": "XMLHttpRequest"}
        });
        if (!response.ok) throw Error("Unable to refresh");
        const doc = new DOMParser().parseFromString(await response.text(), "text/html");
        const replacement = doc.getElementById(targetId);
        if (!replacement) throw Error("Missing results");
        if (current !== serial) return;
        target.replaceChildren(...Array.from(replacement.childNodes));
        const updatedCount = doc.querySelector("[data-results-count]");
        if (count && updatedCount) count.textContent = updatedCount.textContent;
        history.replaceState(null, "", url.pathname + url.search);
        if (message) message.textContent = "";
      } catch (error) {
        if (error.name === "AbortError" || current !== serial) return;
        if (message) message.textContent = "Could not refresh. Try again.";
      }
    }
    form.addEventListener("input", event => {
      if (event.target.matches('input[type="search"], input[type="text"]')) {
        clearTimeout(timer);
        timer = setTimeout(refresh, 350);
      }
    });
    form.addEventListener("change", event => {
      if (event.target.matches("select")) {
        clearTimeout(timer);
        refresh();
      }
    });
    form.addEventListener("submit", event => {
      event.preventDefault();
      clearTimeout(timer);
      refresh();
    });
    if (clear) clear.addEventListener("click", event => {
      event.preventDefault();
      defaults.forEach(el => { el.value = ""; });
      clearTimeout(timer);
      refresh();
    });
  }
  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("form[data-live-target]").forEach(setup);
  });
})();
