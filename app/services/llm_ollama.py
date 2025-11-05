# app/services/llm_ollama.py
import re
import json
from typing import Any, Dict, List, Tuple, Union

from services.llamaindex_client import get_llm
from services.graph_examples import build_llm_context

# Tipos de chat tolerantes a versiones
try:
    from llama_index.core.llms.types import ChatMessage, MessageRole  # type: ignore
except Exception:
    try:
        from llama_index.core.llms import ChatMessage, MessageRole  # type: ignore
    except Exception:
        ChatMessage = None  # type: ignore
        MessageRole = None  # type: ignore

# ----------------------------
# Utilidades de saneo
# ----------------------------

GENERIC_BAD_WORDS = {
    "idea 1", "idea1", "idea 2", "idea2", "placeholder", "lorem",
    "video práctico y específico", "estrategias generales", "contenido genérico"
}
GENERIC_HASHES = {"#tips", "#checklist", "#referencia", "#resultado", "#caso", "#tutorial", "#tecnologia"}

LATIN_WHITELIST = re.compile(r"[^\n\r\t a-zA-Z0-9¿?¡!.,;:()\-_/\"'áéíóúÁÉÍÓÚñÑ]")

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def _spanish_only(s: str) -> str:
    return LATIN_WHITELIST.sub("", s or "")

def _bad_generic(s: str) -> bool:
    t = (s or "").lower()
    return any(bad in t for bad in GENERIC_BAD_WORDS)

def _normalize_hashtag(tag: str) -> str:
    t = (tag or "").strip().lower()
    if not t.startswith("#"):
        t = "#" + t
    t = (t
         .replace("á", "a").replace("é", "e").replace("í", "i")
         .replace("ó", "o").replace("ú", "u").replace("ñ", "n"))
    t = re.sub(r"[^#a-z0-9_]", "", t)
    return t

def _tokenize_for_vocab(text: str) -> List[str]:
    t = (text or "").lower()
    t = (t
         .replace("á","a").replace("é","e").replace("í","i")
         .replace("ó","o").replace("ú","u").replace("ñ","n"))
    t = re.sub(r"[^a-z0-9\s\-_/]", " ", t)
    toks = re.split(r"[\s\-_\/]+", t)
    return [w for w in toks if len(w) >= 3]

def _build_allowed_hashtag_vocab(
    niche: str,
    specialties: List[str],
    llm_ctx: Dict[str, Any],
    ideas: List[str],
) -> set:
    vocab = set()
    for w in (llm_ctx.get("glossary") or []):
        vocab.update(_tokenize_for_vocab(w))
    for w in (llm_ctx.get("expanded_specialties") or []):
        vocab.update(_tokenize_for_vocab(w))
    vocab.update(_tokenize_for_vocab(niche))
    for sp in specialties or []:
        vocab.update(_tokenize_for_vocab(sp))
    for title in ideas or []:
        vocab.update(_tokenize_for_vocab(title))
    junk = {"checklist","tips","tutorial","resultado","caso","referencia"}
    vocab = {w for w in vocab if w not in junk}
    return vocab

def _to_hashtag_candidate(token: str) -> str:
    t = token.lower()
    t = (t
         .replace("á","a").replace("é","e").replace("í","i")
         .replace("ó","o").replace("ú","u").replace("ñ","n"))
    t = re.sub(r"[^a-z0-9_]", "", t)
    return f"#{t}" if t else ""

def _sanitize_hashtags_block(
    hblock: List[List[str]],
    niche: str,
    allowed_vocab: set | None = None
) -> List[List[str]]:
    """Normaliza, filtra por vocabulario permitido, dedup global y elimina genéricos.
       Máx 1 hashtag del nicho en todo el bloque."""
    seen = set()
    out: List[List[str]] = []
    niche_tag = _normalize_hashtag(f"#{(niche or '').replace(' ','')}") if niche else None
    niche_used = False

    def _allowed(tag: str) -> bool:
        if allowed_vocab is None:
            return True
        root = tag.lstrip("#")
        return (root in allowed_vocab) or any(root.startswith(v) or v in root for v in allowed_vocab if len(v) >= 4)

    for row in (hblock or []):
        row2 = []
        for t in (row or []):
            nt = _normalize_hashtag(t)
            if nt in GENERIC_HASHES:
                continue
            if allowed_vocab is not None and not _allowed(nt):
                continue
            if niche_tag and nt == niche_tag:
                if niche_used:
                    continue
                niche_used = True
            if nt not in seen and len(nt) >= 4:
                row2.append(nt)
                seen.add(nt)
        out.append(row2[:3])
    return out

