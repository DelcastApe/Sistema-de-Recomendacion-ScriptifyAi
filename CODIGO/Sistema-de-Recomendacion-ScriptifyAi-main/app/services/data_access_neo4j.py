import os
from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def _norm_region(region: Optional[str]) -> Optional[str]:
    if not region:
        return None
    return region.strip().upper()

def top_examples_by_niche(niche: str, region: Optional[str] = None, k: int = 8) -> List[Dict[str, Any]]:
    """Videos del nicho con mayor engagement_rate, opcionalmente filtrados por región."""
    region = _norm_region(region)
    q = """
    MATCH (v:Video)-[:IN_NICHE]->(n:Niche {name: $niche})
    OPTIONAL MATCH (v)-[:PUBLISHED_IN]->(r:Region)
    WHERE $region IS NULL OR r.code = $region
    RETURN v.videoId AS videoId,
           v.title AS title,
           v.engagement_rate AS engagement_rate,
           v.seconds AS seconds,
           v.publishedAt AS publishedAt,
           v.tags AS tags
    ORDER BY v.engagement_rate DESC NULLS LAST, v.views DESC NULLS LAST
    LIMIT $k
    """
    with driver.session() as s:
        res = s.run(q, niche=niche, region=region, k=k)
        return [r.data() for r in res]

def top_trends_by_niche(niche: str, region: Optional[str] = None, k: int = 25) -> List[str]:
    """Top keywords calientes (Google Trends normalizadas) para el nicho (+ región opcional)."""
    region = _norm_region(region)
    q = """
    MATCH (n:Niche {name: $niche})-[:HAS_KEYWORD]->(t:TrendKeyword)
    WHERE $region IS NULL OR t.region = $region
    RETURN t.keyword AS keyword, t.score_norm AS score
    ORDER BY t.score_norm DESC NULLS LAST
    LIMIT $k
    """
    with driver.session() as s:
        res = s.run(q, niche=niche, region=region, k=k)
        out = []
        for r in res:
            kw = r.get("keyword")
            if isinstance(kw, str) and kw.strip():
                out.append(kw.strip())
        return out

def niche_lexicon(niche: str, region: Optional[str] = None) -> Dict[str, Any]:
    """Devuelve top_keywords, top_tags, vocab del nodo Niche."""
    # región no siempre existe en el nodo; mantenemos firma homogénea por si a futuro lo particionas.
    q = """
    MATCH (n:Niche {name: $niche})
    RETURN n.top_keywords AS top_keywords,
           n.top_tags     AS top_tags,
           n.vocab        AS vocab
    """
    with driver.session() as s:
        rec = s.run(q, niche=niche).single()
        if not rec:
            return {"top_keywords": [], "top_tags": [], "vocab": []}
        def _as_list(x):
            return x if isinstance(x, list) else []
        return {
            "top_keywords": _as_list(rec.get("top_keywords")),
            "top_tags": _as_list(rec.get("top_tags")),
            "vocab": _as_list(rec.get("vocab"))
        }
