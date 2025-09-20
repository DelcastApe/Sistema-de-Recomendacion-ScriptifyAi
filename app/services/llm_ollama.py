import os, json, re, requests
from typing import List, Dict, Any, Tuple

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
MODEL = os.getenv("MODEL", "qwen2.5:7b-instruct")

REC_MAP = {
    "conversion": "Optimiza CONVERSIÓN: muestra resultado real o comparativa; cierra con un próximo paso claro.",
    "retention":  "Mejora RETENCIÓN: hook 0–2s, 1 idea por pieza, ritmo alto y cortes.",
    "discovery":  "Impulsa DESCUBRIMIENTO: miniatura/gancho fuertes y promesa explícita."
}

_AD_BANNED = {
    "reserva","reservá","inscríbete","inscribete","gratis","descuento",
    "oferta","dm","plazas","cupo","pack","hoy"
}

_NICHE_KEYWORDS = {
    "tecnologia": [
        "API","API REST","Docker","Kubernetes","Python","IA","LLM",
        "Cloud","Seguridad","DevOps","Linux","SQL","NoSQL",
        "Backend","Frontend","GraphQL","Microservicios","CI/CD"
    ],
    "boxeo": ["guardia","jab","cross","hook","uppercut","footwork","sparring"],
    "fisioterapia": ["movilidad","isométricos","rotadores","escápula","lumbalgia","tendón","estiramiento"]
}

def _gen(prompt: str, temperature: float = 0.7) -> str:
    r = requests.post(
        f"{OLLAMA_HOST}/api/generate",
        json={
            "model": MODEL,
            "prompt": prompt,
            "temperature": temperature,
            "options": {"num_ctx": 4096, "top_p": 0.9, "top_k": 40, "repeat_penalty": 1.12},
            "stream": False
        },
        timeout=120
    )
    r.raise_for_status()
    return (r.json().get("response") or "").strip()

def _try_json(s: str) -> Dict[str, Any]:
    try:
        return json.loads(s)
    except Exception:
        m = re.search(r"\{[\s\S]*\}$", s.strip())
        if m:
            try: return json.loads(m.group(0))
            except Exception: pass
    return {}

def _strip_emojis(t: str) -> str:
    return re.sub(r'[\U0001F300-\U0001FAFF\U0001F900-\U0001F9FF\U0001F600-\U0001F64F\U00002600-\U000026FF\U00002700-\U000027BF]+', '', t)

def _looks_adlike(t: str) -> bool:
    low = t.lower()
    return any(k in low for k in _AD_BANNED)

def _remove_niche_prefix(t: str, niche: str) -> str:
    pat = re.compile(rf"^\s*{re.escape(niche)}\s*[:\-]\s*", flags=re.IGNORECASE)
    return pat.sub("", t).strip()

def _trim_and_len_ok(t: str, min_len: int = 28, max_len: int = 64) -> Tuple[str, bool]:
    t = t.strip()
    if len(t) > max_len:
        cut = t[:max_len].rstrip()
        if " " in cut:
            cut = cut[:cut.rfind(" ")].rstrip()
        t = cut
    return t, (len(t) >= min_len)

def _dedup(seq: List[str]) -> List[str]:
    out, seen = [], set()
    for x in seq:
        k = re.sub(r"\s+", " ", (x or "").strip().casefold())
        if k and k not in seen:
            seen.add(k); out.append((x or "").strip())
    return out

def _count_words(t: str) -> int:
    return len([w for w in re.split(r"\s+", t.strip()) if w])

def _quality_score(t: str, keys: List[str]) -> int:
    score, L = 0, len(t)
    if 38 <= L <= 60: score += 3
    elif 32 <= L <= 66: score += 2
    elif 28 <= L <= 72: score += 1
    if re.search(r"\d", t): score += 2
    if re.search(r"\bvs\b", t, flags=re.IGNORECASE): score += 2
    if ":" in t: score += 1
    hits = sum(1 for k in keys if k.lower() in t.lower())
    score += min(hits, 3) * 2
    if _looks_adlike(t): score -= 3
    if re.search(r"\b(básico|introducción|para\s+principiantes)\b", t, flags=re.IGNORECASE): score -= 1
    if _count_words(t) < 4: score -= 2
    return score

def _sanitize_titles(cands: List[str], niche: str) -> List[str]:
    out = []
    for c in cands or []:
        if not isinstance(c, str): continue
        txt = _strip_emojis(c)
        txt = _remove_niche_prefix(txt, niche)
        txt = re.sub(r"\s+", " ", txt).strip(" -–—·•")
        if not txt or _looks_adlike(txt): continue
        if not (re.search(r"\d", txt) or ":" in txt or re.search(r"\bvs\b", txt, re.I)):
            continue
        txt, ok_len = _trim_and_len_ok(txt)
        if ok_len and any(ch.isalpha() for ch in txt):
            out.append(txt)
    return _dedup(out)

