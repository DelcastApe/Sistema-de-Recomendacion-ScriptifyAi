# app/services/graph_examples.py
import os
import re
from typing import Any, Dict, List, Optional
from neo4j import GraphDatabase

# ---- Neo4j driver (env .env o defaults)
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "password")

_DRIVER = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))

# ------------------------------------------------------------
# Query “payload”: examples (con videoId/url/hashtags_for_examples) + trends (o fallback)
# ------------------------------------------------------------
_PAYLOAD_QUERY = r"""
MATCH (n:Niche {name:$niche, region:$region})

// ------------ EXAMPLES + HASHTAGS LIMPIOS ------------
CALL {
  WITH n
  MATCH (n)<-[:BELONGS_TO]-(e:Example)
  OPTIONAL MATCH (e)-[:HAS_TAG]->(t:Tag)
  WITH e, collect(DISTINCT toLower(t.name)) AS rawTags,
       coalesce(e.publishedAt, datetime('1900-01-01')) AS p
  ORDER BY p DESC
  WITH e, rawTags
  // fallback desde título
  WITH e, rawTags, apoc.text.split(toLower(coalesce(e.title,'')), '[^\p{L}\p{N}]+') AS words
  WITH e, rawTags,
       [x IN rawTags |
         replace(replace(replace(replace(replace(replace(x,'á','a'),'é','e'),'í','i'),'ó','o'),'ú','u'),'ñ','n')
       ] AS tags_ascii,
       [x IN words |
         replace(replace(replace(replace(replace(replace(x,'á','a'),'é','e'),'í','i'),'ó','o'),'ú','u'),'ñ','n')
       ] AS words_ascii
  WITH e,
       [x IN tags_ascii  WHERE x <> '' AND size(x) >= 3 AND NOT x =~ '^[0-9].*'] AS tag_clean,
       [x IN words_ascii WHERE x <> '' AND size(x) >= 3 AND NOT x =~ '^[0-9].*'] AS word_clean
  WITH e,
       [x IN tag_clean  | '#' + replace(x,' ','')] AS tag_hashes,
       [x IN word_clean | '#' + replace(x,' ','')] AS word_hashes
  WITH e,
       CASE WHEN size(tag_hashes) > 0
            THEN apoc.coll.toSet(tag_hashes)[..3]
            ELSE apoc.coll.toSet(word_hashes)[..3]
       END AS hashtags
  RETURN collect({
    videoId:     e.videoId,
    url:         'https://youtu.be/' + e.videoId,
    title:       e.title,
    publishedAt: e.publishedAt,
    hashtags_for_examples: hashtags
  })[..$top_k] AS examples
}

// ------------ TRENDS (usa IN_TREND o cae a tags) ------------
CALL {
  WITH n
  MATCH (n)-[r:IN_TREND]->(k:Keyword)
  RETURN collect({
    keyword:    toLower(k.name),
    score:      coalesce(r.score,0.0),
    score_norm: coalesce(r.score_norm,0.0),
    timeframe:  r.timeframe,
    source:     r.source
  })[..$top_trends] AS trends_real
}
CALL {
  WITH n
  MATCH (n)<-[:BELONGS_TO]-(e:Example)
  OPTIONAL MATCH (e)-[:HAS_TAG]->(t:Tag)
  WITH toLower(t.name) AS keyword, count(DISTINCT e) AS score
  WHERE keyword IS NOT NULL
  ORDER BY score DESC, keyword
  RETURN collect({
    keyword:    keyword,
    score:      toFloat(score),
    score_norm: toFloat(score),
    timeframe:  'fallback-tags',
    source:     'derived'
  })[..$top_trends] AS trends_fallback
}
RETURN
  examples,
  CASE WHEN size(trends_real) > 0 THEN trends_real ELSE trends_fallback END AS trends
"""

