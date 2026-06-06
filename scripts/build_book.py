#!/usr/bin/env python3
"""Build the book report: chapters/*.md → index.html (+ book_report.html).

Ported from models-medical-evaluation's generate_book_report.py chapter
mechanism, slimmed: chapters are numbered markdown files, the builder
resolves two directives before rendering —

    {{include:reports/slice-eval.md}}   embed a generated report verbatim
    {{stat:total_rows}}                 splice a live number from the DB

so the book always reflects the current dataset and proof runs.
"""

from __future__ import annotations

import re
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CHAPTERS = REPO / "chapters"
DB_PATH = REPO / "data" / "slice.sqlite"
OUT = REPO / "index.html"
TITLE = "Gaucho Caché — $0-Runtime Semantic Cache for FSM Funnels"

CSS = """
:root{--ink:#1a1d23;--soft:#5b6472;--line:#e3e6ea;--accent:#0b6e4f;
--bg:#fbfaf7;--card:#ffffff;--mono:ui-monospace,'SF Mono',Menlo,monospace}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:17px/1.65 Georgia,'Times New Roman',serif}
.wrap{max-width:880px;margin:0 auto;padding:48px 24px}
header{border-bottom:3px double var(--ink);padding-bottom:24px;margin-bottom:8px}
header h1{font-size:34px;margin:0 0 8px}header p{color:var(--soft);margin:0}
nav{margin:24px 0 48px;padding:16px 20px;background:var(--card);
border:1px solid var(--line);border-radius:8px}
nav a{display:block;color:var(--accent);text-decoration:none;padding:2px 0}
.chapter{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:32px 36px;margin:0 0 32px;box-shadow:0 1px 3px rgba(0,0,0,.04)}
.chapter h1{font-size:24px;border-bottom:2px solid var(--accent);
padding-bottom:8px;margin-top:0}
h2{font-size:19px;margin-top:28px}h3{font-size:17px}
table{border-collapse:collapse;width:100%;margin:16px 0;font-size:15px}
th,td{border:1px solid var(--line);padding:7px 10px;text-align:left}
th{background:#f2f4f6;font-family:var(--mono);font-size:13px}
code{font-family:var(--mono);font-size:.85em;background:#f0f1f3;
padding:1px 5px;border-radius:4px}
pre{background:#14161a;color:#e8eaed;padding:16px;border-radius:8px;
overflow-x:auto;font-size:13.5px;line-height:1.5}pre code{background:none;color:inherit;padding:0}
blockquote{border-left:4px solid var(--accent);margin:16px 0;padding:4px 18px;
color:var(--soft);background:#f6f8f7}
strong{color:var(--ink)}hr{border:none;border-top:1px solid var(--line)}
footer{color:var(--soft);font-size:14px;text-align:center;padding:24px 0}
.pass{color:var(--accent);font-weight:bold}.fail{color:#a33;font-weight:bold}
"""


def ledger_table() -> str:
    sys.path.insert(0, str(REPO))
    from gaucho_cache import spend
    s = spend.summary()
    if not s:
        return "*(no ledger yet)*"
    rows = ["| Activity | Calls | Input tok | Output tok | USD |",
            "|---|---|---|---|---|"]
    for act in sorted(s, key=lambda a: -s[a]["usd"]):
        v = s[act]
        rows.append(f"| {act} | {v['calls']} | {v['input_tokens']:,} "
                    f"| {v['output_tokens']:,} | ${v['usd']:.2f} |")
    rows.append(f"| **total (ledgered)** | | | | **${spend.spent():.2f}** |")
    return "\n".join(rows)


