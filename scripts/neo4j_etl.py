# scripts/neo4j_etl.py
import os
import json
import argparse
from typing import Optional, List
import pandas as pd
from neo4j import GraphDatabase

# ======== ENV ========
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j")

# ======== Helpers ========
def clean_niche(x: Optional[str]) -> Optional[str]:
    if x is None:
        return None
    s = str(x).strip().lower()
    return None if s in {"", "nan", "none", "null"} else s

def clean_region(x: Optional[str]) -> str:
    s = (str(x or "")).strip().upper()
    return s if s else "GL"

def split_pipe(s: Optional[str]) -> List[str]:
    if not s or str(s).strip().lower() in {"nan", "none", "null"}:
        return []
    return [t.strip() for t in str(s).split("|") if t.strip()]

def split_tags_csv(s: Optional[str]) -> List[str]:
    if not s or str(s).strip().lower() in {"nan", "none", "null"}:
        return []
    return [t.strip().lower() for t in str(s).split(",") if t.strip()]

def run(session, q, **params):
    session.run(q, **params)

# ======== Esquema (solo UNIQUE, válido en Community) ========
SCHEMA = [
    "CREATE CONSTRAINT niche_id IF NOT EXISTS FOR (n:Niche) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT video_id IF NOT EXISTS FOR (v:Video) REQUIRE v.id IS UNIQUE",
    "CREATE CONSTRAINT tag_id   IF NOT EXISTS FOR (t:Tag)   REQUIRE t.id IS UNIQUE",
    "CREATE CONSTRAINT kw_id    IF NOT EXISTS FOR (k:TrendKeyword) REQUIRE k.id IS UNIQUE",
    "CREATE CONSTRAINT lex_id   IF NOT EXISTS FOR (l:Lexeme) REQUIRE l.id IS UNIQUE"
]

# ======== Cargas ========
def load_trends(session, path: str):
    df = pd.read_csv(path)
    # columnas esperadas: niche,keyword,region,timeframe,score,sources,seeds,source,score_norm
    need = {"keyword", "region", "timeframe"}
    missing = need - set(c.lower() for c in df.columns)
    if missing:
        raise SystemExit(f"[trends] Faltan columnas: {missing}")

    # normaliza nombres
    cols = {c: c.lower() for c in df.columns}
    df.rename(columns=cols, inplace=True)

    # limpieza
    df["niche"] = df.get("niche").map(clean_niche)
    df["region"] = df.get("region").map(clean_region)
    df["keyword"] = df.get("keyword").astype(str).str.strip().str.lower()
    df["timeframe"] = df.get("timeframe").astype(str).str.strip()

    q = """
    MERGE (k:TrendKeyword {id:$id})
    SET k.keyword=$kw, k.region=$region, k.score=$score, k.timeframe=$timeframe,
        k.sources=$sources, k.seeds=$seeds, k.score_norm=$score_norm
    WITH k, $niche AS niche
    FOREACH (_ IN CASE WHEN niche IS NULL THEN [] ELSE [1] END |
      MERGE (n:Niche {id:niche})
      MERGE (k)-[:IN_NICHE]->(n)
    )
    """
    count = 0
    for _, r in df.iterrows():
        run(session, q,
            id=f"kw::{r['region']}::{r['keyword']}",
            kw=r["keyword"],
            region=r["region"],
            score=float(r.get("score", 0) or 0.0),
            timeframe=r.get("timeframe") or "",
            sources=str(r.get("sources") or ""),
            seeds=str(r.get("seeds") or ""),
            score_norm=float(r.get("score_norm", 0) or 0.0),
            niche=r.get("niche")
        )
        count += 1
    print(f"[trends] OK -> {count} keywords")

