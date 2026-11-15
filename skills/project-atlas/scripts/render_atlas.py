#!/usr/bin/env python3
"""
render_atlas.py - turn an atlas.json into an Obsidian "project atlas".

Writes, into one folder of an Obsidian vault:
  * a home note named after the project,
  * one note per person, input, setting, part, storage, outside service and output,
  * one note per flow and per "what if" scenario,
  * a "Plan vs Reality" note and an optional glossary,
  * four canvases: System Map, Flows, What If, Plan vs Reality.

Every note links to the notes it relates to, so Obsidian's graph view shows the
project's structure. Text written under "My notes" at the bottom of any note is
kept when the atlas is regenerated.

Standard library only. Python 3.8+.

Usage:
  python render_atlas.py atlas.json --out "<vault>/Project Atlas/<Project>"
         [--vault <vault root>] [--setup-graph] [--dry-run]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import math
import os
import re
import shutil
import sys
import urllib.parse
from pathlib import Path

GENERATOR = "project-atlas"
VERSION = "0.1.0"
MANIFEST = ".atlas-manifest.json"
KEEP_MARK = "%% atlas:my-notes - anything below this line is kept when the atlas is regenerated %%"

KIND_ORDER = ["actor", "input", "config", "component", "store", "external", "output"]
KIND_ALIASES = {
    "person": "actor", "people": "actor", "user": "actor", "role": "actor",
    "trigger": "input", "source": "input", "entry": "input",
    "setting": "config", "settings": "config", "secret": "config", "secrets": "config", "env": "config",
    "part": "component", "module": "component", "service": "component", "step": "component",
    "storage": "store", "database": "store", "db": "store", "data": "store", "file": "store",
    "outside": "external", "api": "external", "third-party": "external", "integration": "external",
    "result": "output", "outputs": "output",
}
KIND_COLOR = {"actor": "6", "input": "5", "config": None, "component": None,
              "store": "3", "external": "2", "output": "4"}
KIND_TAG = {"actor": "atlas/person", "input": "atlas/input", "config": "atlas/setting",
            "component": "atlas/part", "store": "atlas/storage", "external": "atlas/outside",
            "output": "atlas/output"}
KIND_ICON = {"actor": "👤", "input": "📥", "config": "⚙️", "component": "🧩",
             "store": "🗄️", "external": "☁️", "output": "📤"}
KIND_CALLOUT = {"actor": "example", "input": "info", "config": "note", "component": "abstract",
                "store": "tip", "external": "warning", "output": "success"}

STATUSES = ["core", "extra", "unfinished", "unused", "risky"]
STATUS_ALIASES = {"planned": "core", "added": "extra", "new": "extra", "wip": "unfinished",
                  "partial": "unfinished", "todo": "unfinished", "dead": "unused", "leftover": "unused",
                  "unused-code": "unused", "risk": "risky"}
HANDLED = ["no", "unknown", "partly", "yes"]          # lane order on the What If canvas
HANDLED_ALIASES = {"true": "yes", "handled": "yes", "false": "no", "none": "no", "not": "no",
                   "partial": "partly", "partially": "partly", "?": "unknown", "maybe": "unknown"}
HANDLED_COLOR = {"yes": "4", "partly": "2", "no": "1", "unknown": "6"}
HANDLED_CALLOUT = {"yes": "success", "partly": "warning", "no": "danger", "unknown": "question"}
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}

REALITY_SECTIONS = ["as_planned", "added", "unfinished", "missing", "unused", "risks", "questions"]
REALITY_COLOR = {"as_planned": "4", "added": "6", "unfinished": "3", "missing": "2", "unused": None,
                 "risks": "1", "questions": "5"}
PLAN_STATUS = {"built": "✅", "partly": "🟡", "missing": "❌", "changed": "🔀", "dropped": "🗑️"}
PLAN_STATUS_ALIASES = {"done": "built", "yes": "built", "complete": "built", "partial": "partly",
                       "partially": "partly", "no": "missing", "not built": "missing", "todo": "missing",
                       "removed": "dropped", "cut": "dropped", "different": "changed"}
HISTORY_DIR = "history"

GRAPH_COLORS = {  # tag -> RGB, used by --setup-graph
    "atlas/home": 0xF5C542, "atlas/person": 0xA678DE, "atlas/input": 0x3BB8C4,
    "atlas/setting": 0x8E9AAF, "atlas/part": 0x5B8DEF, "atlas/storage": 0xE6B84C,
    "atlas/outside": 0xF08A4B, "atlas/output": 0x4CAF6E, "atlas/flow": 0x2EC4B6,
    "atlas/what-if": 0xE5534B, "atlas/reality": 0xD16BA5,
}

DEFAULT_LABELS = {
    # folders
    "folder.actor": "People", "folder.input": "Inputs", "folder.config": "Settings",
    "folder.component": "Parts", "folder.store": "Storage", "folder.external": "Outside Services",
    "folder.output": "Outputs", "folder.flow": "Flows", "folder.scenario": "What If", "folder.stage": "Stages",
    "card.comes_from": "Comes from", "card.goes_to": "Goes on to", "card.prev": "Previous stage",
    "card.next": "Next stage", "card.stage_parts": "What happens here",
    # kind names (badges)
    "kind.actor": "Person", "kind.input": "Input", "kind.config": "Setting", "kind.component": "Part",
    "kind.store": "Storage", "kind.external": "Outside service", "kind.output": "Output",
    "kind.flow": "Flow", "kind.scenario": "What if",
    # card titles in the Big Picture's "What it relies on" row
    "group.config": "Settings and secrets", "group.store": "Where data is kept",
    "group.external": "Outside services it relies on",
    # status badges
    "status.core": "", "status.extra": "➕ added along the way", "status.unfinished": "🚧 unfinished",
    "status.unused": "💤 unused", "status.risky": "⚠️ risky",
    # handled
    "handled.yes": "✅ Handled", "handled.partly": "⚠️ Partly handled", "handled.no": "❌ Not handled",
    "handled.unknown": "❔ Unknown, needs a check",
    "severity.high": "high impact", "severity.medium": "medium impact", "severity.low": "low impact",
    # file names
    "canvas.system": "1 Big Picture", "canvas.flows": "2 Flows", "canvas.whatif": "3 What If",
    "canvas.reality": "4 Plan vs Reality", "note.reality": "Plan vs Reality", "note.glossary": "Glossary",
    # home note
    "h.read": "Read this atlas", "h.glance": "At a glance",
    "h.flows": "Flows", "h.whatif": "What if…", "h.how_to_run": "How to run it",
    "h.stack": "Built with", "h.audience": "Who it is for", "h.source": "Source",
    "h.my_notes": "My notes", "h.glossary": "Glossary",
    "read.system": "the whole project on one page, left to right",
    "read.flows": "step by step, what happens when it is used",
    "read.whatif": "what happens when things go wrong",
    "read.reality": "what was planned vs what is here now",
    "h.stages": "How it works, stage by stage", "h.background": "In the background", "h.stage": "Stage",
    "open.system": "Open the Big Picture",
    # node notes
    "h.connections": "Connections", "h.gets_from": "Gets from", "h.sends_to": "Sends to",
    "h.in_flows": "Part of these flows", "h.can_go_wrong": "What can go wrong here",
    "h.in_code": "Where it lives", "step": "step",
    # flow notes
    "h.trigger": "Starts when", "h.steps": "Step by step", "h.result": "Ends with",
    "h.sequence": "Who talks to whom", "h.related_whatif": "What can go wrong",
    # scenario notes
    "h.what_happens": "What happens", "h.user_sees": "What you would notice",
    "h.handled": "Is it handled?", "h.evidence": "Evidence", "h.fix": "How to fix it",
    "h.affects": "Parts involved", "h.category": "Kind of problem",
    # reality
    "h.intent": "What was planned", "h.verdict": "How close is it",
    "h.as_planned": "✅ Built as planned", "h.added": "➕ Added along the way",
    "h.unfinished": "🚧 Unfinished", "h.unused": "💤 Leftovers", "h.risks": "⚠️ Risks to know",
    "h.questions": "❓ Questions for you", "intent_source": "Source of this",
    "h.missing": "❌ Planned but not built", "h.plan_check": "📋 Plan checklist",
    "plan.built": "built", "plan.partly": "partly built", "plan.missing": "not built",
    "plan.changed": "built differently", "plan.dropped": "dropped",
    "intent.from_plan": "your plan, recorded on {date}",
    # plan and changes
    "note.plan": "0 Plan", "note.changes": "Changes",
    "read.plan": "what you set out to build, recorded on {date}",
    "read.changes": "what changed each time the atlas was refreshed",
    "glance.plan": "Plan", "glance.plan_value": "{built} of {total} built",
    "glance.changes": "Last change",
    "changes.title": "Changes over time",
    "changes.intro": "Each time the atlas is refreshed, what changed in the project is added here, newest first.",
    "changes.since": "since", "changes.first": "first atlas", "changes.none": "No changes to parts, stages or risks.",
    "changes.parts": "Parts", "changes.stages": "Stages", "changes.whatif": "What if",
    "changes.plan": "Plan", "changes.reality": "Plan vs Reality",
    "changes.new": "New", "changes.gone": "Gone", "changes.renamed": "Renamed", "changes.moved": "Moved",
    "changes.better": "Better", "changes.worse": "Worse", "changes.status": "Now",
    "changes.counts": "{parts} parts in {stages} stages, {whatifs} what-ifs",
    "changes.n_new": "➕ {n} new", "changes.n_gone": "➖ {n} gone",
    "changes.n_better": "✅ {n} what-if better", "changes.n_worse": "⚠️ {n} what-if worse",
    # cards
    "card.trigger": "▶ Starts when", "card.result": "■ Ends with", "card.legend": "How to read this map",
    "card.nav": "Atlas", "card.start": "Starts here", "card.out": "Comes out",
    "card.parts": "Parts", "card.uses": "Uses", "card.passes": "Hands on", "card.used_by": "Used by",
    "card.from_stage": "from {n}", "card.in": "In", "card.out_short": "Out",
    "group.background": "Runs in the background", "group.relies": "What it relies on",
    "stage.other": "Other parts", "stage.auto": "Step {n}",
    "legend.read": "Read left to right: where it starts, the stages it goes through, what comes out. "
                   "Click any name to open its note; each note shows that part's own connections.",
    "legend.status": "Badges: ➕ added along the way · 🚧 unfinished · 💤 unused · ⚠️ risky",
    # footer
    "footer": "Generated by project-atlas on {date}. Re-run it to refresh. Anything you write under “{my_notes}” in any atlas note is kept.",
    "back": "Back to",
}


# --------------------------------------------------------------------------- helpers

def die(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def sid(*parts: str) -> str:
    return hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()[:16]


_BAD_FILE_CHARS = re.compile(r'[\\/:*?"<>|#^\[\]\x00-\x1f]')
_RESERVED = {"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(1, 10)} | {f"lpt{i}" for i in range(1, 10)}


def safe_name(s: str, limit: int = 80) -> str:
    s = _BAD_FILE_CHARS.sub(" ", str(s))
    s = re.sub(r"\s+", " ", s).strip(" .")
    if len(s) > limit:
        cut = s[:limit]
        if " " in cut[limit // 2:]:
            cut = cut[: cut.rfind(" ")]
        s = cut.strip(" .")
    if not s:
        s = "untitled"
    if s.lower() in _RESERVED:
        s += "_"
    return s


def alias(s: str) -> str:
    return str(s).replace("|", "/").replace("[", "(").replace("]", ")").replace("\n", " ").strip()


def mm(s: str, n: int = 60) -> str:
    """Make text safe for a Mermaid label."""
    s = str(s).replace("&", "+")
    s = re.sub(r'[\[\]{}()<>"`|;#%]', " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > n:
        s = s[: n - 1].rstrip() + "…"
    return s or "·"


def yq(v) -> str:
    return json.dumps(str(v), ensure_ascii=False)


def frontmatter(d: dict) -> str:
    out = ["---"]
    for k, v in d.items():
        if v is None or v == "" or v == []:
            continue
        if isinstance(v, (list, tuple)):
            out.append(f"{k}:")
            out.extend(f"  - {yq(i)}" for i in v)
        elif isinstance(v, bool):
            out.append(f"{k}: {'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            out.append(f"{k}: {v}")
        else:
            out.append(f"{k}: {yq(v)}")
    out.append("---")
    return "\n".join(out) + "\n"


def as_text(v) -> str:
    if v is None:
        return ""
    if isinstance(v, list):
        return "\n".join(f"- {x}" for x in v)
    return str(v).strip()


def callout(kind: str, title: str, body: str) -> str:
    lines = [f"> [!{kind}] {title}".rstrip()]
    for ln in (body or "").splitlines() or [""]:
        lines.append(f"> {ln}".rstrip())
    return "\n".join(lines)


def _visual_len(s: str) -> float:
    """Length in 'average letters': emoji and pictographs are about twice as wide."""
    return sum(2.0 if (ord(ch) >= 0x1F000 or 0x2190 <= ord(ch) <= 0x2BFF) else 1.0
               for ch in s if not 0xFE00 <= ord(ch) <= 0xFE0F)


def est_height(text: str, width: int) -> int:
    """Rough height a canvas text card needs so its text fits without scrolling.

    Calibrated against Obsidian's default 16px font with export_atlas.py --check, which measures the real fit."""
    cpl = max(12, int((width - 44) / 7.6))  # characters per line at default font size
    lines = 0.0
    for raw in text.split("\n"):
        p = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", raw)
        p = re.sub(r"\[\[([^\]]*)\]\]", r"\1", p)
        is_heading = p.lstrip().startswith("#")
        bold = "**" in p
        p = re.sub(r"[*_`#>]", "", p).strip()
        n = _visual_len(p) * (1.08 if bold else 1.0)
        if not p:
            lines += 0.6
        elif is_heading:
            lines += math.ceil(n / (cpl * 0.72)) * 1.5
        else:
            lines += math.ceil(n / cpl)
    h = 48 + lines * 26
    return int(math.ceil(h / 20.0) * 20)


