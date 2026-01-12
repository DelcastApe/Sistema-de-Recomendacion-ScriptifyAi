from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class Metrics(BaseModel):
    platform: Optional[str] = None
    niche: str
    format: Optional[str] = None

    # Conteos puros (usuario solo ingresa números)
    followers: Optional[int] = None
    impressions: Optional[int] = None
    reach: Optional[int] = None
    clicks: Optional[int] = None
    conversions: Optional[int] = None
    likes: Optional[int] = None
    saves: Optional[int] = None
    shares: Optional[int] = None
    comments: Optional[int] = None

    # Métricas opcionales (si las trae, las normalizamos 0–1)
    ctr: Optional[float] = None
    retention: Optional[float] = None
    avg_watch_pct: Optional[float] = None
    completion_rate: Optional[float] = None

    followers_change: Optional[int] = None
    freq: Optional[float] = None

    # Parámetros del sistema
    use_graph: bool = True
    top_k: Optional[int] = 5

class Recommendation(BaseModel):
    recommendation: str
    reason: str
    ideas: List[str]
    diagnostics: Dict[str, Any]
    examples: List[Dict[str, Any]]
