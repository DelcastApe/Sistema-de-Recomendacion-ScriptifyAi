from typing import Optional, Dict, Any, List
from pydantic import BaseModel
import math

class Metrics(BaseModel):
    # contexto
    platform: Optional[str] = None
    niche: str
    format: Optional[str] = None

    # MÉTRICAS (pueden venir vacías o como conteos)
    ctr: Optional[float] = None                # 0–1 o 0–100 (normalizo)
    retention: Optional[float] = None          # 0–1 o 0–100 (normalizo)
    avg_watch_pct: Optional[float] = None      # 0–1 o 0–100 (normalizo)
    completion_rate: Optional[float] = None    # 0–1 o 0–100 (normalizo)

    impressions: Optional[int] = None
    reach: Optional[int] = None
    clicks: Optional[int] = None
    conversions: Optional[int] = None

    # nuevos conteos para inferir tasas cuando no pasen % directamente
    followers: Optional[int] = None
    likes: Optional[int] = None
    shares: Optional[int] = None
    saves: Optional[int] = None
    comments: Optional[int] = None

    followers_change: Optional[int] = None
    freq: Optional[float] = None   # posts/semana aprox

    # controles
    use_graph: bool = True
    top_k: Optional[int] = 5

def _pct(x: Optional[float]) -> Optional[float]:
    if x is None:
        return None
    return x/100.0 if x > 1 else x

def _safe_pct_str(x: Optional[float]) -> str:
    if x is None:
        return "s/d"
    return f"{x:.2%}"

def infer_rates(m: Metrics) -> Metrics:
    """Si el usuario pasa solo conteos (clicks, likes, etc.), calculo CTR y una proxy de retención."""
    m = m.copy(deep=True)

    # Normalizo si ya vienen en 0–100
    m.ctr = _pct(m.ctr) if m.ctr is not None else None
    m.retention = _pct(m.retention) if m.retention is not None else None
    m.avg_watch_pct = _pct(m.avg_watch_pct) if m.avg_watch_pct is not None else None
    m.completion_rate = _pct(m.completion_rate) if m.completion_rate is not None else None

    # CTR si faltó pero hay clicks e impresiones
    if m.ctr is None and (m.clicks is not None and m.impressions not in (None, 0)):
        m.ctr = max(0.0, min(1.0, m.clicks / m.impressions))

    # Retención proxy (engagement por view) si faltó y hay señales
    if m.retention is None and m.impressions not in (None, 0):
        likes = m.likes or 0
        saves = m.saves or 0
        shares = m.shares or 0
        comments = m.comments or 0
        # Pesos conservadores (saves/shares un poco más “fuerte” que like)
        num = 1.0*likes + 1.5*comments + 1.7*shares + 1.8*saves
        m.retention = max(0.0, min(0.95, num / m.impressions))

    return m

def score_discovery(m: Metrics) -> float:
    ctr = m.ctr or 0.0
    # CTR bajo y poco alcance para su base
    low_ctr = 1.0 if ctr < 0.02 else 0.0
    low_reach = 0.0
    if m.reach is not None and m.followers is not None and m.followers > 0:
        low_reach = 1.0 if (m.reach / max(1, m.followers)) < 0.15 else 0.0
    elif m.impressions is not None:
        low_reach = 1.0 if m.impressions < 2000 else 0.0
    # si la retención es decente, más razón para empujar descubrimiento
    ok_ret = 1.0 if (m.retention or 0) >= 0.45 else 0.0
    return 0.6*low_ctr + 0.3*low_reach + 0.1*ok_ret

def score_retention(m: Metrics) -> float:
    low_ret = 1.0 if (m.retention is not None and m.retention < 0.35) else 0.0
    low_watch = 1.0 if (m.avg_watch_pct is not None and m.avg_watch_pct < 0.25) else 0.0
    return 0.8*low_ret + 0.2*low_watch

def score_conversion(m: Metrics) -> float:
    ctr = m.ctr or 0.0
    traffic_ok = 1.0 if (ctr >= 0.04 or (m.clicks or 0) >= 100) else 0.0
    conv_rate = None
    if (m.clicks not in (None, 0)) and (m.conversions is not None):
        conv_rate = m.conversions / max(1, m.clicks)
    low_conv = 1.0 if (traffic_ok and ((conv_rate or 0.0) < 0.02)) else 0.0
    return 0.8*low_conv + 0.2*traffic_ok