def _enforce_hashtags(ideas: List[str], niche: str, specialties: List[str], allowed_vocab: set | None = None) -> List[List[str]]:
    uniq = set()
    results: List[List[str]] = []
    base_niche_tag = f"#{(niche or '').lower().replace(' ', '')}" if niche else None
    spec_tags = [f"#{re.sub(r'[^a-z0-9]', '', (sp or '').lower().replace(' ', ''))}" for sp in (specialties or [])][:3]

    for title in ideas:
        tags: List[str] = []

        for t in spec_tags:
            nt = _normalize_hashtag(t)
            if nt and nt not in uniq and nt not in GENERIC_HASHES:
                if allowed_vocab is None or nt.lstrip("#") in allowed_vocab:
                    tags.append(nt)
                    uniq.add(nt)
                    if len(tags) >= 3:
                        break

        kw = re.findall(r"[a-zA-ZáéíóúñÁÉÍÓÚ0-9]{4,}", title or "")
        if kw:
            pick = _to_hashtag_candidate(kw[0])
            pick = _normalize_hashtag(pick)
            if pick not in uniq and pick not in GENERIC_HASHES:
                if allowed_vocab is None or pick.lstrip("#") in allowed_vocab:
                    tags.append(pick)
                    uniq.add(pick)

        if base_niche_tag and base_niche_tag not in uniq:
            if allowed_vocab is None or base_niche_tag.lstrip("#") in allowed_vocab:
                tags.append(base_niche_tag)
                uniq.add(base_niche_tag)

        tags = [t for t in tags if t not in GENERIC_HASHES]
        results.append(tags[:3] if tags else [])
    return results

def _validate_and_fix(payload: Dict[str, Any], niche: str, specialties: List[str], llm_ctx: Dict[str, Any] | None = None) -> Tuple[Dict[str, Any], bool]:
    ok = True

    for k in ("recommendation", "reason"):
        v = _spanish_only(_norm(payload.get(k, "")))
        if not v or _bad_generic(v):
            ok = False
        payload[k] = v

    ideas = payload.get("ideas") or []
    ideas = [_spanish_only(_norm(x)) for x in ideas if _norm(x)]
    if len(ideas) < 10:
        ok = False
    if any(_bad_generic(x) for x in ideas):
        ok = False

    allowed_vocab = _build_allowed_hashtag_vocab(niche, specialties, llm_ctx or {}, ideas)

    hashtags = payload.get("hashtags_for_ideas") or []
    if len(hashtags) != len(ideas) or not all(isinstance(h, list) for h in hashtags):
        hashtags = _enforce_hashtags(ideas, niche, specialties, allowed_vocab=allowed_vocab)
    payload["hashtags_for_ideas"] = _sanitize_hashtags_block(hashtags, niche, allowed_vocab=allowed_vocab)

    seen = set()
    deduped = []
    for it in ideas:
        if it.lower() not in seen:
            deduped.append(it)
            seen.add(it.lower())
    payload["ideas"] = deduped

    if specialties:
        rec_low = (payload.get("recommendation") or "").lower()
        if not any(sp.lower() in rec_low for sp in specialties):
            ok = False

    reason = payload.get("reason") or ""
    bullet_lines = [ln for ln in reason.splitlines() if ln.strip().startswith("- ")]
    if len(bullet_lines) != 4:
        ok = False

    return payload, ok

# ----------------------------
# Prompts (genéricos por nicho)
# ----------------------------

_AGENT_SYS = """
Eres un estratega de contenido cercano y claro. Devuelves SIEMPRE JSON válido (sin markdown).
Escribe en ESPAÑOL NEUTRO. Nada de jerga ni clichés.

REGLAS DE SALIDA:
- "recommendation": 1 frase sin minutajes, que incluya al menos UNA palabra de las ESPECIALIDADES (si existen).
- "reason": 1 párrafo que siga este orden exacto:
  * Señales (en humano: “poca gente entra”, “se van pronto”, “cuesta el siguiente paso”).
  * Propósito (atraer / retener / vender).
  * Analogía breve ORIGINAL (no uses ninguna de la lista prohibida).
  * **Exactamente 4 bullets**, cada uno en una línea independiente, iniciando con "- " (guión y espacio), modo imperativo, concretos, adaptados a plataforma/especialidades, sin tecnicismos.
- "ideas": 10–12 títulos; ~50% directos y ~50% creativos (antes/después, checklist, errores, en 60s...). Mezcla keywords del glosario + specialties sin forzar ni repetir plantillas.
- "hashtags_for_ideas": para cada idea, 2–3 hashtags concisos, sin tildes, sin genéricos (#tips, #checklist...), sin repeticiones globales. Máx 1 hashtag del nicho en todo el bloque.

PROHIBIDO:
- Porcentajes o números de métricas en "reason".
- Duraciones exactas o promesas de tiempo.
- Analogías de la lista prohibida (llega en el contexto).
- Placeholders ("Idea 1", "Video genérico"...).
"""