def load_youtube(session, path: str):
    df = pd.read_csv(path)
    # columnas esperadas:
    # videoId,title,region,niche,content_type,views,likes,comments,engagement_rate,seconds,publishedAt,categoryTitle,tags,source
    need = {"videoid", "title", "region"}
    missing = need - set(c.lower() for c in df.columns)
    if missing:
        raise SystemExit(f"[youtube] Faltan columnas: {missing}")

    cols = {c: c.lower() for c in df.columns}
    df.rename(columns=cols, inplace=True)

    df["niche"] = df.get("niche").map(clean_niche)
    df["region"] = df.get("region").map(clean_region)
    df["tags"] = df.get("tags").apply(split_tags_csv)

    q_video = """
    MERGE (v:Video {id:$vid})
    SET v.title=$title,
        v.channel=$channel,
        v.region=$region,
        v.publishedAt=$publishedAt,
        v.views=$views,
        v.likes=$likes,
        v.comments=$comments,
        v.engagement=$engagement,
        v.seconds=$seconds,
        v.contentType=$ctype,
        v.category=$category,
        v.source=$source
    WITH v, $niche AS niche
    FOREACH (_ IN CASE WHEN niche IS NULL THEN [] ELSE [1] END |
      MERGE (n:Niche {id:niche})
      MERGE (v)-[:IN_NICHE]->(n)
    )
    """

    q_tag = """
    MERGE (t:Tag {id:$kid})
    SET t.text=$text
    WITH t
    MATCH (v:Video {id:$vid})
    MERGE (v)-[:HAS_TAG]->(t)
    WITH t, $niche AS niche
    FOREACH (_ IN CASE WHEN niche IS NULL THEN [] ELSE [1] END |
      MERGE (n:Niche {id:niche})
      MERGE (t)-[:IN_NICHE]->(n)
    )
    """

    count_v = 0
    count_t = 0
    for _, r in df.iterrows():
        vid = r["videoid"]
        niche_val = r.get("niche")
        region_val = r.get("region")
        title = r.get("title")
        channel = r.get("channeltitle") if "channeltitle" in df.columns else r.get("channel")
        publishedAt = r.get("publishedat") or ""
        views = int(r.get("views", 0) or 0)
        likes = int(r.get("likes", 0) or 0)
        comments = int(r.get("comments", 0) or 0)
        engagement = float(r.get("engagement_rate", 0) or 0.0)
        seconds = float(r.get("seconds", 0) or 0.0)
        ctype = r.get("content_type") or "Video"
        category = r.get("categorytitle") or ""
        source = r.get("source") or ""

        run(session, q_video,
            vid=vid,
            title=title,
            channel=channel,
            region=region_val,
            publishedAt=publishedAt,
            views=views, likes=likes, comments=comments,
            engagement=engagement, seconds=seconds,
            ctype=ctype, category=category, source=source,
            niche=niche_val
        )
        count_v += 1

        tags = r.get("tags") or []
        for tag in tags:
            kid = f"tag::{tag}"
            run(session, q_tag, kid=kid, text=tag, niche=niche_val, vid=vid)
            count_t += 1

    print(f"[youtube] OK -> {count_v} videos, {count_t} tags")

def load_lexicon(session, path: str):
    df = pd.read_csv(path)
    # columnas esperadas:
    # niche,region,top_keywords,top_tags,vocab,examples_json
    need = {"niche", "region"}
    missing = need - set(c.lower() for c in df.columns)
    if missing:
        raise SystemExit(f"[lexicon] Faltan columnas: {missing}")

    cols = {c: c.lower() for c in df.columns}
    df.rename(columns=cols, inplace=True)

    df["niche"] = df.get("niche").map(clean_niche)
    df["region"] = df.get("region").map(clean_region)

    q_niche_only = "MERGE (n:Niche {id:$id})"

    q_kw = """
    MERGE (l:Lexeme {id:$id})
    SET l.text=$text, l.kind='keyword'
    WITH l
    MERGE (n:Niche {id:$niche})
    MERGE (l)-[:IN_NICHE]->(n)
    """

    q_tag = """
    MERGE (t:Tag {id:$id})
    SET t.text=$text
    WITH t
    MERGE (n:Niche {id:$niche})
    MERGE (t)-[:IN_NICHE]->(n)
    """

    q_example_video = """
    MERGE (v:Video {id:$vid})
    SET v.title = coalesce($title, v.title),
        v.views = coalesce($views, v.views)
    WITH v
    MERGE (n:Niche {id:$niche})
    MERGE (v)-[:IN_NICHE]->(n)
    """

    count_rows = 0
    count_kw = 0
    count_tag = 0
    count_ex = 0

    for _, r in df.iterrows():
        niche = r.get("niche")
        if niche is None:
            continue
        # asegura el nodo Niche
        run(session, q_niche_only, id=niche)

        # keywords
        for kw in split_pipe(r.get("top_keywords")):
            lid = f"lex::{niche}::{kw.lower()}"
            run(session, q_kw, id=lid, text=kw.lower(), niche=niche)
            count_kw += 1

        # tags
        for tg in split_pipe(r.get("top_tags")):
            tid = f"tag::{tg.lower()}"
            run(session, q_tag, id=tid, text=tg.lower(), niche=niche)
            count_tag += 1

        # ejemplos
        ex_raw = r.get("examples_json")
        if isinstance(ex_raw, str) and ex_raw.strip():
            try:
                ex_list = json.loads(ex_raw)
                if isinstance(ex_list, list):
                    for ex in ex_list:
                        vid = ex.get("videoId") or ex.get("videoid")
                        if not vid:
                            continue
                        title = ex.get("title")
                        views = ex.get("views")
                        run(session, q_example_video, vid=vid, title=title, views=views, niche=niche)
                        count_ex += 1
            except Exception:
                pass

        count_rows += 1

    print(f"[lexicon] OK -> filas:{count_rows} | keywords:{count_kw} | tags:{count_tag} | examples:{count_ex}")

# ======== Main ========
def main():
    ap = argparse.ArgumentParser(description="ETL -> Neo4j (Trends + YouTube + Lexicon)")
    ap.add_argument("--trends",  required=True, help="CSV trends_keywords_merged_clean.csv")
    ap.add_argument("--youtube", required=True, help="CSV youtube_merged_clean.csv")
    ap.add_argument("--lexicon", required=True, help="CSV niche_lexicon_pack.csv")
    args = ap.parse_args()

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as s:
        # Schema
        for q in SCHEMA:
            run(s, q)

        # Cargas
        load_trends(s, args.trends)
        load_youtube(s, args.youtube)
        load_lexicon(s, args.lexicon)

    driver.close()
    print("[DONE] ETL completo.")

if __name__ == "__main__":
    main()