def stats() -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        sys.path.insert(0, str(REPO))
        from gaucho_cache import spend
        out["spend_total"] = f"{spend.spent():.2f}"
    except Exception:  # noqa: BLE001
        out["spend_total"] = "?"
    if DB_PATH.exists():
        c = sqlite3.connect(DB_PATH)
        q = lambda s: c.execute(s).fetchone()[0]  # noqa: E731
        out["total_rows"] = str(q("SELECT COUNT(*) FROM variants"))
        out["active_positives"] = str(q(
            "SELECT COUNT(*) FROM variants WHERE kind='positive' AND dropped=0"))
        out["active_negatives"] = str(q(
            "SELECT COUNT(*) FROM variants WHERE kind='negative' AND dropped=0"))
        out["dropped"] = str(q("SELECT COUNT(*) FROM variants WHERE dropped=1"))
        out["relabeled"] = str(q(
            "SELECT COUNT(*) FROM variants WHERE judged_intent IS NOT NULL "
            "AND judged_intent != ''"))
    sha = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short",
                          "HEAD"], capture_output=True, text=True)
    out["commit"] = sha.stdout.strip() or "?"
    return out


def resolve(md: str, st: dict[str, str]) -> str:
    def inc(m: re.Match) -> str:
        p = REPO / m.group(1)
        return p.read_text(encoding="utf-8") if p.exists() else f"*({m.group(1)} not generated yet)*"
    md = re.sub(r"\{\{include:([^}]+)\}\}", inc, md)
    md = md.replace("{{ledger_table}}", ledger_table())
    return re.sub(r"\{\{stat:(\w+)\}\}",
                  lambda m: st.get(m.group(1), "?"), md)


def md_to_html(md: str) -> str:
    """Minimal markdown → HTML (headings, tables, code, lists, emphasis).
    No external dependency; covers what our chapters use."""
    lines = md.split("\n")
    html: list[str] = []
    in_code = in_table = in_list = False
    for ln in lines:
        if ln.startswith("```"):
            html.append("<pre><code>" if not in_code else "</code></pre>")
            in_code = not in_code
            continue
        if in_code:
            html.append(ln.replace("&", "&amp;").replace("<", "&lt;"))
            continue
        if ln.startswith("|"):
            cells = [c.strip() for c in ln.strip("|").split("|")]
            if all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                continue
            tag = "td" if in_table else "th"
            if not in_table:
                html.append("<table>")
                in_table = True
            html.append("<tr>" + "".join(
                f"<{tag}>{inline(c)}</{tag}>" for c in cells) + "</tr>")
            continue
        if in_table:
            html.append("</table>")
            in_table = False
        if ln.startswith("- "):
            if not in_list:
                html.append("<ul>")
                in_list = True
            html.append(f"<li>{inline(ln[2:])}</li>")
            continue
        if in_list and not ln.startswith("- "):
            html.append("</ul>")
            in_list = False
        m = re.match(r"^(#{1,4}) (.*)", ln)
        if m:
            h = len(m.group(1))
            html.append(f"<h{h}>{inline(m.group(2))}</h{h}>")
        elif ln.startswith("> "):
            html.append(f"<blockquote>{inline(ln[2:])}</blockquote>")
        elif ln.strip() == "---":
            html.append("<hr>")
        elif ln.strip():
            html.append(f"<p>{inline(ln)}</p>")
    if in_table:
        html.append("</table>")
    if in_list:
        html.append("</ul>")
    return "\n".join(html)


def inline(s: str) -> str:
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    s = s.replace("**PASS**", '<span class="pass">PASS</span>')
    return s


