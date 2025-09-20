import os
API_KEY = os.getenv("API_KEY", "supersecreto")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "28080808")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
MODEL = os.getenv("MODEL", "qwen2.5:7b-instruct")
DEFAULT_TOP_K = int(os.getenv("TOP_K", "5"))
EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
