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
<p>This is not a video and there is no server: the embedding model
(<code>Xenova/paraphrase-multilingual-mpnet-base-v2</code>) downloads once
from the Hugging Face Hub and runs <strong>inside this tab</strong>
(transformers.js); the index, thresholds and match contracts are inlined
in this very HTML file. After the model loads you can go offline — the
bot keeps deciding. Open DevTools → Network and watch: no API calls,
ever.</p>
<p id="demo-status" style="font-family:var(--mono);font-size:13px"></p>
<div id="demo-chips" style="display:flex;flex-wrap:wrap;gap:8px;margin:12px 0"></div>
<div style="display:flex;gap:8px">
<input id="demo-input" placeholder="Escribile al bot (etapa de objeciones)… typos y lunfardo bienvenidos"
 style="flex:1;padding:10px 14px;border:1px solid var(--line);border-radius:8px;font:15px Georgia"/>
<button id="demo-send" style="padding:10px 18px;border:0;border-radius:8px;
background:var(--accent);color:#fff;font-weight:bold;cursor:pointer">→</button>
</div>
<div id="demo-out" style="margin-top:14px"></div>
<p id="demo-counter" style="color:var(--soft);font-size:14px"></p>
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
for (let i=0;i<u16.length;i++){ // f16 -> f32
  const h=u16[i],s=(h&0x8000)>>15,e=(h&0x7C00)>>10,f=h&0x03FF;
  EMB[i]=(e===0?(s?-1:1)*Math.pow(2,-14)*(f/1024)
   :e===31?(f?NaN:(s?-1:1)*Infinity)
   :(s?-1:1)*Math.pow(2,e-15)*(1+f/1024));
}
const N=D.n, DIM=D.dim;
const POS=[],NEG={};
D.intents.forEach((it,i)=>{ if(D.kinds[i]==="positive") POS.push([it,i]);
  else (NEG[it]=NEG[it]||[]).push(i); });

function decide(q){
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
  let verdict="miss", reason="";
  if(s1<th.threshold) reason="below_threshold";
  else if(th2 && s2>=Math.min(th2.threshold,D.compound_floor)) reason="multi_intent (mensaje compuesto)";
  else if(s1-s2<th.margin) reason="ambiguous_margin";
  else if(s1-ns<th.negative_margin) reason="negative_margin (patrón impostor conocido)";
  else if((c.requires_state||[]).length) reason="precondition_failed (estado de stock desconocido)";
  else if(!c.audited){ verdict="hit"; reason="template_unaudited (shadow-only)"; }
  else verdict="serve";
  const pool=D.variants[i1]||[];
  const reply=(verdict==="serve"&&pool.length)?pool[Math.floor(Math.random()*pool.length)]:null;
  return {verdict,reason,intent:i1,score:s1,margin:s1-s2,negMargin:s1-ns,
          reply,ms:performance.now()-t0};
}

let extractor=null, count=0;
async function init(){
  status("⏳ descargando el modelo desde Hugging Face (una vez, queda cacheado)…");
  const {pipeline}=await import("https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.3.1");
  extractor=await pipeline("feature-extraction",D.model,{dtype:"q8",
    progress_callback:p=>{ if(p.status==="progress"&&p.file?.endsWith(".onnx"))
      status(`⏳ modelo: ${(p.progress||0).toFixed(0)}%`); }});
  status("✅ modelo listo — el bot corre en esta pestaña. Probá los escenarios o escribí lo que quieras.");
  $("demo-send").disabled=false;
}
async function ask(text){
  if(!extractor||!text.trim()) return;
  status("…");
  const out=await extractor(text,{pooling:"mean",normalize:true});
  const d=decide(Array.from(out.data));
  count++;
  const color=d.verdict==="serve"?"#0b6e4f":d.verdict==="hit"?"#9a6b00":"#a33";
  const label=d.verdict==="serve"?"SERVE":d.verdict==="hit"?"HIT (no-serve)":"MISS";
  $("demo-out").innerHTML=`
   <div style="border:1px solid var(--line);border-radius:10px;padding:14px 18px;background:#fff">
   <div><span style="color:${color};font-weight:bold">${label}</span>
   <span style="color:var(--soft)"> · intent <code>${d.intent}</code> · score ${d.score.toFixed(3)}
   · margin ${d.margin.toFixed(3)} · neg ${d.negMargin.toFixed(3)}
   · <strong>${d.ms.toFixed(1)} ms · $0.00</strong></span></div>
   ${d.reason?`<div style="color:var(--soft);font-size:14px">razón: ${d.reason} → este turno iría al LLM de fallback</div>`:""}
   ${d.reply?`<div style="margin-top:10px;padding:10px 14px;background:#eef7f3;border-radius:10px">🤖 ${d.reply}</div>`:""}
   </div>`;
  status("✅ listo");
  $("demo-counter").textContent=
    `${count} decisión(es) en esta sesión — gasto acumulado de API: $0.00 (no hay API)`;
}
D.scenarios.forEach(([label,text])=>{
  const b=document.createElement("button");
  b.textContent=label;
  b.style.cssText="padding:6px 12px;border:1px solid var(--line);border-radius:16px;background:#fff;cursor:pointer;font-size:13px";
  b.onclick=()=>{ $("demo-input").value=text; ask(text); };
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
