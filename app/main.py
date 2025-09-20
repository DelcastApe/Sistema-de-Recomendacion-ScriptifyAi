import os
from typing import List, Dict, Any
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from core.config import API_KEY
from models.schemas import Metrics, Recommendation
from graph.neo4j_repo import Neo4jRepository
from services.recommender import decide_focus, reason_for_focus, ideas_for_focus
from services.embeddings_neo4j import seed_embeddings, vector_search as vsvc
from services.llm_ollama import llm_recommend, REC_MAP

NEO4J_URI=os.getenv("NEO4J_URI","bolt://neo4j:7687")
NEO4J_USER=os.getenv("NEO4J_USER","neo4j")
NEO4J_PASSWORD=os.getenv("NEO4J_PASSWORD","28080808")

repo = Neo4jRepository(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)

app = FastAPI(title="Reco API", version="0.4.0")
app.add_middleware(CORSMiddleware,
    allow_origins=["http://localhost:3000","http://127.0.0.1:3000"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("shutdown")
def _shutdown():
    repo.close()

@app.get("/health")
def health():
    try:
        _ = repo.topic_counts()
        return {"status":"ok","db":1}
    except Exception as e:
        return {"status":"degraded","error":str(e)}

@app.get("/debug/topics")
def topics()->List[Dict[str,Any]]:
    return repo.topic_counts()

def graph_examples(niche: str, top_k: int) -> List[Dict[str, Any]]:
    rows = repo.examples_by_niche(niche, top_k)
    return [
        {"id": r.get("id"), "title": r.get("title"), "format": r.get("format"),
         "retention": r.get("retention"), "ctr": r.get("ctr"),
         "score": round(r.get("score", 0.0), 4), "topic": (niche or "").lower()}
        for r in rows
    ]

@app.post("/recommend", response_model=Recommendation)
def recommend(m: Metrics, x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    decision = decide_focus(m)
    focus = decision["focus"]

    base_reason = reason_for_focus(focus, m)
    base_reason = reason_for_focus(focus, m)
    base_reason = reason_for_focus(focus, m)
    base_reason = reason_for_focus(focus, m)
    rec_map = {
        "conversion": "Optimiza CONVERSIÓN: CTA claro, prueba social y congruencia promesa-landing.",
        "retention":  "Mejora RETENCIÓN: hook 0–2s, una sola idea, ritmo alto y cortes.",
        "discovery":  "Impulsa DESCUBRIMIENTO: miniatura/gancho fuertes y promesa explícita.",
    }
    recommendation = rec_map[focus]
    reason = reason_for_focus(focus, m)
    ideas = ideas_for_focus(focus, m.niche)

    examples: List[Dict[str, Any]] = []
    try:
        if m.use_graph:
            examples = graph_examples(m.niche, (m.top_k or 5))
    except Exception as e:
        reason += f" (Nota: no se pudo consultar ejemplos del grafo: {e})"

    return Recommendation(
        recommendation=recommendation,
        reason=reason,
        ideas=ideas,
        diagnostics={"focus": focus, "scores": decision["scores"], "inputs": m.dict()},
        examples=examples
    )

@app.post("/debug/seed-embeddings")
def seed_embeddings_endpoint(x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        stats = seed_embeddings(repo)
        return {"status":"ok", **stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/debug/vector-search")
def vector_search_endpoint(q: str, k: int = 5, x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        rows = vsvc(repo, q, k)
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/recommend/llm", response_model=Recommendation)
@app.post("/recommend/llm", response_model=Recommendation)
def recommend_llm(m: Metrics, x_api_key: str = Header(None), temperature: float = 0.7):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # 1) Heurística base: decide foco (conversion / retention / discovery)
    decision = decide_focus(m)
    focus = decision["focus"]
    base_reason = reason_for_focus(focus, m)

    # 2) Contexto: ejemplos del grafo + vecinos KNN
    examples: List[Dict[str, Any]] = []
    if m.use_graph:
        try:
            examples = graph_examples(m.niche, (m.top_k or 5))
        except Exception:
            examples = []
    neighbors: List[Dict[str, Any]] = []
    try:
        neighbors = vsvc(repo, f"{m.niche} {focus}", (m.top_k or 5))
    except Exception:
        neighbors = []

    # 3) LLM (Qwen vía Ollama) SOLO para títulos; reason = heurística
    out = llm_recommend(
        focus, m.niche, m.dict(),
        examples, neighbors,
        temperature=temperature,
        base_reason=base_reason
    )
    recommendation = out.get("recommendation", REC_MAP.get(focus, focus))
    reason = base_reason
    ideas = out.get("ideas") or ideas_for_focus(focus, m.niche)

    return Recommendation(
        recommendation=recommendation,
        reason=reason,
        ideas=ideas,
        diagnostics={"focus": focus, "scores": decision["scores"], "inputs": m.dict(), "llm": True},
        examples=examples or neighbors
    )

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
            "platform": "str|optional",
            "niche": "str|required",
            "format": "str|optional",
            "ctr": "float (0-1 o 0-100) opcional",
            "retention": "float (0-1 o 0-100) opcional",
            "avg_watch_pct": "float opcional",
            "completion_rate": "float opcional",
            "impressions": "int opcional",
            "reach": "int opcional",
            "clicks": "int opcional",
            "conversions": "int opcional",
            "saves": "int opcional",
            "shares": "int opcional",
            "comments": "int opcional",
            "followers_change": "int opcional",
            "freq": "float (posts/semana) opcional",
            "use_graph": "bool opcional",
            "top_k": "int opcional (default 5)"
        },
        "note": "Las métricas en % pueden enviarse como 0-1 o 0-100. El sistema normaliza."
    }
# PYBLOCKEND
