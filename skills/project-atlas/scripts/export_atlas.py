#!/usr/bin/env python3
"""
export_atlas.py - look at an atlas outside Obsidian.

Two modes:

  --check   For Claude, right after rendering: draws every canvas as an image (PNG, when a
            Chrome / Edge / Chromium browser is installed) and reports cards whose text does
            not fit and cards that overlap. Look at the images before handing the atlas over.

  default   For sharing: one self-contained HTML file with every canvas (zoom, tabs) and every
            note (opens in a side panel), e.g. to send to a client or a teammate who has no
            Obsidian. Add --png for images, e.g. for a README. "My notes" sections are left out
            unless you pass --include-my-notes.

Standard library only (Python 3.8+). PNGs need a Chromium-based browser; without one you get
the HTML only.

Usage:
  python export_atlas.py "<atlas folder>" --check --out <temp dir>
  python export_atlas.py "<atlas folder>" --out <dir> [--png] [--include-my-notes] [--browser PATH]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

KEEP_MARK_RE = re.compile(r"%%\s*atlas:my-notes.*?%%", re.S)
COLORS = {"1": "#e93147", "2": "#ec7500", "3": "#e0ac00", "4": "#08b94e", "5": "#00bfbc", "6": "#a882ff"}


# --------------------------------------------------------------------------- browser

def find_browser(explicit: str | None = None) -> str | None:
    cands = [explicit, os.environ.get("ATLAS_BROWSER")]
    if sys.platform.startswith("win"):
        for base in (os.environ.get("PROGRAMFILES(X86)"), os.environ.get("PROGRAMFILES"), os.environ.get("LOCALAPPDATA")):
            if base:
                cands += [str(Path(base) / "Microsoft/Edge/Application/msedge.exe"),
                          str(Path(base) / "Google/Chrome/Application/chrome.exe"),
                          str(Path(base) / "Chromium/Application/chrome.exe"),
                          str(Path(base) / "BraveSoftware/Brave-Browser/Application/brave.exe")]
    elif sys.platform == "darwin":
        cands += ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                  "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                  "/Applications/Chromium.app/Contents/MacOS/Chromium",
                  "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"]
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge",
                 "microsoft-edge-stable", "brave-browser", "chrome", "msedge"):
        found = shutil.which(name)
        if found:
            cands.append(found)
    for c in cands:
        if c and Path(c).exists():
            return c
    return None


def run_browser(browser: str, page: Path, workdir: Path, *extra: str, timeout: int = 90) -> subprocess.CompletedProcess:
    """Run a headless browser with a throw-away profile inside workdir."""
    profile = Path(tempfile.mkdtemp(prefix=".browser-", dir=workdir))
    args = [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
            "--no-default-browser-check", "--disable-extensions", f"--user-data-dir={profile}",
            "--force-device-scale-factor=1", "--virtual-time-budget=3000", *extra, page.resolve().as_uri()]
    try:
        return subprocess.run(args, capture_output=True, timeout=timeout)
    finally:
        shutil.rmtree(profile, ignore_errors=True)


def file_safe(s: str) -> str:
    return re.sub(r"[^\w .,()&'+-]+", "_", s).strip() or "atlas"


# --------------------------------------------------------------------------- markdown

def inline(text: str, link) -> str:
    """Escape and render inline Markdown. link(target, alias) -> html."""
    codes = []

    def keep_code(m):
        codes.append(f"<code>{html.escape(m.group(1))}</code>")
        return f"\x00{len(codes) - 1}\x00"
    text = re.sub(r"`([^`]+)`", keep_code, text)
    links = []

    def keep_wiki(m):
        target, _, alias = m.group(1).partition("|")
        links.append(link(target.strip(), (alias or target.split("/")[-1]).strip()))
        return f"\x01{len(links) - 1}\x01"
    text = re.sub(r"\[\[([^\]]+)\]\]", keep_wiki, text)

    def keep_md(m):
        url = m.group(2).strip().strip("<>")
        safe = url if re.match(r"^(https?:|mailto:)", url) else "#"
        links.append(f'<a href="{html.escape(safe)}" target="_blank" rel="noopener">{html.escape(m.group(1))}</a>')
        return f"\x01{len(links) - 1}\x01"
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", keep_md, text)
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", text)
    text = re.sub(r"~~(.+?)~~", r"<del>\1</del>", text)
    text = re.sub(r"\x01(\d+)\x01", lambda m: links[int(m.group(1))], text)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], text)


def markdown(md: str, link, drop_my_notes: bool = True) -> str:
    md = re.sub(r"\A---\n.*?\n---\n", "", md, flags=re.S)
    if drop_my_notes:
        md = re.split(r"\n## [^\n]*\n" + KEEP_MARK_RE.pattern, md, maxsplit=1, flags=re.S)[0]
    md = KEEP_MARK_RE.sub("", md)
    out, lines, i = [], md.split("\n"), 0
    list_stack: list = []

    def close_lists(to=0):
        while len(list_stack) > to:
            out.append(f"</{list_stack.pop()}>")

    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            close_lists()
            lang = line[3:].strip()
            body = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                body.append(lines[i])
                i += 1
            code = html.escape("\n".join(body))
            out.append(f'<pre class="mermaid">{code}</pre>' if lang == "mermaid" else f"<pre><code>{code}</code></pre>")
            i += 1
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            close_lists()
            n = len(m.group(1))
            out.append(f"<h{n}>{inline(m.group(2), link)}</h{n}>")
            i += 1
            continue
        if line.startswith(">"):
            close_lists()
            block = []
            while i < len(lines) and lines[i].startswith(">"):
                block.append(lines[i][1:].lstrip(" ") if len(lines[i]) > 1 else "")
                i += 1
            cm = re.match(r"^\[!(\w+)\]\s*(.*)$", block[0]) if block else None
            inner = markdown("\n".join(block[1:] if cm else block), link, False)
            if cm:
                out.append(f'<div class="callout callout-{html.escape(cm.group(1).lower())}">'
                           f'<div class="callout-title">{inline(cm.group(2), link)}</div>{inner}</div>')
            else:
                out.append(f"<blockquote>{inner}</blockquote>")
            continue
        if line.startswith("|"):
            close_lists()
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.match(r"^:?-{2,}:?$", c) or c == "" for c in cells) or not rows:
                    rows.append(cells)
                i += 1
            rows = [r for r in rows if not all(re.match(r"^:?-{2,}:?$", c) for c in r if c)]
            body = "".join("<tr>" + "".join(f"<td>{inline(c, link)}</td>" for c in r) + "</tr>" for r in rows)
            out.append(f"<table>{body}</table>")
            continue
        m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", line)
        if m:
            depth = len(m.group(1).replace("\t", "    ")) // 2 + 1
            tag = "ol" if m.group(2)[0].isdigit() else "ul"
            if len(list_stack) < depth:
                while len(list_stack) < depth:
                    list_stack.append(tag)
                    out.append(f"<{tag}>")
            else:
                close_lists(depth)
            out.append(f"<li>{inline(m.group(3), link)}</li>")
            i += 1
            continue
        if re.match(r"^\s*-{3,}\s*$", line):
            close_lists()
            out.append("<hr>")
            i += 1
            continue
        if not line.strip():
            close_lists()
            i += 1
            continue
        close_lists()
        para = []
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,6}\s|>|\||```|\s*([-*]|\d+\.)\s|\s*-{3,}\s*$)", lines[i]):
            para.append(inline(lines[i], link))
            i += 1
        out.append(f"<p>{'<br>'.join(para)}</p>")
    close_lists()
    return "\n".join(out)


# --------------------------------------------------------------------------- atlas loading

class AtlasFiles:
    def __init__(self, folder: Path):
        self.folder = folder.resolve()
        vault = next((d for d in [self.folder, *self.folder.parents] if (d / ".obsidian").is_dir()), self.folder)
        rel = self.folder.relative_to(vault).as_posix() if vault != self.folder else ""
        self.prefix = (rel + "/") if rel else ""
        self.spec = {}
        if (self.folder / "atlas.json").exists():
            try:
                self.spec = json.loads((self.folder / "atlas.json").read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError):
                pass
        self.name = (self.spec.get("project") or {}).get("name") or self.folder.name
        self.canvases = sorted(p.relative_to(self.folder).as_posix() for p in self.folder.rglob("*.canvas"))
        self.notes = sorted(p.relative_to(self.folder).as_posix()[:-3] for p in self.folder.rglob("*.md")
                            if "history" not in p.relative_to(self.folder).parts)

    def local(self, target: str) -> str | None:
        """Vault-path link target -> path inside the atlas folder (no .md), or None if outside."""
        t = target.split("#")[0].strip()
        if self.prefix and t.startswith(self.prefix):
            t = t[len(self.prefix):]
        if t.endswith(".canvas"):
            return t if t in self.canvases else None
        t = t[:-3] if t.endswith(".md") else t
        if t in self.notes:
            return t
        tail = [n for n in self.notes if n.split("/")[-1] == t.split("/")[-1]]
        return tail[0] if len(tail) == 1 else None

    def link_html(self, target: str, alias: str) -> str:
        loc = self.local(target)
        if loc is None:
            return f'<span class="wl-missing">{html.escape(alias)}</span>'
        return f'<a class="wl" href="#" data-target="{html.escape(loc)}">{html.escape(alias)}</a>'


def canvas_title(path: str) -> str:
    return Path(path).stem


# --------------------------------------------------------------------------- canvas drawing

def side_point(n, side):
    x, y, w, h = n["x"], n["y"], n["width"], n["height"]
    return {"top": (x + w / 2, y), "bottom": (x + w / 2, y + h), "left": (x, y + h / 2),
            "right": (x + w, y + h / 2)}.get(side, (x + w / 2, y + h / 2))


def board_html(canvas: dict, files: AtlasFiles) -> tuple:
    """Returns (html, width, height) for one canvas, positioned from (0, 0)."""
    nodes = canvas.get("nodes") or []
    if not nodes:
        return '<div class="board" style="width:400px;height:200px"></div>', 400, 200
    pad = 60
    ox = min(n["x"] for n in nodes) - pad
    oy = min(n["y"] for n in nodes) - pad - 30
    w = max(n["x"] + n["width"] for n in nodes) - ox + pad
    h = max(n["y"] + n["height"] for n in nodes) - oy + pad
    parts = [f'<div class="board" style="width:{w}px;height:{h}px">']
    byid = {n["id"]: n for n in nodes}
    for n in nodes:
        col = n.get("color", "")
        c = COLORS.get(col, col if str(col).startswith("#") else "")
        style = f"left:{n['x'] - ox}px;top:{n['y'] - oy}px;width:{n['width']}px;height:{n['height']}px"
        cvar = f";--c:{c}" if c else ""
        if n.get("type") == "group":
            parts.append(f'<div class="group{" colored" if c else ""}" style="{style}{cvar}"></div>')
            parts.append(f'<div class="group-label" style="left:{n["x"] - ox}px;top:{n["y"] - oy - 30}px">'
                         f'{html.escape(n.get("label", ""))}</div>')
        elif n.get("type") == "text":
            body = markdown(n.get("text", ""), files.link_html, False)
            parts.append(f'<div class="card{" colored" if c else ""}" data-id="{n["id"]}" style="{style}{cvar}">'
                         f'<div class="content">{body}</div></div>')
        elif n.get("type") == "file":
            parts.append(f'<div class="card" style="{style}"><div class="content">'
                         f'{files.link_html(n.get("file", ""), Path(n.get("file", "")).stem)}</div></div>')
    svg = [f'<svg class="edges" width="{w}" height="{h}" viewBox="0 0 {w} {h}">']
    for e in canvas.get("edges") or []:
        a, b = byid.get(e.get("fromNode")), byid.get(e.get("toNode"))
        if not a or not b:
            continue
        p1, p2 = side_point(a, e.get("fromSide", "right")), side_point(b, e.get("toSide", "left"))
        d = max(40, min(160, (abs(p1[0] - p2[0]) + abs(p1[1] - p2[1])) / 3))
        off = {"top": (0, -d), "bottom": (0, d), "left": (-d, 0), "right": (d, 0)}
        c1 = (p1[0] + off.get(e.get("fromSide", "right"))[0], p1[1] + off.get(e.get("fromSide", "right"))[1])
        c2 = (p2[0] + off.get(e.get("toSide", "left"))[0], p2[1] + off.get(e.get("toSide", "left"))[1])
        pts = [(x - ox, y - oy) for x, y in (p1, c1, c2, p2)]
        col = COLORS.get(e.get("color", ""), "")
        stroke = f' style="stroke:{col}"' if col else ""
        svg.append(f'<path d="M{pts[0][0]:.0f},{pts[0][1]:.0f} C{pts[1][0]:.0f},{pts[1][1]:.0f} '
                   f'{pts[2][0]:.0f},{pts[2][1]:.0f} {pts[3][0]:.0f},{pts[3][1]:.0f}"{stroke} marker-end="url(#arrow)"/>')
    svg.append('<defs><marker id="arrow" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto">'
               '<path d="M0,0 L12,6 L0,12 z" class="arrowhead"/></marker></defs></svg>')
    parts.insert(1, "".join(svg))
    parts.append("</div>")
    return "".join(parts), w, h


BASE_CSS = """
:root{--bg:#1e1e1e;--card:#262626;--fg:#dcddde;--muted:#9a9a9a;--line:#5a5a5a;--link:#a68af9;--panel:#202020;--bar:#181818}
@media (prefers-color-scheme: light){:root:not(.dark){--bg:#f6f6f4;--card:#ffffff;--fg:#222;--muted:#666;--line:#b8b8b8;--link:#6d4fd8;--panel:#fff;--bar:#ececea}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Inter",sans-serif}
.board{position:relative}
.edges{position:absolute;left:0;top:0;pointer-events:none;overflow:visible}
.edges path{fill:none;stroke:var(--muted);stroke-width:2.5}
.arrowhead{fill:var(--muted)}
.group{position:absolute;border:2px solid var(--line);border-radius:12px}
.group.colored{border-color:var(--c);background:color-mix(in srgb,var(--c) 7%,transparent)}
.group-label{position:absolute;font-size:15px;padding:2px 10px;border-radius:6px;background:var(--bar);color:var(--fg);white-space:nowrap}
.card{position:absolute;background:var(--card);border:2px solid var(--line);border-radius:10px;overflow:hidden}
.card.colored{border-color:var(--c);background:color-mix(in srgb,var(--c) 9%,var(--card))}
.card .content{padding:12px 20px}
.content>:first-child{margin-top:0}
.content p{margin:0 0 .6em}
.content h1{font-size:1.6em;margin:.2em 0 .3em;line-height:1.2}
.content h2{font-size:1.35em;margin:.6em 0 .3em}
.content h3{font-size:1.15em;margin:.1em 0 .35em;line-height:1.3}
.content ul,.content ol{margin:.2em 0 .6em;padding-left:1.3em}
.content li{margin:.1em 0}
.content table{border-collapse:collapse;margin:.4em 0}
.content td{border:1px solid var(--line);padding:3px 8px}
.content pre{background:color-mix(in srgb,var(--fg) 6%,transparent);padding:8px 10px;border-radius:6px;overflow:auto;font-size:13px}
.content code{font-size:.88em;background:color-mix(in srgb,var(--fg) 8%,transparent);padding:1px 4px;border-radius:4px}
.content blockquote{margin:.4em 0;padding:.2em .9em;border-left:3px solid var(--line);color:var(--muted)}
.callout{border-left:4px solid var(--link);background:color-mix(in srgb,var(--link) 8%,transparent);padding:.5em .9em;border-radius:6px;margin:.6em 0}
.callout-title{font-weight:600;margin-bottom:.2em}
.callout-danger{border-color:#e93147}.callout-warning{border-color:#ec7500}.callout-success{border-color:#08b94e}
.callout-question,.callout-example{border-color:#a882ff}.callout-tip,.callout-info,.callout-abstract{border-color:#00bfbc}
a.wl,a{color:var(--link);text-decoration:underline;text-underline-offset:2px;cursor:pointer}
.wl-missing{color:var(--fg)}
.overflow{outline:4px solid #e93147;outline-offset:2px}
"""

CHECK_JS = """
const out=[];
document.querySelectorAll('.card').forEach(c=>{const k=c.querySelector('.content');
 const need=k.scrollHeight, have=c.clientHeight;
 if(need>have+2){c.classList.add('overflow');out.push({id:c.dataset.id||'',need:need,have:have,
   text:(k.innerText||'').replace(/\\s+/g,' ').slice(0,70)})}});
const r=document.createElement('pre');r.id='atlas-report';r.style.display='none';
r.textContent=JSON.stringify(out);document.body.appendChild(r);
"""


def check_page(board: str) -> str:
    return (f"<!doctype html><html class='dark'><head><meta charset='utf-8'><style>{BASE_CSS}</style></head>"
            f"<body>{board}<script>{CHECK_JS}</script></body></html>")


def overlaps(canvas: dict) -> list:
    cards = [n for n in canvas.get("nodes") or [] if n.get("type") != "group"]
    hits = []
    for i, a in enumerate(cards):
        for b in cards[i + 1:]:
            if (a["x"] < b["x"] + b["width"] and b["x"] < a["x"] + a["width"]
                    and a["y"] < b["y"] + b["height"] and b["y"] < a["y"] + a["height"]):
                hits.append((a, b))
    return hits


def edge_crossings(canvas: dict) -> list:
    """Arrows that pass behind a card they don't connect: on a canvas that reads as if they fed that card.
    Follows the same curve as the drawing (a cubic curve leaving and entering each card's side)."""
    nodes = canvas.get("nodes") or []
    byid = {n["id"]: n for n in nodes}
    cards = [n for n in nodes if n.get("type") != "group"]
    hits = []
    for e in canvas.get("edges") or []:
        a, b = byid.get(e.get("fromNode")), byid.get(e.get("toNode"))
        if not a or not b:
            continue
        fs, ts = e.get("fromSide", "right"), e.get("toSide", "left")
        p1, p2 = side_point(a, fs), side_point(b, ts)
        d = max(40, min(160, (abs(p1[0] - p2[0]) + abs(p1[1] - p2[1])) / 3))
        off = {"top": (0, -d), "bottom": (0, d), "left": (-d, 0), "right": (d, 0)}
        c1 = (p1[0] + off[fs][0], p1[1] + off[fs][1])
        c2 = (p2[0] + off[ts][0], p2[1] + off[ts][1])
        for c in cards:
            if c is a or c is b:
                continue
            x0, y0, x1, y1 = c["x"] + 6, c["y"] + 6, c["x"] + c["width"] - 6, c["y"] + c["height"] - 6
            for k in range(1, 40):
                t = k / 40
                u = 1 - t
                x = u ** 3 * p1[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t ** 3 * p2[0]
                y = u ** 3 * p1[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t ** 3 * p2[1]
                if x0 < x < x1 and y0 < y < y1:
                    hits.append((a, b, c))
                    break
    return hits


def short(n) -> str:
    t = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", n.get("text", n.get("label", "")))
    return re.sub(r"[#*_`>\s]+", " ", t).strip()[:60]


# --------------------------------------------------------------------------- modes

def do_check(files: AtlasFiles, out: Path, browser: str | None) -> int:
    out.mkdir(parents=True, exist_ok=True)
    problems = 0
    print(f"Checking the canvases of '{files.name}'" + ("" if browser else " (no Chrome/Edge/Chromium found: HTML only, "
          "no images and no text-fit check; open the HTML files to look)"))
    for rel in files.canvases:
        canvas = json.loads((files.folder / rel).read_text(encoding="utf-8"))
        board, w, h = board_html(canvas, files)
        page = out / (re.sub(r"[^\w.-]+", "_", rel) + ".html")
        page.write_text(check_page(board), encoding="utf-8")
        cards = sum(1 for n in canvas.get("nodes", []) if n.get("type") != "group")
        line = f"- {rel}: {cards} cards, {len(canvas.get('edges', []))} arrows, {w}x{h}px"
        issues = []
        for a, b in overlaps(canvas):
            issues.append(f"cards overlap: '{short(a)}' / '{short(b)}'")
        for a, b, c in edge_crossings(canvas):
            issues.append(f"arrow '{short(a)[:30]}' → '{short(b)[:30]}' passes behind '{short(c)[:30]}'")
        if browser:
            r = run_browser(browser, page, out, "--dump-dom", f"--window-size={w},{h}")
            m = re.search(r'<pre id="atlas-report"[^>]*>(.*?)</pre>', r.stdout.decode("utf-8", "replace"), re.S)
            if m:
                for o in json.loads(html.unescape(m.group(1))):
                    issues.append(f"text does not fit ({o['need']}px needed, {o['have']}px): '{o['text']}'")
            png = page.with_suffix(".png")
            run_browser(browser, page, out, f"--screenshot={png}", f"--window-size={w},{h}")
            if png.exists():
                line += f" -> {png}"
        print(line)
        for s in issues:
            print(f"    ! {s}")
        problems += len(issues)
    print("No problems found." if not problems else f"{problems} problem(s): fix the wording or the atlas and render again.")
    return 0


SHARE_JS = r"""
const DATA=JSON.parse(document.getElementById('atlas-data').textContent);
const tabs=document.getElementById('tabs'), view=document.getElementById('view'), panel=document.getElementById('panel');
let scale=1, current=null;
function el(t,c,h){const e=document.createElement(t);if(c)e.className=c;if(h!==undefined)e.innerHTML=h;return e}
function showOverview(){current='__overview';setActive();view.innerHTML='';const d=el('div','note page',DATA.home||'');view.appendChild(d);renderMermaid(d)}
function showCanvas(key){const c=DATA.canvases[key];if(!c)return;current=key;setActive();view.innerHTML='';
 const wrap=el('div','board-wrap');wrap.innerHTML=c.html;view.appendChild(wrap);fit();}
function fit(){const w=view.clientWidth-40, b=view.querySelector('.board');if(!b)return;scale=Math.min(1,w/b.offsetWidth);apply()}
function apply(){const b=view.querySelector('.board');if(!b)return;b.style.transform='scale('+scale+')';b.style.transformOrigin='0 0';
 const wrap=view.querySelector('.board-wrap');wrap.style.width=(b.offsetWidth*scale)+'px';wrap.style.height=(b.offsetHeight*scale)+'px';
 document.getElementById('zoomlabel').textContent=Math.round(scale*100)+'%'}
function zoom(f){scale=Math.max(.15,Math.min(2,scale*f));apply()}
function openNote(key){const n=DATA.notes[key];if(!n)return;panel.innerHTML='';const close=el('button','close','×');close.onclick=()=>panel.classList.remove('open');
 panel.appendChild(close);const d=el('div','note',n);panel.appendChild(d);panel.classList.add('open');panel.scrollTop=0;renderMermaid(d)}
function setActive(){tabs.querySelectorAll('button').forEach(b=>b.classList.toggle('active',b.dataset.key===current))}
document.addEventListener('click',e=>{const a=e.target.closest('a.wl');if(!a)return;e.preventDefault();const t=a.dataset.target;
 if(t.endsWith('.canvas')){showCanvas(t);panel.classList.remove('open')}else if(t===DATA.homeKey){showOverview();panel.classList.remove('open')}else openNote(t)});
let drag=null;view.addEventListener('mousedown',e=>{if(e.target.closest('a,button'))return;drag={x:e.clientX,y:e.clientY,l:view.scrollLeft,t:view.scrollTop};view.classList.add('dragging')});
window.addEventListener('mousemove',e=>{if(!drag)return;view.scrollLeft=drag.l-(e.clientX-drag.x);view.scrollTop=drag.t-(e.clientY-drag.y)});
window.addEventListener('mouseup',()=>{drag=null;view.classList.remove('dragging')});
window.addEventListener('resize',()=>{if(current&&current!=='__overview')fit()});
function addTab(key,label){const b=el('button','',label);b.dataset.key=key;b.onclick=()=>key==='__overview'?showOverview():showCanvas(key);tabs.appendChild(b)}
addTab('__overview','Overview');DATA.order.forEach(k=>addTab(k,DATA.canvases[k].title));
async function renderMermaid(root){const blocks=root.querySelectorAll('pre.mermaid');if(!blocks.length)return;
 try{const m=(await import('https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.esm.min.mjs')).default;
  m.initialize({startOnLoad:false,theme:matchMedia('(prefers-color-scheme: dark)').matches?'dark':'default'});await m.run({nodes:blocks})}catch(e){}}
DATA.order.length?showCanvas(DATA.order[0]):showOverview();
"""

SHARE_CSS = """
html,body{height:100%}
body{display:flex;flex-direction:column;overflow:hidden}
header{display:flex;flex-wrap:wrap;align-items:center;gap:8px 16px;padding:10px 16px;background:var(--bar);border-bottom:1px solid var(--line)}
header h1{font-size:18px;margin:0}
header .sub{color:var(--muted);font-size:14px;flex:1 1 300px}
#tabs{display:flex;flex-wrap:wrap;gap:6px}
#tabs button,.zoom button{font:inherit;font-size:14px;padding:4px 10px;border-radius:6px;border:1px solid var(--line);background:var(--card);color:var(--fg);cursor:pointer}
#tabs button.active{border-color:var(--link);color:var(--link)}
.zoom{display:flex;align-items:center;gap:4px;font-size:13px;color:var(--muted)}
#view{flex:1;overflow:auto;padding:20px;cursor:grab}
#view.dragging{cursor:grabbing}
.note{max-width:820px;margin:0 auto;cursor:auto}
.note.page{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 28px}
.note h1{font-size:1.7em}
.note pre.mermaid{background:transparent;text-align:center}
#panel{position:fixed;top:0;right:0;width:min(560px,100%);height:100%;overflow:auto;background:var(--panel);border-left:1px solid var(--line);
 padding:18px 26px;transform:translateX(105%);transition:transform .2s;box-shadow:-8px 0 24px rgba(0,0,0,.25);z-index:5}
#panel.open{transform:none}
#panel .close{position:sticky;top:0;float:right;font-size:22px;background:var(--card);border:1px solid var(--line);color:var(--fg);border-radius:6px;cursor:pointer;width:34px;height:34px}
footer{padding:6px 16px;font-size:12px;color:var(--muted);border-top:1px solid var(--line);background:var(--bar)}
.card .content .note{max-width:none}
"""


def do_share(files: AtlasFiles, out: Path, png: bool, browser: str | None, include_my_notes: bool,
             include_paths: bool = False) -> int:
    out.mkdir(parents=True, exist_ok=True)
    home_key = next((n for n in files.notes if n == files.name or n.split("/")[-1] == files.name), None)
    data = {"canvases": {}, "order": [], "notes": {}, "homeKey": home_key}
    boards = {}
    for rel in files.canvases:
        canvas = json.loads((files.folder / rel).read_text(encoding="utf-8"))
        board, w, h = board_html(canvas, files)
        boards[rel] = (board, w, h)
        title = canvas_title(rel) if "/" not in rel else f"{rel.split('/')[0]}: {canvas_title(rel)}"
        data["canvases"][rel] = {"title": title, "html": board}
    data["order"] = [r for r in files.canvases if "/" not in r] + [r for r in files.canvases if "/" in r]
    source = str((files.spec.get("project") or {}).get("source") or "").strip()
    for key in files.notes:
        md = (files.folder / (key + ".md")).read_text(encoding="utf-8", errors="replace")
        if source and not include_paths:
            # the owner's local folder (E:\..., /Users/...) is nobody else's business
            md = "\n".join(l for l in md.splitlines() if source not in l and source.replace("\\", "/") not in l)
        data["notes"][key] = markdown(md, files.link_html, drop_my_notes=not include_my_notes)
    data["home"] = data["notes"].get(home_key, "")
    one_liner = (files.spec.get("project") or {}).get("one_liner", "")
    stamp = _dt.date.today().isoformat()
    page = ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{html.escape(files.name)}: project atlas</title><style>{BASE_CSS}{SHARE_CSS}</style></head><body>"
            f"<header><h1>{html.escape(files.name)}</h1><span class='sub'>{html.escape(one_liner)}</span>"
            "<nav id='tabs'></nav><div class='zoom'><button onclick='zoom(1/1.25)'>−</button><span id='zoomlabel'>100%</span>"
            "<button onclick='zoom(1.25)'>+</button><button onclick='fit()'>Fit</button></div></header>"
            "<main id='view'></main><aside id='panel'></aside>"
            f"<footer>Project atlas · exported {stamp} · made with project-atlas</footer>"
            "<script type='application/json' id='atlas-data'>"
            + json.dumps(data, ensure_ascii=False).replace("</", "<\\/") +
            f"</script><script>{SHARE_JS}</script></body></html>")
    target = out / (file_safe(files.name) + " - atlas.html")
    target.write_text(page, encoding="utf-8")
    print(f"Shareable atlas -> {target}")
    print("  one file, works offline; diagrams inside notes need an internet connection to draw")
    if not include_my_notes:
        print("  'My notes' sections were left out (use --include-my-notes to keep them)")
    if source and not include_paths:
        print("  the project's local folder path was left out (use --include-paths to keep it)")
    if png:
        if not browser:
            print("  no Chrome/Edge/Chromium found, so no PNG images were made")
            return 0
        for rel, (board, w, h) in boards.items():
            tmp_page = out / ".tmp-board.html"
            tmp_page.write_text(check_page(board).replace(CHECK_JS, ""), encoding="utf-8")
            img = out / (file_safe(rel[:-len(".canvas")].replace("/", " - ")) + ".png")
            run_browser(browser, tmp_page, out, f"--screenshot={img}", f"--window-size={w},{h}")
            if tmp_page.exists():
                tmp_page.unlink()
            print(f"  image: {img}" if img.exists() else f"  could not make an image of {rel}")
    return 0


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description="Check or share a project atlas outside Obsidian.")
    ap.add_argument("atlas", type=Path, help="the project's atlas folder (the one with atlas.json)")
    ap.add_argument("--out", type=Path, required=True, help="where to write the HTML/PNG files")
    ap.add_argument("--check", action="store_true", help="render images and report layout problems")
    ap.add_argument("--png", action="store_true", help="also make PNG images (share mode)")
    ap.add_argument("--include-my-notes", action="store_true", help="keep 'My notes' sections in the shared file")
    ap.add_argument("--include-paths", action="store_true", help="keep the project's local folder path in the shared file")
    ap.add_argument("--browser", help="path to Chrome, Edge or Chromium")
    args = ap.parse_args()
    folder = args.atlas.expanduser()
    if not folder.is_dir():
        sys.exit(f"error: {folder} is not a folder")
    files = AtlasFiles(folder)
    if not files.canvases:
        sys.exit(f"error: no .canvas files in {folder}")
    browser = find_browser(args.browser) if (args.check or args.png) else None
    out = args.out.expanduser().resolve()
    sys.exit(do_check(files, out, browser) if args.check
             else do_share(files, out, args.png, browser, args.include_my_notes, args.include_paths))


if __name__ == "__main__":
    main()