# ⚠️ DOBLES LLAVES en salida JSON para evitar .format colisiones
_USER_TMPL = """
Contexto del negocio:
- Nicho: {niche}
- Especialidades: {specialties}
- Plataforma: {platform}
- Foco (objetivo): {focus_hint}
- Glosario del nicho: {glossary}
- Expansion de specialties: {expanded_specialties}
- Estilo por plataforma (guía): {style_guide}
- Analogías prohibidas: {banned_analogies}
- Métricas crudas: {metrics}
- Ejemplos recientes (títulos): {examples}

Guías por foco (aplícalas SOLO al foco actual):
- attract (atraer): hooks claros, curiosidad, antes/después, comparativas, promesas de resultado visual.
  * Patrones sugeridos: "Antes y después: ...", "Errores que arruinan ...", "En 3 pasos: ..."
- retain (retener): series, paso a paso, comparativas más profundas, “qué haría un pro”, desmontar mitos.
  * Patrones sugeridos: "Paso a paso: ...", "Comparativa real: A vs B", "Mitos vs realidad: ..."
- convert (vender / siguiente paso): casos prácticos con coste/beneficio, mini-oferta, checklist de compra/preventa, objeciones.
  * Patrones sugeridos: "Checklist antes de ...", "Caso real: ... y cuánto costó", "Qué elegir: ..."

Tu tarea:
1) "recommendation": una frase que contenga al menos UNA palabra de las especialidades (si hay).
2) "reason": párrafo con el orden indicado y **4 bullets exactos** con formato "- ".
3) "ideas": 10–12, variadas, humanas, **adaptadas al foco actual**.
   - 30–70 caracteres por título.
   - Evita repeticiones raras (“detailing detailing”) y marcas/modelos si no aportan.
   - ~50% directos (guía, checklist, errores, comparativa) y ~50% creativos (antes/después, reto, mito/realidad).
4) "hashtags_for_ideas": 2–3 por idea, sin genéricos ni tildes, sin repeticiones globales, máx 1 hashtag del nicho en todo el bloque.

SALIDA:
{{"recommendation": "...", "reason": "...", "ideas": ["..."], "hashtags_for_ideas": [["#...","#..."]]}}
"""

_CRITIC = """
Repara el JSON si hay fallas:
- "recommendation" debe incluir al menos UNA palabra de las especialidades (si existen).
- "reason": sin números de métricas; analogía original (no prohibida); **exactamente 4 bullets** con formato "- ", imperativos y concretos, adaptados a plataforma/especialidades.
- "ideas": 10–12; mezcla glosario+specialties; sin plantillas clonadas y **coherentes con el foco actual**.
- "hashtags_for_ideas": 2–3/idea; sin genéricos, sin tildes, sin repeticiones globales; máx 1 hashtag del nicho en todo el bloque.
Responde SOLO el JSON corregido.
"""

# ----------------------------
# Chat helpers
# ----------------------------

def _coerce_messages(msgs: List[Any]) -> List[Any]:
    if ChatMessage is None or MessageRole is None:
        out: List[Dict[str, str]] = []
        for m in msgs:
            if isinstance(m, dict) and "role" in m and "content" in m:
                out.append({"role": m["role"], "content": m["content"]})
            else:
                out.append({"role": "user", "content": str(m)})
        return out

    out2: List[ChatMessage] = []  # type: ignore
    for m in msgs:
        if isinstance(m, dict):
            role = (m.get("role") or "user").lower()
            if role == "system":
                rr = MessageRole.SYSTEM  # type: ignore
            elif role == "assistant":
                rr = MessageRole.ASSISTANT  # type: ignore
            else:
                rr = MessageRole.USER  # type: ignore
            out2.append(ChatMessage(role=rr, content=m.get("content", "")))  # type: ignore
        else:
            try:
                out2.append(m)  # type: ignore
            except Exception:
                out2.append(ChatMessage(role=MessageRole.USER, content=str(m)))  # type: ignore
    return out2  # type: ignore


