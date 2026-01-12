import os
import math
import json
import re
import datetime
from typing import Any, Dict, List

from fastapi import FastAPI, Request, Query, Header, HTTPException
from fastapi.responses import PlainTextResponse
from starlette.responses import JSONResponse
from pydantic import BaseModel

from services.graph_examples import get_context_for_llm
from services.llm_ollama import llm_recommend
from services.recommender import Metrics, decide_focus, reason_for_focus, infer_rates
from services.embeddings_neo4j import seed_embeddings as v_seed, vector_search as v_search

# ---- Neo4j DateTime compat
try:
    from neo4j.time import DateTime as NeoDateTime, Date as NeoDate
except Exception:
    NeoDateTime = None  # type: ignore
    NeoDate = None      # type: ignore

API_KEY = os.getenv("API_KEY", "supersecreto")

class Recommendation(BaseModel):
    recommendation: str
    reason: str
    ideas: List[str]
    diagnostics: Dict[str, Any]
    examples: List[Dict[str, Any]] = []
    ideas_by_focus: Dict[str, List[str]] = {}
    hashtags_by_focus: Dict[str, List[str]] = {}

app = FastAPI()

# -----------------------------
# Utilidades de saneo de JSON
# -----------------------------

def _to_iso(val: Any) -> str:
    if NeoDateTime is not None and isinstance(val, NeoDateTime):
        try: return val.to_native().isoformat()
        except Exception: return str(val)
    if NeoDate is not None and isinstance(val, NeoDate):
        try: return val.to_native().isoformat()
        except Exception: return str(val)
    if isinstance(val, (datetime.datetime, datetime.date)):
        try: return val.isoformat()
        except Exception: return str(val)
    return str(val)

