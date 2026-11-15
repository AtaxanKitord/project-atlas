#!/usr/bin/env python3
"""
save_plan.py - record what the owner sets out to build, at the start of a project.

Writes plan.json and a "0 Plan" note into the project's atlas folder. Later, when the
project is mapped with render_atlas.py, Plan vs Reality checks every must-have against
this recorded plan instead of guessing the intent from the README.

Saving again keeps the earlier version in history/plan-<date>.json.

Standard library only. Python 3.8+.

Usage:
  python save_plan.py plan.json --out "<vault>/Project Atlas/<Project>" [--vault <vault root>] [--dry-run]

plan.json:
  {
    "project": "Pantry Chef",                       required: the name you will use for the atlas
    "goal": "A bot that turns a fridge list into recipes.",   required: one to three sentences
    "for_whom": "Friends on my Discord server",
    "must_have": ["Three recipes per request", "..."],
    "nice_to_have": ["..."],
    "out_of_scope": ["Payments", "..."],
    "stages": ["Read the fridge list", "Write the recipes", "Reply"],   the story you expect
    "done_when": ["A friend can get a recipe in under 10 seconds"],
    "notes": "free text",
    "source": "the user, in conversation"
  }
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_atlas as ra  # noqa: E402  (shared helpers: file names, links, kept notes)

LIST_FIELDS = ("must_have", "nice_to_have", "out_of_scope", "stages", "done_when")
LABELS = {
    "title": "Plan: {project}", "recorded": "Recorded on {date}", "for_whom": "For whom",
    "must_have": "Must have", "nice_to_have": "Nice to have", "out_of_scope": "Out of scope",
    "done_when": "Done when", "stages": "The story we expect", "notes": "Notes",
    "earlier": "Earlier versions", "about": "This is the plan as it was recorded. When the project is mapped, "
    "Plan vs Reality checks every must-have against what was actually built. To change the plan, ask Claude to "
    "update it; the old version is kept in `history/`.",
}


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description="Record a project plan for project-atlas.")
    ap.add_argument("plan", type=Path)
    ap.add_argument("--out", type=Path, required=True, help="the project's atlas folder")
    ap.add_argument("--vault", type=Path, help="vault root; found automatically if --out is inside a vault")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as e:
        ra.die(f"cannot read {args.plan}: {e}")
    errors = []
    if not str(plan.get("project", "")).strip():
        errors.append("project is required")
    if not str(plan.get("goal", "")).strip():
        errors.append("goal is required")
    for f in LIST_FIELDS:
        v = plan.get(f)
        if v is None:
            plan[f] = []
        elif isinstance(v, str):
            plan[f] = [v]
        elif not isinstance(v, list):
            errors.append(f"{f} must be a list of strings")
    if errors:
        ra.die("; ".join(errors))

    out = args.out.expanduser().resolve()
    vault = args.vault.expanduser().resolve() if args.vault else (ra.find_vault(out) or out)
    rel_root = out.relative_to(vault).as_posix() if out != vault else ""

    now = _dt.datetime.now().replace(microsecond=0)
    plan_path = out / "plan.json"
    history = []
    if plan_path.exists():
        try:
            old = json.loads(plan_path.read_text(encoding="utf-8-sig"))
            plan["first_recorded"] = old.get("first_recorded") or old.get("recorded")
            stamp = str(old.get("recorded", "")).replace(":", "-").replace("T", "_") or now.strftime("%Y-%m-%d_%H-%M-%S")
            if not args.dry_run:
                (out / ra.HISTORY_DIR).mkdir(parents=True, exist_ok=True)
                ra.write_lf(out / ra.HISTORY_DIR / f"plan-{stamp}.json",
                            json.dumps(old, ensure_ascii=False, indent=2) + "\n")
        except (OSError, json.JSONDecodeError):
            pass
    plan["recorded"] = now.isoformat()
    plan.setdefault("first_recorded", plan["recorded"])
    if (out / ra.HISTORY_DIR).is_dir():
        history = sorted(p.stem[len("plan-"):] for p in (out / ra.HISTORY_DIR).glob("plan-*.json"))

    note_name = ra.DEFAULT_LABELS["note.plan"]
    lines = [f"# {LABELS['title'].format(project=plan['project'])}", "",
             ra.callout("abstract", f"📋 {LABELS['recorded'].format(date=now.strftime('%Y-%m-%d %H:%M'))}"
                        + (f" · {plan['source']}" if plan.get("source") else ""), ra.as_text(plan["goal"])), ""]
    if plan.get("for_whom"):
        lines += [f"**{LABELS['for_whom']}:** {ra.as_text(plan['for_whom'])}", ""]
    for f in ("must_have", "nice_to_have", "out_of_scope", "done_when"):
        if plan[f]:
            lines += [f"## {LABELS[f]}"] + [f"- {x}" for x in plan[f]] + [""]
    if plan["stages"]:
        items = [(f"▶ {ra.mm(ra.DEFAULT_LABELS['card.start'], 30)}", None, "end")]
        items += [(ra.mm(f"{i} · {s}", 60), None, "stage") for i, s in enumerate(plan["stages"], 1)]
        items += [(f"■ {ra.mm(ra.DEFAULT_LABELS['card.out'], 30)}", None, "end")]
        lines += [f"## {LABELS['stages']}"] + ra.chain_mermaid(items) + [""]
    if plan.get("notes"):
        lines += [f"## {LABELS['notes']}", ra.as_text(plan["notes"]), ""]
    if history:
        lines += [f"*{LABELS['earlier']}: " + ", ".join(f"`history/plan-{h}.json`" for h in history) + "*", ""]
    lines += ["---", f"*{LABELS['about']}*"]
    home = f"{rel_root}/{ra.safe_name(plan['project'])}" if rel_root else ra.safe_name(plan["project"])
    if (out / (ra.safe_name(plan["project"]) + ".md")).exists():
        lines.append(f"\n{ra.DEFAULT_LABELS['back']}: [[{home}|{ra.alias(plan['project'])}]]")

    fm = ra.frontmatter({"generator": ra.GENERATOR, "project": plan["project"], "atlas": "plan",
                         "recorded": plan["recorded"], "tags": ["atlas", "atlas/plan"]})
    text = fm + "\n".join(lines).rstrip() + "\n\n## " + ra.DEFAULT_LABELS["h.my_notes"] + "\n" + ra.KEEP_MARK + "\n"
    note_path = out / f"{note_name}.md"
    if note_path.exists():
        existing = note_path.read_text(encoding="utf-8", errors="replace")
        if not ra.is_generated(note_path):
            ra.die(f"{note_path} exists and was not made by project-atlas; not overwriting it")
        keep = ra.kept_notes(existing)
        if keep.strip():
            text = text.rstrip("\n") + "\n" + keep + "\n"
    if args.dry_run:
        print(f"[dry run] plan for '{plan['project']}' is valid; would write {plan_path} and {note_path}")
        return
    out.mkdir(parents=True, exist_ok=True)
    ra.write_lf(plan_path, json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
    ra.write_lf(note_path, text)
    print(f"Plan for '{plan['project']}' recorded -> {out}")
    print(f"  {len(plan['must_have'])} must-haves, {len(plan['nice_to_have'])} nice-to-haves, "
          f"{len(plan['out_of_scope'])} out of scope, {len(plan['stages'])} expected stages")
    print(f"  note: {note_path}")
    if history:
        print(f"  earlier versions kept: {len(history)} in {out / ra.HISTORY_DIR}")


if __name__ == "__main__":
    main()
