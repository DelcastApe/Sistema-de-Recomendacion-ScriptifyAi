# app/services/llamaindex_client.py
import os
from typing import Optional

from llama_index.core import Settings
from llama_index.llms.ollama import Ollama

_MODEL = os.getenv("MODEL", "qwen2.5:7b-instruct")
_OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")

_llm_singleton: Optional[Ollama] = None

def get_llm() -> Ollama:
    """
    Crea (si no existe) y devuelve el cliente Ollama compartido para todo el proceso.
    Subimos el request_timeout para evitar timeouts en pulls fríos/modelos pesados.
    """
    global _llm_singleton
    if _llm_singleton is None:
        _llm_singleton = Ollama(
            model=_MODEL,
            base_url=_OLLAMA_HOST,
            request_timeout=300,  # ⬅️ timeout alto para evitar errores ReadTimeout
        )
        Settings.llm = _llm_singleton
    return _llm_singleton
