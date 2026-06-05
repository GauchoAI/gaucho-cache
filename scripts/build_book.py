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
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{TITLE}</title><style>{CSS}</style></head><body><div class="wrap">
<header><h1>Gaucho Caché</h1>
<p>{TITLE.split("— ")[1]} · build {st.get("commit", "?")} ·
{st.get("total_rows", "?")} generated variants</p></header>
<nav>{"".join(toc)}</nav>
{"".join(body)}
<footer>Generated by scripts/build_book.py — methodology ported from
<a href="https://miguelemosreverte.github.io/models-medical-evaluation/">models-medical-evaluation</a></footer>
</div></body></html>"""
    OUT.write_text(doc, encoding="utf-8")
    (REPO / "book_report.html").write_text(doc, encoding="utf-8")
    print(f"✓ built {OUT} ({len(files)} chapters, {len(doc)//1024}KB)")


if __name__ == "__main__":
    main()
