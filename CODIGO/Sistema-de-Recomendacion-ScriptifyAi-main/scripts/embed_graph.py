# scripts/embed_graph.py
import os
import time
import json
import requests
from neo4j import GraphDatabase
from dotenv import load_dotenv

DIM = 768  # nomic-embed-text
BATCH = 40
SLEEP = (0.2, 0.6)

def get_driver():
    load_dotenv()
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    pwd  = os.getenv("NEO4J_PASSWORD", "neo4j")
    return GraphDatabase.driver(uri, auth=(user, pwd))

def embed(texts):
    base = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    model = os.getenv("EMBED_MODEL", "nomic-embed-text")
    resp = requests.post(f"{base}/api/embeddings", json={"model": model, "input": texts}, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    # Ollama devuelve {"embeddings":[...]} o {"data":[{"embedding":[...]}...]}
    if "embeddings" in data:
        return data["embeddings"]
    if "data" in data:
        return [d["embedding"] for d in data["data"]]
    raise RuntimeError(f"Formato inesperado embeddings: {data}")

SCHEMA = [
    # Vector index para Video
    f"""
    CREATE VECTOR INDEX video_embedding_index
    IF NOT EXISTS FOR (v:Video) ON (v.embedding)
    OPTIONS {{
      indexConfig: {{
        `vector.dimensions`: {DIM},
        `vector.similarity_function`: 'cosine'
      }}
    }}
    """,
    # Vector index para Keyword
    f"""
    CREATE VECTOR INDEX keyword_embedding_index
    IF NOT EXISTS FOR (k:Keyword) ON (k.embedding)
    OPTIONS {{
      indexConfig: {{
        `vector.dimensions`: {DIM},
        `vector.similarity_function`: 'cosine'
      }}
    }}
    """,
]

Q_SELECT_V = """
MATCH (v:Video)
WHERE v.embedding IS NULL
RETURN v.videoId AS id, coalesce(v.title,'') + ' | ' + coalesce(v.niche,'') + ' | ' + coalesce(v.region,'') AS text
LIMIT $lim
"""

Q_UPDATE_V = """
UNWIND $rows AS row
MATCH (v:Video {videoId: row.id})
SET v.embedding = row.vec
"""

Q_SELECT_K = """
MATCH (k:Keyword)
WHERE k.embedding IS NULL
RETURN k.id AS id, coalesce(k.text,'') + ' | ' + coalesce(k.niche,'') + ' | ' + coalesce(k.region,'') AS text
LIMIT $lim
"""

Q_UPDATE_K = """
UNWIND $rows AS row
MATCH (k:Keyword {id: row.id})
SET k.embedding = row.vec
"""

def create_indexes(session):
    for q in SCHEMA:
        session.run(q)

def process_label(session, select_q, update_q, label):
    total = 0
    while True:
        res = session.run(select_q, lim=BATCH).data()
        if not res: break
        texts = [r["text"] for r in res]
        ids = [r["id"] for r in res]
        vecs = embed(texts)
        rows = [{"id": i, "vec": v} for i, v in zip(ids, vecs)]
        session.run(update_q, rows=rows)
        total += len(rows)
        time.sleep(0.3)
    print(f"[{label}] Embeddings generados: {total}")

def main():
    drv = get_driver()
    with drv.session() as s:
        create_indexes(s)
        process_label(s, Q_SELECT_V, Q_UPDATE_V, "Video")
        process_label(s, Q_SELECT_K, Q_UPDATE_K, "Keyword")
    drv.close()
    print("[DONE] Embeddings listos.")

if __name__ == "__main__":
    main()