def decide_focus(m: Metrics) -> Dict[str, Any]:
    m = infer_rates(m)
    s_dis = score_discovery(m)
    s_ret = score_retention(m)
    s_conv = score_conversion(m)
    scores = {"discovery": s_dis, "retention": s_ret, "conversion": s_conv}
    # Prioridad: conversion > retention > discovery cuando hay empate ajustado
    focus = max(scores, key=lambda k: (scores[k], 1 if k=="conversion" else 0, 0.5 if k=="retention" else 0))
    return {"focus": focus, "scores": scores, "metrics": m}

def reason_for_focus(focus: str, m: Metrics) -> str:
    m = infer_rates(m)
    ctr_s = _safe_pct_str(m.ctr)
    ret_s = _safe_pct_str(m.retention)
    reach = m.reach if m.reach is not None else "s/d"
    impr = m.impressions if m.impressions is not None else "s/d"
    clicks = m.clicks if m.clicks is not None else 0
    convs = m.conversions if m.conversions is not None else 0
    conv_rate = (convs / clicks) if clicks else None
    conv_s = _safe_pct_str(conv_rate)

    if focus == "discovery":
        return (f"Descubrimiento insuficiente (CTR≈{ctr_s}, reach={reach}, impresiones={impr}) "
                f"con retención {ret_s if m.retention is not None else 's/d'}. "
                f"Recomendamos DESCUBRIMIENTO: miniatura/gancho fuertes y promesa explícita para elevar el CTR.")

    if focus == "retention":
        base = (f"Watch-time débil (ret≈{ret_s})"
                if m.retention is not None else
                f"Baja interacción relativa (likes/shares/saves/comments vs vistas).")
        return (f"{base} CTR≈{ctr_s}, reach={reach}, impresiones={impr}. "
                f"Recomendamos RETENCIÓN: hook 0–2s, 1 idea por pieza y ritmo/cortes altos; añade demostración clara.")

    # conversion
    return (f"Tienes interés validado (CTR≈{ctr_s}, clics={clicks}, alcance={reach}) pero conversión baja "
            f"({convs} → {conv_s if conv_rate is not None else 's/d'}). "
            f"Recomendamos CONVERSIÓN: mostrar resultado/caso breve, resolver objeciones y cerrar con siguiente paso claro.")

def ideas_for_focus(focus: str, niche: str) -> List[str]:
    n = niche or "tu tema"
    if focus == "discovery":
        return [
            f"{n}: 3 errores comunes y cómo evitarlos (60s)",
            f"{n}: REST vs GraphQL (cuándo elegir)",
            f"{n}: monolito vs microservicios en 1 min",
            f"{n}: checklist para empezar de cero",
            f"{n}: mito vs realidad en 60s",
            f"{n}: lo que nadie te cuenta al iniciar",
            f"{n}: top 5 herramientas que sí uso",
            f"{n}: antes y después (caso real)",
            f"{n}: guía exprés en 3 pasos",
            f"{n}: preguntas clave que debes hacerte"
        ]
    if focus == "retention":
        return [
            f"{n}: el error #1 que sabotea tu progreso",
            f"{n}: del 0 al 1 en 3 pasos (ritmo alto)",
            f"{n}: caso real, cómo lo resolvimos en 30s",
            f"{n}: microtutorial con demostración clara",
            f"{n}: 1 concepto — 3 ejemplos rápidos",
            f"{n}: desmintiendo un mito con evidencia",
            f"{n}: cómo corregir esto en 60s",
            f"{n}: 3 señales de que vas bien",
            f"{n}: evita esto si empiezas hoy",
            f"{n}: antes/después con explicación breve"
        ]
    # conversion
    return [
        f"{n}: caso real y resultados medibles",
        f"{n}: antes/después + qué cambió",
        f"{n}: comparativa de enfoques (pros/contras)",
        f"{n}: 3 objeciones y respuestas claras",
        f"{n}: errores que frenan resultados y cómo evitarlos",
        f"{n}: mini-demo del método paso a paso",
        f"{n}: FAQ rápida (lo más preguntado)",
        f"{n}: checklist de decisión en 1 minuto",
        f"{n}: métrica que importa y cómo mejorarla",
        f"{n}: plan 7 días con objetivos concretos"
    ]