# --------------------------------------------------------------------------- spec loading

def norm_kind(k, warns, where):
    k0 = str(k or "").strip().lower()
    k1 = KIND_ALIASES.get(k0, k0)
    if k1 not in KIND_ORDER:
        warns.append(f"{where}: unknown kind '{k}', treated as 'component'")
        return "component"
    return k1


def norm_status(s, warns, where):
    s0 = str(s or "core").strip().lower()
    s1 = STATUS_ALIASES.get(s0, s0)
    if s1 not in STATUSES:
        warns.append(f"{where}: unknown status '{s}', treated as 'core'")
        return "core"
    return s1


def norm_handled(h, warns, where):
    h0 = str(h if h is not None else "unknown").strip().lower()
    h1 = HANDLED_ALIASES.get(h0, h0)
    if h1 not in HANDLED:
        warns.append(f"{where}: unknown 'handled' value '{h}', treated as 'unknown'")
        return "unknown"
    return h1


def load_spec(path: Path):
    try:
        spec = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        die(f"{path} is not valid JSON: {e}")
    errors, warns = [], []
    if not isinstance(spec, dict):
        die("the atlas file must contain a JSON object")

    proj = spec.get("project") or {}
    for f in ("name", "one_liner", "summary"):
        if not str(proj.get(f, "")).strip():
            errors.append(f"project.{f} is required")
    spec["project"] = proj

    nodes = spec.get("nodes") or []
    ids = {}
    for i, n in enumerate(nodes):
        where = f"nodes[{i}]"
        for f in ("id", "name", "summary"):
            if not str(n.get(f, "")).strip():
                errors.append(f"{where}.{f} is required")
        nid = str(n.get("id", "")).strip()
        if nid in ids:
            errors.append(f"{where}: duplicate id '{nid}'")
        ids[nid] = n
        n["id"] = nid
        n["kind"] = norm_kind(n.get("kind"), warns, f"{where} ({nid})")
        n["status"] = norm_status(n.get("status"), warns, f"{where} ({nid})")
        if isinstance(n.get("files"), str):
            n["files"] = [n["files"]]
    spec["nodes"] = nodes

    def check_ref(ref, where):
        if ref not in ids:
            errors.append(f"{where}: unknown node id '{ref}'")
            return False
        return True

    links = []
    for i, l in enumerate(spec.get("links") or []):
        ok = check_ref(l.get("from"), f"links[{i}].from") & check_ref(l.get("to"), f"links[{i}].to")
        if ok:
            links.append(l)
    spec["links"] = links

    # stages: the backbone of the Big Picture. Only parts (components) belong to stages.
    stages, stage_ids, placed = [], set(), {}
    for i, st in enumerate(spec.get("stages") or []):
        where = f"stages[{i}]"
        if not isinstance(st, dict):
            errors.append(f"{where} must be an object")
            continue
        st.setdefault("id", f"stage-{i + 1}")
        if st["id"] in stage_ids:
            errors.append(f"{where}: duplicate stage id '{st['id']}'")
        stage_ids.add(st["id"])
        if not str(st.get("name", "")).strip():
            errors.append(f"{where}.name is required")
        lane = str(st.get("lane", "main")).strip().lower()
        if lane not in ("main", "background"):
            warns.append(f"{where}: lane '{lane}' is not 'main' or 'background'; treated as 'main'")
            lane = "main"
        st["lane"] = lane
        members = []
        for nid in st.get("nodes") or []:
            if not check_ref(nid, f"{where}.nodes"):
                continue
            if ids[nid]["kind"] != "component":
                warns.append(f"{where}: '{nid}' is a {ids[nid]['kind']}, not a part; it is shown elsewhere on the "
                             f"map automatically, so it was left out of the stage")
                continue
            if nid in placed:
                warns.append(f"{where}: '{nid}' is already in stage '{placed[nid]}'; a part belongs to one stage")
                continue
            placed[nid] = st["id"]
            members.append(nid)
        st["nodes"] = members
        st["uses"] = [u for u in (st.get("uses") or []) if check_ref(u, f"{where}.uses")]
        stages.append(st)
    loose = [n["id"] for n in nodes if n["kind"] == "component" and n["id"] not in placed]
    if stages and loose:
        warns.append("parts in no stage (shown under 'Other parts'): " + ", ".join(loose))
        stages.append({"id": "other-parts", "name": "", "auto_name": "stage.other", "summary": "",
                       "nodes": loose, "uses": [], "lane": "background"})
    spec["stages"] = stages
    main_count = sum(1 for s in stages if s["lane"] == "main")
    if stages and not 2 <= main_count <= 7:
        warns.append(f"{main_count} main stages; 3 to 6 tell the story best")

    flow_ids = set()
    for i, fl in enumerate(spec.get("flows") or []):
        where = f"flows[{i}]"
        fl.setdefault("id", f"flow-{i + 1}")
        if fl["id"] in flow_ids:
            errors.append(f"{where}: duplicate flow id '{fl['id']}'")
        flow_ids.add(fl["id"])
        if not str(fl.get("name", "")).strip():
            errors.append(f"{where}.name is required")
        steps = fl.get("steps") or []
        if not steps:
            errors.append(f"{where}: a flow needs at least one step")
        for j, st in enumerate(steps):
            check_ref(st.get("node"), f"{where}.steps[{j}].node")
            if st.get("to"):
                check_ref(st.get("to"), f"{where}.steps[{j}].to")
            if not str(st.get("action", "")).strip():
                errors.append(f"{where}.steps[{j}].action is required")
    spec["flows"] = spec.get("flows") or []

    sc_ids = set()
    for i, sc in enumerate(spec.get("scenarios") or []):
        where = f"scenarios[{i}]"
        sc.setdefault("id", f"what-if-{i + 1}")
        if sc["id"] in sc_ids:
            errors.append(f"{where}: duplicate scenario id '{sc['id']}'")
        sc_ids.add(sc["id"])
        if not str(sc.get("question", "")).strip():
            errors.append(f"{where}.question is required")
        sc["handled"] = norm_handled(sc.get("handled"), warns, where)
        sev = str(sc.get("severity", "medium")).lower()
        sc["severity"] = sev if sev in SEVERITY_ORDER else "medium"
        if sc.get("trigger_node"):
            check_ref(sc["trigger_node"], f"{where}.trigger_node")
        sc["affects"] = [a for a in (sc.get("affects") or []) if check_ref(a, f"{where}.affects")]
        for fid in sc.get("flows") or []:
            if fid not in flow_ids:
                warns.append(f"{where}: unknown flow id '{fid}' in flows")
        if sc["handled"] == "yes" and not str(sc.get("evidence", "")).strip():
            warns.append(f"{where}: marked handled but has no evidence; say where in the code it is handled")
    spec["scenarios"] = spec.get("scenarios") or []

    reality = spec.get("reality") or {}
    for sec in REALITY_SECTIONS:
        items = reality.get(sec) or []
        fixed = []
        for j, it in enumerate(items):
            if isinstance(it, str):
                it = {"title": it}
            if not str(it.get("title", "")).strip():
                errors.append(f"reality.{sec}[{j}].title is required")
            it["nodes"] = [x for x in (it.get("nodes") or []) if check_ref(x, f"reality.{sec}[{j}].nodes")]
            fixed.append(it)
        reality[sec] = fixed
    checks = []
    for j, it in enumerate(reality.get("plan_check") or []):
        if isinstance(it, str):
            it = {"item": it}
        if not str(it.get("item", "")).strip():
            errors.append(f"reality.plan_check[{j}].item is required")
            continue
        status = str(it.get("status", "")).strip().lower()
        status = PLAN_STATUS_ALIASES.get(status, status)
        if status not in PLAN_STATUS:
            warns.append(f"reality.plan_check[{j}]: unknown status '{it.get('status')}', treated as 'partly'")
            status = "partly"
        it["status"] = status
        it["nodes"] = [x for x in (it.get("nodes") or []) if check_ref(x, f"reality.plan_check[{j}].nodes")]
        checks.append(it)
    reality["plan_check"] = checks
    spec["reality"] = reality

    # soft checks
    linked = {l["from"] for l in links} | {l["to"] for l in links}
    for n in nodes:
        if n["id"] and n["id"] not in linked:
            warns.append(f"node '{n['id']}' has no links; it will float alone on the map")
    if not spec["scenarios"]:
        warns.append("no scenarios: the What If canvas will be empty")
    if not spec["flows"]:
        warns.append("no flows: the Flows canvas will be empty")
    if not reality.get("intent") and not proj.get("intent"):
        warns.append("no intent: Plan vs Reality cannot compare against a plan")
    return spec, errors, warns


# --------------------------------------------------------------------------- context

