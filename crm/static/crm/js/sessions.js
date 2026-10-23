document.addEventListener('DOMContentLoaded', function () {
    const modal = document.getElementById('deleteSessionModal');
    const form = document.getElementById('deleteSessionForm');
    const confirm = document.getElementById('confirmDeleteSession');
    if (!modal || !form || !confirm) return;
    modal.addEventListener('show.bs.modal', function (event) {
        const trigger = event.relatedTarget;
        const url = trigger && trigger.dataset.deleteUrl;
        confirm.disabled = !url;
        if (url) form.action = url;
        document.getElementById('deleteSessionLabel').textContent =
            trigger ? trigger.dataset.sessionLabel : '';
    });
    modal.addEventListener('hidden.bs.modal', function () {
        form.removeAttribute('action');
        confirm.disabled = true;
    });
    form.addEventListener('submit', function (event) {
        if (!form.getAttribute('action')) {
            event.preventDefault();
            return;
        }
        confirm.disabled = true;
    });
});
