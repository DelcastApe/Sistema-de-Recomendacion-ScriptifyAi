---

# Scriptify AI — Sistema de Recomendación de Contenidos (RAG + LLM)

---

## 📘 Información académica del proyecto

- **Asignatura:** Sistemas de Información de Gestión y Business Intelligence  
- **Tipo de trabajo:** Proyecto final de la asignatura  
- **Curso académico:** 2024–2025  
- **Universidad:** Universidad de León  
- **Profesor:** Enrique López González  
- **Titulación:** Bachiller en ING. Informatica
- **Modalidad:** Proyecto individual  
- **Autor:** Jhonnatan Gerardo Chávez Del Castillo  

Este repositorio corresponde a un **trabajo académico evaluable**, desarrollado en el marco de la asignatura *Sistemas de Información de Gestión y Business Intelligence* de la Universidad de León.

---

## 🎓 Contexto académico y objetivo del proyecto

Este proyecto se desarrolla como **proyecto final de la asignatura Sistemas de Información de Gestión y Business Intelligence**, y tiene como objetivo aplicar de forma práctica los conceptos fundamentales de:

- Sistemas de información  
- Gestión  
- Business Intelligence  
- Apoyo a la toma de decisiones  

El sistema propuesto, **Scriptify AI**, aborda un problema habitual en la gestión de contenidos digitales: la **falta de conocimiento, orientación y criterios objetivos** para decidir qué tipo de contenido publicar en plataformas digitales.

Mediante el uso de un sistema de recomendación basado en datos, métricas de rendimiento y técnicas de *Retrieval-Augmented Generation (RAG)*, el proyecto proporciona **apoyo a la toma de decisiones**, permitiendo a los usuarios identificar oportunidades de contenido más alineadas con su contexto, nicho y rendimiento histórico.

---

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

````

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
````

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
    {
      "title": "...",
      "videoId": "...",
      "publishedAt": "2025-10-10T15:00:54+00:00",
      "hashtags_for_examples": ["#..."]
    }
  ],
  "diagnostics": { "inputs": { ... }, "llm": true }
}
```

### 🔹 `POST /feedback/like`

Registra un “me gusta” de una **idea** para el nicho.

**Body**

```json
{
  "niche": "tecnologia",
  "region": "GL",
  "idea": "Comparativa: Realidad Virtual vs Realidad Mixta",
  "specialties": ["realidad virtual", "realidad mixta"]
}
```

---

## 🧠 Contexto RAG desde el grafo

El servicio intenta traer de Neo4j:

* **examples**
* **trends**

Ambos alimentan vocabulario, hashtags y sesgos de recomendación.

---

## 🗂️ Estructura del proyecto

```
app/
  main.py
  services/
    graph_examples.py
    llm_ollama.py
    llamaindex_client.py
infra/
  docker-compose.yml
  Dockerfile
README.md
```

---

## 📂 Materiales del proyecto

- 📄 **Memoria final:** `/memoria/INFORME_FINAL_SCRIPTIFY.pdf`
- 📊 **Presentación:** `/presentacion/PRESENTACION.pdf`
- 🎥 **Vídeo de introducción:** `/videos/VIDEO_INTRODUCCION_DEL_PROYECTO.mp4`
- 🎥 **Vídeo de demostración del sistema:** `/videos/VIDEO_DEMOSTRACION_DEL_SISTEMA.mp4`
- 💻 **Código fuente:** `/codigo/`


## 📄 Licencia

MIT

---

## 👤 Autor

**Jhonnatan Gerardo Chávez Del Castillo**

Proyecto final — Universidad de León

---

```

---
