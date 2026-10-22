(() => {
  const sidebar = document.getElementById('sidebar');
  if (!sidebar) return;
  sidebar.addEventListener('pointerleave', (event) => {
    if (event.pointerType !== 'mouse' || !window.matchMedia('(hover: hover) and (pointer: fine)').matches) return;
    if (!sidebar.classList.contains('show')) return;
    window.bootstrap?.Offcanvas.getInstance(sidebar)?.hide();
  });
})();