class Atlas:
    def __init__(self, spec: dict, out: Path, vault: Path, labels: dict):
        self.spec = spec
        self.out = out
        self.vault = vault
        self.L = labels
        rel = out.resolve().relative_to(vault.resolve()).as_posix() if out.resolve() != vault.resolve() else ""
        self.rel_root = "" if rel == "." else rel
        self.files: dict[str, str] = {}
        self.nodes = {n["id"]: n for n in spec["nodes"]}
        self.flows = {f["id"]: f for f in spec["flows"]}
        self.stages = list(spec.get("stages") or [])
        self.auto_stages = False
        if not self.stages:
            comps = [n["id"] for n in spec["nodes"] if n["kind"] == "component"]
            if comps:
                kinds = {n["id"]: n["kind"] for n in spec["nodes"]}
                cols = layer_components(comps, spec["links"], {i for i, k in kinds.items() if k == "output"},
                                        {i for i, k in kinds.items() if k in ("actor", "input")})
                self.stages = [{"id": f"auto-{k + 1}", "name": "", "auto_name": "stage.auto", "n": k + 1,
                                "summary": "", "nodes": col, "uses": [], "lane": "main"} for k, col in enumerate(cols)]
                self.auto_stages = True
        self.stage_of = {nid: st for st in self.stages for nid in st["nodes"]}
        self.extra_home_links: list = []    # filled by optional features (plan, changes)
        self.extra_glance_rows: list = []
        self.plan: dict | None = None       # plan.json recorded at the start of the project, if any
        self.plan_note: str | None = None
        self.changes_note: str | None = None
        self.date = _dt.date.today().isoformat()
        self._used: dict[str, set] = {}
        self.path: dict[str, str] = {}  # entity key -> path relative to out, no extension
        pname = safe_name(spec["project"]["name"])
        self.home = self._claim("", pname)
        self.reality_note = self._claim("", self.t("note.reality"))
        self.glossary_note = self._claim("", self.t("note.glossary")) if spec.get("glossary") else None
        self._claim("", self.t("note.plan"))  # written by save_plan.py; reserved so nothing else takes the name
        self.changes_note = self._claim("", self.t("note.changes"))
        self.canvas = {k: self._claim("", self.t(f"canvas.{k}")) + ".canvas"
                       for k in ("system", "flows", "whatif", "reality")}
        for n in spec["nodes"]:
            self.path["n:" + n["id"]] = self._claim(self.t(f"folder.{n['kind']}"), n["name"])
        for f in spec["flows"]:
            self.path["f:" + f["id"]] = self._claim(self.t("folder.flow"), f["name"])
        for s in spec["scenarios"]:
            # questions can be long; a shorter file name keeps paths well under Windows' 260-character limit
            self.path["s:" + s["id"]] = self._claim(self.t("folder.scenario"), s["question"], limit=64)
        self.stage_canvas = {}
        mains = [s for s in self.stages if s["lane"] == "main"]
        for st in self.stages:
            fname = f"{mains.index(st) + 1} {self.stage_name(st)}" if st in mains else self.stage_name(st)
            self.stage_canvas[st["id"]] = self._claim(self.t("folder.stage"), fname) + ".canvas"

    def t(self, key: str, **kw) -> str:
        s = self.L.get(key, DEFAULT_LABELS.get(key, key))
        return s.format(**kw) if kw else s

    def _claim(self, folder: str, name: str, limit: int = 80) -> str:
        folder = "/".join(safe_name(p) for p in folder.split("/") if p) if folder else ""
        base = safe_name(name, limit)
        used = self._used.setdefault(folder.lower(), set())
        cand, i = base, 2
        while cand.lower() in used:
            cand, i = f"{base} ({i})", i + 1
        used.add(cand.lower())
        return f"{folder}/{cand}" if folder else cand

    # links ---------------------------------------------------------------
    def target(self, rel: str) -> str:
        return f"{self.rel_root}/{rel}" if self.rel_root else rel

    def wl(self, rel: str, text: str) -> str:
        return f"[[{self.target(rel)}|{alias(text)}]]"

    def node_link(self, nid: str) -> str:
        n = self.nodes[nid]
        return self.wl(self.path["n:" + nid], n["name"])

    def flow_link(self, fid: str) -> str:
        return self.wl(self.path["f:" + fid], self.flows[fid]["name"])

    def sc_link(self, sc: dict) -> str:
        return self.wl(self.path["s:" + sc["id"]], sc["question"])

    def intent(self) -> tuple:
        """What was planned, and where that came from. A recorded plan beats an inferred intent."""
        r, p = self.spec["reality"], self.spec["project"]
        text = as_text(r.get("intent") or p.get("intent"))
        src = r.get("intent_source") or p.get("intent_source")
        if self.plan and as_text(self.plan.get("goal")):
            text = as_text(self.plan.get("goal"))
            src = self.t("intent.from_plan", date=str(self.plan.get("recorded", ""))[:10])
        return text, src

    def stage_name(self, st: dict) -> str:
        return str(st.get("name") or "").strip() or self.t(st.get("auto_name", "stage.other"), n=st.get("n", ""))

    def stage_label(self, st: dict) -> str:
        """'2 · Edit the photos' for main stages, plain name for background ones."""
        mains = [s for s in self.stages if s["lane"] == "main"]
        return f"{mains.index(st) + 1} · {self.stage_name(st)}" if st in mains else self.stage_name(st)

    def stage_link(self, st: dict, text: str | None = None) -> str:
        return self.wl(self.stage_canvas[st["id"]], text or self.stage_label(st))

    def stage_uses(self, st: dict) -> list:
        res = list(st.get("uses") or [])
        members = set(st["nodes"])
        for l in self.spec["links"]:
            for here, there in ((l["from"], l["to"]), (l["to"], l["from"])):
                if here in members and self.nodes[there]["kind"] in ("store", "external", "config") and there not in res:
                    res.append(there)
        return res

    def home_link(self) -> str:
        return self.wl(self.home, self.spec["project"]["name"])

    def canvas_link(self, key: str, text: str | None = None) -> str:
        return self.wl(self.canvas[key], text or self.t(f"canvas.{key}"))

    # output --------------------------------------------------------------
    def add_note(self, rel: str, fm: dict, body: str) -> None:
        fm = {"generator": GENERATOR, "project": self.spec["project"]["name"], **fm}
        text = frontmatter(fm) + body.rstrip() + "\n\n## " + self.t("h.my_notes") + "\n" + KEEP_MARK + "\n"
        self.files[rel + ".md"] = text

    def add_canvas(self, rel: str, canvas: "Canvas") -> None:
        self.files[rel] = json.dumps(canvas.dump(), ensure_ascii=False, indent="\t") + "\n"

    def footer(self) -> str:
        nav = " · ".join([self.home_link(), self.canvas_link("system"), self.canvas_link("flows"),
                          self.canvas_link("whatif"), self.canvas_link("reality")])
        return "\n---\n" + f"{self.t('back')}: {nav}\n"


# --------------------------------------------------------------------------- relations

def relations(a: Atlas):
    ins = {nid: [] for nid in a.nodes}
    outs = {nid: [] for nid in a.nodes}
    for l in a.spec["links"]:
        outs[l["from"]].append(l)
        ins[l["to"]].append(l)
    in_flows = {nid: [] for nid in a.nodes}
    for f in a.spec["flows"]:
        for j, st in enumerate(f.get("steps") or []):
            in_flows[st["node"]].append((f, j + 1, st))
    sc_for = {nid: [] for nid in a.nodes}
    for s in a.spec["scenarios"]:
        touched = set(s.get("affects") or [])
        if s.get("trigger_node"):
            touched.add(s["trigger_node"])
        for nid in touched:
            sc_for[nid].append(s)
    return ins, outs, in_flows, sc_for


# --------------------------------------------------------------------------- notes

def chain_mermaid(items, direction: str = "TB") -> list:
    """items: [(label, hands_on_or_None, shape)] with shape 'stage' or 'end'. Returns Mermaid lines."""
    lines = ["```mermaid", f"flowchart {direction}"]
    for i, (label, _, shape) in enumerate(items):
        lines.append(f'  c{i}(["{label}"])' if shape == "end" else f'  c{i}["{label}"]')
    for i in range(len(items) - 1):
        hands_on = items[i][1]
        lines.append(f'  c{i} -->|"{mm(hands_on, 40)}"| c{i + 1}' if hands_on else f"  c{i} --> c{i + 1}")
    return lines + ["```"]


def story_items(a: Atlas) -> list:
    """The Big Picture story as Mermaid-safe chain items: start, each main stage with its parts, end."""
    nodes = a.spec["nodes"]
    items = []
    if any(n["kind"] in ("actor", "input") for n in nodes):
        items.append((f"▶ {mm(a.t('card.start'), 30)}", None, "end"))
    for st in (s for s in a.stages if s["lane"] == "main"):
        label = mm(a.stage_label(st), 50)
        if st["nodes"]:
            label += "<br>" + " · ".join(mm(a.nodes[n]["name"], 30) for n in st["nodes"][:5])
        items.append((label, st.get("passes"), "stage"))
    if any(n["kind"] == "output" for n in nodes):
        items.append((f"■ {mm(a.t('card.out'), 30)}", None, "end"))
    return items


def render_home(a: Atlas):
    p = a.spec["project"]
    nodes = a.spec["nodes"]
    lines = [f"# {p['name']}", "", f"> **{p['one_liner'].strip()}**", ""]
    # the story first: what someone should see the moment they open the atlas
    if a.stages:
        lines += chain_mermaid(story_items(a)) + ["", f"🗺️ **{a.canvas_link('system', a.t('open.system'))}**", ""]
    lines += [as_text(p["summary"]), ""]
    lines += [f"## {a.t('h.read')}",
              f"- 🗺️ {a.canvas_link('system')}: {a.t('read.system')}",
              f"- 🔁 {a.canvas_link('flows')}: {a.t('read.flows')}",
              f"- ⚡ {a.canvas_link('whatif')}: {a.t('read.whatif')}",
              f"- 🎯 {a.canvas_link('reality')} ({a.wl(a.reality_note, a.t('note.reality'))}): {a.t('read.reality')}"]
    lines += a.extra_home_links + [""]
    # at a glance
    lines += [f"## {a.t('h.glance')}", "", "| | |", "|---|---|"]
    for k in KIND_ORDER:
        c = sum(1 for n in nodes if n["kind"] == k)
        if c:
            lines.append(f"| {KIND_ICON[k]} {a.t('folder.' + k)} | {c} |")
    if a.spec["flows"]:
        lines.append(f"| 🔁 {a.t('h.flows')} | {len(a.spec['flows'])} |")
    if a.spec["scenarios"]:
        counts = {h: sum(1 for s in a.spec["scenarios"] if s["handled"] == h) for h in HANDLED}
        detail = ", ".join(f"{a.t('handled.' + h)} {c}" for h, c in counts.items() if c)
        lines.append(f"| ⚡ {a.t('h.whatif')} | {len(a.spec['scenarios'])} ({detail}) |")
    lines += a.extra_glance_rows + [""]
    if p.get("audience"):
        lines += [f"**{a.t('h.audience')}:** {as_text(p['audience'])}", ""]
    if p.get("stack"):
        stack = p["stack"] if isinstance(p["stack"], list) else [p["stack"]]
        lines += [f"**{a.t('h.stack')}:** " + " · ".join(str(s) for s in stack), ""]
    if p.get("source"):
        lines += [f"**{a.t('h.source')}:** `{p['source']}`", ""]

    if a.stages:
        lines += [f"## {a.t('h.stages')}"]
        ordered = [s for s in a.stages if s["lane"] == "main"] + [s for s in a.stages if s["lane"] == "background"]
        for st in ordered:
            if st["lane"] == "background" and st is next(s for s in ordered if s["lane"] == "background"):
                lines += ["", f"**🔄 {a.t('h.background')}**"]
            parts = ", ".join(a.node_link(n) for n in st["nodes"])
            summary = as_text(st.get("summary"))
            lines.append(f"- **{a.stage_link(st)}**" + (f": {summary}" if summary else "") + (f" ({parts})" if parts else ""))
        lines.append("")

    for k in KIND_ORDER:
        members = [n for n in nodes if n["kind"] == k]
        if not members:
            continue
        lines += [f"## {KIND_ICON[k]} {a.t('folder.' + k)}"]
        for n in members:
            badge = a.t("status." + n["status"])
            lines.append(f"- {a.node_link(n['id'])}: {n['summary'].strip()}" + (f" *({badge})*" if badge else ""))
        lines.append("")
    if a.spec["flows"]:
        lines += [f"## 🔁 {a.t('h.flows')}"]
        for f in a.spec["flows"]:
            lines.append(f"- {a.flow_link(f['id'])}: {as_text(f.get('summary') or f.get('trigger'))}")
        lines.append("")
    if a.spec["scenarios"]:
        lines += [f"## ⚡ {a.t('h.whatif')}"]
        for s in sorted(a.spec["scenarios"], key=lambda s: (HANDLED.index(s["handled"]), SEVERITY_ORDER[s["severity"]])):
            lines.append(f"- {a.t('handled.' + s['handled']).split(' ')[0]} {a.sc_link(s)}")
        lines.append("")
    if p.get("how_to_run"):
        lines += [f"## {a.t('h.how_to_run')}", as_text(p["how_to_run"]), ""]
    if a.glossary_note:
        lines += [f"## {a.t('h.glossary')}", a.wl(a.glossary_note, a.t("note.glossary")), ""]
    lines += ["---", "*" + a.t("footer", date=a.date, my_notes=a.t("h.my_notes")) + "*"]
    a.add_note(a.home, {"atlas": "home", "generated": a.date, "source": p.get("source"),
                        "tags": ["atlas", "atlas/home"]}, "\n".join(lines))


