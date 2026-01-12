from typing import List, Dict, Any
from neo4j import GraphDatabase

class Neo4jRepository:
    def __init__(self, uri: str, user: str, password: str):
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        try:
            self._driver.close()
        except Exception:
            pass

    def topic_counts(self) -> List[Dict[str, Any]]:
        q = """
        MATCH (t:Topic)<-[:TIENE_TEMA]-(v:Video)
        RETURN t.name AS topic, count(v) AS count
        ORDER BY topic
        """
        with self._driver.session() as s:
            return s.run(q).data()

    def examples_by_niche(self, niche: str, k: int) -> List[Dict[str, Any]]:
        q = """
        MATCH (t:Topic {name:$niche})<-[:TIENE_TEMA]-(v:Video)
        WITH v, coalesce(v.retention,0.0) AS r, coalesce(v.ctr,0.0) AS c
        RETURN v.id AS id, v.title AS title, v.format AS format,
               toFloat(r) AS retention, toFloat(c) AS ctr,
               (0.6*toFloat(r) + 0.4*toFloat(c)) AS score
        ORDER BY score DESC, title ASC
        LIMIT $k
        """
        with self._driver.session() as s:
            return s.run(q, niche=niche.lower(), k=k).data()

    def videos_for_embeddings(self) -> List[Dict[str, Any]]:
        q = """
        MATCH (v:Video)-[:TIENE_TEMA]->(t:Topic)
        RETURN v.id AS id, v.title AS title, coalesce(v.description,'') AS description, t.name AS topic
        ORDER BY title
        """
        with self._driver.session() as s:
            return s.run(q).data()

    def ensure_vector_index(self, dim: int):
        q = """
        CREATE VECTOR INDEX video_embedding_index IF NOT EXISTS
        FOR (v:Video) ON (v.embedding)
        OPTIONS { indexConfig: {
          `vector.dimensions`: $dim,
          `vector.similarity_function`: 'cosine'
        } }
        """
        with self._driver.session() as s:
            s.run(q, dim=dim)

    def set_video_embedding(self, vid: str, emb: List[float]):
        q = """
        MATCH (v:Video {id:$id})
        SET v.embedding = $emb
        RETURN v.id AS id
        """
        with self._driver.session() as s:
            s.run(q, id=vid, emb=emb)

    def vector_search(self, emb: List[float], k: int = 5) -> List[Dict[str, Any]]:
        q = """
        CALL db.index.vector.queryNodes('video_embedding_index', $k, $emb)
        YIELD node, score
        RETURN node.id AS id, node.title AS title, node.format AS format,
               coalesce(node.retention,0.0) AS retention, coalesce(node.ctr,0.0) AS ctr,
               score
        ORDER BY score DESC
        """
        with self._driver.session() as s:
            return s.run(q, emb=emb, k=k).data()