def get_context_for_llm(
    niche: str,
    region: Optional[str],
    k: int = 15,
    ann_limit: int = 0,
    query_text: Optional[str] = None,
) -> Dict[str, Any]:
    """Lee Neo4j y devuelve examples (con videoId/url/hashtags_for_examples) y trends."""
    params = {
        "niche": (niche or "").lower().strip(),
        "region": (region or "GL").upper().strip(),
        "top_k": int(k or 15),
        "top_trends": 12,
    }
    with _DRIVER.session() as sess:
        rec = sess.run(_PAYLOAD_QUERY, **params).single()
        if not rec:
            return {"examples": [], "trends": [], "examples_list": []}
        examples = rec["examples"] or []
        trends = rec["trends"] or []
        # Compatibilidad con llamadas que esperan solo títulos
        examples_list = [{"title": e.get("title")} for e in examples if e.get("title")]
        return {"examples": examples, "trends": trends, "examples_list": examples_list}

# ---------------------------
# Utilidades RAG (fallbacks)
# ---------------------------

_STYLE_GUIDES = {
    "youtube": [
        "Evita intros largas; muestra el resultado al inicio",
        "Capítulos claros; CTA suave entre minuto 1 y 2",
    ],
    "shorts": [
        "Hook en 1–2s con resultado visual",
        "Texto grande y limpio; cortes rápidos",
    ],
    "tiktok": [
        "Formato 9:16 con subtítulos auto",
        "Cortes cada 2–3s; una sola idea por video",
    ],
    "instagram": [
        "Abre con el beneficio en la primera frase",
        "Visual claro del resultado; texto breve",
    ],
}

_BANNED_ANALOGIES = [
    "tabs vs spaces",
    "iceberg",
    "caballo de troya",
    "montaña rusa",
    "final de fútbol",
]

def _normalize_token(s: str) -> str:
    s = (s or "").lower()
    s = (
        s.replace("á", "a").replace("é", "e").replace("í", "i")
         .replace("ó", "o").replace("ú", "u").replace("ñ", "n")
    )
    s = re.sub(r"[^a-z0-9\-\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _extract_top_keywords_from_titles(titles: List[str], limit: int = 20) -> List[str]:
    stop = {
        "de","la","el","los","las","y","o","u","para","por","en","del","con","sin",
        "una","un","uno","al","lo","que","como","sus","su","tu","mi","se","es",
        "vs","vs.","en","sobre","guia","paso","checklist","errores","tutorial"
    }
    freq: Dict[str, int] = {}
    for t in titles:
        toks = _normalize_token(t).split()
        for w in toks:
            if len(w) < 3 or w in stop:
                continue
            freq[w] = freq.get(w, 0) + 1
    sorted_kw = [w for w, _ in sorted(freq.items(), key=lambda x: (-x[1], x[0]))]
    return sorted_kw[:limit] if sorted_kw else []

def _expand_terms_fallback(terms: List[str], k: int = 6) -> List[str]:
    acc = set()
    for t in terms or []:
        n = _normalize_token(t)
        if not n:
            continue
        acc.add(n)
        if n.endswith("s"):
            acc.add(n[:-1])
        if "-" in n:
            acc.update(n.split("-"))
    return list(sorted(acc))[:max(k, len(acc))]

def build_llm_context(
    niche: str,
    specialties: List[str],
    platform: Optional[str] = None,
    top_k: int = 10,
    region: Optional[str] = None,
    preset_examples: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    # 1) Ejemplos (full) + trends desde Neo4j si no vienen pre-seteados
    if preset_examples is not None:
        examples = preset_examples
        trends = []
    else:
        ctx = get_context_for_llm(niche=niche, region=region, k=max(top_k, 10))
        examples = ctx.get("examples") or []
        trends = ctx.get("trends") or []

    example_titles = [e.get("title") for e in examples if e.get("title")]

    # 2) Glosario fallback desde títulos
    glossary = _extract_top_keywords_from_titles(example_titles, limit=20)
    if not glossary and niche:
        glossary = [_normalize_token(niche)]

    # 3) Expansión sencilla de specialties (fallback)
    expanded = _expand_terms_fallback(specialties, k=8)

    # 4) Style por plataforma
    style = _STYLE_GUIDES.get((platform or "").lower(), [])

    return {
        "glossary": glossary,
        "expanded_specialties": expanded,
        "example_titles": example_titles[:top_k],
        "style_guides": _STYLE_GUIDES,
        "style_for_platform": style,
        "banned_analogies": _BANNED_ANALOGIES,
        "trends": trends,
        "examples_full": examples,
    }
