import os
from typing import Optional, List, Dict, Any

from llama_index.core import Settings
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding

# ----------------------------------------------------------------------
# Inicialización explícita de LlamaIndex con Ollama (sin resolver defaults)
# ----------------------------------------------------------------------

def _init_llamaindex_once() -> None:
    """
    Fija Settings.llm y Settings.embed_model con Ollama, evitando acceder
    a Settings.llm antes de tiempo (lo que forzaría resolver el backend 'default').
    """
    # Lee envs (con defaults razonables)
    base_url = os.getenv("OLLAMA_HOST", "http://ollama:11434").rstrip("/")
    model = os.getenv("MODEL", "qwen2.5:7b-instruct")
    embed_model = os.getenv("EMBED_MODEL", "nomic-embed-text")

    # Asigna SIEMPRE sin consultar Settings.llm (evita resolver OpenAI)
    Settings.llm = Ollama(model=model, base_url=base_url, request_timeout=500.0)
    Settings.embed_model = OllamaEmbedding(model_name=embed_model, base_url=base_url)


# Ejecuta la init en import
_init_llamaindex_once()

# ----------------------------------------------------------------------
# Utilidades opcionales (wrapper simple por si quieres probar el LLM)
# ----------------------------------------------------------------------

def generate_with_llamaindex(prompt: str, system: Optional[str] = None, **kwargs) -> str:
    """
    Wrapper sencillo para invocar el LLM de Settings.llm.
    No usa OpenAI; va directo contra Ollama (ya fijado arriba).
    """
    llm: Ollama = Settings.llm  # type: ignore
    if system:
        # Los backends de Ollama vía LlamaIndex no tienen "system" explícito;
        # lo concatenamos de forma simple.
        full_prompt = f"[SYSTEM]\n{system}\n\n[USER]\n{prompt}"
    else:
        full_prompt = prompt
    resp = llm.complete(full_prompt, **kwargs)
    # resp puede ser un objeto con .text o una string, según versión
    return getattr(resp, "text", str(resp))


def get_embed(texts: List[str]) -> List[List[float]]:
    """Embeddings desde OllamaEmbedding configurado en Settings.embed_model."""
    em = Settings.embed_model  # type: ignore
    vecs = em.get_text_embedding_batch(texts)
    return vecs
