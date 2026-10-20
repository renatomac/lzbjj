/* Progressive enhancement for the Django member/contact editor. */
(function () {
  "use strict";
  function init() {
    const root = document.getElementById("memberEditor");
    if (!root) return;
    root.classList.add("js-enabled");
    // Belt choices depend on the member type, without requiring a page reload.
    const memberType = root.querySelector('[name="member_type"]');
    const beltPicker = root.querySelector('[data-belt-image-picker]');
    if (memberType && beltPicker) {
      const nativeBelt = beltPicker.querySelector('select[name="belt_selection"]');
      const beltButtons = Array.from(beltPicker.querySelectorAll(".lzbjj-belt-option"));
      const youthRanks = new Set([
        "white", "gray-white", "gray", "gray-black", "yellow-white", "yellow",
        "yellow-black", "orange-white", "orange", "orange-black",
        "green-white", "green", "green-black"
      ]);
      const adultRanks = new Set(["white", "blue", "purple", "brown", "black"]);
      function allowed(value, type) {
        const [rank, count] = value.split("|");
        const stripes = Number(count);
        const youth = youthRanks.has(rank) && stripes >= 0 && stripes <= 11;
        const adult = adultRanks.has(rank) && stripes >= 0 &&
          stripes <= (rank === "black" ? 9 : 4);
        return type === "child" ? youth :
          type === "adult" ? adult : (youth || adult);
      }
      function filterBelts() {
        if (!nativeBelt) return;
        const type = memberType.value;
        for (const option of nativeBelt.options) {
          option.hidden = !allowed(option.value, type);
          option.disabled = option.hidden;
        }
        for (const button of beltButtons) {
          button.hidden = !allowed(button.dataset.value, type);
          button.disabled = button.hidden;
        }
        // A change in member type must not silently submit an invalid belt.
        if (!allowed(nativeBelt.value, type)) nativeBelt.value = "white|0";
        nativeBelt.dispatchEvent(new Event("change", {bubbles: true}));
      }
      memberType.addEventListener("change", filterBelts);
      filterBelts();
    }
    const contactList = root.querySelector("#memberContacts");
    const addButton = root.querySelector("#addContact");
    const template = root.querySelector("#emptyContactTemplate");
    const total = root.querySelector('[name$="-TOTAL_FORMS"]');
    const max = root.querySelector('[name$="-MAX_NUM_FORMS"]');

    function setContactState(item) {
      const checkbox = item.querySelector('[name$="-DELETE"]');
      const button = item.querySelector(".member-editor-remove");
      if (!checkbox || !button) return;
      const deleted = checkbox.checked;
      item.classList.toggle("is-pending-delete", deleted);
      button.textContent = deleted ? "Undo removal" : "Remove";
      button.setAttribute("aria-pressed", String(deleted));
      const label = item.querySelector(".member-editor-contact-name");
      if (label) {
        label.textContent = deleted ? "Marked for removal" : "Contact " + (Number(item.dataset.contactIndex) + 1);
      }
    }
    function formatPhone(input) {
      if (input.readOnly || input.disabled) return;
      const original = input.value;
      let digits = original.replace(/\D/g, "");
      if (digits.length === 11 && digits.startsWith("1")) digits = digits.slice(1);
      digits = digits.slice(0, 10);
      let result = digits;
      if (digits.length > 6) result = "(" + digits.slice(0, 3) + ") " + digits.slice(3, 6) + "-" + digits.slice(6);
      else if (digits.length > 3) result = "(" + digits.slice(0, 3) + ") " + digits.slice(3);
      input.value = result;
    }
    function initPhones(scope) {
      scope.querySelectorAll('input[name="phone"], input[name$="-phone"]').forEach(function (input) {
        input.setAttribute("inputmode", "tel");
        input.setAttribute("autocomplete", "tel-national");
        if (input.value) formatPhone(input);
      });
    }
    if (contactList && addButton && template && total) {
      addButton.addEventListener("click", function () {
        const next = Number.parseInt(total.value, 10);
        if (!Number.isInteger(next)) return;
        const maximum = max ? Number.parseInt(max.value, 10) : 1000;
        if (Number.isInteger(maximum) && next >= maximum) return;
        const fragment = template.content.cloneNode(true);
        const item = fragment.querySelector(".member-editor-contact");
        if (!item) return;
        item.innerHTML = item.innerHTML.replace(/__prefix__/g, String(next));
        item.dataset.contactIndex = String(next);
        contactList.appendChild(fragment);
        total.value = String(next + 1);
        initPhones(item);
        setContactState(item);
        const first = item.querySelector('input:not([type="hidden"]):not([type="checkbox"])');
        if (first) first.focus();
      });
      contactList.addEventListener("click", function (event) {
        const button = event.target.closest(".member-editor-remove");
        if (!button) return;
        const item = button.closest(".member-editor-contact");
        const checkbox = item && item.querySelector('[name$="-DELETE"]');
        if (!checkbox) return;
        checkbox.checked = !checkbox.checked;
        setContactState(item);
      });
      contactList.querySelectorAll(".member-editor-contact").forEach(setContactState);
    }
    root.addEventListener("input", function (event) {
      if (event.target.matches('input[name="phone"], input[name$="-phone"]')) {
        formatPhone(event.target);
      }
    });
    initPhones(root);
    const form = root.querySelector("form");
    const submit = root.querySelector("#saveMember");
    if (form && submit) {
      form.addEventListener("submit", function () {
        // Preserve the browser's normal constraint validation and keep the
        // submit button enabled if validation rejects the submission.
        if (form.checkValidity()) {
          submit.disabled = true;
          submit.innerHTML = '<i class="fa-solid fa-spinner fa-spin me-2" aria-hidden="true"></i>Saving…';
        }
      });
    }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
