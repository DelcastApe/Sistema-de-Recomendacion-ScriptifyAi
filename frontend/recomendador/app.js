// UI
const QUIPS = [
  "Leyendo tus métricas y preparando una estrategia.",
  "Midiendo si hoy toca vender, retener o demostrar autoridad…",
  "El agente está discutiendo consigo mismo (¡y va ganando!).",
  "Revisando si el algoritmo tomó café ☕",
  "Buscando títulos que no sean clickbait… pero que sí funcionen 😉",
  "Consultando al oráculo de los thumbnails 🔮",
  "Puliendo una recomendación que puedas ejecutar hoy."
];
const $ = (s)=>document.querySelector(s);
function show(e){e.classList.remove("hidden")} function hide(e){e.classList.add("hidden")}
let quipTimer=null; function startQuips(){const el=$("#quip"); if(!el) return; let i=0; el.textContent=QUIPS[i]; quipTimer=setInterval(()=>{i=(i+1)%QUIPS.length; el.textContent=QUIPS[i];},1600)} function stopQuips(){ if(quipTimer) clearInterval(quipTimer); quipTimer=null; }
const youtube = id => `https://www.youtube.com/watch?v=${encodeURIComponent(id)}`;
const fmt = iso => { try { return new Date(iso).toLocaleString(); } catch { return "—"; } };

// ===== Render: SOLO recommendation, reason, ideas y examples =====
function renderOutput(data){
  $("#rec-text").textContent = data.recommendation || "—";
  $("#reason-text").textContent = data.reason || "—";

  const ideasUl=$("#ideas-list"); ideasUl.innerHTML="";
  (data.ideas||[]).forEach(t=>{
    const li=document.createElement("li");
    li.textContent=t;
    ideasUl.appendChild(li);
  });

  const exWrap=$("#examples"); exWrap.innerHTML="";
  (data.examples||[]).forEach(ex=>{
    const div=document.createElement("div"); div.className="example";
    const h4=document.createElement("h4");
    const title=ex.title||"Ejemplo";
    if(ex.videoId){
      const a=document.createElement("a");
      a.href=youtube(ex.videoId); a.target="_blank"; a.rel="noopener";
      a.textContent=title;
      h4.appendChild(a);
    } else {
      h4.textContent=title;
    }
    const meta=document.createElement("p"); meta.className="meta";
    meta.textContent=`Publicado: ${fmt(ex.publishedAt)} · ${ex.url ? ex.url : ""}`;
    div.append(h4, meta);
    exWrap.appendChild(div);
  });

  show($("#results"));
}

// ===== Helpers =====
const simulate = d => new Promise(r=>setTimeout(()=>r(d),800));

function formToPayload(form){
  const fd=new FormData(form), get=k=>fd.get(k)||null;
  const num=v=>v===""||v===null?null:Number(v);
  const specialties=(get("specialties")||"").split(",").map(s=>s.trim()).filter(Boolean);
  return {
    platform:get("platform"),
    niche:get("niche"),
    region:"GL",
    impressions:num(get("impressions")),
    reach:num(get("reach")),
    likes:num(get("likes")),
    shares:num(get("shares")),
    saves:num(get("saves")),
    comments:num(get("comments")),
    followers:num(get("followers")),
    specialties,
    top_k:10,
    use_graph:true
  };
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
    examples:[
      {publishedAt:"2025-10-10T15:00:54+00:00", title:"Demo XR", videoId:"S_shhw4VV68", url:"https://youtu.be/S_shhw4VV68"},
      {publishedAt:"2025-10-08T20:43:13+00:00", title:"Tendencias XR", videoId:"bGH-DvBlUhM", url:"https://youtu.be/bGH-DvBlUhM"}
    ]
  };

  form.addEventListener("submit", async (e)=>{
    e.preventDefault(); hide(results); show(modal); startQuips();
    try{
      const payload = formToPayload(form);            // *** PLANO, como tu curl
      const data = await window.API.recommendLLM(payload); // pasa por /api → FastAPI
      renderOutput(data);
    }catch(err){
      console.error(err);
      const d=await simulate(DEMO); renderOutput(d);
    }finally{ stopQuips(); hide(modal); }
  });

  $("#demo-btn").addEventListener("click", async ()=>{
    hide(results); show(modal); startQuips();
    const d=await simulate(DEMO); renderOutput(d);
    stopQuips(); hide(modal);
  });

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