DEMO_SECTION = """
<div class="chapter" id="live-demo">
<h1>Live demo — the cache running in YOUR browser, $0</h1>
<p>No server, no API: the embedding model
(<code>Xenova/paraphrase-multilingual-mpnet-base-v2</code>) downloads once
from the Hugging Face Hub and runs <strong>inside this tab</strong>; the
index, thresholds and match contracts are inlined in this HTML file.
After the model loads you can go offline — the bot keeps answering.</p>
<p id="demo-status" style="font-family:var(--mono);font-size:13px"></p>
<div id="demo-chips" style="display:flex;flex-wrap:wrap;gap:8px;margin:12px 0"></div>
<div id="chatbox" style="display:flex;flex-direction:column;height:500px;
 background:#efeae2;border:1px solid var(--line);border-radius:14px;overflow:hidden">
 <div style="background:#0b6e4f;color:#fff;padding:10px 16px;
  font:600 14px -apple-system,'Segoe UI',sans-serif;display:flex;align-items:center;gap:10px">
  <span style="font-size:20px">🛏️</span>
  <span>La Feria del Colchón<br>
  <span style="font-weight:400;font-size:11.5px;opacity:.85">asistente · respondiendo desde tu navegador · $0.00</span></span>
 </div>
 <div id="demo-thread" style="flex:1;overflow-y:auto;padding:14px 14px 8px;
  display:flex;flex-direction:column;gap:5px"></div>
 <div style="display:flex;gap:8px;padding:10px;background:#f6f6f4;border-top:1px solid var(--line)">
  <input id="demo-input" placeholder="Escribí un mensaje…"
   style="flex:1;padding:10px 14px;border:1px solid var(--line);border-radius:20px;
   font:15px -apple-system,'Segoe UI',sans-serif;outline:none"/>
  <button id="demo-send" style="width:42px;height:42px;border:0;border-radius:50%;
   background:var(--accent);color:#fff;font-size:18px;cursor:pointer">➤</button>
 </div>
</div>
<p id="demo-counter" style="color:var(--soft);font-size:14px;margin-top:8px"></p>
</div>
<script>window.DEMO_DATA = __DEMO_DATA__;</script>
<script type="module">
const D = window.DEMO_DATA;
const $ = id => document.getElementById(id);
const status = m => $("demo-status").textContent = m;

// ---- decode f16 index --------------------------------------------------
const raw = Uint8Array.from(atob(D.embeddings_f16_b64), c=>c.charCodeAt(0));
const u16 = new Uint16Array(raw.buffer);
const EMB = new Float32Array(u16.length);
for (let i=0;i<u16.length;i++){
  const h=u16[i],s=(h&0x8000)>>15,e=(h&0x7C00)>>10,f=h&0x03FF;
  EMB[i]=(e===0?(s?-1:1)*Math.pow(2,-14)*(f/1024)
   :e===31?(f?NaN:(s?-1:1)*Infinity)
   :(s?-1:1)*Math.pow(2,e-15)*(1+f/1024));
}
const N=D.n, DIM=D.dim;
const POS=[],NEG={};
D.intents.forEach((it,i)=>{ if(D.kinds[i]==="positive") POS.push([it,i]);
  else (NEG[it]=NEG[it]||[]).push(i); });
const SOCIAL=new Set(["greet","thanks_goodbye","confirmation","declination","answer_for_whom"]);
const FUNNEL=new Set(["want_to_buy","answer_size_posture","answer_for_whom","ask_recommendation"]); // one funnel move, not two concerns

function normTxt(t){return t.toLowerCase().normalize("NFKD").replace(/[^a-z0-9ñ ]+/g,"").trim();}
function decide(q, nWords, rawText){
  const isShort=nWords<=3;
  const ce=(D.curated_exact||{})[normTxt(rawText||"")];
  if(ce && D.contracts[ce] && D.contracts[ce].audited){
    return {verdict:"serve",reason:"curated_exact",intent:ce,score:1,margin:1,negMargin:1,ms:0.1};
  }
  const t0=performance.now();
  const best={};
  for(const [it,i] of POS){
    let s=0; const o=i*DIM;
    for(let d=0;d<DIM;d++) s+=EMB[o+d]*q[d];
    if(!(it in best)||s>best[it]) best[it]=s;
  }
  const ranked=Object.entries(best).sort((a,b)=>b[1]-a[1]);
  const [i1,s1]=ranked[0], [i2,s2]=ranked[1];
  let ns=-1;
  for(const i of (NEG[i1]||[])){
    let s=0; const o=i*DIM;
    for(let d=0;d<DIM;d++) s+=EMB[o+d]*q[d];
    if(s>ns) ns=s;
  }
  const th=D.thresholds[i1]||{threshold:.7,margin:.05,negative_margin:.03};
  const th2=D.thresholds[i2];
  const c=D.contracts[i1]||{};
  const corpusExact=s1>=0.995; // verbatim corpus member: multi/margin legs don't apply
  // context conditioning: the demo knows what it just asked (lastBotIntent)
  const expected=(D.expected_next||{})[lastBotIntent]||[];
  const effTh=expected.includes(i1)?Math.max(0.70,th.threshold-(D.context_discount||0.05)):th.threshold;
  let verdict="miss", reason="";
  if(s1<effTh) reason="below_threshold";
  else if(!corpusExact && nWords>2 && th2 && s2>=0.75 && s2>=Math.min(th2.threshold,D.compound_floor)
          && (!isShort || s1-s2<0.12)
          && !(SOCIAL.has(i1)&&SOCIAL.has(i2))
          && !(FUNNEL.has(i1)&&FUNNEL.has(i2))) reason="multi_intent";
  else if(!corpusExact && s1-s2<th.margin && !(SOCIAL.has(i1)&&SOCIAL.has(i2)) && !(FUNNEL.has(i1)&&FUNNEL.has(i2))) reason="ambiguous_margin";
  else if(s1-ns<th.negative_margin) reason="negative_margin";
  // funnel-tie slot preference: both slots present -> never re-ask them
  let servedIntent=i1, cc=c;
  if(!reason && s1-s2<th.margin && FUNNEL.has(i1) && i1!=="answer_size_posture"
     && i2==="answer_size_posture"
     && /\b(1|una?|2|dos)\s*plazas?\b|\bqueen\b|\bking\b/i.test(rawText||"")
     && /\bde\s+costado\b|\bde\s+lado\b|\bboca\s+(arriba|abajo)\b|\bde\s+espaldas?\b/i.test(rawText||"")
     && D.contracts["answer_size_posture"] && D.contracts["answer_size_posture"].audited){
    servedIntent="answer_size_posture"; cc=D.contracts["answer_size_posture"]; reason="funnel_tie_slots";
  }
  if(reason==="" || reason==="funnel_tie_slots"){
    if((cc.requires_state||[]).length){ reason="precondition_failed"; }
    else if(!cc.audited){ verdict="hit"; reason="template_unaudited"; }
    else verdict="serve";
  }
  return {verdict,reason,intent:servedIntent,score:s1,margin:s1-s2,negMargin:s1-ns,
          ms:performance.now()-t0};
}

const lastServed={};
const GREET_AGAIN=["¡Hola de nuevo! 😄 Contame, ¿qué estás buscando?",
 "¡Buenas! ¿En qué te puedo ayudar?","Acá estoy 👂 decime nomás.",
 "¡Hola! ¿Seguimos? Contame qué necesitás."];
let lastBotIntent=null;

// ---- class B: catalog renders (deterministic slot-fill, $0) ------------
// Mirrors gaucho_cache/serving.py + render.py.
const BOT={slots:{},recommended:false,offered:false};
const SIZE_MAP=[[/\\b1\\s*plaza\\s*y\\s*media\\b|\\buna\\s*plaza\\s*y\\s*media\\b|\\b1[,.]5\\s*plazas?\\b/i,"1 plaza y media"],
 [/\\b(2|dos)\\s*plazas?\\b|\\b140\\s*x\\s*190\\b/i,"2 plazas"],
 [/\\b(1|una)\\s*plaza\\b|\\b90\\s*x\\s*190\\b/i,"1 plaza"],
 [/\\bqueen\\b|\\b160\\s*x\\s*200\\b/i,"queen"],
 [/\\bking\\b|\\b180\\s*x\\s*200\\b|\\b200\\s*x\\s*200\\b/i,"king"]];
const FIRM_RX=[[/\\bextra\\s*firme\\b|\\bbien\\s+firme\\b|\\bdur[oa]\\b/i,["firme"]],
 [/\\bfirme\\b/i,["firme","medio firme"]],
 [/\\bbland[oa]\\b|\\bsuave\\b|\\bsoft\\b/i,["blando"]],
 [/\\bmedi[oa]\\b/i,["medio","medio firme"]]];
const POST_RX=[[/\\bde\\s+costado\\b|\\bde\\s+lado\\b|\\bfetal\\b/i,["blando","medio"]],
 [/\\bboca\\s+abajo\\b/i,["firme","medio firme"]],
 [/\\bboca\\s+arriba\\b|\\bde\\s+espaldas?\\b/i,["medio","firme"]]];
function extractSlots(t){
  for(const [rx,size] of SIZE_MAP){ if(rx.test(t)){BOT.slots.size=size;break;} }
  for(const [rx,p] of FIRM_RX){ if(rx.test(t)){BOT.slots.pref=p;return;} }
  for(const [rx,p] of POST_RX){ if(rx.test(t)){BOT.slots.pref=BOT.slots.pref||p;return;} }
}
const ars=n=>"$"+Math.round(n).toLocaleString("es-AR");
const SALT=Math.floor(Math.random()*3); // per-session phrasing rotation (anti-tell)
const RECO_INTRO=["Estas son mis recomendaciones para tu cama {s}: 🛏️","Mirá, para una cama {s} yo iría por alguno de estos: 🛏️","Te separé lo mejor que tengo en {s}: 🛏️"];
const RECO_OUTRO=["¿Te paso las opciones de pago de alguno, o querés ver otro estilo?","Si alguno te tienta te paso enseguida cómo pagarlo, ¿dale?","Decime cuál te llama y vemos números, o te muestro otro estilo."];
const PAY_INTRO=["Para el <b>{n}</b> (lista {p}) tenés: 💳","Con el <b>{n}</b> (lista {p}) los números quedan así: 💳","Te detallo cómo queda el <b>{n}</b> (lista {p}): 💳"];
const PAY_OUTRO=["¿Con cuál te queda cómodo? Apenas elijas te paso el link para cerrarlo.","Decime cuál te conviene y te mando el link al toque.","Elegí la que más te sirva y lo dejamos cerrado en un minuto."];
const CLOSE_INTRO=["¡Listo! 🎉 Te reservo el <b>{n}</b> con {m}: {t}{x}.","¡Hecho! 🙌 Queda apartado el <b>{n}</b> con {m}: {t}{x}.","¡Excelente elección! ✨ Te dejo el <b>{n}</b> con {m}: {t}{x}."];
function pickProducts(k){
  let items=(D.catalog||[]).filter(p=>p.stock_status==="instock");
  if(BOT.slots.size){const f=items.filter(p=>p.size===BOT.slots.size); if(f.length) items=f;}
  const pref=BOT.slots.pref||[];
  items=items.slice().sort((a,b)=>{
    const ra=pref.length?(pref.includes(a.firmeza)?0:pref.some(x=>a.firmeza.includes(x))?1:2):0;
    const rb=pref.length?(pref.includes(b.firmeza)?0:pref.some(x=>b.firmeza.includes(x))?1:2):0;
    return ra-rb||((a.on_sale?0:1)-(b.on_sale?0:1))||a.price-b.price;});
  return items.slice(0,k);
}
function bestOffer(price){const m=(D.ladder||[]).reduce((a,b)=>a.multiplier<b.multiplier?a:b);return [m.label,price*m.multiplier];}
function renderReco(){
  if(!BOT.slots.size) return null;
  const ps=pickProducts(2); if(!ps.length) return null;
  BOT.recommended=true;
  const lines=ps.map(p=>{const [lab,off]=bestOffer(p.price);
    return `• <b>${p.name}</b> (${p.firmeza}, ${p.tecnologia}, ${p.altura_cm} cm)${p.on_sale?" 🔥 en oferta":""} — lista ${ars(p.price)}, con ${lab.toLowerCase()}: ${ars(off)}`;});
  return `${RECO_INTRO[SALT].replace("{s}",BOT.slots.size)}<br>${lines.join("<br>")}<br>${RECO_OUTRO[SALT]}`;
}
function renderPayments(){
  const p=pickProducts(1)[0]; BOT.offered=true;
  const lines=(D.ladder||[]).map(m=>{const tot=p.price*m.multiplier;
    return m.cuotas>1?`• ${m.label}: ${m.cuotas}× ${ars(tot/m.cuotas)} (total ${ars(tot)})`:`• ${m.label}: ${ars(tot)}`;});
  return `${PAY_INTRO[SALT].replace("{n}",p.name).replace("{p}",ars(p.price))}<br>${lines.join("<br>")}<br>${PAY_OUTRO[SALT]}`;
}
function detectPayment(t){t=(t||"").toLowerCase();
  if(/\\befectivo\\b|\\bcontado\\b/.test(t))return "efectivo";
  if(/\\bd[eé]bito\\b/.test(t))return "debito";
  if(/\\btransferencia\\b|\\btransfer\\b/.test(t))return "transferencia";
  if(/\\b6\\s*cuotas\\b|\\bseis\\s*cuotas\\b/.test(t))return "cuotas_6";
  if(/\\b3\\s*cuotas\\b|\\btres\\s*cuotas\\b|\\bcuotas\\b/.test(t))return "cuotas_3";
  return null;}
function renderClose(mk){
  const p=pickProducts(1)[0];
  const m=(D.ladder||[]).find(x=>x.method_key===mk)||(D.ladder||[]).reduce((a,b)=>a.multiplier<b.multiplier?a:b);
  const tot=p.price*m.multiplier;
  const per=m.cuotas>1?` (${m.cuotas}× ${ars(tot/m.cuotas)})`:"";
  return `${CLOSE_INTRO[SALT].replace("{n}",p.name).replace("{m}",m.label.toLowerCase()).replace("{t}",ars(tot)).replace("{x}",per)} Completá el pago acá y queda confirmado: <a href="#" onclick="return false">laferia.example/checkout/${p.sku}?pago=${m.method_key}</a> 🧾 — cualquier cosa me escribís por acá.`;
}
const FUNNEL_B=new Set(["answer_size_posture","ask_recommendation","want_to_buy","answer_for_whom"]);
const ACK_B=new Set(["confirmation","awaiting_reply"]);
function classBReply(intent, rawText){
  if(FUNNEL_B.has(intent)&&BOT.slots.size){const r=renderReco();if(r){lastBotIntent="answer_size_posture";return [r,"class_b_recommend"];}}
  if(intent==="answer_payment_choice"&&BOT.recommended){lastBotIntent="answer_payment_choice";return [renderPayments(),"class_b_payments"];}
  if(ACK_B.has(intent)&&BOT.recommended&&!BOT.offered){lastBotIntent="answer_payment_choice";return [renderPayments(),"class_b_payments"];}
  if(intent==="price"&&BOT.recommended){lastBotIntent="answer_payment_choice";return [renderPayments(),"class_b_payments"];}
  return null;
}
function pickReply(intent){
  const pool=D.variants[intent]||[];
  if(!pool.length) return null;
  let cands=pool.filter(v=>v!==lastServed[intent]);
  if(!cands.length) cands=pool;
  const r=cands[Math.floor(Math.random()*cands.length)];
  lastServed[intent]=r;
  return r;
}
const F="font:14.5px/1.45 -apple-system,'Segoe UI',sans-serif";
function bubble(side, html){
  const b=document.createElement("div");
  b.style.cssText=side==="user"
    ?`align-self:flex-end;max-width:75%;background:#d9fdd3;border-radius:10px 10px 2px 10px;padding:7px 11px;${F};box-shadow:0 1px 1px rgba(0,0,0,.08)`
    :`align-self:flex-start;max-width:80%;background:#fff;border-radius:10px 10px 10px 2px;padding:7px 11px;${F};box-shadow:0 1px 1px rgba(0,0,0,.08)`;
  b.innerHTML=html;
  $("demo-thread").appendChild(b);
  $("demo-thread").scrollTop=$("demo-thread").scrollHeight;
}
const meta=t=>`<div style="color:#8a948e;font-size:10.5px;margin-top:3px;font-family:var(--mono)">${t}</div>`;
function welcome(){
  lastBotIntent="greet";
  const g=pickReply("greet");
  if(g) bubble("bot",`${g}${meta("greet · plantilla local · $0.00")}`);
}
let extractor=null, count=0;
async function init(){
  status("⏳ descargando el modelo desde Hugging Face (una vez, queda cacheado)…");
  const {pipeline}=await import("https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.3.1");
  extractor=await pipeline("feature-extraction",D.model,{dtype:"q8",
    progress_callback:p=>{ if(p.status==="progress"&&p.file?.endsWith(".onnx"))
      status(`⏳ modelo: ${(p.progress||0).toFixed(0)}%`); }});
  status("✅ listo");
  $("demo-send").disabled=false; welcome();
}
const SAL_RX=/^(holi+s*|hola+|buenas( tardes| noches)?|buen d[ií]a|buenos d[ií]as)[\\s,!.:;]*((c[oó]mo|como) (va|est[aá]s|est[aá]n|andas)\\??)?[\\s,!.:;]*/i;
async function ask(text){
  if(!extractor||!text.trim()) return;
  $("demo-input").value="";
  bubble("user",text);
  extractSlots(text);
  // the close is slot-gated, not similarity-gated (serving.py parity):
  // a stated payment choice after a recommendation means one thing.
  const pmEarly=detectPayment(text);
  if(pmEarly && BOT.recommended && text.trim().split(/\\s+/).length<=8){
    count++; lastBotIntent="close";
    bubble("bot",`${renderClose(pmEarly)}${meta("answer_payment_choice · catálogo local · $0.00 · class_b_close")}`);
    $("demo-counter").textContent=`${count} decisión(es) — gasto acumulado de API: $0.00 (no hay API)`;
    return;
  }
  // payment-options ASK after a recommendation: a ladder lookup, not a similarity call
  if(!pmEarly && BOT.recommended && text.trim().split(/\\s+/).length<=10
     && /opciones\\s+de\\s+pago|formas?\\s+de\\s+pago|c[oó]mo\\s+(se\\s+)?paga|c[oó]mo\\s+puedo\\s+pagar|medios\\s+de\\s+pago/i.test(text)){
    count++; lastBotIntent="answer_payment_choice";
    bubble("bot",`${renderPayments()}${meta("answer_payment_choice · catálogo local · $0.00 · class_b_payments")}`);
    $("demo-counter").textContent=`${count} decisión(es) — gasto acumulado de API: $0.00 (no hay API)`;
    return;
  }
  // salutation decomposition: greet + concern → route the concern
  let target=text, saluted=false;
  const sm=text.trim().match(SAL_RX);
  if(sm && sm[0].length>0){
    const rest=text.trim().slice(sm[0].length).replace(/^[\\s,.!¡¿?:;]+|[\\s,.!¡¿?:;]+$/g,"");
    if(rest.split(/\\s+/).length>=2){ target=rest; saluted=true; }
  }
  const out=await extractor(target,{pooling:"mean",normalize:true});
  let d=decide(Array.from(out.data), target.trim().split(/\\s+/).length, target);
  if(saluted && d.verdict!=="serve"){
    const out2=await extractor(text,{pooling:"mean",normalize:true});
    d=decide(Array.from(out2.data), text.trim().split(/\\s+/).length, text);
  } else if(saluted && d.verdict==="serve" && d.intent!=="greet"){
    d.salutation=true;
  }
  count++;
  const m=`${d.intent} · s ${d.score.toFixed(2)} · ${d.ms.toFixed(0)} ms · $0.00`+(d.reason?` · ${d.reason}`:"");
  if(d.verdict==="serve"){
    let r, mm=m;
    const cb=classBReply(d.intent, text);
    if(cb){ r=cb[0]; mm=`${d.intent} · catálogo local · $0.00 · ${cb[1]}`; }
    else if(d.intent==="greet" && lastBotIntent==="greet"){
      r=GREET_AGAIN[Math.floor(Math.random()*GREET_AGAIN.length)]; lastBotIntent=d.intent;
    } else { r=pickReply(d.intent); lastBotIntent=d.intent; }
    if(d.salutation && !cb) r="¡Hola! "+r.charAt(0).toLowerCase()+r.slice(1);
    bubble("bot",`${r}${meta(mm)}`);
  } else if(d.verdict==="hit"){
    bubble("bot",`<em style="color:#9a6b00">plantilla en re-auditoría — acá contestaría el LLM de fallback</em>${meta(m)}`);
  } else {
    bubble("bot",`<em style="color:#8a948e">el caché prefiere callar — acá contestaría el LLM de fallback (centavos, nunca mentiras)</em>${meta(m)}`);
  }
  $("demo-counter").textContent=
    `${count} decisión(es) — gasto acumulado de API: $0.00 (no hay API)`;
}
D.scenarios.forEach(([label,text])=>{
  const b=document.createElement("button");
  b.textContent=label;
  b.style.cssText="padding:6px 12px;border:1px solid var(--line);border-radius:16px;background:#fff;cursor:pointer;font-size:13px";
  b.onclick=()=>ask(text);
  $("demo-chips").appendChild(b);
});
$("demo-send").disabled=true;
$("demo-send").onclick=()=>ask($("demo-input").value);
$("demo-input").addEventListener("keydown",e=>{ if(e.key==="Enter") ask($("demo-input").value); });
init();
</script>
"""