def render_node(a: Atlas, n: dict, ins, outs, in_flows, sc_for):
    k = n["kind"]
    badge = f"{KIND_ICON[k]} {a.t('kind.' + k)}"
    st = a.t("status." + n["status"])
    if st:
        badge += f" · {st}"
    if n["id"] in a.stage_of:
        badge += f" · {a.t('h.stage')} {a.stage_link(a.stage_of[n['id']])}"
    lines = [f"# {n['name']}", "", callout(KIND_CALLOUT[k], badge, n["summary"].strip()), ""]
    if n.get("details"):
        lines += [as_text(n["details"]), ""]

    gets, sends = ins[n["id"]], outs[n["id"]]
    if gets or sends:
        lines += [f"## {a.t('h.connections')}"]
        if gets:
            lines.append(f"**{a.t('h.gets_from')}**")
            for l in gets:
                lines.append(f"- {a.node_link(l['from'])}" + (f": {l['label']}" if l.get("label") else ""))
            lines.append("")
        if sends:
            lines.append(f"**{a.t('h.sends_to')}**")
            for l in sends:
                lines.append(f"- {a.node_link(l['to'])}" + (f": {l['label']}" if l.get("label") else ""))
            lines.append("")
        # local diagram
        neigh = []
        for l in gets[:8]:
            neigh.append((l["from"], n["id"], l.get("label")))
        for l in sends[:8]:
            neigh.append((n["id"], l["to"], l.get("label")))
        ids = []
        for x, y, _ in neigh:
            for z in (x, y):
                if z not in ids:
                    ids.append(z)
        m = {z: f"n{i}" for i, z in enumerate(ids)}
        lines += ["```mermaid", "flowchart LR"]
        for z in ids:
            shape = f'(["{mm(a.nodes[z]["name"], 40)}"])' if z == n["id"] else f'["{mm(a.nodes[z]["name"], 40)}"]'
            lines.append(f"  {m[z]}{shape}")
        for x, y, lab in neigh:
            arrow = f'-->|"{mm(lab, 30)}"|' if lab else "-->"
            lines.append(f"  {m[x]} {arrow} {m[y]}")
        lines += ["```", ""]

    if in_flows[n["id"]]:
        lines += [f"## {a.t('h.in_flows')}"]
        grouped: dict[str, list] = {}
        for f, num, st in in_flows[n["id"]]:
            grouped.setdefault(f["id"], []).append((num, st))
        for fid, items in grouped.items():
            if len(items) == 1:
                num, st = items[0]
                lines.append(f"- {a.flow_link(fid)}, {a.t('step')} {num}: {st['action'].strip()}")
            else:
                lines.append(f"- {a.flow_link(fid)}")
                lines.extend(f"    - {a.t('step')} {num}: {st['action'].strip()}" for num, st in items)
        lines.append("")
    if sc_for[n["id"]]:
        lines += [f"## {a.t('h.can_go_wrong')}"]
        for s in sc_for[n["id"]]:
            lines.append(f"- {a.t('handled.' + s['handled']).split(' ')[0]} {a.sc_link(s)}")
        lines.append("")
    if n.get("files"):
        lines += [f"## {a.t('h.in_code')}"] + [f"- `{f}`" for f in n["files"]] + [""]
    lines.append(a.footer())
    extra_tags = [re.sub(r"\s+", "-", str(t).strip().lstrip("#")) for t in (n.get("tags") or []) if str(t).strip()]
    tags = [KIND_TAG[k]] + [f"atlas/status/{n['status']}"] * (n["status"] != "core") + extra_tags
    a.add_note(a.path["n:" + n["id"]], {"atlas": "node", "kind": k, "status": n["status"],
                                        "files": n.get("files"), "tags": tags}, "\n".join(lines))


def render_flow(a: Atlas, f: dict):
    steps = f.get("steps") or []
    lines = [f"# {f['name']}", ""]
    lines += [callout("abstract", f"🔁 {a.t('kind.flow')}", as_text(f.get("summary"))), ""]
    if f.get("trigger"):
        lines += [f"**{a.t('h.trigger')}:** {as_text(f['trigger'])}", ""]
    lines += [f"## {a.t('h.steps')}"]
    for j, st in enumerate(steps, 1):
        s = f"{j}. {a.node_link(st['node'])}: {st['action'].strip()}"
        if st.get("to") and st["to"] != st["node"]:
            s += f" → {a.node_link(st['to'])}"
        if st.get("data"):
            s += f" *({st['data']})*"
        lines.append(s)
    lines.append("")
    if f.get("result"):
        lines += [f"**{a.t('h.result')}:** {as_text(f['result'])}", ""]
    # sequence diagram
    parts = []
    for st in steps:
        for z in (st["node"], st.get("to")):
            if z and z not in parts:
                parts.append(z)
    pid = {z: f"p{i}" for i, z in enumerate(parts)}
    lines += [f"## {a.t('h.sequence')}", "```mermaid", "sequenceDiagram"]
    for z in parts:
        lines.append(f"  participant {pid[z]} as {mm(a.nodes[z]['name'], 40)}")
    for st in steps:
        act = mm(st["action"], 70)
        if st.get("to"):
            lines.append(f"  {pid[st['node']]}->>{pid[st['to']]}: {act}")
        else:
            lines.append(f"  Note over {pid[st['node']]}: {act}")
    lines += ["```", ""]
    related = [s for s in a.spec["scenarios"] if f["id"] in (s.get("flows") or [])]
    if related:
        lines += [f"## {a.t('h.related_whatif')}"]
        lines += [f"- {a.t('handled.' + s['handled']).split(' ')[0]} {a.sc_link(s)}" for s in related] + [""]
    lines.append(a.footer())
    a.add_note(a.path["f:" + f["id"]], {"atlas": "flow", "tags": ["atlas/flow"]}, "\n".join(lines))


def render_scenario(a: Atlas, s: dict):
    h = s["handled"]
    title = f"{a.t('handled.' + h)} · {a.t('severity.' + s['severity'])}"
    lines = [f"# {s['question']}", "", callout(HANDLED_CALLOUT[h], title, as_text(s.get("user_sees"))), ""]
    if s.get("category"):
        lines += [f"**{a.t('h.category')}:** {s['category']}", ""]
    lines += [f"## {a.t('h.what_happens')}", as_text(s.get("what_happens")) or "-", ""]
    if s.get("user_sees"):
        lines += [f"## {a.t('h.user_sees')}", as_text(s["user_sees"]), ""]
    lines += [f"## {a.t('h.handled')}", a.t("handled." + h), ""]
    if s.get("evidence"):
        lines += [f"**{a.t('h.evidence')}:** {as_text(s['evidence'])}", ""]
    if s.get("fix"):
        lines += [f"## {a.t('h.fix')}", as_text(s["fix"]), ""]
    involved = ([s["trigger_node"]] if s.get("trigger_node") else []) + [x for x in s["affects"] if x != s.get("trigger_node")]
    if involved:
        lines += [f"## {a.t('h.affects')}"] + [f"- {a.node_link(x)}" for x in involved] + [""]
        lines += ["```mermaid", "flowchart LR", f'  q{{"{mm(s["question"], 50)}"}}']
        first = "q"
        if s.get("trigger_node"):
            lines.append(f'  t["{mm(a.nodes[s["trigger_node"]]["name"], 40)}"]')
            lines.append("  q --> t")
            first = "t"
        affected = [x for x in s["affects"] if x != s.get("trigger_node")]
        for i, x in enumerate(affected):
            lines.append(f'  a{i}["{mm(a.nodes[x]["name"], 40)}"]')
            lines.append(f"  {first} --> a{i}")
        if s.get("user_sees"):
            lines.append(f'  u(["{mm(s["user_sees"], 50)}"])')
            for tl in [f"a{i}" for i in range(len(affected))] or [first]:
                lines.append(f"  {tl} --> u")
        lines += ["```", ""]
    if s.get("flows"):
        lines += [f"## {a.t('h.flows')}"] + [f"- {a.flow_link(fid)}" for fid in s["flows"] if fid in a.flows] + [""]
    lines.append(a.footer())
    a.add_note(a.path["s:" + s["id"]], {"atlas": "what-if", "handled": h, "severity": s["severity"],
                                        "tags": ["atlas/what-if", f"atlas/handled/{h}"]}, "\n".join(lines))


def reality_item_md(a: Atlas, it: dict) -> str:
    s = f"**{it['title'].strip()}**"
    if it.get("text"):
        s += f": {as_text(it['text'])}"
    if it.get("nodes"):
        s += " → " + ", ".join(a.node_link(x) for x in it["nodes"])
    if it.get("files"):
        s += " (" + ", ".join(f"`{f}`" for f in it["files"]) + ")"
    return s


def plan_check_md(a: Atlas, it: dict) -> str:
    s = f"{PLAN_STATUS[it['status']]} **{str(it['item']).strip()}** *({a.t('plan.' + it['status'])})*"
    if it.get("note"):
        s += f": {as_text(it['note'])}"
    if it.get("nodes"):
        s += " → " + ", ".join(a.node_link(x) for x in it["nodes"])
    return s


def plan_score(a: Atlas):
    checks = a.spec["reality"].get("plan_check") or []
    return sum(1 for c in checks if c["status"] == "built"), len(checks)


def plan_summary(a: Atlas) -> str:
    """'✅ 1 · 🔀 1 · 🟡 1 · ❌ 1': each status with its count, so 'built differently' doesn't read as a failure."""
    checks = a.spec["reality"].get("plan_check") or []
    counts = [(icon, sum(1 for c in checks if c["status"] == st)) for st, icon in PLAN_STATUS.items()]
    return " · ".join(f"{icon} {n}" for icon, n in counts if n)