def _build_prompt(
    niche: str,
    metrics: Dict[str, Any],
    examples: List[Dict[str, Any]],
    specialties: List[str],
    platform: Union[str, None],
    llm_ctx: Dict[str, Any],
) -> List[Any]:
    ex_titles = [e.get("title") for e in (examples or []) if e.get("title")]
    user = _USER_TMPL.format(
        platform=platform or "multi-plataforma",
        niche=niche,
        specialties=", ".join(specialties) if specialties else "—",
        glossary=", ".join(llm_ctx.get("glossary") or []),
        expanded_specialties=", ".join(llm_ctx.get("expanded_specialties") or []),
        style_guide="; ".join(llm_ctx.get("style_for_platform") or []),
        banned_analogies=", ".join(llm_ctx.get("banned_analogies") or []),
        metrics=json.dumps(metrics, ensure_ascii=False),
        examples=json.dumps(ex_titles[:10], ensure_ascii=False),
        focus_hint=(metrics.get("inputs", {}) or {}).get("focus_hint", "attract"),
    )
    return [
        {"role": "system", "content": _AGENT_SYS},
        {"role": "user", "content": user},
    ]


def _chat_once(messages: List[Any], temperature: float) -> Dict[str, Any]:
    """
    Envía mensajes al LLM. Forzamos complete() (endpoint /api/generate) para evitar
    timeouts del endpoint /api/chat que viste en los logs. Si falla, reintentamos.
    """
    llm = get_llm()

    sys_txt, usr_txt = "", ""
    for m in messages:
        if isinstance(m, dict):
            role = (m.get("role") or "user")
            content = (m.get("content") or "")
        else:
            role = getattr(m, "role", "user")
            content = getattr(m, "content", "")

        rv = str(getattr(role, "value", role)).lower()
        if rv == "system":
            sys_txt += (content or "").strip() + "\n\n"
        else:
            usr_txt += (content or "").strip() + "\n\n"

    prompt = (("### Sistema\n" + sys_txt) if sys_txt else "") + ("### Usuario\n" + usr_txt)

    try:
        resp = llm.complete(prompt, temperature=temperature)
        txt = getattr(resp, "text", str(resp))
    except Exception:
        resp = llm.complete(prompt, temperature=max(0.2, temperature - 0.2))
        txt = getattr(resp, "text", str(resp))

    m = re.search(r"\{[\s\S]*\}\s*$", txt)
    raw = txt if m is None else m.group(0)
    try:
        return json.loads(raw)
    except Exception:
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)


def _critique_and_repair(draft: Dict[str, Any], niche: str, platform: str, specialties: List[str]) -> Dict[str, Any]:
    msgs = [
        {"role": "system", "content": _AGENT_SYS},
        {"role": "user", "content": _CRITIC},
        {"role": "assistant", "content": json.dumps(draft, ensure_ascii=False)},
        {"role": "user", "content": f"Nicho: {niche} | Plataforma: {platform or 'multi'} | Especialidades: {', '.join(specialties) or '—'}"},
    ]
    try:
        return _chat_once(msgs, temperature=0.4)
    except Exception:
        return draft

# ----------------------------
# API principal
# ----------------------------

def llm_recommend(
    focus: str,
    niche: str,
    metrics: Dict[str, Any],
    examples: List[Dict[str, Any]],
    neighbors: List[Dict[str, Any]] | None = None,
    temperature: float = 0.6,
) -> Dict[str, Any]:
    """
    Recomendación robusta y generalista (nicho-agnóstica).
    Usa RAG (glossary/expanded/examples) + crítica/repair + saneo.
    """
    inputs = metrics.get("inputs", {}) or {}
    platform = inputs.get("platform")
    specialties: List[str] = inputs.get("specialties") or []
    top_k = max(int(inputs.get("top_k") or 10), 8)

    llm_ctx = build_llm_context(
        niche=niche,
        specialties=specialties,
        platform=platform,
        top_k=top_k,
        region=inputs.get("region"),
        preset_examples=examples,
    )

    messages = _build_prompt(
        niche=niche,
        metrics=metrics,
        examples=examples,
        specialties=specialties,
        platform=platform,
        llm_ctx=llm_ctx,
    )
    draft = _chat_once(messages, temperature=temperature)

    draft, ok = _validate_and_fix(draft, niche, specialties, llm_ctx=llm_ctx)
    if not ok:
        draft2 = _critique_and_repair(draft, niche=niche, platform=(platform or "multi"), specialties=specialties)
        draft2, ok2 = _validate_and_fix(draft2, niche, specialties, llm_ctx=llm_ctx)
        if ok2:
            draft = draft2

    draft.setdefault("recommendation", "Tu siguiente video debe ser algo concreto y con resultado visible (sin minutajes).")
    draft.setdefault("reason", "Señales en humano; objetivo claro; analogía original; 4 bullets imperativos y concretos.")
    draft.setdefault("ideas", [])

    allowed_vocab_final = _build_allowed_hashtag_vocab(niche, specialties, llm_ctx or {}, draft.get("ideas", []))
    draft.setdefault(
        "hashtags_for_ideas",
        _enforce_hashtags(draft.get("ideas", []), niche, specialties, allowed_vocab=allowed_vocab_final)
    )

    return draft
