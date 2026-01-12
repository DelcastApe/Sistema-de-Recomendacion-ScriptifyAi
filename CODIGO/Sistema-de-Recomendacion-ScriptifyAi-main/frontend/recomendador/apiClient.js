(function () {
  let _cfg = null;
  let _ready = null;

  async function loadConfig() {
    if (_cfg) return _cfg;
    const res = await fetch("/config.json");
    if (!res.ok) throw new Error("No se pudo leer /config.json");
    _cfg = await res.json();
    if (!_cfg.API_URL) throw new Error("API_URL faltante en config.json");
    return _cfg;
  }
  async function ready() { if (!_ready) _ready = loadConfig(); return _ready; }

  async function recommendLLM(payload) {
    const cfg = await ready();
    const res = await fetch(cfg.API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(cfg.API_KEY ? { "x-api-key": cfg.API_KEY } : {})
      },
      body: JSON.stringify(payload)
    });
    const text = await res.text();
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${text}`);
    try { return JSON.parse(text); } catch { return { recommendation: text }; }
  }

  // si luego quieres likes:
  async function sendLike({ niche, idea, specialties = [], region = "GL" }) {
    const cfg = await ready();
    const res = await fetch("/api/feedback/like", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(cfg.API_KEY ? { "x-api-key": cfg.API_KEY } : {})
      },
      body: JSON.stringify({ niche, idea, specialties, region })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
    return res.json();
  }

  window.API = { ready, recommendLLM, sendLike };
})();