def render_reality(a: Atlas):
    r = a.spec["reality"]
    intent, src = a.intent()
    lines = [f"# {a.t('note.reality')}", "", f"## {a.t('h.intent')}", intent or "-", ""]
    if src:
        lines += [f"*{a.t('intent_source')}: {src}*" + (f" · {a.wl(a.plan_note, a.t('note.plan'))}" if a.plan_note else ""), ""]
    if r.get("verdict"):
        lines += [f"## {a.t('h.verdict')}", as_text(r["verdict"]), ""]
    if r.get("plan_check"):
        lines += [f"## {a.t('h.plan_check')} ({plan_summary(a)})"]
        lines += [f"- {plan_check_md(a, it)}" for it in r["plan_check"]] + [""]
    for sec in REALITY_SECTIONS:
        if r.get(sec):
            lines += [f"## {a.t('h.' + sec)}"] + [f"- {reality_item_md(a, it)}" for it in r[sec]] + [""]
    lines.append(a.footer())
    a.add_note(a.reality_note, {"atlas": "reality", "tags": ["atlas/reality"]}, "\n".join(lines))


def render_glossary(a: Atlas):
    lines = [f"# {a.t('note.glossary')}", ""]
    for g in a.spec.get("glossary") or []:
        if isinstance(g, dict):
            lines.append(f"- **{g.get('term', '')}**: {g.get('meaning', '')}")
    lines.append(a.footer())
    a.add_note(a.glossary_note, {"atlas": "glossary", "tags": ["atlas/glossary"]}, "\n".join(lines))


# --------------------------------------------------------------------------- history and changes

def _stamp(when: _dt.datetime) -> str:
    return when.strftime("%Y-%m-%d_%H-%M-%S")


def _when_label(when: _dt.datetime) -> str:
    return when.strftime("%Y-%m-%d %H:%M")


def _canon(spec) -> str:
    return json.dumps(spec, sort_keys=True, ensure_ascii=False)


def update_history(out: Path, new_text: str, dry: bool, window_minutes: float = 60) -> list:
    """Keep a snapshot of atlas.json each time it changes. Returns [(datetime, spec)] oldest first.

    A render within `window_minutes` of the previous snapshot replaces it instead of adding one: fixes made while
    building or polishing an atlas (renaming a card so its text fits, say) are not changes in the project."""
    hdir = out / HISTORY_DIR
    entries, paths = [], []
    if hdir.is_dir():
        for p in sorted(hdir.glob("atlas-*.json")):
            try:
                when = _dt.datetime.strptime(p.stem[len("atlas-"):], "%Y-%m-%d_%H-%M-%S")
                entries.append((when, json.loads(p.read_text(encoding="utf-8-sig"))))
                paths.append(p)
            except (ValueError, OSError, json.JSONDecodeError):
                continue
    had_history = bool(entries)
    new_spec = json.loads(new_text)
    now = _dt.datetime.now().replace(microsecond=0)
    if (entries and _canon(entries[-1][1]) != _canon(new_spec)
            and (now - entries[-1][0]).total_seconds() < window_minutes * 60):
        if not dry:
            paths[-1].unlink(missing_ok=True)
        entries.pop()
        paths.pop()
    if not had_history and (out / "atlas.json").exists():
        # an atlas made before history existed: its current atlas.json is the first snapshot
        try:
            old = json.loads((out / "atlas.json").read_text(encoding="utf-8-sig"))
            when = _dt.datetime.fromtimestamp((out / "atlas.json").stat().st_mtime).replace(microsecond=0)
            if (now - when).total_seconds() >= window_minutes * 60 or _canon(old) == _canon(new_spec):
                if not dry:
                    hdir.mkdir(parents=True, exist_ok=True)
                    write_lf(hdir / f"atlas-{_stamp(when)}.json", _canon_pretty(old))
                entries.append((when, old))
        except (OSError, json.JSONDecodeError):
            pass
    new = new_spec
    if not entries or _canon(entries[-1][1]) != _canon(new):
        when = now
        if entries and when <= entries[-1][0]:
            when = entries[-1][0] + _dt.timedelta(seconds=1)
        if not dry:
            hdir.mkdir(parents=True, exist_ok=True)
            write_lf(hdir / f"atlas-{_stamp(when)}.json", _canon_pretty(new))
        entries.append((when, new))
    return entries


def _canon_pretty(spec) -> str:
    return json.dumps(spec, ensure_ascii=False, indent=2) + "\n"


def snapshot_view(spec: dict) -> dict:
    """The parts of an atlas that matter for 'what changed', normalised the same way the renderer does."""
    w: list = []
    view = {"nodes": {}, "stages": {}, "scenarios": {}, "reality": {}, "plan": {}}
    for n in spec.get("nodes") or []:
        if isinstance(n, dict) and n.get("id"):
            view["nodes"][n["id"]] = {"name": str(n.get("name", n["id"])), "kind": norm_kind(n.get("kind"), w, ""),
                                      "status": norm_status(n.get("status"), w, "")}
    for i, st in enumerate(spec.get("stages") or []):
        if isinstance(st, dict):
            view["stages"][st.get("id", f"stage-{i + 1}")] = {"name": str(st.get("name", "")),
                                                              "nodes": list(st.get("nodes") or [])}
    for i, s in enumerate(spec.get("scenarios") or []):
        if isinstance(s, dict):
            view["scenarios"][s.get("id", f"what-if-{i + 1}")] = {"q": str(s.get("question", "")),
                                                                  "h": norm_handled(s.get("handled"), w, "")}
    reality = spec.get("reality") or {}
    for sec in REALITY_SECTIONS:
        view["reality"][sec] = [str(it if isinstance(it, str) else it.get("title", "")).strip()
                                for it in reality.get(sec) or []]
    for it in reality.get("plan_check") or []:
        item = str(it if isinstance(it, str) else it.get("item", "")).strip()
        status = "" if isinstance(it, str) else str(it.get("status", "")).strip().lower()
        view["plan"][item] = PLAN_STATUS_ALIASES.get(status, status)
    return view


def diff_lines(a: Atlas, old: dict, new: dict) -> list:
    def node_ref(nid, name):
        return a.node_link(nid) if nid in a.nodes else name

    def sc_ref(sid_, q):
        sc = next((s for s in a.spec["scenarios"] if s["id"] == sid_), None)
        return a.sc_link(sc) if sc else q

    out = []
    on, nn = old["nodes"], new["nodes"]
    parts = []
    for nid in nn.keys() - on.keys():
        n = nn[nid]
        badge = a.t("status." + n["status"])
        parts.append(f"- ➕ {a.t('changes.new')}: {KIND_ICON.get(n['kind'], '')} {node_ref(nid, n['name'])}"
                     + (f" *({badge})*" if badge else ""))
    for nid in on.keys() - nn.keys():
        parts.append(f"- ➖ {a.t('changes.gone')}: {on[nid]['name']}")
    for nid in on.keys() & nn.keys():
        if on[nid]["name"] != nn[nid]["name"]:
            parts.append(f"- ✏️ {a.t('changes.renamed')}: {on[nid]['name']} → {node_ref(nid, nn[nid]['name'])}")
        if on[nid]["status"] != nn[nid]["status"]:
            now = a.t("status." + nn[nid]["status"]) or nn[nid]["status"]
            parts.append(f"- 🏷️ {node_ref(nid, nn[nid]['name'])}: {a.t('changes.status')} {now}")
    if parts:
        out += [f"**{a.t('changes.parts')}**"] + sorted(parts) + [""]

    def stage_of(view):
        return {nid: st["name"] for st in view["stages"].values() for nid in st["nodes"]}
    so, sn = stage_of(old), stage_of(new)
    stages = []
    for sid_ in new["stages"].keys() - old["stages"].keys():
        stages.append(f"- ➕ {a.t('changes.new')}: {new['stages'][sid_]['name']}")
    for sid_ in old["stages"].keys() - new["stages"].keys():
        stages.append(f"- ➖ {a.t('changes.gone')}: {old['stages'][sid_]['name']}")
    for nid in so.keys() & sn.keys():
        if so[nid] != sn[nid] and nid in nn:
            stages.append(f"- 🔀 {a.t('changes.moved')}: {node_ref(nid, nn[nid]['name'])} ({so[nid]} → {sn[nid]})")
    if stages:
        out += [f"**{a.t('changes.stages')}**"] + sorted(stages) + [""]

    osc, nsc = old["scenarios"], new["scenarios"]
    whatifs = []
    for sid_ in nsc.keys() - osc.keys():
        whatifs.append(f"- ➕ {a.t('changes.new')}: {a.t('handled.' + nsc[sid_]['h']).split(' ')[0]} {sc_ref(sid_, nsc[sid_]['q'])}")
    for sid_ in osc.keys() - nsc.keys():
        whatifs.append(f"- ➖ {a.t('changes.gone')}: {osc[sid_]['q']}")
    for sid_ in osc.keys() & nsc.keys():
        before, after = osc[sid_]["h"], nsc[sid_]["h"]
        if before != after:
            better = HANDLED.index(after) > HANDLED.index(before)
            word = a.t("changes.better") if better else a.t("changes.worse")
            whatifs.append(f"- {'✅' if better else '⚠️'} {word}: {sc_ref(sid_, nsc[sid_]['q'])} "
                           f"({a.t('handled.' + before)} → {a.t('handled.' + after)})")
    if whatifs:
        out += [f"**{a.t('changes.whatif')}**"] + sorted(whatifs) + [""]

    plan = []
    for item, status in new["plan"].items():
        before = old["plan"].get(item)
        if before != status and status in PLAN_STATUS:
            was = f"{a.t('plan.' + before)} → " if before in PLAN_STATUS else ""
            plan.append(f"- {PLAN_STATUS[status]} {item}: {was}{a.t('plan.' + status)}")
    if plan:
        out += [f"**{a.t('changes.plan')}**"] + plan + [""]

    reality = []
    for sec in ("added", "risks", "unfinished", "missing", "questions"):
        fresh = [t for t in new["reality"].get(sec, []) if t and t not in old["reality"].get(sec, [])]
        reality += [f"- {a.t('h.' + sec)}: {t}" for t in fresh]
    if reality:
        out += [f"**{a.t('changes.reality')}**"] + reality + [""]
    return out


def latest_change_summary(a: Atlas, old: dict, new: dict) -> str:
    added = len(new["nodes"].keys() - old["nodes"].keys())
    gone = len(old["nodes"].keys() - new["nodes"].keys())
    better = worse = 0
    for sid_ in old["scenarios"].keys() & new["scenarios"].keys():
        b, n = old["scenarios"][sid_]["h"], new["scenarios"][sid_]["h"]
        if b != n:
            better += HANDLED.index(n) > HANDLED.index(b)
            worse += HANDLED.index(n) < HANDLED.index(b)
    bits = [a.t("changes.n_new", n=added) if added else "", a.t("changes.n_gone", n=gone) if gone else "",
            a.t("changes.n_better", n=better) if better else "", a.t("changes.n_worse", n=worse) if worse else ""]
    return ", ".join(b for b in bits if b) or a.t("changes.none")


def render_changes(a: Atlas, entries: list):
    views = [(when, snapshot_view(spec)) for when, spec in entries]
    lines = [f"# {a.t('changes.title')}", "", f"> {a.t('changes.intro')}", ""]
    for i in range(len(views) - 1, 0, -1):
        (t_new, new), (t_old, old) = views[i], views[i - 1]
        lines.append(f"## {_when_label(t_new)} ({a.t('changes.since')} {_when_label(t_old)})")
        lines += diff_lines(a, old, new) or [f"- {a.t('changes.none')}", ""]
    if views:
        when, first = views[0]
        lines += [f"## {_when_label(when)}: {a.t('changes.first')}",
                  "- " + a.t("changes.counts",
                             parts=sum(1 for n in first["nodes"].values() if n["kind"] == "component"),
                             stages=len(first["stages"]),
                             whatifs=len(first["scenarios"])), ""]
    lines.append(a.footer())
    a.add_note(a.changes_note, {"atlas": "changes", "tags": ["atlas/changes"]}, "\n".join(lines))
    if len(views) >= 2:
        summary = latest_change_summary(a, views[-2][1], views[-1][1])
        a.extra_glance_rows.append(f"| 🕑 {a.t('glance.changes')} | {a.wl(a.changes_note, _when_label(views[-1][0]))}: {summary} |")