def _clean_json(x: Any):
    if isinstance(x, float):
        if math.isnan(x) or math.isinf(x): return None
        return x
    if NeoDateTime is not None and isinstance(x, NeoDateTime):
        return _to_iso(x)
    if NeoDate is not None and isinstance(x, NeoDate):
        return _to_iso(x)
    if isinstance(x, (datetime.datetime, datetime.date)):
        return _to_iso(x)
    if isinstance(x, dict):
        return {k: _clean_json(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_clean_json(v) for v in x]
    if isinstance(x, (set, tuple)):
        return [_clean_json(v) for v in x]
    try:
        json.dumps(x)
        return x
    except Exception:
        return str(x)

# -----------------------------
# Endpoints
# -----------------------------

@app.get("/health")
def health():
    return {"status": "ok", "db": 1}

@app.get("/health/ollama")
def health_ollama():
    import requests
    try:
        r = requests.get(os.getenv("OLLAMA_HOST","http://ollama:11434")+"/api/tags", timeout=5)
        r.raise_for_status()
        data = r.json()
        ok = any(isinstance(m, dict) and "model" in m for m in data.get("models", [])) or bool(data)
        return {"status": "ok" if ok else "degraded"}
    except Exception as e:
        return {"status": "down", "error": str(e)}

@app.get("/recommend/schema")
def recommend_schema():
    return {
        "fields": {
            "platform": "str|optional (youtube|shorts|tiktok|instagram|reels|...)",
            "niche": "str|required",
            "region": "str opcional (p.ej. ES, MX)",
            "format": "str|optional",
            "followers": "int opcional",
            "impressions": "int opcional",
            "reach": "int opcional",
            "clicks": "int opcional",
            "conversions": "int opcional",
            "likes": "int opcional",
            "shares": "int opcional",
            "saves": "int opcional",
            "comments": "int opcional",
            "ctr": "float (0-1 o 0-100) opcional",
            "retention": "float (0-1 o 0-100) opcional",
            "avg_watch_pct": "float opcional",
            "completion_rate": "float opcional",
            "followers_change": "int opcional",
            "freq": "float (posts/semana) opcional",
            "specialties": "list[str] opcional",
            "use_graph": "bool opcional",
            "top_k": "int opcional (default 5)"
        },
        "note": "Si solo pasas conteos, el sistema infiere señales (poca gente entra / se van pronto / cuesta siguiente paso) sin jerga."
    }

@app.post("/debug/seed-embeddings")
def debug_seed_embeddings(x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return v_seed()

@app.get("/debug/vector-search")
def debug_vector_search(q: str = Query(...), k: int = Query(5), x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return v_search(q, k)

@app.post("/recommend")
def recommend(m: Metrics, x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    m = infer_rates(m)
    decision = decide_focus(m)
    focus = decision["focus"]

    recommendation = f"Sugerencia base para foco={focus}"
    reason = reason_for_focus(focus, m)
    ideas: List[str] = []

    payload = Recommendation(
        recommendation=recommendation,
        reason=reason,
        ideas=ideas,
        diagnostics={"focus": focus, "scores": decision["scores"], "inputs": m.dict()},
        examples=[]
    )
    return _clean_json(payload.dict())

@app.post("/recommend/llm")
async def recommend_llm(
    request: Request,
    pretty: int = Query(default=0),
    temperature: float = Query(default=0.7),
    x_api_key: str = Header(default="")
):
    expected = os.getenv("API_KEY", "supersecreto")
    if x_api_key != expected:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    try:
        payload_in = await request.json()
    except Exception:
        payload_in = {}

    platform = (payload_in or {}).get("platform")
    niche = (payload_in or {}).get("niche") or ""
    region = (payload_in or {}).get("region")
    top_k = int((payload_in or {}).get("top_k") or 10)

    inputs = {
        "platform": platform,
        "niche": niche,
        "format": (payload_in or {}).get("format"),
        "ctr": (payload_in or {}).get("ctr"),
        "retention": (payload_in or {}).get("retention"),
        "avg_watch_pct": (payload_in or {}).get("avg_watch_pct"),
        "completion_rate": (payload_in or {}).get("completion_rate"),
        "impressions": (payload_in or {}).get("impressions"),
        "reach": (payload_in or {}).get("reach"),
        "clicks": (payload_in or {}).get("clicks"),
        "conversions": (payload_in or {}).get("conversions"),
        "followers": (payload_in or {}).get("followers"),
        "likes": (payload_in or {}).get("likes"),
        "shares": (payload_in or {}).get("shares"),
        "saves": (payload_in or {}).get("saves"),
        "comments": (payload_in or {}).get("comments"),
        "followers_change": (payload_in or {}).get("followers_change"),
        "freq": (payload_in or {}).get("freq"),
        "specialties": (payload_in or {}).get("specialties") or [],
        "use_graph": True,
        "top_k": top_k,
        "region": region,
    }

    # --- NUEVO: calcular foco y pasarlo como hint al LLM
    try:
        m_for_focus = Metrics(
            platform=inputs.get("platform"),
            niche=inputs.get("niche"),
            impressions=inputs.get("impressions"),
            reach=inputs.get("reach"),
            likes=inputs.get("likes"),
            shares=inputs.get("shares"),
            saves=inputs.get("saves"),
            comments=inputs.get("comments"),
            ctr=inputs.get("ctr"),
            retention=inputs.get("retention"),
            avg_watch_pct=inputs.get("avg_watch_pct"),
            completion_rate=inputs.get("completion_rate"),
            followers=inputs.get("followers"),
            freq=inputs.get("freq"),
        )
        m_for_focus = infer_rates(m_for_focus)
        decision = decide_focus(m_for_focus)
        inputs["focus_hint"] = decision.get("focus", "attract")
    except Exception:
        inputs["focus_hint"] = "attract"

    # 1) Contexto desde Neo4j (examples completos + trends)
    ctx = get_context_for_llm(
        niche=niche,
        region=region,
        k=max(top_k, 10),
        ann_limit=max(2 * top_k, 12),
        query_text=None
    )
    examples_full = ctx.get("examples") or []
    trends = ctx.get("trends") or []

    # 2) LLM (con RAG). Le pasamos los examples completos.
    draft = llm_recommend(
        focus="",
        niche=niche,
        metrics={"inputs": inputs},
        examples=examples_full,
        neighbors=[],
        temperature=temperature
    )

    payload = {
        "recommendation": draft.get("recommendation"),
        "reason": draft.get("reason"),
        "ideas": draft.get("ideas") or [],
        "diagnostics": {
            "focus": "personalized",
            "inputs": inputs,
            "llm": True,
            "note": "Agente experto: interpreta señales y devuelve consejo humano (sin jerga). Ejemplos YouTube como referencia para cualquier plataforma.",
            "trends": trends,
        },
        "examples": examples_full[:max(top_k, 10)],
        "hashtags_for_ideas": draft.get("hashtags_for_ideas") or [],
        "hashtags_for_examples": draft.get("hashtags_for_examples") or [],
    }

    safe = _clean_json(payload)

    if pretty:
        return PlainTextResponse(json.dumps(safe, ensure_ascii=False, indent=2), media_type="application/json")
    return JSONResponse(safe)

# -----------------------------
# Feedback endpoints (opcionales)
# -----------------------------

@app.post("/feedback/like")
async def feedback_like(request: Request, x_api_key: str = Header(default="")):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        body = await request.json()
    except Exception:
        body = {}

    niche = (body or {}).get("niche") or ""
    idea_title = (body or {}).get("idea") or ""
    specialties = (body or {}).get("specialties") or []

    toks = _simple_tokenize(idea_title)
    return _clean_json({"ok": True, "niche": niche, "specialties": specialties, "tokens": toks})

# ---------- helpers para feedback ---------

def _simple_norm(s: str) -> str:
    s = (s or "").lower()
    s = s.replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ú","u").replace("ñ","n")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()

def _simple_tokenize(title: str) -> List[str]:
    t = _simple_norm(title)
    return [w for w in t.split() if len(w) >= 3]
