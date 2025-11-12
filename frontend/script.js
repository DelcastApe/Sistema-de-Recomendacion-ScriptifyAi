// Scroll suave para enlaces con data-scroll (ej: "Ver demo")
document.querySelectorAll('[data-scroll]').forEach((el) => {
  el.addEventListener('click', (e) => {
    const href = el.getAttribute('href');
    if (href && href.startsWith('#')) {
      const target = document.querySelector(href);
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }
  });
});

// Hook sencillo por si quieres medir clics del CTA principal
const btnReco = document.getElementById('btn-recomendador');
if (btnReco) {
  btnReco.addEventListener('click', () => {
    // Reemplaza por tu analítica (ej: gtag, posthog, plausible, etc.)
    // window.gtag?.('event', 'click_recomendador_hero');
  });
}
