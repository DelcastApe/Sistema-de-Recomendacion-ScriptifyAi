
---

# Scriptify AI — Sistema de Recomendación de Contenidos (RAG + LLM)

Motor de recomendaciones para **ideas de contenido** y **guías accionables** orientadas a redes (YouTube/Shorts/TikTok/IG).
Combina **RAG** con un **grafo Neo4j** (nichos, ejemplos reales, tendencias) y un **LLM** (Ollama vía LlamaIndex) para producir:

* `recommendation`: 1 frase clara que incluya alguna *specialty*.
* `reason`: párrafo con analogía original + **exactamente 4 bullets** accionables (formato `- `).
* `ideas`: 10–12 títulos útiles (mix directos/creativos).
* `hashtags_for_ideas`: 2–3 hashtags por idea (limpios, sin tildes ni genéricos).
* Opcional: `examples` y `trends` derivados del grafo (si hay datos).

---

## 🧱 Arquitectura

* **FastAPI** (API REST)
* **Ollama + LlamaIndex** (LLM local o remoto)
* **Neo4j** (grafo con `Niche`, `Example`, `Keyword` y relaciones como `BELONGS_TO`, `HAS_TAG`, `IN_TREND`)
* **RAG** en `services/graph_examples.py` → construye contexto (glosario, trends, ejemplos)
* **Saneado/validación** en `services/llm_ollama.py` → corrige spanglish, hashtags vacíos, bullets, etc.

```
client → FastAPI (/recommend/llm) → LlamaIndex(Ollama)
                          ↘
                           Neo4j (examples + trends → vocab/hashtags)
```

---

## 🚀 Inicio rápido

### 1) Requisitos

* Docker + Docker Compose
* (Opcional) Python 3.11+ si quieres ejecutar local sin contenedores
* **Neo4j** con APOC habilitado y datos de `Niche/Example/Keyword`
* **Ollama** con un modelo disponible (ej. `llama3.1` o el que uses)

### 2) Variables de entorno

Crea un `.env` (o exporta en tu shell) con algo como:

```env
API_KEY=supersecreto
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=pass
NEO4J_DB=neo4j

# Dirección del servidor de Ollama al que se conectará la API
OLLAMA_HOST=http://ollama:11434
OLLAMA_MODEL=llama3.1:latest
LLM_TIMEOUT=60
```

> Si corres Ollama fuera de Docker en tu máquina: `OLLAMA_HOST=http://host.docker.internal:11434`.

### 3) Docker Compose

```bash
docker compose up -d --build
docker compose logs -f api
```

Verás:

```
Uvicorn running on http://0.0.0.0:8000
```

---

## 📚 Endpoints

### 🔹 `POST /recommend/llm`

Genera recomendación + ideas. **Requiere** header `x-api-key`.

**Headers**

```
x-api-key: supersecreto
Content-Type: application/json
```

**Request (ejemplo Tecnología + XR)**

```json
{
  "platform": "youtube",
  "niche": "tecnologia",
  "impressions": 90000,
  "reach": 72000,
  "clicks": 880,
  "followers": 41000,
  "likes": 2800,
  "shares": 210,
  "saves": 360,
  "comments": 230,
  "specialties": ["realidad virtual", "realidad mixta", "webxr", "xr"],
  "use_graph": true,
  "top_k": 8
}
```

> **Nota**: En la UI el usuario no introduce `avg_watch_pct` ni `completion_rate`. Si tu backend los necesita, usa defaults.

**cURL**

```bash
curl -sS -X POST "http://localhost:8000/recommend/llm?pretty=1" \
  -H "x-api-key: supersecreto" -H "Content-Type: application/json" \
  --data-binary @/tmp/req_tecnologia_xr.json | jq .
```

**Response (resumen)**