# --------------------------------------------------------------------------- canvas

class Rect:
    __slots__ = ("x", "y", "w", "h")

    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = int(x), int(y), int(w), int(h)


class Canvas:
    def __init__(self, name: str):
        self.name = name
        self.groups, self.cards, self.edges = [], [], []
        self.rect: dict[str, Rect] = {}

    def card(self, key, x, y, w, h, text, color=None):
        nid = sid(self.name, "card", key)
        node = {"id": nid, "type": "text", "text": text, "x": int(x), "y": int(y), "width": int(w), "height": int(h)}
        if color:
            node["color"] = color
        self.cards.append(node)
        self.rect[nid] = Rect(x, y, w, h)
        return nid

    def group(self, key, x, y, w, h, label, color=None):
        nid = sid(self.name, "group", key)
        node = {"id": nid, "type": "group", "label": label, "x": int(x), "y": int(y), "width": int(w), "height": int(h)}
        if color:
            node["color"] = color
        self.groups.append(node)
        self.rect[nid] = Rect(x, y, w, h)
        return nid

    def edge(self, a, b, label=None, color=None, sides=None):
        ra, rb = self.rect[a], self.rect[b]
        fs, ts = sides or pick_sides(ra, rb)
        e = {"id": sid(self.name, "edge", a, b, str(len(self.edges))), "fromNode": a, "fromSide": fs,
             "toNode": b, "toSide": ts}
        if label:
            e["label"] = str(label)
        if color:
            e["color"] = color
        self.edges.append(e)

    def dump(self):
        return {"nodes": self.groups + self.cards, "edges": self.edges}


def pick_sides(a: Rect, b: Rect):
    hgap = max(b.x - (a.x + a.w), a.x - (b.x + b.w))
    vgap = max(b.y - (a.y + a.h), a.y - (b.y + b.h))
    if hgap >= vgap and hgap > 0:
        return ("right", "left") if b.x > a.x else ("left", "right")
    if vgap > 0:
        return ("bottom", "top") if b.y > a.y else ("top", "bottom")
    # overlapping boxes: fall back to centre comparison
    if abs((b.x + b.w / 2) - (a.x + a.w / 2)) >= abs((b.y + b.h / 2) - (a.y + a.h / 2)):
        return ("right", "left") if b.x > a.x else ("left", "right")
    return ("bottom", "top") if b.y > a.y else ("top", "bottom")


def bbox(rects, pad):
    x0 = min(r.x for r in rects) - pad
    y0 = min(r.y for r in rects) - pad
    x1 = max(r.x + r.w for r in rects) + pad
    y1 = max(r.y + r.h for r in rects) + pad
    return x0, y0, x1 - x0, y1 - y0


def status_icon(a: Atlas, n: dict) -> str:
    badge = a.t("status." + n["status"])
    return f" {badge.split(' ')[0]}" if badge else ""


def header_card(a: Atlas, cv: Canvas, key: str, x: int, y: int, w: int = 760) -> int:
    p = a.spec["project"]
    others = [a.canvas_link(k) for k in ("system", "flows", "whatif", "reality") if k != key]
    text = (f"# {p['name']}\n**{a.t('canvas.' + key)}**\n\n{p['one_liner'].strip()}\n\n"
            f"{a.t('card.nav')}: {a.home_link()} · " + " · ".join(others))
    h = est_height(text, w)
    cv.card("header", x, y - h, w, h, text)
    return h


def layer_components(comp_ids, links, out_ids, in_ids):
    idset = set(comp_ids)
    adj = {i: [] for i in comp_ids}
    for l in links:
        if l["from"] in idset and l["to"] in idset and l["from"] != l["to"]:
            if l["to"] not in adj[l["from"]]:
                adj[l["from"]].append(l["to"])
    # drop back edges (iterative DFS in spec order) to get a DAG
    color = {i: 0 for i in comp_ids}
    dag = {i: [] for i in comp_ids}
    for root in comp_ids:
        if color[root]:
            continue
        stack = [(root, iter(adj[root]))]
        color[root] = 1
        while stack:
            u, it = stack[-1]
            v = next(it, None)
            if v is None:
                color[u] = 2
                stack.pop()
                continue
            if color[v] == 1:
                continue  # back edge
            dag[u].append(v)
            if color[v] == 0:
                color[v] = 1
                stack.append((v, iter(adj[v])))
    indeg = {i: 0 for i in comp_ids}
    for u in comp_ids:
        for v in dag[u]:
            indeg[v] += 1
    layer = {i: 0 for i in comp_ids}
    queue = [i for i in comp_ids if indeg[i] == 0]
    while queue:
        u = queue.pop(0)
        for v in dag[u]:
            layer[v] = max(layer[v], layer[u] + 1)
            indeg[v] -= 1
            if indeg[v] == 0:
                queue.append(v)
    connected = {i for i in comp_ids if adj[i]} | {v for i in comp_ids for v in adj[i]}
    n_layers = (max(layer.values()) + 1) if layer else 1
    # isolated parts: push towards outputs if they only feed outputs, else fill the emptiest layer
    counts = [0] * n_layers
    for i in comp_ids:
        if i in connected:
            counts[layer[i]] += 1
    for i in comp_ids:
        if i in connected:
            continue
        feeds_out = any(l["from"] == i and l["to"] in out_ids for l in links)
        fed_by_in = any(l["to"] == i and l["from"] in in_ids for l in links)
        if feeds_out and not fed_by_in and n_layers > 1:
            layer[i] = n_layers - 1
        elif fed_by_in and not feeds_out:
            layer[i] = 0
        else:
            layer[i] = counts.index(min(counts))
        counts[layer[i]] += 1
    cols = [[] for _ in range(n_layers)]
    for i in comp_ids:
        cols[layer[i]].append(i)
    return [c for c in cols if c]


def render_big_picture_canvas(a: Atlas):
    """One page, read left to right: where it starts -> 3-6 stages -> what comes out.

    Few cards and few arrows on purpose: the canvas is for seeing the whole project at once.
    Each stage card lists its parts as links; every part's own connections live in its note.
    """
    cv = Canvas("system")
    W, GX, GP = 320, 110, 50
    nodes = a.spec["nodes"]
    mains = [s for s in a.stages if s["lane"] == "main"]
    background = [s for s in a.stages if s["lane"] == "background"]

    def stages_touching(nid):
        """The stages of the parts this node is linked to, in story order."""
        found = []
        for l in a.spec["links"]:
            other = l["to"] if l["from"] == nid else l["from"] if l["to"] == nid else None
            st = a.stage_of.get(other)
            if st and st not in found:
                found.append(st)
        return sorted(found, key=a.stages.index)

    # inputs and outputs that only touch background parts belong with those parts, not in the main story
    side_io = {}
    for n in nodes:
        if n["kind"] in ("input", "output"):
            touched = stages_touching(n["id"])
            if touched and all(s["lane"] == "background" for s in touched):
                side_io.setdefault(touched[0]["id"], []).append(n)
    side_ids = {n["id"] for ns in side_io.values() for n in ns}
    starters = [n for n in nodes if n["kind"] in ("actor", "input") and n["id"] not in side_ids]
    outputs = [n for n in nodes if n["kind"] == "output" and n["id"] not in side_ids]

    def node_line(n, with_summary=False):
        s = f"- {KIND_ICON[n['kind']]} {a.node_link(n['id'])}{status_icon(a, n)}"
        return s + (f": {n['summary'].strip()}" if with_summary else "")

    def output_line(n):
        """An output says which stage makes it, since the one arrow into 'Comes out' starts at the last stage."""
        made_in = [s for s in stages_touching(n["id"]) if s in mains]
        hint = f" · *{a.t('card.from_stage', n=mains.index(made_in[-1]) + 1)}*" if made_in else ""
        return node_line(n) + hint

    def stage_text(st):
        t = f"### {a.stage_link(st)}"  # the title opens the stage's own zoom-in canvas
        if str(st.get("summary", "")).strip():
            t += f"\n{as_text(st['summary'])}"
        if st["nodes"]:
            t += f"\n\n**{a.t('card.parts')}**\n" + "\n".join(node_line(a.nodes[n]) for n in st["nodes"])
        # settings have their own card below; listing them on every stage is just noise
        uses = [u for u in a.stage_uses(st) if a.nodes[u]["kind"] != "config"]
        if uses:
            t += f"\n\n**{a.t('card.uses')}:** " + " · ".join(
                f"{KIND_ICON[a.nodes[u]['kind']]} {a.node_link(u)}" for u in uses)
        if str(st.get("passes") or "").strip() and st["lane"] == "main":
            t += f"\n\n➜ **{a.t('card.passes')}:** {str(st['passes']).strip()}"
        own = side_io.get(st["id"], [])
        if [n for n in own if n["kind"] == "input"]:
            t += f"\n\n**{a.t('card.in')}:** " + " · ".join(
                f"{KIND_ICON['input']} {a.node_link(n['id'])}" for n in own if n["kind"] == "input")
        if [n for n in own if n["kind"] == "output"]:
            t += f"\n**{a.t('card.out_short')}:** " + " · ".join(
                f"{KIND_ICON['output']} {a.node_link(n['id'])}" for n in own if n["kind"] == "output")
        return t

    row = []
    if starters:
        row.append(("start", f"### ▶ {a.t('card.start')}\n" + "\n".join(node_line(n) for n in starters), "5", None))
    for st in mains:
        row.append((f"stage:{st['id']}", stage_text(st), None, st.get("passes")))
    if outputs:
        row.append(("out", f"### ■ {a.t('card.out')}\n" + "\n".join(output_line(n) for n in outputs), "4", None))
    height = max((est_height(t, W) for _, t, _, _ in row), default=200)
    placed = []
    for i, (key, t, color, passes) in enumerate(row):
        placed.append((cv.card(key, i * (W + GX), 0, W, height, t, color), passes))
    # Arrows carry no labels: Obsidian draws labels at a fixed screen size, so when you zoom out they spill
    # over the cards. What a stage hands on is the last line of its own card instead.
    for (from_id, _), (to_id, _) in zip(placed, placed[1:]):
        cv.edge(from_id, to_id, sides=("right", "left"))

    # Lower row: background stages, then what it relies on. No arrows here; the stage cards say what they use.
    y, x = height + 220, 0
    if background:
        bh = max(est_height(stage_text(st), W) for st in background)
        rects = []
        for st in background:
            nid = cv.card(f"stage:{st['id']}", x + GP, y + GP, W, bh, stage_text(st), "6")
            rects.append(cv.rect[nid])
            x += W + 60
        gx, gy, gw, gh = bbox(rects, GP)
        cv.group("background", gx, gy, gw, gh, f"🔄 {a.t('group.background')}")
        x = gx + gw + 120
    relies = [(k, [n for n in nodes if n["kind"] == k]) for k in ("store", "external", "config")]
    relies = [(k, ns) for k, ns in relies if ns]
    if relies:
        # one-line summaries help with a few items; with more they turn the card into a wall of text
        texts = [(k, f"### {KIND_ICON[k]} {a.t('group.' + k)}\n" + "\n".join(node_line(n, len(ns) <= 3) for n in ns))
                 for k, ns in relies]
        rh = max(est_height(t, W) for _, t in texts)
        rects = []
        for i, (k, t) in enumerate(texts):
            nid = cv.card(f"relies:{k}", x + GP + i * (W + 60), y + GP, W, rh, t, KIND_COLOR[k])
            rects.append(cv.rect[nid])
        gx, gy, gw, gh = bbox(rects, GP)
        cv.group("relies", gx, gy, gw, gh, f"🧰 {a.t('group.relies')}")

    legend = f"**{a.t('card.legend')}**\n{a.t('legend.read')}\n\n{a.t('legend.status')}"
    lh = est_height(legend, 600)
    cv.card("legend", 820, -100 - lh, 600, lh, legend)
    header_card(a, cv, "system", 0, -100)
    a.add_canvas(a.canvas["system"], cv)


