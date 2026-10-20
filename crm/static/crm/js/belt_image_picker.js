/* Reusable illustrated rank/stripe selector, progressive enhancement.
 * Native select remains available if this script cannot initialize.
 * No Bootstrap dependency, so this also works inside Django admin.
 */
(function () {
  "use strict";

  function setup(picker) {
    if (picker.dataset.initialized === "true") return;
    const select = picker.querySelector(".lzbjj-belt-native select");
    const ui = picker.querySelector(".lzbjj-belt-ui");
    const trigger = picker.querySelector(".lzbjj-belt-trigger");
    const menu = picker.querySelector(".lzbjj-belt-menu");
    const preview = picker.querySelector(".lzbjj-belt-preview");
    const options = Array.from(picker.querySelectorAll(".lzbjj-belt-option"));
    if (!select || !ui || !trigger || !preview || !menu || !options.length) return;
    picker.dataset.initialized = "true";

    function selectedOption() {
      return options.find(item => item.dataset.value === select.value) || options[0];
    }
    function render() {
      const matched = options.find(item => item.dataset.value === select.value);
      const shown = matched || options[0];
      preview.replaceChildren();
      const img = shown.querySelector("img");
      const art = shown.querySelector(".lzbjj-belt-art-fallback");
      if (img) preview.appendChild(img.cloneNode(true));
      else if (art) preview.appendChild(art.cloneNode(true));
      const label = document.createElement("span");
      label.textContent = shown.dataset.label || shown.textContent.trim();
      preview.appendChild(label);
      options.forEach(item => {
        const chosen = item === matched;
        item.classList.toggle("active", chosen);
        item.setAttribute("aria-selected", String(chosen));
      });
      trigger.disabled = select.disabled;
      trigger.setAttribute("aria-label", "Belt: " + label.textContent);
      if (picker.dataset.previewTarget) {
        const target = document.querySelector(picker.dataset.previewTarget);
        if (target) target.textContent = label.textContent;
      }
    }
    function close(focusTrigger) {
      menu.hidden = true;
      picker.classList.remove("is-open");
      trigger.setAttribute("aria-expanded", "false");
      if (focusTrigger) trigger.focus();
    }
    function open() {
      if (trigger.disabled) return;
      menu.hidden = false;
      picker.classList.add("is-open");
      trigger.setAttribute("aria-expanded", "true");
      const current = selectedOption();
      // Keep the chosen belt visible without scrolling the page.
      menu.scrollTop = Math.max(0, current.offsetTop - menu.offsetTop - 40);
      current.focus();
    }
    function choose(option) {
      if (select.disabled) return;
      select.value = option.dataset.value;
      select.dispatchEvent(new Event("change", {bubbles: true}));
      render();
      close(true);
    }
    trigger.addEventListener("click", function () {
      if (menu.hidden) open();
      else close(true);
    });
    trigger.addEventListener("keydown", function (event) {
      if (["ArrowDown", "ArrowUp", "Enter", " "].includes(event.key)) {
        event.preventDefault();
        open();
      }
      if (event.key === "Escape") close(true);
    });
    options.forEach((option, i) => {
      option.addEventListener("click", () => choose(option));
      option.addEventListener("keydown", function (event) {
        if (event.key === "ArrowDown" || event.key === "ArrowUp") {
          event.preventDefault();
          const step = event.key === "ArrowDown" ? 1 : -1;
          options[(i + step + options.length) % options.length].focus();
        } else if (event.key === "Home") {
          event.preventDefault();
          options[0].focus();
        } else if (event.key === "End") {
          event.preventDefault();
          options[options.length - 1].focus();
        } else if (event.key === "Escape") {
          event.preventDefault();
          close(true);
        }
      });
    });
    document.addEventListener("click", function (event) {
      if (!picker.contains(event.target)) close(false);
    });
    picker.addEventListener("focusout", function (event) {
      if (!picker.contains(event.relatedTarget)) close(false);
    });
    select.addEventListener("change", render);

    menu.hidden = true;
    ui.hidden = false;
    picker.classList.add("is-enhanced");
    render();
  }
  function init() {
    document.querySelectorAll("[data-belt-image-picker]").forEach(setup);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
  window.LZBJJBeltPicker = {init};
})();
