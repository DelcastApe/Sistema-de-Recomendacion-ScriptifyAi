from typing import Optional, Dict, Any, List
from pydantic import BaseModel

class Metrics(BaseModel):
    platform: Optional[str] = None
    niche: str
    format: Optional[str] = None
    ctr: Optional[float] = None
    retention: Optional[float] = None
    avg_watch_pct: Optional[float] = None
    completion_rate: Optional[float] = None
    impressions: Optional[int] = None
    reach: Optional[int] = None
    clicks: Optional[int] = None
    conversions: Optional[int] = None
    saves: Optional[int] = None
    shares: Optional[int] = None
    comments: Optional[int] = None
    followers_change: Optional[int] = None
    freq: Optional[float] = None
    use_graph: bool = True
    top_k: Optional[int] = 5

def pct(x: Optional[float]) -> Optional[float]:
    if x is None: return None
    return x/100.0 if x > 1.0 else x

def safe_div(a: Optional[float], b: Optional[float]) -> Optional[float]:
    try:
        if a is None or b in (None, 0): return None
        return a/b
    except ZeroDivisionError:
        return None

def _fmt_pct(x: Optional[float]) -> str:
    if x is None: return "s/d"
    return f"{x:.2%}"

def score_discovery(m: Metrics) -> float:
    _ctr = pct(m.ctr)
    low_ctr = 1.0 if (_ctr is not None and _ctr < 0.04) else 0.0
    low_reach = 1.0 if (m.reach is not None and m.reach < 1000) or (m.impressions is not None and m.impressions < 2000) else 0.0
    ok_ret = 1.0 if (pct(m.retention) or 0) >= 0.45 else 0.0
    return 0.55*low_ctr + 0.35*low_reach + 0.10*ok_ret

def score_retention(m: Metrics) -> float:
    _ret = pct(m.retention); _avg = pct(m.avg_watch_pct); _comp = pct(m.completion_rate)
    weak_watch = 1.0 if (_ret is not None and _ret < 0.40) or (_avg is not None and _avg < 0.40) or (_comp is not None and _comp < 0.30) else 0.0
    low_eng = 1.0 if ((m.saves or 0)+(m.shares or 0)+(m.comments or 0)) < 10 else 0.0
    low_freq = 1.0 if (m.freq is not None and m.freq < 2.0) else 0.0
    return 0.6*weak_watch + 0.25*low_eng + 0.15*low_freq

def score_conversion(m: Metrics) -> float:
    _ctr = pct(m.ctr)
    conv_rate = safe_div(m.conversions, m.clicks)
    enough_traffic = 1.0 if (_ctr is not None and _ctr >= 0.05) or (m.clicks and m.clicks > 50) else 0.0
    low_conv = 1.0 if (conv_rate is not None and conv_rate < 0.02) or (m.conversions == 0 and (m.clicks or 0) > 20) else 0.0
    reach_ok = 1.0 if (m.reach and m.reach > 1000) or (m.impressions and m.impressions > 2000) else 0.0
    return 0.5*enough_traffic + 0.35*low_conv + 0.15*reach_ok

def decide_focus(m: Metrics) -> Dict[str, Any]:
    s_disc = score_discovery(m)
    s_ret = score_retention(m)
    s_conv = score_conversion(m)
    scores = {"discovery": round(s_disc,3), "retention": round(s_ret,3), "conversion": round(s_conv,3)}
    focus = max(scores, key=scores.get)
    return {"focus": focus, "scores": scores}

def reason_for_focus(focus: str, m: Metrics) -> str:
    _ctr = pct(m.ctr)
    _ret = pct(m.retention)
    _avg = pct(m.avg_watch_pct)
    _comp = pct(m.completion_rate)
    conv_rate = safe_div(m.conversions, m.clicks)

    ctr_s = _fmt_pct(_ctr)
    ret_base = _ret if _ret is not None else (_avg if _avg is not None else (_comp if _comp is not None else None))
    ret_s = _fmt_pct(ret_base)
    conv_s = _fmt_pct(conv_rate)

    if focus == "conversion":
        return (
            f"Tienes interés validado (CTR≈{ctr_s}, clics={m.clicks or 0}, alcance={m.reach or 0}) "
            f"pero conversión baja ({conv_s}). Recomendamos CONVERSIÓN: mostrar resultado real/caso breve, "
            f"resolver objeciones frecuentes y cerrar con un siguiente paso claro, manteniendo congruencia promesa→landing."
        )

    if focus == "retention":
        interacciones = (m.saves or 0)+(m.shares or 0)+(m.comments or 0)
        return (
            f"Watch-time débil (ret≈{ret_s}) e interacción baja (saves+shares+comments={interacciones}). "
            f"Recomendamos RETENCIÓN: hook 0–2s, 1 sola idea por pieza y ritmo/cortes altos; añade demostración clara en {m.niche}."
        )

    return (
        f"Descubrimiento insuficiente (CTR≈{ctr_s}, reach={m.reach or 0}, impresiones={m.impressions or 0}) "
        f"con retención aceptable ({ret_s} si provista). Recomendamos DESCUBRIMIENTO: miniatura y promesa explícita, "
        f"títulos orientados a búsqueda y ángulos comparativos para elevar el CTR."
    )

def ideas_for_focus(focus: str, niche: str) -> List[str]:
    n = (niche or "tu nicho").strip()
    if focus == "conversion":
        return [
            f"{n}: caso real (antes/después en 30d)",
            f"{n}: 3 objeciones y su respuesta",
            f"{n}: qué obtienes y para quién SÍ/NO",
            f"{n}: comparativa método A vs B",
            f"{n}: prueba social en 45s",
            f"{n}: guía rápida para decidir hoy",
            f"{n}: errores que frenan resultados",
            f"{n}: checklist de decisión",
            f"{n}: resultados típicos y tiempos",
            f"{n}: dudas frecuentes en 60s",
        ]
    if focus == "retention":
        return [
            f"{n}: 3 errores y cómo evitarlos",
            f"Mini tutorial de {n}: del 0 al 1",
            f"{n}: rutina en 60s (guardable)",
            f"{n}: mitos vs realidad",
            f"{n}: test rápido de progreso",
            f"Hook + 1 idea: {n} básico",
            f"{n}: challenge 7 días",
            f"{n}: pro tip en 1 minuto",
            f"{n}: antes/después explicados",
            f"{n}: preguntas rápidas y respuesta",
        ]
    return [
        f"{n}: hoja de ruta simple",
        f"Por qué {n}: beneficios reales",
        f"{n} en 3 pasos (principiantes)",
        f"Herramientas esenciales para {n}",
        f"Errores típicos al iniciar {n}",
        f"{n}: marco para decidir",
        f"Qué esperar en tu 1ª semana de {n}",
        f"{n}: la técnica que más impacta",
        f"{n}: señales de buen progreso",
        f"{n}: evita esto si empiezas hoy",
    ]