```json
{
  "recommendation": "Realidad mixta para retener: explora los mejores casos de uso.",
  "reason": "Señales: ... - bullet1 - bullet2 - bullet3 - bullet4",
  "ideas": ["...", "..."],
  "hashtags_for_ideas": [["#realidadmixta","#webxr"], ...],
  "examples": [
    {"title": "...", "videoId": "...", "publishedAt": "2025-10-10T15:00:54+00:00", "hashtags_for_examples": ["#..."] }
  ],
  "diagnostics": { "inputs": { ... }, "llm": true }
}
```

### 🔹 `POST /feedback/like`

Registra un “me gusta” de una **idea** para el nicho (puedes usarlo para reforzar tendencias futuras).

**Body**

```json
{
  "niche": "tecnologia",
  "region": "GL",
  "idea": "Comparativa: Realidad Virtual vs Realidad Mixta",
  "specialties": ["realidad virtual", "realidad mixta"]
}
```

**cURL**

```bash
curl -sS -X POST "http://localhost:8000/feedback/like" \
  -H "x-api-key: supersecreto" -H "Content-Type: application/json" \
  --data-binary @/tmp/feedback_like.json | jq .
```

---

## 🧠 Contexto RAG desde el grafo

El servicio intenta traer de Neo4j:

* **examples** (títulos y hashtags limpios)
* **trends** (palabras clave con score)

Ambos alimentan:

* `glossary` (a partir de títulos)
* `trends_tokens` (bias de hashtags/títulos)
* Vocabulario permitido para **hashtags** (evita genéricos y ruido)

### Ejemplo de Cypher (hashtags limpios por ejemplo)

```cypher
WITH [
  'the','and','for','con','por','las','los','una','unos','unas','que','como','para','consejos',
  'del','de','la','el','un','en','por','tu','sus','mis','muy','mas','más','sin','son','soy',
  'esa','ese','esto','esta','este','cuando','donde','dónde','qué','que','cómo','cual','cuál',
  'sobre','entre','desde','hasta','solo','sólo','todo','toda','todos','todas','aqui','aquí',
  'ahora','hoy','pero','porque','porqué','ya','no','si','sí','al','lo','se','una','un','y','o'
] AS STOP

MATCH (n:Niche {name:'automotriz', region:'GL'})<-[:BELONGS_TO]-(e:Example)
OPTIONAL MATCH (e)-[:HAS_TAG]->(t:Tag)
WITH e, STOP, collect(DISTINCT toLower(t.name)) AS rawTags
WITH e, STOP, rawTags, apoc.text.split(toLower(coalesce(e.title,'')), '[^\\p{L}\\p{N}]+') AS words
WITH e, STOP, rawTags, words,
     [x IN rawTags | replace(replace(replace(replace(replace(replace(x,'á','a'),'é','e'),'í','i'),'ó','o'),'ú','u'),'ñ','n')] AS tags_ascii,
     [x IN words   | replace(replace(replace(replace(replace(replace(x,'á','a'),'é','e'),'í','i'),'ó','o'),'ú','u'),'ñ','n')] AS words_ascii
WITH e,
     [x IN tags_ascii  WHERE x <> '' AND size(x) >= 3 AND NOT x =~ '^[0-9].*'] AS tag_clean,
     [x IN words_ascii WHERE x <> '' AND size(x) >= 3 AND NOT x =~ '^[0-9].*'] AS word_clean
WITH e,
     [x IN tag_clean  | '#' + replace(x,' ','')] AS tag_hashes,
     [x IN word_clean | '#' + replace(x,' ','')] AS word_hashes
WITH e,
     CASE WHEN size(tag_hashes) > 0 THEN apoc.coll.toSet(tag_hashes)[..3]
          ELSE apoc.coll.toSet(word_hashes)[..3]
     END AS hashtags
RETURN
  e.videoId AS videoId,
  'https://youtu.be/' + e.videoId AS url,
  e.title AS title,
  e.publishedAt AS publishedAt,
  hashtags AS hashtags_for_examples
ORDER BY coalesce(e.publishedAt, datetime('1900-01-01')) DESC
LIMIT 15;
```

---

