import os, requests
from typing import List, Dict, Any
from neo4j import GraphDatabase

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "28080808")

def _parse_embed_response(data: Dict[str, Any]) -> List[float]:
    if isinstance(data, dict) and isinstance(data.get("embedding"), list) and data["embedding"]:
        return data["embedding"]
    if isinstance(data, dict) and isinstance(data.get("embeddings"), list) and data["embeddings"]:
        first = data["embeddings"][0]
        if isinstance(first, list) and first:
            return first
    if isinstance(data, dict) and isinstance(data.get("data"), list) and data["data"]:
        emb = data["data"][0].get("embedding")
        if isinstance(emb, list) and emb:
            return emb
    return []

def _embed(text: str) -> List[float]:
    url = f"{OLLAMA_HOST}/api/embeddings"
    payloads = [
        {"model": EMBED_MODEL, "prompt": text},   # preferido por Ollama
        {"model": EMBED_MODEL, "input": text},    # fallback 1
        {"model": EMBED_MODEL, "input": [text]},  # fallback 2
    ]
    last_err = None
    for pl in payloads:
        try:
            r = requests.post(url, json=pl, timeout=60)
            r.raise_for_status()
            vec = _parse_embed_response(r.json())
            if isinstance(vec, list) and len(vec) > 0:
                return vec
        except Exception as e:
            last_err = e
    raise RuntimeError(f"Embeddings vacíos o respuesta inesperada de Ollama: {last_err}")

def _ensure_index(session, dim: int):
    if not isinstance(dim, int) or dim < 1 or dim > 4096:
        raise RuntimeError(f"Dimensión de embedding inválida: {dim}")
    session.run("DROP INDEX video_embedding_index IF EXISTS")
    session.run("""
    CREATE VECTOR INDEX video_embedding_index
    FOR (v:Video) ON (v.embedding)
    OPTIONS {
      indexConfig: {
        `vector.dimensions`: $dim,
        `vector.similarity_function`: 'cosine'
      }
    }
    """, dim=dim)

def seed_embeddings(_repo=None) -> Dict[str, Any]:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    updated = 0
    dim = None
    try:
        with driver.session() as s:
            rows = s.run("MATCH (v:Video) RETURN v.id AS id, v.title AS title ORDER BY id").data()
            if not rows:
                return {"updated": 0, "index": "video_embedding_index", "dim": 0}
            first_vec = _embed(rows[0]["title"])
            dim = len(first_vec)
            _ensure_index(s, dim)
            payload = [{"id": rows[0]["id"], "emb": first_vec}]
            for r in rows[1:]:
                v = _embed(r["title"])
                if len(v) != dim:
                    raise RuntimeError(f"Dimensión inconsistente en {r['id']}: {len(v)} != {dim}")
                payload.append({"id": r["id"], "emb": v})
            s.run("""
            UNWIND $rows AS row
            MATCH (v:Video {id: row.id})
            SET v.embedding = row.emb
            """, rows=payload)
            updated = len(payload)
    finally:
        driver.close()
    return {"updated": updated, "index": "video_embedding_index", "dim": dim or 0}

def vector_search(_repo, q: str, k: int = 5) -> List[Dict[str, Any]]:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        qvec = _embed(q)
        with driver.session() as s:
            res = s.run("""
                CALL db.index.vector.queryNodes('video_embedding_index', $k, $vec)
                YIELD node, score
                RETURN node.id AS id, node.title AS title, node.format AS format,
                       node.retention AS retention, node.ctr AS ctr, score
                ORDER BY score DESC
            """, vec=qvec, k=int(k)).data()
            return res
    finally:
        driver.close()