def render_stage_canvases(a: Atlas):
    """One small canvas per stage, laid out so no arrow passes behind a card.

    The stage's parts sit in one column (in the order work flows through them). What feeds them sits on the left
    and what they feed sits on the right, each level with the part it connects to, so arrows only cross the gaps.
    Storage, outside services and settings go in a row underneath without arrows: each part card says what it
    uses and each of those cards says who uses it.
    """
    resource_kinds = ("store", "external", "config")
    mains = [s for s in a.stages if s["lane"] == "main"]
    for st in a.stages:
        cv = Canvas("stage:" + st["id"])
        mset = set(st["nodes"])
        links = [l for l in a.spec["links"] if l["from"] in mset or l["to"] in mset]
        inner = [l for l in links if l["from"] in mset and l["to"] in mset]
        layers = layer_components(list(st["nodes"]), inner, set(), set()) if st["nodes"] else []
        members = [m for layer in layers for m in layer]
        incoming, outgoing, resources = [], [], []
        for l in links:
            if l["from"] in mset and l["to"] in mset:
                continue
            other = l["to"] if l["from"] in mset else l["from"]
            if other in incoming or other in outgoing or other in resources:
                continue
            if a.nodes[other]["kind"] in resource_kinds:
                resources.append(other)
            else:
                (outgoing if l["from"] in mset else incoming).append(other)
        W, NW, GX, GY, GP = 320, 260, 170, 44, 50

        def touching(x, y):
            return any({l["from"], l["to"]} == {x, y} for l in links)

        def where(nid):
            if nid in a.stage_of:
                return a.stage_link(a.stage_of[nid])
            return a.t("kind." + a.nodes[nid]["kind"])

        def part_text(nid):
            n = a.nodes[nid]
            t = f"### {KIND_ICON[n['kind']]} {a.node_link(nid)}{status_icon(a, n)}\n{n['summary'].strip()}"
            uses = [r for r in resources if touching(nid, r) and a.nodes[r]["kind"] != "config"]
            if uses:
                t += f"\n\n**{a.t('card.uses')}:** " + " · ".join(
                    f"{KIND_ICON[a.nodes[r]['kind']]} {a.nodes[r]['name']}" for r in uses)
            return t

        def neighbour_text(nid):
            n = a.nodes[nid]
            t = f"{KIND_ICON[n['kind']]} **{a.node_link(nid)}**\n*{where(nid)}*"
            if n["kind"] in resource_kinds:
                users = [m for m in members if touching(m, nid)]
                if users:
                    t += f"\n{a.t('card.used_by')}: " + ", ".join(a.nodes[u]["name"] for u in users)
            return t

        # the parts, top to bottom
        x_parts = (NW + GX) if incoming else 0
        pos, centre, y = {}, {}, 0
        for m in members:
            h = est_height(part_text(m), W)
            pos[m] = cv.card("n:" + m, x_parts, y, W, h, part_text(m), KIND_COLOR[a.nodes[m]["kind"]])
            centre[m] = y + h / 2
            y += h + GY

        def place_side(ids, x):
            """Stack neighbours, each as close as possible to the height of the parts it connects to."""
            wanted = []
            for nid in ids:
                ys = [centre[m] for m in members if touching(m, nid)]
                wanted.append((sum(ys) / len(ys) if ys else 0, nid))
            bottom = None
            for want, nid in sorted(wanted):
                h = est_height(neighbour_text(nid), NW)
                top = want - h / 2 if bottom is None else max(want - h / 2, bottom + GY)
                pos[nid] = cv.card("n:" + nid, x, top, NW, h, neighbour_text(nid), KIND_COLOR[a.nodes[nid]["kind"]])
                bottom = top + h

        place_side(incoming, 0)
        place_side(outgoing, x_parts + W + GX)

        part_rects = [cv.rect[pos[m]] for m in members]
        if part_rects:
            gx, gy, gw, gh = bbox(part_rects, GP)
            cv.group("stage", gx, gy, gw, gh, f"🧩 {a.t('card.stage_parts')}")
        lowest = max((r.y + r.h for r in cv.rect.values()), default=0)
        if resources:
            resources.sort(key=lambda r: (a.nodes[r]["kind"] == "config", resource_kinds.index(a.nodes[r]["kind"])))
            rx = 0
            for r in resources:
                h = est_height(neighbour_text(r), NW)
                pos[r] = cv.card("n:" + r, rx, lowest + 140, NW, h, neighbour_text(r), KIND_COLOR[a.nodes[r]["kind"]])
                rx += NW + 50

        order = {m: i for i, m in enumerate(members)}
        for l in links:
            f, t = l["from"], l["to"]
            if f not in pos or t not in pos or f in resources or t in resources:
                continue
            if f in mset and t in mset:
                gap = order[t] - order[f]
                sides = ("bottom", "top") if gap == 1 else ("top", "bottom") if gap == -1 else ("right", "right")
            elif f in mset:  # part -> neighbour, on whichever side the neighbour sits
                sides = ("right", "left") if t in outgoing else ("left", "right")
            else:            # neighbour -> part
                sides = ("right", "left") if f in incoming else ("left", "right")
            cv.edge(pos[f], pos[t], sides=sides)

        # header with a way back and to the neighbouring stages
        nav = [f"← {a.canvas_link('system')}"]
        if st in mains:
            i = mains.index(st)
            if i > 0:
                nav.append(f"{a.t('card.prev')}: {a.stage_link(mains[i - 1])}")
            if i < len(mains) - 1:
                nav.append(f"{a.t('card.next')}: {a.stage_link(mains[i + 1])}")
        text = f"# {a.stage_label(st)}\n{as_text(st.get('summary'))}\n\n" + " · ".join(nav)
        if st.get("passes") and st in mains:
            text += f"\n\n➜ **{a.t('card.passes')}:** {str(st['passes']).strip()}"
        top = min((r.y for r in cv.rect.values()), default=0)
        left = min((r.x for r in cv.rect.values()), default=0)
        hh = est_height(text, 760)
        cv.card("header", left, top - 80 - hh, 760, hh, text)
        a.add_canvas(a.stage_canvas[st["id"]], cv)


def render_flows_canvas(a: Atlas):
    cv = Canvas("flows")
    W, GX, GYR, GP, PER_ROW = 280, 100, 80, 50, 5
    y = 0
    for fi, f in enumerate(a.spec["flows"]):
        cards = []
        if f.get("trigger"):
            cards.append(("trigger", f"**{a.t('card.trigger')}**\n{as_text(f['trigger'])}", "5", None))
        for j, st in enumerate(f.get("steps") or [], 1):
            n = a.nodes[st["node"]]
            t = f"**{j}. {KIND_ICON[n['kind']]} {a.node_link(n['id'])}**\n{st['action'].strip()}"
            to = a.node_link(st["to"]) if st.get("to") and st["to"] != st["node"] else ""
            data = str(st.get("data") or "").strip()
            if to or data:
                t += "\n➜ " + to + (": " if to and data else "") + data
            cards.append((f"s{j}", t, KIND_COLOR[n["kind"]], None))
        if f.get("result"):
            cards.append(("result", f"**{a.t('card.result')}**\n{as_text(f['result'])}", "4", None))
        rows = [cards[i:i + PER_ROW] for i in range(0, len(cards), PER_ROW)]
        ids, rects = [], []
        yy = y + GP
        for ri, row in enumerate(rows):
            rh = max(est_height(c[1], W) for c in row)
            for ci, c in enumerate(row):
                col = ci if ri % 2 == 0 else (PER_ROW - 1 - ci) if len(rows) > 1 else ci
                xx = GP + col * (W + GX)
                nid = cv.card(f"{f['id']}:{c[0]}", xx, yy, W, rh, c[1], c[2])
                ids.append((nid, c[3]))
                rects.append(cv.rect[nid])
            yy += rh + GYR
        gx, gy, gw, gh = bbox(rects, GP)
        cv.groups.append({"id": sid("flows", "group", f["id"]), "type": "group",
                          "label": f"🔁 {fi + 1}. {f['name']}", "x": gx, "y": gy, "width": gw, "height": gh})
        for (a_id, _), (b_id, _) in zip(ids, ids[1:]):
            # no labels on arrows (they spill over cards when zoomed out); the step card says what is handed on
            cv.edge(a_id, b_id)
        y = gy + gh + 160
    hh = header_card(a, cv, "flows", 0, -80)
    a.add_canvas(a.canvas["flows"], cv)


def render_whatif_canvas(a: Atlas):
    """A board: one column per answer to "is it handled?", one short card per scenario.

    The card says what you would notice and the fix; the full chain of events is in the scenario's note.
    """
    cv = Canvas("whatif")
    W, GX, GY, GP = 340, 90, 30, 40
    x = 0
    for h in HANDLED:
        scs = sorted((s for s in a.spec["scenarios"] if s["handled"] == h), key=lambda s: SEVERITY_ORDER[s["severity"]])
        if not scs:
            continue
        rects, y = [], GP
        for s in scs:
            t = f"### {a.sc_link(s)}\n*{a.t('severity.' + s['severity'])}*"
            if s.get("trigger_node"):
                t += f" · {KIND_ICON[a.nodes[s['trigger_node']]['kind']]} {a.node_link(s['trigger_node'])}"
            if s.get("user_sees"):
                t += f"\n\n**{a.t('h.user_sees')}:** {as_text(s['user_sees'])}"
            if s.get("fix") and h != "yes":
                t += f"\n\n**{a.t('h.fix')}:** {as_text(s['fix'])}"
            card_h = est_height(t, W)
            nid = cv.card(s["id"], x + GP, y, W, card_h, t)
            rects.append(cv.rect[nid])
            y += card_h + GY
        gx, gy, gw, gh = bbox(rects, GP)
        cv.group(h, gx, gy, gw, gh, f"{a.t('handled.' + h)} ({len(scs)})", HANDLED_COLOR[h])
        x = gx + gw + GX
    header_card(a, cv, "whatif", 0, -80)
    a.add_canvas(a.canvas["whatif"], cv)


