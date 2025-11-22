// ===== UI helpers =====
const QUIPS = [
  "Leyendo tus métricas y preparando una estrategia.",
  "El agente está discutiendo consigo mismo (¡y va ganando!).",
  "Midiendo si hoy toca vender, retener o demostrar autoridad…",
  "Contando tus clics como si fueran likes de tu crush ❤️",
  "Comparando tu CTR con el clima: ¿hay tormenta o sol?",
  "Analizando retenciones con lupa de detective 🕵️",
  "Buscando títulos que no sean clickbait… pero que sí funcionen 😉",
  "Consultando al oráculo de los thumbnails 🔮",
  "Ajustando el gancho del video con precisión quirúrgica ✂️",
  "Revisando ejemplos reales para inspirarte (sin humo).",
  "Separando opinión de dato duro… como buenos científicos 🧪",
  "Viendo qué funcionó a canales similares al tuyo.",
  "Hablando con el grafo de conocimiento (es tímido).",
  "Chequeando si tu nicho está en tendencia 📈",
  "Detectando si conviene corto, mediano o largo… el video.",
  "Mapeando hashtags que no parezcan poema de 2007 #porfavor",
  "Evadiendo gurús y encontrando evidencia real.",
  "Puliendo una recomendación que puedas ejecutar hoy.",
  "Decidiendo si conviene autoridad o retención para crecer sostenido.",
  "Confirmando que tus métricas no son de otro universo 🪐",
  "Leyendo comentarios para encontrar señales escondidas.",
  "Cuenta regresiva para una idea accionable…",
  "Midiendo si tu audiencia se queda por valor o por carisma.",
  "¿Miniatura con cara sorpresa? Evaluando riesgos 😮",
  "Quitándole puntos a los títulos con 11 emojis.",
  "Probando variantes de gancho mental (sin dolor).",
  "Pensando como humano, calculando como máquina 🤝",
  "La IA está tomando notas para tu próximo video.",
  "Hablando con YouTube: ‘trátalo bien, es buena gente’."
];

const $ = (s)=>document.querySelector(s);
function show(e){e.classList.remove("hidden")}
function hide(e){e.classList.add("hidden")}

let quipTimer=null;
function startQuips(){
  const el=$("#quip"); if(!el) return;
  let i=0; el.textContent=QUIPS[i];
  quipTimer=setInterval(()=>{
    i=(i+1)%QUIPS.length; el.textContent=QUIPS[i];
  },6000);
}
function stopQuips(){ if(quipTimer) clearInterval(quipTimer); quipTimer=null; }

const youtube = id => `https://www.youtube.com/watch?v=${encodeURIComponent(id)}`;
const fmt = iso => { try { return new Date(iso).toLocaleString(); } catch { return "—"; } };

// ===== Render: SOLO lo que interesa + hashtags correctos =====
function renderOutput(data){
  $("#rec-text").textContent = data.recommendation || "—";
  $("#reason-text").textContent = data.reason || "—";

  // ===== Ideas =====
  const ideasUl=$("#ideas-list"); ideasUl.innerHTML="";
  const ideas = data.ideas || [];
  ideas.forEach(t=>{
    const li=document.createElement("li");
    li.textContent=t;
    ideasUl.appendChild(li);
  });

  // ===== Hashtags sugeridos (todos juntos) =====
  const tagsUl = $("#hashtags-ideas");
  tagsUl.innerHTML = "";

  // Unir todos los hashtags en una sola lista
  const flatTags = (data.hashtags_for_ideas || []).flat();

  // Filtrar vacíos y duplicados
  const uniqueTags = [...new Set(flatTags.filter(Boolean))];

  if (uniqueTags.length === 0) {
    const li = document.createElement("li");
    li.textContent = "Sin hashtags sugeridos";
    li.className = "tag muted";
    tagsUl.appendChild(li);
  } else {
    uniqueTags.forEach(tag => {
      const li = document.createElement("li");
      li.className = "tag";
      li.textContent = tag;
      tagsUl.appendChild(li);
    });
  }


  // ===== Examples + hashtags_for_examples =====
  const exWrap=$("#examples"); exWrap.innerHTML="";
  (data.examples||[]).forEach(ex=>{
    const div=document.createElement("div"); div.className="example";
    const h4=document.createElement("h4");
    const title=ex.title||"Ejemplo";

    if(ex.videoId){
      const a=document.createElement("a");
      a.href=youtube(ex.videoId);
      a.target="_blank";
      a.rel="noopener";
      a.textContent=title;
      h4.appendChild(a);
    } else {
      h4.textContent=title;
    }

    const meta=document.createElement("p"); meta.className="meta";
    meta.textContent=`Publicado: ${fmt(ex.publishedAt)}${ex.url ? " · "+ex.url : ""}`;

    div.append(h4, meta);

    // ✅ hashtags del ejemplo (hashtags_for_examples)
    const exTags = ex.hashtags_for_examples || [];
    if (exTags.length > 0) {
      const tagsWrap = document.createElement("div");
      tagsWrap.className = "example-tags";

      exTags.forEach(tag => {
        const s = document.createElement("span");
        s.className = "tag";
        s.textContent = tag;
        tagsWrap.appendChild(s);
      });

      div.appendChild(tagsWrap);
    }

    exWrap.appendChild(div);
  });

  show($("#results"));
}

