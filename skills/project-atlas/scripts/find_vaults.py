#!/usr/bin/env python3
"""
find_vaults.py - list the Obsidian vaults on this computer for project-atlas.

Reads Obsidian's own vault list (obsidian.json) and, for each vault, reports
whether it already holds project atlases (folders with an .atlas-manifest.json).
Read-only. Standard library only.

Usage:
  python find_vaults.py            # JSON
  python find_vaults.py --text     # human-readable
  python find_vaults.py --scan DIR # also look for vault folders (.obsidian) under DIR
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from pathlib import Path

MANIFEST = ".atlas-manifest.json"
SKIP = {".obsidian", ".trash", ".git", "node_modules", ".venv"}


def config_files():
    home = Path.home()
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        return [Path(appdata) / "obsidian" / "obsidian.json"] if appdata else []
    if sys.platform == "darwin":
        return [home / "Library" / "Application Support" / "obsidian" / "obsidian.json"]
    xdg = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    return [xdg / "obsidian" / "obsidian.json",
            home / ".var" / "app" / "md.obsidian.Obsidian" / "config" / "obsidian" / "obsidian.json",
            home / "snap" / "obsidian" / "current" / ".config" / "obsidian" / "obsidian.json"]


def atlases_in(vault: Path, max_depth: int = 4):
    found = []
    base_depth = len(vault.parts)
    for dirpath, dirnames, filenames in os.walk(vault):
        d = Path(dirpath)
        dirnames[:] = [x for x in dirnames if x not in SKIP]
        if len(d.parts) - base_depth >= max_depth:
            dirnames[:] = []
        if MANIFEST in filenames:
            try:
                m = json.loads((d / MANIFEST).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                m = {}
            found.append({"project": m.get("project", d.name), "folder": str(d),
                          "generated_at": m.get("generated_at", "")})
    return found


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description="List Obsidian vaults and existing project atlases.")
    ap.add_argument("--text", action="store_true", help="human-readable output")
    ap.add_argument("--scan", type=Path, action="append", default=[], help="also search this folder for vaults")
    args = ap.parse_args()

    vaults, seen = [], set()
    cfg_used = None
    for cfg in config_files():
        if not cfg.exists():
            continue
        cfg_used = str(cfg)
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for info in (data.get("vaults") or {}).values():
            p = Path(info.get("path", ""))
            key = str(p).lower()
            if not info.get("path") or key in seen:
                continue
            seen.add(key)
            ts = info.get("ts")
            vaults.append({"name": p.name, "path": str(p), "exists": p.is_dir(), "open": bool(info.get("open")),
                           "last_opened": _dt.datetime.fromtimestamp(ts / 1000).isoformat(timespec="minutes") if ts else "",
                           "registered": True})
    for root in args.scan:
        for dirpath, dirnames, _ in os.walk(root.expanduser()):
            if ".obsidian" in dirnames:
                p = Path(dirpath)
                if str(p).lower() not in seen:
                    seen.add(str(p).lower())
                    vaults.append({"name": p.name, "path": str(p), "exists": True, "open": False,
                                   "last_opened": "", "registered": False})
                dirnames[:] = []
            else:
                dirnames[:] = [d for d in dirnames if d not in SKIP and not d.startswith(".")]
    for v in vaults:
        v["atlases"] = atlases_in(Path(v["path"])) if v["exists"] else []

    result = {"obsidian_config": cfg_used, "vaults": vaults}
    if not args.text:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if not vaults:
        print("No Obsidian vaults found." + ("" if cfg_used else " Obsidian's vault list was not found; is Obsidian installed?"))
        return
    for v in vaults:
        flags = [f for f, on in (("open now", v["open"]), ("missing", not v["exists"]),
                                 ("not registered in Obsidian", not v["registered"])) if on]
        print(f"- {v['name']}: {v['path']}" + (f" ({', '.join(flags)})" if flags else ""))
        for a in v["atlases"]:
            print(f"    atlas: {a['project']} -> {a['folder']} ({a['generated_at']})")


if __name__ == "__main__":
    main()