def render_reality_canvas(a: Atlas):
    cv = Canvas("reality")
    r = a.spec["reality"]
    p = a.spec["project"]
    W, GX, GY, GP = 300, 80, 30, 40
    intent, src = a.intent()
    it_text = f"### 🎯 {a.t('h.intent')}\n{intent or '-'}" + (f"\n\n*{a.t('intent_source')}: {src}*" if src else "")
    if a.plan_note:
        it_text += f"\n\n📋 {a.wl(a.plan_note, a.t('note.plan'))}"
    vd_text = f"### {a.t('h.verdict')}\n{as_text(r.get('verdict')) or '-'}"
    BW = 640
    th = max(est_height(it_text, BW), est_height(vd_text, BW))
    cv.card("intent", 0, 0, BW, th, it_text, "5")
    cv.card("verdict", BW + 60, 0, BW, th, vd_text)
    x = 0
    top = th + 160
    if r.get("plan_check"):
        # the recorded plan, item by item, comes first: it is what everything else is measured against
        yy, rects = top + GP, []
        for j, it in enumerate(r["plan_check"]):
            t = f"{PLAN_STATUS[it['status']]} **{str(it['item']).strip()}**\n*{a.t('plan.' + it['status'])}*"
            if it.get("note"):
                t += f"\n{as_text(it['note'])}"
            if it.get("nodes"):
                t += "\n\n→ " + " · ".join(a.node_link(n) for n in it["nodes"])
            h = est_height(t, W)
            rects.append(cv.rect[cv.card(f"plan:{j}", x + GP, yy, W, h, t)])
            yy += h + GY
        gx, gy, gw, gh = bbox(rects, GP)
        cv.group("plan_check", gx, gy, gw, gh, f"{a.t('h.plan_check')} ({plan_summary(a)})", "5")
        x = gx + gw + GX
    for sec in REALITY_SECTIONS:
        items = r.get(sec) or []
        if not items:
            continue
        yy = top + GP
        rects = []
        for j, it in enumerate(items):
            t = f"**{it['title'].strip()}**"
            if it.get("text"):
                t += f"\n{as_text(it['text'])}"
            if it.get("nodes"):
                t += "\n\n→ " + " · ".join(a.node_link(n) for n in it["nodes"])
            h = est_height(t, W)
            nid = cv.card(f"{sec}:{j}", x + GP, yy, W, h, t)
            rects.append(cv.rect[nid])
            yy += h + GY
        gx, gy, gw, gh = bbox(rects, GP)
        cv.groups.append({"id": sid("reality", "group", sec), "type": "group", "label": f"{a.t('h.' + sec)} ({len(items)})",
                          "x": gx, "y": gy, "width": gw, "height": gh, **({"color": REALITY_COLOR[sec]} if REALITY_COLOR[sec] else {})})
        x = gx + gw + GX
    header_card(a, cv, "reality", 0, -80)
    a.add_canvas(a.canvas["reality"], cv)


# --------------------------------------------------------------------------- writing

def write_lf(path: Path, text: str) -> None:
    """Write UTF-8 with Unix line endings on every OS (Path.write_text's newline= needs Python 3.10)."""
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def find_vault(start: Path):
    for d in [start, *start.parents]:
        if (d / ".obsidian").is_dir():
            return d
    return None


def kept_notes(text: str) -> str:
    i = text.find(KEEP_MARK)
    return text[i + len(KEEP_MARK):].strip("\n") if i >= 0 else ""


def is_generated(path: Path) -> bool:
    if path.suffix == ".canvas":
        return True
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:600]
    except OSError:
        return False
    return f'generator: "{GENERATOR}"' in head or f"generator: {GENERATOR}" in head


def write_all(a: Atlas, spec_path: Path, dry: bool):
    out = a.out
    old = []
    mpath = out / MANIFEST
    if mpath.exists():
        try:
            old = json.loads(mpath.read_text(encoding="utf-8")).get("files", [])
        except (OSError, json.JSONDecodeError):
            old = []
    old_set = set(old)
    warnings, written, skipped = [], 0, []
    a.files["atlas.json"] = spec_path.read_text(encoding="utf-8-sig")
    for rel, content in a.files.items():
        p = out / rel
        if p.exists() and rel not in old_set and rel != "atlas.json" and not is_generated(p):
            skipped.append(rel)
            continue
        if rel.endswith(".md") and p.exists():
            keep = kept_notes(p.read_text(encoding="utf-8", errors="replace"))
            if keep.strip():
                content = content.rstrip("\n") + "\n" + keep + "\n"
        if not dry:
            p.parent.mkdir(parents=True, exist_ok=True)
            write_lf(p, content)
        written += 1
    removed = 0
    for rel in old_set - set(a.files):
        p = out / rel
        if not p.exists():
            continue
        if rel.endswith(".md"):
            keep = kept_notes(p.read_text(encoding="utf-8", errors="replace"))
            if keep.strip():
                warnings.append(f"kept '{rel}': it is no longer in the atlas but has your notes in it")
                continue
        if not dry:
            p.unlink()
            d = p.parent
            while d != out and d.is_dir() and not any(d.iterdir()):
                d.rmdir()
                d = d.parent
        removed += 1
    if not dry:
        manifest = {"generator": GENERATOR, "version": VERSION, "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
                    "project": a.spec["project"]["name"], "files": sorted(a.files)}
        write_lf(mpath, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    for rel in skipped:
        warnings.append(f"did not overwrite '{rel}': a file with that name exists and was not made by project-atlas")
    return written, removed, warnings


def remember_atlas(project: dict, out: Path) -> None:
    """Record project folder -> atlas folder, so the plugin's SessionStart hook can say when an atlas is out of date.
    Stored in <Claude config dir>/project-atlas/registry.json. Only for local project folders; failures are ignored."""
    src = str(project.get("source") or "").strip()
    if not src or not Path(src).expanduser().is_dir():
        return
    base = Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude"))
    path = base / "project-atlas" / "registry.json"
    try:
        reg = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        reg[str(Path(src).expanduser().resolve())] = {"atlas": str(out), "project": project.get("name", ""),
                                                     "rendered_at": _dt.datetime.now().isoformat(timespec="seconds")}
        path.parent.mkdir(parents=True, exist_ok=True)
        write_lf(path, json.dumps(reg, ensure_ascii=False, indent=2) + "\n")
    except (OSError, ValueError):
        pass


def setup_graph(vault: Path, rel_root: str, dry: bool):
    gpath = vault / ".obsidian" / "graph.json"
    data = {}
    if gpath.exists():
        try:
            data = json.loads(gpath.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
    groups = [g for g in data.get("colorGroups", []) if not str(g.get("query", "")).startswith("tag:#atlas/")]
    for tag, rgb in GRAPH_COLORS.items():
        groups.append({"query": f"tag:#{tag}", "color": {"a": 1, "rgb": rgb}})
    data["colorGroups"] = groups
    if not dry:
        gpath.parent.mkdir(parents=True, exist_ok=True)
        write_lf(gpath, json.dumps(data, indent=2) + "\n")
    return gpath


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description="Render atlas.json into Obsidian notes and canvases.")
    ap.add_argument("spec", type=Path, help="path to atlas.json")
    ap.add_argument("--out", type=Path, required=True, help="folder for this project's atlas (inside a vault)")
    ap.add_argument("--vault", type=Path, help="vault root; found automatically if --out is inside a folder with .obsidian")
    ap.add_argument("--setup-graph", action="store_true", help="add colour groups for atlas tags to the vault's graph view")
    ap.add_argument("--dry-run", action="store_true", help="validate and report, write nothing")
    ap.add_argument("--no-registry", action="store_true",
                    help="don't record where this atlas lives (used by the plugin's refresh reminder)")
    ap.add_argument("--history-window", type=float, default=60, metavar="MINUTES",
                    help="a render this soon after the last snapshot replaces it (default 60; 0 = always a new one)")
    args = ap.parse_args()

    if not args.spec.exists():
        die(f"{args.spec} not found")
    spec, errors, warns = load_spec(args.spec)
    if errors:
        print("The atlas has problems to fix before it can be drawn:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    out = args.out.expanduser().resolve()
    if args.vault:
        vault = args.vault.expanduser().resolve()
        try:
            out.relative_to(vault)
        except ValueError:
            die(f"--out ({out}) is not inside --vault ({vault})")
    else:
        vault = find_vault(out)
        if vault is None:
            vault = out
            warns.append(f"no Obsidian vault (.obsidian folder) found above {out}; links assume this folder itself is "
                         f"opened as a vault. Pass --vault to set the vault root.")

    labels = dict(DEFAULT_LABELS)
    labels.update({k: v for k, v in (spec.get("labels") or {}).items() if isinstance(v, str)})
    a = Atlas(spec, out, vault, labels)

    # the plan recorded at the start of the project (save_plan.py), if there is one
    plan_path = out / "plan.json"
    if plan_path.exists():
        try:
            a.plan = json.loads(plan_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            warns.append(f"{plan_path} is not valid JSON; the plan was ignored")
    if a.plan:
        if (out / (a.t("note.plan") + ".md")).exists():
            a.plan_note = a.t("note.plan")
        recorded = str(a.plan.get("recorded", ""))[:10]
        if a.plan_note:
            a.extra_home_links.append(f"- 📋 {a.wl(a.plan_note, a.t('note.plan'))}: {a.t('read.plan', date=recorded)}")
        if not spec["reality"].get("plan_check"):
            warns.append("a plan was recorded but reality.plan_check is empty: check each must-have against the project")
    if spec["reality"].get("plan_check"):
        built, total = plan_score(a)
        a.extra_glance_rows.append(f"| 📋 {a.t('glance.plan')} | {a.t('glance.plan_value', built=built, total=total)}"
                                   f" ({plan_summary(a)}) |")

    # history: a snapshot each time the atlas changes, and a note listing what changed
    entries = update_history(out, args.spec.read_text(encoding="utf-8-sig"), args.dry_run, args.history_window)
    a.extra_home_links.append(f"- 🕑 {a.wl(a.changes_note, a.t('changes.title'))}: {a.t('read.changes')}")
    render_changes(a, entries)

    ins, outs, in_flows, sc_for = relations(a)
    render_home(a)
    for n in spec["nodes"]:
        render_node(a, n, ins, outs, in_flows, sc_for)
    for f in spec["flows"]:
        render_flow(a, f)
    for s in spec["scenarios"]:
        render_scenario(a, s)
    render_reality(a)
    if a.glossary_note:
        render_glossary(a)
    if a.auto_stages:
        warns.append("no stages: the Big Picture shows automatic 'Step n' stages. Define 3-6 named stages for a "
                     "clearer story (see 'stages' in references/atlas-format.md)")
    render_big_picture_canvas(a)
    render_stage_canvases(a)
    render_flows_canvas(a)
    render_whatif_canvas(a)
    render_reality_canvas(a)

    written, removed, wwarns = write_all(a, args.spec, args.dry_run)
    warns += wwarns
    if not args.dry_run and not args.no_registry:
        remember_atlas(spec["project"], out)
    graph_note = ""
    if args.setup_graph:
        g = setup_graph(vault, a.rel_root, args.dry_run)
        graph_note = f"graph colours: {g}" + (" (reopen the graph view, or restart Obsidian if it was open)" if not args.dry_run else "")

    home_abs = (out / (a.home + ".md")).resolve()
    print(("[dry run] " if args.dry_run else "") + f"Atlas for '{spec['project']['name']}' -> {out}")
    print(f"  vault: {vault}")
    n_notes = sum(1 for r in a.files if r.endswith(".md"))
    n_canvas = sum(1 for r in a.files if r.endswith(".canvas"))
    if args.dry_run:
        print(f"  would write {n_notes} notes and {n_canvas} canvases ({written} files) and remove {removed} stale files")
    else:
        print(f"  {n_notes} notes, {n_canvas} canvases written ({written} files), {removed} stale files removed")
    print(f"  home note: {home_abs}")
    print(f"  open in Obsidian: obsidian://open?path={urllib.parse.quote(str(home_abs))}")
    if graph_note:
        print(f"  {graph_note}")
    if warns:
        print("Warnings:")
        for w in warns:
            print(f"  - {w}")


if __name__ == "__main__":
    main()