// ===== Helpers =====
const FIXED = { use_graph: true, top_k: 8, region: "GL" };

function toNumberOrNull(v){
  if (v === "" || v === null || v === undefined) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}
function uniq(arr){ return [...new Set(arr)]; }

function parseSpecialties(s){
  return uniq(String(s||"")
    .split(",")
    .map(x => x.trim())
    .filter(Boolean));
}

// quita null/undefined/NaN y arrays vacíos
function cleanPayload(obj){
  const out = {};
  for (const [k,v] of Object.entries(obj)){
    if (v === null || v === undefined) continue;
    if (Array.isArray(v) && v.length === 0) continue;
    out[k] = v;
  }
  return out;
}

// Form -> payload PLANO (igual que tu curl + FIXED)
function formToPayload(form){
  const fd = new FormData(form);
  const get = k => fd.get(k);

  const payload = {
    platform: get("platform") || "tiktok",
    niche: (get("niche") || "").toString(),
    impressions: toNumberOrNull(get("impressions")),
    reach: toNumberOrNull(get("reach")),
    likes: toNumberOrNull(get("likes")),
    shares: toNumberOrNull(get("shares")),
    saves: toNumberOrNull(get("saves")),
    comments: toNumberOrNull(get("comments")),
    followers: toNumberOrNull(get("followers")),
    specialties: parseSpecialties(get("specialties")),
    ...FIXED,
  };

  return cleanPayload(payload);
}

// (opcional) reintento si 504 por modelo frío
async function callWithRetry(payload, tries=2){
  for (let i=1;i<=tries;i++){
    try { return await window.API.recommendLLM(payload); }
    catch (e){
      if (String(e).includes("HTTP 504") && i < tries){
        $("#quip").textContent = "Calentando el modelo… reintentamos en 5s ⏳";
        await new Promise(r=>setTimeout(r, 5000));
        continue;
      }
      throw e;
    }
  }
}

// ===== Main =====
window.addEventListener("DOMContentLoaded", ()=>{
  const form=$("#reco-form"), modal=$("#loading-modal"), results=$("#results");

  const DEMO={
    recommendation:"Explora la realidad virtual y mixta para nuevas experiencias inmersivas.",
    reason:"Buen engagement pero alcance por debajo del potencial. Trabaja piezas de autoridad con ganchos claros.",
    ideas:[
      "Comparativa: Realidad Mixta vs. WebXR",
      "Checklist de inicio en XR para marcas",
      "3 ganchos para captar en 3 segundos",
      "Antes y después: experiencia inmersiva"
    ],
    hashtags_for_ideas:[
      ["#xr","#comparativa"],
      ["#checklist","#inicio"],
      ["#ganchos","#retencion"],
      []
    ],
    examples:[
      {
        publishedAt:"2025-10-10T15:00:54+00:00",
        title:"Demo XR",
        videoId:"S_shhw4VV68",
        url:"https://youtu.be/S_shhw4VV68",
        hashtags_for_examples:["#xr","#demo"]
      },
      {
        publishedAt:"2025-10-08T20:43:13+00:00",
        title:"Tendencias XR",
        videoId:"bGH-DvBlUhM",
        url:"https://youtu.be/bGH-DvBlUhM",
        hashtags_for_examples:["#tendencias","#realidadmixta"]
      }
    ]
  };

  form.addEventListener("submit", async (e)=>{
    e.preventDefault(); hide(results); show(modal); startQuips();
    try{
      const payload = formToPayload(form);
      const data = await callWithRetry(payload, 2);
      renderOutput(data);
    }catch(err){
      console.error(err);
      const d=await new Promise(r=>setTimeout(()=>r(DEMO),800));
      renderOutput(d);
    }finally{ stopQuips(); hide(modal); }
  });

  $("#demo-btn").addEventListener("click", async ()=>{
    hide(results); show(modal); startQuips();
    const d=await new Promise(r=>setTimeout(()=>r(DEMO),800));
    renderOutput(d);
    stopQuips(); hide(modal);
  });

  // enlaces del mini-funnel
  document.querySelectorAll(".funnel-link").forEach(a=>{
    a.addEventListener("click",(e)=>{
      e.preventDefault();
      const p=formToPayload(form);
      const qs=new URLSearchParams({
        utm_source:"recomendador", utm_medium:"funnel", utm_campaign:a.dataset.service||"servicio",
        platform:p.platform||"", niche:p.niche||"",
        impressions:p.impressions??"", reach:p.reach??"",
        likes:p.likes??"", shares:p.shares??"", saves:p.saves??"",
        comments:p.comments??"", followers:p.followers??""
      });
      window.open(`${a.dataset.base}?${qs.toString()}`,"_blank","noopener");
    });
  });
});