## 🗂️ Estructura del proyecto (resumen)

```
app/
  main.py                  # FastAPI (endpoints /recommend/llm, /feedback/like, etc.)
  services/
    graph_examples.py      # build_llm_context (glossary, trends, examples)
    llm_ollama.py          # prompt, chat, critic&repair, saneado/hashtags
    llamaindex_client.py   # get_llm() → instancia de LlamaIndex con Ollama
infra/
  docker-compose.yml
  Dockerfile
README.md
```

---

## 🧪 Ejemplos de requests

### Tecnología + XR

```json
{
  "platform": "youtube",
  "niche": "tecnologia",
  "impressions": 90000,
  "reach": 72000,
  "clicks": 880,
  "followers": 41000,
  "likes": 2800,
  "shares": 210,
  "saves": 360,
  "comments": 230,
  "specialties": ["realidad virtual", "realidad mixta", "webxr", "xr"],
  "use_graph": true,
  "top_k": 8
}
```

### Automotriz (detailing)

```json
{
  "platform": "youtube",
  "niche": "automotriz",
  "impressions": 50000,
  "reach": 42000,
  "clicks": 400,
  "followers": 15000,
  "likes": 1200,
  "shares": 120,
  "saves": 210,
  "comments": 95,
  "specialties": ["detailing", "pulido", "interior"],
  "use_graph": true,
  "top_k": 8
}
```

---

## 🛠️ Desarrollo

### Levantar local (sin Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Asegúrate de tener **Ollama corriendo** y el **modelo descargado**:

```bash
ollama pull llama3.1
ollama serve
```

---

## 🩺 Troubleshooting

* **`TypeError: Object of type DateTime is not JSON serializable`**
  Serializa `publishedAt` a string (ISO) *antes* de devolver JSON (ver `_coerce_examples` en `graph_examples.py`).

* **`NameError: name 're' is not defined`**
  Asegura `import re` en cualquier archivo que use regex (ej. funciones de tokenización en `main.py` o servicios).

* **`httpx.ReadTimeout: timed out` (Ollama)**

  * Verifica `OLLAMA_HOST` y que `ollama serve` esté activo.
  * Sube `LLM_TIMEOUT`.
  * Comprueba que el `OLLAMA_MODEL` existe (`ollama list`).

* **`Neo.ClientNotification.Statement.FeatureDeprecationWarning` (CALL subquery)**
  No es fatal, pero puedes modernizar a `CALL (n) { ... }` para evitar deprecaciones futuras.

* **`jq: parse error: Invalid numeric literal`**
  Ocurre cuando la API responde con **texto** (p.ej., 500 con `text/plain`).
  Usa `curl -i` para ver `content-type` y el **status**:

  ```bash
  curl -i -sS -X POST "http://localhost:8000/recommend/llm" ... 
  ```

* **Hashtags vacíos o genéricos**
  El saneador ahora rellena hasta **2–3 por idea** usando vocab permitido (glossary + specialties + trends).
  Evita `#tips`, `#checklist`, etc.

---

## 🔒 Seguridad

* Todas las rutas privadas requieren `x-api-key`.
* Evita exponer `NEO4J_*`, `OLLAMA_*` en logs públicos.
* Considera añadir **rate limit** y **CORS** según tu despliegue.

---

## 🗺️ Roadmap

* [ ] Endpoints para **persistir feedback** (like/dislike) como sesgo de futuras tendencias.
* [ ] Soporte multi-plataforma (plantillas de estilo más específicas).
* [ ] Evaluadores automáticos de calidad (detección de clichés o repetición).
* [ ] Métricas de *post-hoc* (tracking de CTR/retención por idea sugerida).

---

## 📄 Licencia

Este proyecto se distribuye bajo la licencia **MIT**. (Cámbiala si lo necesitas).

---

## 👤 Autor

**Jhonnatan Del Castillo** — Lava Software Development
Emprendimientos IA, marketing digital y herramientas de recomendación de contenido.

---
