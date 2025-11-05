from typing import Optional
from models.schemas import Metrics

def _pct(x: Optional[float]) -> Optional[float]:
    if x is None: return None
    return x/100.0 if x > 1.0 else x

def _safe_div(a: Optional[float], b: Optional[float]) -> Optional[float]:
    try:
        if a is None or b in (None, 0): return None
        return a / b
    except ZeroDivisionError:
        return None

def autopopulate_metrics(m: Metrics) -> Metrics:
    # Normaliza si vinieron porcentajes como 3 -> 0.03
    if m.ctr is not None: m.ctr = _pct(m.ctr)
    if m.retention is not None: m.retention = _pct(m.retention)
    if m.avg_watch_pct is not None: m.avg_watch_pct = _pct(m.avg_watch_pct)
    if m.completion_rate is not None: m.completion_rate = _pct(m.completion_rate)

    # Calcula CTR si no vino, y hay clicks+impressions
    if m.ctr is None:
        m.ctr = _safe_div(m.clicks, m.impressions)

    # Calcula retención si no vino:
    if m.retention is None:
        # Preferir datos directos si existen
        if m.avg_watch_pct is not None:
            m.retention = m.avg_watch_pct
        elif m.completion_rate is not None:
            m.retention = m.completion_rate
        else:
            # Estimar una proxy suave desde engagement
            eng_num = (m.likes or 0) + (m.comments or 0) + (m.shares or 0) + (m.saves or 0)
            den = m.impressions or m.followers or 0
            eng_rate = _safe_div(eng_num, den) or 0.0
            # Proxy acotada (evitamos inventar demasiado)
            proxy = max(0.10, min(0.70, eng_rate * 1.5)) if den > 0 else None
            if proxy is not None:
                m.retention = proxy

    return m
