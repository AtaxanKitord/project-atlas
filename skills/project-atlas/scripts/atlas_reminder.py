#!/usr/bin/env python3
"""
atlas_reminder.py - SessionStart hook for the project-atlas plugin.

If the project Claude is opened in has an atlas (recorded by render_atlas.py in
<Claude config dir>/project-atlas/registry.json) and the project changed after the atlas
was last rendered, print one line of context so Claude can offer, once, to refresh it.
Prints nothing otherwise. Never fails loudly: any problem means silence.

Standard library only.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import subprocess
import sys
from pathlib import Path

SKIP = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next", "target", ".cache"}


def registry_path() -> Path:
    base = os.environ.get("CLAUDE_CONFIG_DIR") or str(Path.home() / ".claude")
    return Path(base) / "project-atlas" / "registry.json"


def norm(p: str) -> str:
    return os.path.normcase(os.path.abspath(p))


def changed_since(project: Path, since: _dt.datetime) -> str | None:
    """A short description of what changed after `since`, or None."""
    ts = since.timestamp() + 600  # ignore edits made in the same sitting as the render
    try:
        r = subprocess.run(["git", "-C", str(project), "rev-list", "--count", f"--since={int(ts)}", "HEAD"],
                           capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            commits = int(r.stdout.strip() or 0)
            dirty = subprocess.run(["git", "-C", str(project), "status", "--porcelain"],
                                   capture_output=True, text=True, timeout=10).stdout.strip().splitlines()
            recent_dirty = 0
            for line in dirty:
                f = project / line[3:].strip().strip('"')
                try:
                    if f.exists() and f.stat().st_mtime > ts:
                        recent_dirty += 1
                except OSError:
                    pass
            if commits or recent_dirty:
                bits = [f"{commits} new commit{'s' if commits != 1 else ''}" if commits else "",
                        f"{recent_dirty} changed file{'s' if recent_dirty != 1 else ''} not committed" if recent_dirty else ""]
                return ", ".join(b for b in bits if b)
            return None
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    newer, seen = 0, 0
    for dirpath, dirnames, filenames in os.walk(project):
        dirnames[:] = [d for d in dirnames if d not in SKIP and not d.startswith(".")]
        for f in filenames:
            seen += 1
            try:
                if os.path.getmtime(os.path.join(dirpath, f)) > ts:
                    newer += 1
            except OSError:
                pass
            if seen > 5000:
                break
        if seen > 5000:
            break
    return f"{newer} file{'s' if newer != 1 else ''} changed" if newer else None


def main():
    try:
        data = json.loads(sys.stdin.read() or "{}") if not sys.stdin.isatty() else {}
    except (ValueError, OSError):
        data = {}
    cwd = norm(data.get("cwd") or os.getcwd())
    try:
        registry = json.loads(registry_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    best = None
    for project, entry in registry.items():
        p = norm(project)
        if cwd == p or cwd.startswith(p + os.sep):
            if best is None or len(p) > len(norm(best[0])):
                best = (project, entry)
    if not best:
        return
    project, entry = best
    atlas = Path(entry.get("atlas", ""))
    if not atlas.is_dir():
        return
    try:
        rendered = _dt.datetime.fromisoformat(entry["rendered_at"])
    except (KeyError, ValueError):
        return
    change = changed_since(Path(project), rendered)
    if not change:
        return
    msg = (f"project-atlas: this project has an Obsidian atlas at {atlas} (last refreshed "
           f"{rendered.strftime('%Y-%m-%d')}); since then: {change}. At a natural stopping point, or when the user "
           f"wraps up, offer once to refresh the atlas with the project-atlas skill. Don't refresh without asking.")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": msg}}))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # a reminder must never get in the way
        pass
