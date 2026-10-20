/* Shared progressive enhancement for Django ChoiceFields backed by belt artwork. */
(function () {
  "use strict";
  function setup(picker) {
    if (picker.dataset.initialized === "true") return;
    const select = picker.querySelector(".lzbjj-belt-native select");
    const ui = picker.querySelector(".lzbjj-belt-ui");
    const trigger = picker.querySelector(".lzbjj-belt-trigger");
    const preview = picker.querySelector(".lzbjj-belt-preview");
    const options = Array.from(picker.querySelectorAll(".lzbjj-belt-option"));
    if (!select || !ui || !trigger || !preview || !options.length || !window.bootstrap?.Dropdown) return;
    picker.dataset.initialized = "true";

    function render() {
      const option = options.find(item => item.dataset.value === select.value);
      const shown = option || options[0];
      preview.replaceChildren();
      const img = shown.querySelector("img");
      const art = shown.querySelector(".lzbjj-belt-art-fallback");
      if (img) preview.appendChild(img.cloneNode(true));
      else if (art) preview.appendChild(art.cloneNode(true));
      const label = document.createElement("span");
      label.textContent = shown.dataset.label || shown.textContent.trim();
      preview.appendChild(label);
      options.forEach(item => {
        const chosen = item === option;
        item.classList.toggle("active", chosen);
        item.setAttribute("aria-selected", String(chosen));
      });
      trigger.disabled = select.disabled;
      trigger.setAttribute("aria-label", "Belt: " + label.textContent);
    }

    options.forEach(option => option.addEventListener("click", () => {
      if (select.disabled) return;
      select.value = option.dataset.value;
      select.dispatchEvent(new Event("change", {bubbles:true}));
      render();
      window.bootstrap.Dropdown.getOrCreateInstance(trigger).hide();
      trigger.focus();
    }));
    select.addEventListener("change", render);
    picker.addEventListener("show.bs.dropdown", function () {
      const option = options.find(item => item.dataset.value === select.value) || options[0];
      requestAnimationFrame(() => option.scrollIntoView({block:"nearest"}));
    });
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
