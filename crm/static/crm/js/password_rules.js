/*
 * Live password strength checklist.
 *
 * Highlights each rule in red (unmet) or green (met) as the user types,
 * mirroring the server-side rules enforced in crm/password_validation.py.
 */
(function () {
    var RULES = [
        { id: "length", test: function (value) { return value.length >= 8; } },
        { id: "uppercase", test: function (value) { return /[A-Z]/.test(value); } },
        { id: "lowercase", test: function (value) { return /[a-z]/.test(value); } },
        { id: "number", test: function (value) { return /[0-9]/.test(value); } },
        { id: "symbol", test: function (value) { return /[^A-Za-z0-9]/.test(value); } },
    ];

    function initPasswordRulesChecklist(inputId, listId) {
        var input = document.getElementById(inputId);
        var list = document.getElementById(listId);
        if (!input || !list) {
            return;
        }

        function update() {
            var value = input.value || "";
            RULES.forEach(function (rule) {
                var item = list.querySelector('[data-rule="' + rule.id + '"]');
                if (!item) {
                    return;
                }
                var met = rule.test(value);
                item.classList.toggle("text-danger", !met);
                item.classList.toggle("text-success", met);
                var icon = item.querySelector(".rule-icon");
                if (icon) {
                    icon.classList.toggle("fa-times-circle", !met);
                    icon.classList.toggle("fa-check-circle", met);
                }
            });
        }

        input.addEventListener("input", update);
        update();
    }

    window.initPasswordRulesChecklist = initPasswordRulesChecklist;
})();
