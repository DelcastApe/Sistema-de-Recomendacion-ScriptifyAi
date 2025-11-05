# app/services/embeddings_neo4j.py
import os
import math
import requests
from typing import Any, Dict, List, Optional

from neo4j import GraphDatabase

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "28080808")

EMBED_PROVIDER = os.getenv("EMBED_PROVIDER", "ollama").lower()
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")

# Dim esperada por tu índice HNSW (768 para nomic-embed-text)
EXPECTED_DIM = int(os.getenv("EMBED_DIM", "768"))

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))


def _len_or_zero(x):
    try:
        return len(x)
    except Exception:
        return 0


def _embed_ollama(text: str) -> List[float]:
    """
    Hace embedding vía Ollama probando ambos formatos:
      1) {"input": "texto"} -> data['embedding']
      2) {"input": ["texto"]} -> data['embeddings'][0]
    Devuelve [] si no hay vector usable.
    """
    url = f"{OLLAMA_HOST}/api/embeddings"
    headers = {"Content-Type": "application/json"}

    # intento #1: forma simple
    try:
        r = requests.post(url, headers=headers, json={"model": EMBED_MODEL, "input": text}, timeout=30)
        r.raise_for_status()
        data = r.json()
        vec = data.get("embedding") or []
        if _len_or_zero(vec) > 0:
            return vec
    except Exception:
        pass

    # intento #2: forma batched
    try:
        r2 = requests.post(url, headers=headers, json={"model": EMBED_MODEL, "input": [text]}, timeout=30)
        r2.raise_for_status()
        data2 = r2.json()
        embs = data2.get("embeddings") or []
        if isinstance(embs, list) and embs and _len_or_zero(embs[0]) > 0:
            return embs[0]
    except Exception:
        pass

    return []


def _embed(text: str) -> List[float]:
    if EMBED_PROVIDER == "ollama":
        vec = _embed_ollama(text)
    else:
        vec = []
    return vec


def _check_dim(vec: List[float]) -> Optional[str]:
    if not vec:
        return "embedding vacío"
    if EXPECTED_DIM and len(vec) != EXPECTED_DIM:
        return f"dimensión {len(vec)} != {EXPECTED_DIM}"
    # NaN/Inf guard
    for v in vec:
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return "valores NaN/Inf en embedding"
    return None


def seed_embeddings(batch_size: int = 2000) -> Dict[str, Any]:
    """
    Busca videos sin embedding y les genera v.embedding con la dimensión esperada.
    """
    with driver.session() as session:
        # count candidatos
        q_cnt = """
        MATCH (v:Video)
        WHERE v.embedding IS NULL
        RETURN count(v) AS total
        """
        total = session.run(q_cnt).single()["total"]

        q_pick = """
        MATCH (v:Video)
        WHERE v.embedding IS NULL
        RETURN v.id AS id, v.title AS title
        LIMIT $batch
        """

        q_set = """
        MATCH (v:Video {id:$id})
        SET v.embedding = $emb
        """

        updated = 0
        tries = 0

        while updated < total and tries < 10:
            rows = list(session.run(q_pick, batch=batch_size))
            if not rows:
                break

            for row in rows:
                vid = row["id"]
                title = row["title"] or ""
                vec = _embed(title)
                err = _check_dim(vec)
                if err:
                    # si embedding falla, salta y continúa
                    continue
                session.run(q_set, id=vid, emb=vec)
                updated += 1

            tries += 1

        return {
            "ok": True,
            "total_candidates": total,
            "updated": updated,
            "dim": EXPECTED_DIM,
            "model": EMBED_MODEL,
            "provider": EMBED_PROVIDER,
        }


def vector_search(q: str, k: int = 5) -> Dict[str, Any]:
    """
    Genera embedding para la query y pregunta al índice.
    Devuelve ok=False si el embedding es vacío o dim incorrecta.
    """
    vec = _embed(q)
    err = _check_dim(vec)
    if err:
        return {
            "ok": False,
            "where": "vector-search",
            "error": f"Embeddings vacíos o inválidos desde {EMBED_PROVIDER}. ({err})",
        }

    cypher = """
    CALL db.index.vector.queryNodes('video_embedding_index', $limit, $vec)
    YIELD node, score
    RETURN node.videoId AS videoId,
           node.title AS title,
           node.engagement_rate AS engagement_rate,
           node.seconds AS seconds,
           node.publishedAt AS publishedAt,
           score
    LIMIT $k
    """
    with driver.session() as session:
        recs = []
        for r in session.run(cypher, limit=max(50, k), vec=vec, k=k):
            recs.append({
                "videoId": r["videoId"],
                "title": r["title"],
                "engagement_rate": r["engagement_rate"],
                "seconds": r["seconds"],
                "publishedAt": r["publishedAt"],
                "score": float(r["score"]),
            })
        return {
            "ok": True,
            "query": q,
            "k": k,
            "embed_dim": EXPECTED_DIM,
            "model": EMBED_MODEL,
            "provider": EMBED_PROVIDER,
            "results": recs[:k],
        }