def _fallback_titles(focus: str, niche: str) -> List[str]:
    n = niche.lower()
    if n == "tecnologia":
        pairs = [("SQL","NoSQL"),("Docker","VM"),("REST","GraphQL"),("Monolito","Microservicios")]
        singles = ["Docker","Kubernetes","Python","API REST","Seguridad","DevOps","Cloud","Linux"]
        base = [f"{a} vs {b}: cuándo elegir (60s)" for a,b in pairs]
        base += [f"{kw}: 3 errores al empezar" for kw in singles]
        base += [f"{kw}: checklist de despliegue (1 min)" for kw in ["Kubernetes","CI/CD","Cloud"]]
        base += [f"{kw}: lo que nadie te cuenta" for kw in ["API REST","DevOps","Docker"]]
        return base
    if focus == "retention":
        return [
            "Hook fuerte: ¿Estás haciendo esto mal?",
            "1 idea, 60s: paso a paso",
            "Caso práctico: de 0 a resultado",
            "Errores que te frenan (y solución)",
            "Mini tutorial: técnica correcta",
            "Comparativa rápida: A vs. B",
            "Checklist guardable"
        ]
    return [
        "Caso real: el cambio con este método",
        "Antes/después: qué marcó la diferencia",
        "Comparativa: enfoque A vs. B",
        "3 objeciones y cómo las resuelvo",
        "Preguntas frecuentes: respuesta clara",
        "Mini demo: del problema a la solución",
        "Resultado medible en 30 días"
    ]

def _rank_titles(titles: List[str], niche: str) -> List[str]:
    keys = _NICHE_KEYWORDS.get(niche.lower(), [])
    scored = [(t, _quality_score(t, keys)) for t in titles]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [t for t,_ in scored]

def llm_recommend(
    focus: str,
    niche: str,
    inputs: Dict[str, Any],
    examples: List[Dict[str, Any]],
    neighbors: List[Dict[str, Any]],
    temperature: float = 0.7,
    base_reason: str = ""
) -> Dict[str, Any]:
    ctx_titles: List[str] = []
    for row in (neighbors or []):
        t = row.get("title")
        if isinstance(t, str) and t.strip():
            ctx_titles.append(t.strip())
    for ex in (examples or []):
        t = ex.get("title")
        if isinstance(t, str) and t.strip():
            ctx_titles.append(t.strip())
    ctx_titles = _dedup(ctx_titles)[:6]

    keys = _NICHE_KEYWORDS.get(niche.lower(), [])
    hint = f"Incluye al menos 1 término de: {', '.join(keys)}." if keys else ""

    prompt = f"""
Eres un generador de títulos concisos para videos cortos en español.
Nicho: "{niche}". Enfoque: "{focus}".
Evita lenguaje de anuncio (no uses: {", ".join(sorted(_AD_BANNED))}).
{hint}
Obligatorio en cada título: 4+ palabras y al menos UNO de: un número, el separador ":" o "vs".
Longitud objetivo: 38–60 caracteres.

Salida EXCLUSIVA en JSON -> {{"ideas": ["título 1", "título 2", ...]}}
Hasta 10 ideas; sin emojis ni prefijos de nicho.

Ideas relacionadas (no copies literal):
- """ + ("\n- ".join(ctx_titles) if ctx_titles else "(sin contexto)") + """
"""

    raw = _gen(prompt, temperature=temperature)
    data = _try_json(raw)
    ideas_llm = [str(x) for x in (data.get("ideas") or [])] if isinstance(data, dict) else []

    # limpia y añade fallbacks
    cleaned_llm = _sanitize_titles(ideas_llm, niche)
    fallbacks = _sanitize_titles(_fallback_titles(focus, niche), niche)
    pool = _dedup(fallbacks + cleaned_llm)

    # si faltan, rellena con plantillas del nicho
    if len(pool) < 10:
        extra: List[str] = []
        for kw in keys[:10]:
            extra += [
                f"{kw}: 3 errores al empezar",
                f"{kw}: lo que nadie te cuenta",
                f"{kw}: guía rápida en 3 pasos"
            ]
            if len(extra) >= 20:
                break
        pool = _dedup(pool + _sanitize_titles(extra, niche))

    ideas = _rank_titles(pool, niche)[:10]
    return {"recommendation": REC_MAP.get(focus, focus), "reason": base_reason or "", "ideas": ideas}
