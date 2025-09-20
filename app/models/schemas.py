from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class Metrics(BaseModel):
    platform: Optional[str] = None
    niche: str
    format: Optional[str] = None
    ctr: Optional[float] = None
    retention: Optional[float] = None
    avg_watch_pct: Optional[float] = None
    completion_rate: Optional[float] = None
    impressions: Optional[int] = None
    reach: Optional[int] = None
    clicks: Optional[int] = None
    conversions: Optional[int] = None
    saves: Optional[int] = None
    shares: Optional[int] = None
    comments: Optional[int] = None
    followers_change: Optional[int] = None
    freq: Optional[float] = None
    # embeddings/grafo
    use_graph: bool = True
    top_k: Optional[int] = 5

class Recommendation(BaseModel):
    recommendation: str
    reason: str
    ideas: List[str]
    diagnostics: Dict[str, Any]
    examples: List[Dict[str, Any]] = []
