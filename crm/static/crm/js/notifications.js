(() => {
  const widget = document.getElementById('notificationWidget');
  if (!widget) return;
  let pending = false;
  const error = document.getElementById('notificationError');
  const badge = document.getElementById('notifBadge');
  function count(value) {
    badge.textContent = value; badge.hidden = !value; badge.style.display = value ? '' : 'none';
    document.getElementById('notifBell').setAttribute('aria-label', `Notifications: ${value} unread`);
  }
  async function refresh() {
    if (pending) return;
    pending = true;
    try {
      const response = await fetch(widget.dataset.recentUrl, {credentials: 'same-origin'});
      if (!response.ok) throw new Error('Unable to refresh notifications.');
      const data = await response.json();
      const list = document.getElementById('notifDropdown'); list.replaceChildren();
      count(data.unread);
      for (const item of data.recent) {
        const row = document.createElement('div');
        row.className = 'p-3 border-bottom' + (item.is_read ? '' : ' bg-light fw-semibold');
        const message = document.createElement('div'); message.textContent = item.message; row.append(message);
        const time = document.createElement('div'); time.className = 'small text-muted mt-1';
        time.textContent = new Date(item.created_at).toLocaleString(); row.append(time);
        if (!item.is_read) {
          const button = document.createElement('button'); button.className = 'btn btn-sm btn-link px-0';
          button.textContent = 'Mark as read'; button.dataset.notificationAction = 'read'; button.dataset.id = item.id; row.append(button);
        }
        list.append(row);
      }
      if (!data.recent.length) { const empty = document.createElement('div'); empty.className = 'p-4 text-center text-muted'; empty.textContent = 'You’re all caught up.'; list.append(empty); }
      error.textContent = '';
    } catch (e) { error.textContent = 'Unable to refresh. Try again shortly.'; }
    finally { pending = false; }
  }
  window.refreshNotifications = refresh;
  document.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-notification-action]'); if (!button) return;
    event.preventDefault();
    const action = button.dataset.notificationAction;
    if (action === 'delete' && !confirm('Delete this notification permanently?')) return;
    const url = action === 'all' ? widget.dataset.markAllUrl : (action === 'delete' ? widget.dataset.deleteUrl : widget.dataset.markUrl).replace('/0/', `/${button.dataset.id}/`);
    button.disabled = true;
    try {
      const response = await fetch(url, {method: 'POST', credentials: 'same-origin', headers: {'X-CSRFToken': document.getElementById('notificationCsrf').value}});
      if (!response.ok) throw new Error();
      if (document.getElementById('notificationCenter')) window.location.reload();
      else await refresh();
    } catch (e) { error.textContent = 'Action failed. Refresh the page and try again.'; const centerError = document.getElementById('centerError'); if (centerError) centerError.textContent = error.textContent; }
    finally { button.disabled = false; }
  });
  refresh();
  setInterval(() => { if (!document.hidden) refresh(); }, 30000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
  document.getElementById('notifBell').addEventListener('click', refresh);
})();