def main() -> None:
    st = stats()
    files = sorted(CHAPTERS.glob("*.md"))
    if not files:
        sys.exit("no chapters/ found")
    toc, body = [], []
    for i, f in enumerate(files, 1):
        md = resolve(f.read_text(encoding="utf-8"), st)
        first = next((l for l in md.split("\n") if l.startswith("# ")), f.stem)
        title = first.lstrip("# ").strip()
        anchor = f"ch{i}"
        toc.append(f'<a href="#{anchor}">Chapter {i}: {title}</a>')
        body.append(f'<div class="chapter" id="{anchor}">'
                    + md_to_html(md) + "</div>")
    demo_html = ""
    demo_data = REPO / "web" / "demo-data.json"
    if demo_data.exists():
        demo_html = DEMO_SECTION.replace(
            "__DEMO_DATA__", demo_data.read_text(encoding="utf-8"))
        toc.insert(0, '<a href="#live-demo">▶ Live demo (in-browser, $0)</a>')

    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{TITLE}</title><style>{CSS}</style></head><body><div class="wrap">
<header><h1>Gaucho Caché</h1>
<p>{TITLE.split("— ")[1]} · build {st.get("commit", "?")} ·
{st.get("total_rows", "?")} generated variants</p></header>
<nav>{"".join(toc)}</nav>
{demo_html}
{"".join(body)}
<footer>Generated by scripts/build_book.py — methodology ported from
<a href="https://miguelemosreverte.github.io/models-medical-evaluation/">models-medical-evaluation</a></footer>
</div></body></html>"""
    OUT.write_text(doc, encoding="utf-8")
    (REPO / "book_report.html").write_text(doc, encoding="utf-8")
    print(f"✓ built {OUT} ({len(files)} chapters, {len(doc)//1024}KB)")


if __name__ == "__main__":
    main()
