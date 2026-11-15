#!/usr/bin/env python3
"""
scan_project.py - a quick, read-only survey of a project folder for project-atlas.

It does not try to understand the project. It finds the places worth reading:
stack and run scripts, entry points, where input comes in (environment variables,
HTTP routes, CLI flags, schedules, bots, automation workflows), which outside
services and storage are used, how errors are handled, loose ends (TODO/FIXME),
and what git history says about how the project started.

Standard library only. Python 3.8+. Nothing is written except the optional --out file.

Usage:
  python scan_project.py <project-root> [--out scan.md] [--max-files 6000]
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import subprocess
import sys
from pathlib import Path

IGNORE_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "bower_components", ".venv", "venv", "env", ".env",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".nox", "dist", "build",
    "out", ".next", ".nuxt", ".svelte-kit", ".turbo", ".parcel-cache", ".vercel", ".netlify",
    "target", "vendor", "coverage", ".coverage", "htmlcov", ".cache", ".npm-cache", ".yarn",
    ".pnpm-store", ".gradle", ".idea", ".vs", "obj", "Pods", "DerivedData", ".dart_tool",
    ".expo", ".terraform", "site-packages", ".eggs", "eggs", "wheels", ".ipynb_checkpoints",
    "tmp", "temp", "logs",
}
KEEP_HIDDEN = {".github", ".gitlab", ".circleci", ".devcontainer", ".husky", ".claude", ".cursor"}
LANG = {
    ".py": "Python", ".ipynb": "Jupyter", ".js": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".jsx": "JavaScript (JSX)", ".ts": "TypeScript", ".tsx": "TypeScript (TSX)", ".vue": "Vue",
    ".svelte": "Svelte", ".astro": "Astro", ".go": "Go", ".rs": "Rust", ".java": "Java", ".kt": "Kotlin",
    ".kts": "Kotlin", ".scala": "Scala", ".rb": "Ruby", ".php": "PHP", ".cs": "C#", ".fs": "F#",
    ".swift": "Swift", ".m": "Objective-C", ".dart": "Dart", ".c": "C", ".h": "C/C++ header",
    ".cpp": "C++", ".cc": "C++", ".hpp": "C++", ".lua": "Lua", ".ex": "Elixir", ".exs": "Elixir",
    ".erl": "Erlang", ".clj": "Clojure", ".hs": "Haskell", ".r": "R", ".jl": "Julia", ".sh": "Shell",
    ".bash": "Shell", ".zsh": "Shell", ".ps1": "PowerShell", ".bat": "Batch", ".sql": "SQL",
    ".prisma": "Prisma", ".graphql": "GraphQL", ".gql": "GraphQL", ".proto": "Protobuf",
    ".html": "HTML", ".css": "CSS", ".scss": "SCSS", ".sass": "Sass", ".less": "Less",
    ".json": "JSON", ".yml": "YAML", ".yaml": "YAML", ".toml": "TOML", ".ini": "INI", ".xml": "XML",
    ".md": "Markdown", ".mdx": "MDX", ".tf": "Terraform", ".gd": "GDScript", ".sol": "Solidity",
}
CODE_EXT = {e for e in LANG if e not in {".md", ".mdx", ".json", ".xml", ".ini"}}
TEXT_EXT = set(LANG) | {".txt", ".cfg", ".conf", ".env", ".example", ".sample", ".lock", ".csv", ".gitignore"}
MAX_BYTES = 1_500_000

ENV_PATTERNS = [
    r"process\.env\.([A-Z_][A-Z0-9_]{1,})",
    r"process\.env\[\s*['\"]([A-Z_][A-Z0-9_]{1,})['\"]",
    r"import\.meta\.env\.([A-Z_][A-Z0-9_]{1,})",
    r"os\.environ(?:\.get)?\s*[\[(]\s*['\"]([A-Z_][A-Z0-9_]{1,})['\"]",
    r"os\.getenv\(\s*['\"]([A-Z_][A-Z0-9_]{1,})['\"]",
    r"\bgetenv\(\s*['\"]([A-Z_][A-Z0-9_]{1,})['\"]",
    r"\bENV\[\s*['\"]([A-Z_][A-Z0-9_]{1,})['\"]",
    r"\benv\(\s*['\"]([A-Z_][A-Z0-9_]{1,})['\"]",
    r"Deno\.env\.get\(\s*['\"]([A-Z_][A-Z0-9_]{1,})['\"]",
    r"\$env\.([A-Z_][A-Z0-9_]{1,})",
    r"\$env\[\s*['\"]([A-Z_][A-Z0-9_]{1,})['\"]",
    r"\$\{\{\s*(?:secrets|vars)\.([A-Z_][A-Z0-9_]{1,})",
    r"Environment\.GetEnvironmentVariable\(\s*\"([A-Z_][A-Z0-9_]{1,})\"",
    r"System\.getenv\(\s*\"([A-Z_][A-Z0-9_]{1,})\"",
]
ROUTE_PATTERNS = [
    (r"\b(?:app|router|server|api|fastify|r|route)\.(get|post|put|patch|delete|all)\(\s*['\"`]([^'\"`]+)['\"`]", "express-style"),
    (r"@\w+\.(get|post|put|patch|delete|route|websocket|api_route)\(\s*['\"]([^'\"]*)['\"]", "decorator"),
    (r"\b(?:re_)?path\(\s*r?['\"]([^'\"]*)['\"]\s*,", "django"),
    (r"\.(GET|POST|PUT|PATCH|DELETE|Any)\(\s*\"([^\"]+)\"", "go"),
    (r"HandleFunc\(\s*\"([^\"]+)\"", "go"),
    (r"@(Get|Post|Put|Patch|Delete|Request)Mapping\(\s*(?:value\s*=\s*|path\s*=\s*)?\"([^\"]*)\"", "spring"),
    (r"Route::(get|post|put|patch|delete|any)\(\s*['\"]([^'\"]+)['\"]", "laravel"),
    (r"(?:req|request|ctx\.request)\.url\s*={2,3}\s*['\"](/[^'\"]*)['\"]", "url-compare"),
    (r"\bpathname\s*={2,3}\s*['\"](/[^'\"]*)['\"]", "url-compare"),
]
CLI_PATTERNS = [
    r"add_argument\(\s*['\"](-{1,2}[\w-]+|[a-z_]+)['\"]",
    r"(?:click|typer)\.(?:option|argument)\(\s*['\"](-{0,2}[\w-]+)['\"]",
    r"\.option\(\s*['\"](-{1,2}[\w-]+)",
    r"flag\.(?:String|Int|Bool|Duration)\(\s*\"([\w-]+)\"",
]
SCHEDULE_PATTERNS = [
    r"['\"]((?:[\d*/,-]+\s+){4}[\d*/,?A-Z-]+)['\"]",
    r"\b(schedule\.every\([^)]*\)[\w.()]*)",
    r"\b(setInterval)\(",
    r"\b(cron:\s*['\"]?[^'\"\n]+)",
    r"@(Scheduled)\(",
    r"\b(BackgroundScheduler|BlockingScheduler|AsyncIOScheduler|node-cron|cron\.schedule)\b",
]
SERVICES = {
    "OpenAI": r"\bopenai\b|api\.openai\.com",
    "Anthropic (Claude)": r"\banthropic\b|@anthropic-ai|api\.anthropic\.com",
    "Google AI (Gemini)": r"google\.generativeai|@google/genai|generativelanguage\.googleapis",
    "Telegram": r"telegram|telegraf|aiogram|api\.telegram\.org|grammy",
    "Discord": r"discord\.js|discord\.py|\bdiscord\b",
    "Slack": r"@slack/|slack_sdk|slack\.com/api",
    "WhatsApp": r"whatsapp",
    "Stripe": r"\bstripe\b",
    "PayPal": r"paypal",
    "Twilio": r"twilio",
    "Email (SMTP/SendGrid/Resend/Mailgun)": r"smtplib|nodemailer|sendgrid|resend|mailgun|postmark",
    "AWS": r"boto3|@aws-sdk|aws-sdk",
    "Google Cloud / Firebase": r"firebase|google\.cloud|@google-cloud|googleapis",
    "Supabase": r"supabase",
    "Notion": r"@notionhq|notion_client|api\.notion\.com",
    "Airtable": r"airtable",
    "Shopify": r"shopify",
    "GitHub API": r"octokit|api\.github\.com|PyGithub",
    "ElevenLabs": r"elevenlabs",
    "Replicate": r"replicate",
    "Hugging Face": r"huggingface|transformers\b",
    "Sentry": r"sentry",
    "PostHog / Mixpanel / Segment": r"posthog|mixpanel|@segment/|analytics\.segment|segment\.io",
    "Pusher / Ably / Socket.IO": r"pusher|ably|socket\.io",
    "Kafka / RabbitMQ / SQS": r"kafka|amqplib|pika|rabbitmq|\bsqs\b",
    "n8n": r"n8n-nodes-|\bn8n\b",
    "Zapier / Make": r"zapier|hook\.\w+\.make\.com|integromat",
}
STORAGE = {
    "SQLite": r"sqlite",
    "PostgreSQL": r"psycopg|\bpg\b|postgres",
    "MySQL / MariaDB": r"mysql|mariadb",
    "MongoDB": r"mongo",
    "Redis": r"\bredis\b|ioredis",
    "ORM (Prisma/SQLAlchemy/Drizzle/TypeORM/Sequelize/Django)": r"prisma|sqlalchemy|drizzle|typeorm|sequelize|django\.db|knex|peewee|tortoise",
    "Browser storage (localStorage/IndexedDB)": r"localStorage|sessionStorage|indexedDB|idb-keyval|dexie",
    "Local files (write)": r"writeFile|write_text|write_bytes|open\([^)]*['\"][wa]b?['\"]|fs\.createWriteStream|shutil\.copy",
    "Object storage (S3/R2/GCS/Blob)": r"\bs3\b|putObject|upload_fileobj|r2\.dev|storage\.bucket|@vercel/blob|storage\.blob",
    "Google Sheets / Excel": r"gspread|sheets\.googleapis|openpyxl|xlsx|exceljs",
    "Vector DB": r"pinecone|chroma|qdrant|weaviate|pgvector|faiss|lancedb",
}
# storage kinds that are about using an API in code; the rest are only trusted from imports and dependencies
STORAGE_USAGE = {"Browser storage (localStorage/IndexedDB)", "Local files (write)"}
LOCK_FILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "Pipfile.lock", "Cargo.lock",
              "composer.lock", "Gemfile.lock", "bun.lock", "uv.lock", "npm-shrinkwrap.json"}
DOC_NAMES = {"README", "CLAUDE.MD", "AGENTS.MD", "STATUS.MD", "CHANGELOG.MD", "CONTRIBUTING.MD", "ROADMAP.MD",
             "TODO.MD", "SPEC.MD", "PLAN.MD", "NOTES.MD", "ARCHITECTURE.MD", "DESIGN.MD"}
DATA_EXT = {".json", ".jsonl", ".ndjson", ".csv", ".tsv", ".xml", ".log", ".lock"}
PROJECT_MARKERS = ("package.json", "pyproject.toml", "requirements.txt", "go.mod", "Cargo.toml", "composer.json",
                   "Gemfile", "pom.xml", "build.gradle", "deno.json")
IMPORT_LINE = re.compile(r"^\s*(import|from|using|use|require|include)\b|require\(|import\(|@[\w-]+/[\w-]")
CHAT_COMMANDS = [
    (r"\.setName\(\s*['\"]([\w-]+)['\"]", "Discord slash command", "SlashCommandBuilder"),
    (r"\.command\(\s*['\"]/?([\w-]+)['\"]", "command (bot or CLI)", None),
    (r"CommandHandler\(\s*['\"]([\w-]+)['\"]", "Telegram command", None),
    (r"\bCommand\(\s*['\"]([\w-]+)['\"]\s*\)", "Telegram command", "aiogram"),
    (r"onText\(\s*/\\?/([\w-]+)", "Telegram command", None),
]
TODO_RE = re.compile(r"\b(TODO|FIXME|HACK|XXX|BUG)\b[:\s-]*(.{0,110})")
URL_RE = re.compile(r"https?://([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})(?::\d+)?")
URL_SKIP = re.compile(r"(^|\.)(localhost|example\.(com|org|net)|w3\.org|json-schema\.org|schema\.org|"
                      r"github\.com|githubusercontent\.com|npmjs\.(com|org)|python\.org|mozilla\.org|"
                      r"stackoverflow\.com|wikipedia\.org|apache\.org|opensource\.org|semver\.org|"
                      r"shields\.io|fonts\.googleapis\.com|fonts\.gstatic\.com|cdn\.jsdelivr\.net|"
                      r"unpkg\.com|cdnjs\.cloudflare\.com|readthedocs\.io|yourdomain\.\w+|domain\.com)$")
ENTRY_NAMES = {
    "main.py", "app.py", "server.py", "manage.py", "wsgi.py", "asgi.py", "cli.py", "__main__.py", "bot.py",
    "run.py", "index.js", "index.ts", "index.mjs", "main.js", "main.ts", "server.js", "server.ts", "app.js",
    "app.ts", "main.go", "main.rs", "lib.rs", "Program.cs", "index.html", "App.tsx", "App.jsx", "App.vue",
    "main.tsx", "main.jsx", "index.php", "Main.java", "Application.java", "main.dart", "worker.js", "worker.ts",
}


def rel(p: Path, root: Path) -> str:
    return p.relative_to(root).as_posix()


def list_files(root: Path, max_files: int):
    files, skipped_dirs = [], collections.Counter()
    try:
        r = subprocess.run(["git", "-C", str(root), "ls-files", "-co", "--exclude-standard", "-z"],
                           capture_output=True, timeout=60)
        if r.returncode == 0 and r.stdout:
            for s in r.stdout.decode("utf-8", errors="replace").split("\0"):
                if not s:
                    continue
                parts = s.split("/")
                if any(p in IGNORE_DIRS for p in parts[:-1]):
                    skipped_dirs[parts[0]] += 1
                    continue
                p = root / s
                if p.is_file():
                    files.append(p)
            return files[:max_files], skipped_dirs, True
    except (OSError, subprocess.SubprocessError):
        pass
    for dirpath, dirnames, filenames in os.walk(root):
        keep = []
        for d in dirnames:
            if d in IGNORE_DIRS or (d.startswith(".") and d not in KEEP_HIDDEN):
                skipped_dirs[rel(Path(dirpath) / d, root)] += 1
            else:
                keep.append(d)
        dirnames[:] = sorted(keep)
        for f in sorted(filenames):
            files.append(Path(dirpath) / f)
            if len(files) >= max_files:
                return files, skipped_dirs, False
    return files, skipped_dirs, False


def read_text(p: Path):
    try:
        if p.stat().st_size > MAX_BYTES:
            return None
        data = p.read_bytes()
    except OSError:
        return None
    if b"\0" in data[:8192]:
        return None
    return data.decode("utf-8", errors="replace")


def git(root: Path, *args):
    try:
        r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, timeout=30)
        if r.returncode == 0:
            return r.stdout.decode("utf-8", errors="replace").strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


def find_subprojects(root: Path, max_depth: int = 2) -> list:
    """Folders below root that look like projects of their own (a manifest or their own .git)."""
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        d = Path(dirpath)
        depth = len(d.relative_to(root).parts)
        if d != root and (any(m in filenames for m in PROJECT_MARKERS) or ".git" in dirnames):
            found.append(d)
            dirnames[:] = []  # a project's own sub-folders are its business
            continue
        if depth >= max_depth:
            dirnames[:] = []
        dirnames[:] = [x for x in dirnames if x not in IGNORE_DIRS and not x.startswith(".")]
    return found


def find_secret_files(root: Path, max_depth: int = 3) -> list:
    """Real .env files on disk (not examples). Their contents are never read."""
    found = []
    pat = re.compile(r"^\.env(\.(?!example$|sample$|template$|dist$)[\w.-]+)?$", re.I)
    for dirpath, dirnames, filenames in os.walk(root):
        d = Path(dirpath)
        if len(d.relative_to(root).parts) >= max_depth:
            dirnames[:] = []
        dirnames[:] = [x for x in dirnames if x not in IGNORE_DIRS and not x.startswith(".")]
        found += [d / f for f in filenames if pat.match(f)]
    return found


def add_sample(d, key, where, limit=3):
    d.setdefault(key, [])
    if len(d[key]) < limit and where not in d[key]:
        d[key].append(where)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description="Survey a project folder for project-atlas (read-only).")
    ap.add_argument("root", type=Path)
    ap.add_argument("--out", type=Path, help="write the report here instead of printing it")
    ap.add_argument("--max-files", type=int, default=6000)
    args = ap.parse_args()
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        sys.exit(f"error: {root} is not a folder")

    files, skipped_dirs, used_git = list_files(root, args.max_files)
    lang_files, lang_lines = collections.Counter(), collections.Counter()
    dir_files, dir_lines = collections.Counter(), collections.Counter()
    sizes = []
    env, routes, cli, sched = {}, [], {}, {}
    services, storage, hosts = {}, {}, {}
    todos, err_files, retries, empty_catch = [], collections.Counter(), {}, []
    entries, n8n, docs, manifests, tests = [], [], [], [], set()
    env_examples, chat_cmds, deps = {}, {}, {}
    dir_data = collections.Counter()
    total_lines = 0

    env_res = [re.compile(p) for p in ENV_PATTERNS]
    route_res = [(re.compile(p), k) for p, k in ROUTE_PATTERNS]
    cli_res = [re.compile(p) for p in CLI_PATTERNS]
    sched_res = [re.compile(p) for p in SCHEDULE_PATTERNS]
    svc_res = {k: re.compile(v, re.I) for k, v in SERVICES.items()}
    sto_res = {k: re.compile(v) for k, v in STORAGE.items()}
    err_re = re.compile(r"^\s*(try\s*[:{]|except\b|catch\s*[({]|\.catch\(|rescue\b|recover\(\))", re.M)
    retry_re = re.compile(r"\b(retry|retries|backoff|tenacity|maxRetries|max_retries|retryOnFail|p-retry)\b", re.I)
    empty_re = re.compile(r"except[^:\n]*:\s*\n\s*pass\b|catch\s*(\([^)]*\))?\s*\{\s*\}")

    for p in files:
        r = rel(p, root)
        ext = p.suffix.lower()
        name = p.name
        top = r.split("/")[0] if "/" in r else "."
        parts = r.split("/")
        if any(x.lower() in {"test", "tests", "__tests__", "spec", "e2e"} for x in parts[:-1]) or re.search(r"(^test_|_test\.|\.test\.|\.spec\.)", name):
            tests.add(r)
        if (ext in {".md", ".mdx", ".rst", ".pdf", ".docx"} or name.upper() in DOC_NAMES
                or ext == ".txt" and (top in {".", "docs", "doc"} or name.lower().startswith("readme"))):
            docs.append(r)
        if name in LOCK_FILES:
            continue  # generated dependency lists: full of hosts and package names that say nothing about the project
        if name in ENTRY_NAMES:
            entries.append(r)
        if name in {"package.json", "pyproject.toml", "requirements.txt", "Pipfile", "setup.py", "go.mod",
                    "Cargo.toml", "composer.json", "Gemfile", "pom.xml", "build.gradle", "Dockerfile",
                    "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml", "Makefile",
                    "Procfile", "vercel.json", "netlify.toml", "wrangler.toml", "serverless.yml",
                    "app.json", "manifest.json", "deno.json", "bun.lockb", "fly.toml", "render.yaml"} \
                or name.startswith("requirements") and ext == ".txt" or (r.startswith(".github/workflows/")):
            manifests.append(r)
        if name.lower().endswith(("env.example", "env.sample", "env.template", "env.dist")):
            env_examples[r] = None
        if ext not in TEXT_EXT and name not in {"Dockerfile", "Makefile", "Procfile"}:
            continue
        text = read_text(p)
        if text is None:
            continue
        n_lines = text.count("\n") + 1
        total_lines += n_lines
        lang = LANG.get(ext, "Other text")
        lang_files[lang] += 1
        lang_lines[lang] += n_lines
        d = "/".join(parts[:2]) if len(parts) > 2 else (parts[0] if len(parts) > 1 else ".")
        if ext in DATA_EXT and name not in {"package.json", "tsconfig.json", "manifest.json", "app.json"}:
            dir_data[d] += 1  # data files are counted, not mistaken for code
        else:
            dir_files[d] += 1
            dir_lines[d] += n_lines
        if name == "package.json":
            try:
                pj = json.loads(text)
                for dep in list((pj.get("dependencies") or {})) + list((pj.get("devDependencies") or {})):
                    deps.setdefault(dep, r)
            except (json.JSONDecodeError, AttributeError):
                pass
        elif name.startswith("requirements") and ext == ".txt" or name == "pyproject.toml":
            for dep in re.findall(r"^\s*['\"]?([A-Za-z][\w.-]+)", text, re.M):
                deps.setdefault(dep.lower(), r)
        is_code = ext in CODE_EXT or name in {"Dockerfile", "Makefile", "Procfile"}
        if is_code and ext not in {".json", ".yml", ".yaml", ".toml", ".css", ".scss", ".html"}:
            sizes.append((n_lines, r))
        if r in env_examples:
            env_examples[r] = [m.group(1) for m in re.finditer(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", text, re.M)]

        # n8n workflow files
        if ext == ".json" and '"nodes"' in text and '"connections"' in text and "n8n-nodes" in text:
            try:
                wf = json.loads(text)
                nodes = wf.get("nodes", []) if isinstance(wf, dict) else []
                types = collections.Counter(str(n.get("type", "")).split(".")[-1] for n in nodes)
                triggers = [f"{n.get('name')} ({str(n.get('type', '')).split('.')[-1]})" for n in nodes
                            if re.search(r"trigger|webhook|cron|schedule", str(n.get("type", "")), re.I)]
                urls = sorted({str(n.get("parameters", {}).get("url", ""))[:90] for n in nodes
                               if n.get("parameters", {}).get("url")})
                creds = sorted({f"{ctype}" + (f" ({c.get('name')})" if isinstance(c, dict) and c.get("name") else "")
                                for n in nodes for ctype, c in (n.get("credentials") or {}).items()})
                retry_nodes = [f"{n.get('name')} (×{n.get('maxTries', 3)})" for n in nodes if n.get("retryOnFail")]
                on_error = sorted({str(n.get("onError")) for n in nodes if n.get("onError")})
                n8n.append({"file": r, "name": wf.get("name", ""), "nodes": len(nodes), "triggers": triggers,
                            "types": types.most_common(8), "urls": urls[:6], "creds": creds,
                            "retry": retry_nodes[:10], "on_error": on_error,
                            "error_wf": (wf.get("settings") or {}).get("errorWorkflow"),
                            "names": [str(n.get("name")) for n in nodes][:40]})
            except (json.JSONDecodeError, AttributeError):
                pass

        if not is_code and ext not in {".json", ".yml", ".yaml", ".toml", ".env", ".example"}:
            continue
        lines = text.splitlines()
        for i, line in enumerate(lines, 1):
            if len(line) > 600:
                continue
            for rx in env_res:
                for m in rx.finditer(line):
                    add_sample(env, m.group(1), f"{r}:{i}")
            if is_code:
                for rx, kind in route_res:
                    for m in rx.finditer(line):
                        g = m.groups()
                        method, path = (g[0].upper(), g[1]) if len(g) == 2 else ("ANY", g[0])
                        if kind == "django" and not path:
                            path = "/"
                        found = (method, path, f"{r}:{i}")
                        if len(routes) < 80 and found not in routes:
                            routes.append(found)
                            if r not in entries and not any(t in r for t in ("test", "mock")):
                                entries.append(r)
                for rx in cli_res:
                    for m in rx.finditer(line):
                        add_sample(cli, m.group(1), f"{r}:{i}", 2)
                if "sys.argv" in line or "process.argv" in line or "os.Args" in line:
                    add_sample(cli, "(raw argv)", f"{r}:{i}", 3)
                m = TODO_RE.search(line)
                if m and len(todos) < 60:
                    todos.append(f"{r}:{i}: {m.group(1)} {m.group(2).strip()}")
            for rx in sched_res:
                for m in rx.finditer(line):
                    add_sample(sched, m.group(1).strip()[:80], f"{r}:{i}", 2)
            for m in URL_RE.finditer(line) if is_code else ():
                h = m.group(1).lower()
                if not URL_SKIP.search(h) and not re.match(r"^\d+\.\d+\.\d+\.\d+$", h):
                    add_sample(hosts, h, f"{r}:{i}", 2)
        if is_code:
            low = text if len(text) < 400_000 else text[:400_000]
            # services and most storage are only trusted from import lines, URLs and package names, not from
            # comments, keyword lists or regexes that happen to contain the word
            imports = "\n".join(l for l in low.splitlines() if IMPORT_LINE.search(l))
            for k, rx in svc_res.items():
                if rx.search(imports):
                    add_sample(services, k, r, 4)
            for k, rx in sto_res.items():
                if rx.search(low if k in STORAGE_USAGE else imports):
                    add_sample(storage, k, r, 4)
            for pattern, label, needs in CHAT_COMMANDS:
                if needs and needs not in low:
                    continue
                for m in re.finditer(pattern, low):
                    add_sample(chat_cmds, f"{label}: {m.group(1)}", r, 2)
            if "parseArgs(" in low:
                for opt in re.findall(r"['\"]?([a-z][\w-]*)['\"]?\s*:\s*\{\s*type\s*:\s*['\"](?:string|boolean)['\"]", low):
                    add_sample(cli, f"--{opt}", r, 1)
            ec = len(err_re.findall(low))
            if ec:
                err_files[r] = ec
            if retry_re.search(low):
                add_sample(retries, "retry/backoff", r, 12)
            if re.search(r"\btimeout\b", low, re.I):
                add_sample(retries, "timeouts", r, 12)
            for m in empty_re.finditer(low):
                if len(empty_catch) < 25:
                    empty_catch.append(f"{r}:{low[:m.start()].count(chr(10)) + 1}")
            if ext == ".py" and "__name__" in low and "__main__" in low and r not in entries:
                entries.append(r)

    # dependencies are better evidence for outside services than words in code
    for dep, where in deps.items():
        for k, rx in svc_res.items():
            if rx.search(dep):
                add_sample(services, k, f"{where}: dependency {dep}", 4)
        for k, rx in sto_res.items():
            if k not in STORAGE_USAGE and rx.search(dep):
                add_sample(storage, k, f"{where}: dependency {dep}", 4)
    subprojects = find_subprojects(root)
    root_is_project = any((root / m).exists() for m in PROJECT_MARKERS) or (root / ".git").exists()
    secret_files = find_secret_files(root)
    prose = {"Markdown", "MDX", "JSON", "YAML", "XML", "Other text", "TOML", "INI"}
    code_lines = sum(n for lang, n in lang_lines.items() if lang not in prose)

    # ------------------------------------------------------------------ report
    out = []
    w = out.append
    w(f"# Project scan: {root.name}")
    w("")
    w(f"- Root: `{root}`")
    w(f"- Files listed: {len(files)}{' (limit reached)' if len(files) >= args.max_files else ''}"
      f" · text lines read: {total_lines:,}" + (" · file list from git (respects .gitignore)" if used_git else ""))
    if skipped_dirs:
        w("- Skipped folders (dependencies, builds, caches, hidden): " +
          ", ".join(f"`{d}`" for d, _ in skipped_dirs.most_common(15)))
    if code_lines < 100 and docs:
        w("- **Mostly documents, little or no code.** Map it from the documents: see the outline at the end.")
    w("")

    if len(subprojects) >= 2:
        kind = "parts of one project (it has its own manifest)" if root_is_project else "separate projects"
        w(f"## This folder holds {len(subprojects)} {kind}")
        for sp in subprojects[:15]:
            commits = git(sp, "rev-list", "--count", "HEAD") if (sp / ".git").exists() else ""
            markers = [m for m in PROJECT_MARKERS if (sp / m).exists()] + ([".git"] if (sp / ".git").exists() else [])
            w(f"- `{rel(sp, root)}` ({', '.join(markers)}{f', {commits} commits' if commits else ''})")
        if not root_is_project:
            w("- Ask which one to map, or map each into its own atlas. One atlas for unrelated projects tells no story.")
        w("")

    if secret_files:
        w("## Secret files on disk (contents not read)")
        for f in secret_files[:10]:
            tracked = git(root, "ls-files", "--error-unmatch", rel(f, root)) if used_git else ""
            w(f"- `{rel(f, root)}`" + (" **is tracked by git: the secrets are in the repository history**" if tracked else ""))
        w("")

    count = git(root, "rev-list", "--count", "HEAD")
    if count:
        w("## Git history")
        first = git(root, "log", "--reverse", "--format=%ad  %s", "--date=short").splitlines()[:12]
        recent = git(root, "log", "-n", "10", "--format=%ad  %s", "--date=short").splitlines()
        dirty = git(root, "status", "--porcelain").splitlines()
        w(f"- {count} commits · uncommitted changes: {len(dirty)}")
        w("- First commits (how it started):")
        out.extend(f"  - {c}" for c in first)
        w("- Latest commits:")
        out.extend(f"  - {c}" for c in recent)
        w("")

    w("## Languages (by lines)")
    for lang, n in lang_lines.most_common(12):
        w(f"- {lang}: {n:,} lines in {lang_files[lang]} files")
    w("")

    w("## Where the code is (folders, two levels deep; data files counted separately)")
    for d in sorted(set(dir_lines) | set(dir_data), key=lambda k: -dir_lines.get(k, 0))[:45]:
        data = f" + {dir_data[d]} data files" if dir_data.get(d) else ""
        w(f"- `{d}`: {dir_files.get(d, 0)} files, {dir_lines.get(d, 0):,} lines{data}")
    w("")

    if docs:
        ordered = sorted(docs, key=lambda d: (d.count("/"), d.lower()))
        w(f"## Docs to read ({len(docs)})")
        out.extend(f"- `{d}`" for d in ordered[:40])
        if len(ordered) > 40:
            w(f"- … and {len(ordered) - 40} more")
        w("")

    if manifests:
        w("## Manifests, run scripts and deploy files")
        for m in sorted(manifests)[:40]:
            p = root / m
            text = read_text(p) or ""
            info = ""
            if p.name == "package.json":
                try:
                    pj = json.loads(text)
                    dep_list = list((pj.get("dependencies") or {}).keys())
                    dev = list((pj.get("devDependencies") or {}).keys())
                    scripts = pj.get("scripts") or {}
                    info = (f" name={pj.get('name', '')!r}; scripts: " +
                            "; ".join(f"{k}=`{str(v)[:60]}`" for k, v in list(scripts.items())[:12]) +
                            f"; deps: {', '.join(dep_list[:30])}" + (f"; devDeps: {', '.join(dev[:15])}" if dev else ""))
                except json.JSONDecodeError:
                    info = " (unreadable JSON)"
            elif p.name.startswith("requirements"):
                pk = [re.split(r"[<>=!~\[;\s]", l.strip())[0] for l in text.splitlines()
                      if l.strip() and not l.strip().startswith(("#", "-"))]
                info = " packages: " + ", ".join(pk[:40])
            elif p.name == "pyproject.toml":
                dep_list = re.findall(r"^\s*['\"]([A-Za-z0-9_.-]+)", text.split("dependencies", 1)[-1][:1500], re.M)
                scripts = re.findall(r"^\s*([\w-]+)\s*=\s*['\"][\w.]+:[\w]+['\"]", text, re.M)
                info = (f" deps: {', '.join(dep_list[:30])}" if dep_list else "") + (f"; scripts: {', '.join(scripts)}" if scripts else "")
            elif p.name == "Dockerfile":
                keep = [l.strip() for l in text.splitlines() if re.match(r"\s*(FROM|CMD|ENTRYPOINT|EXPOSE)\b", l)]
                info = " " + " | ".join(keep[:6])
            elif "compose" in p.name:
                sv = re.findall(r"^  ([A-Za-z0-9_.-]+):\s*$", text.split("services:", 1)[-1], re.M)
                info = " services: " + ", ".join(sv[:15])
            elif m.startswith(".github/workflows/"):
                nm = re.search(r"^name:\s*(.+)$", text, re.M)
                on = re.search(r"^on:\s*(.*)$", text, re.M)
                info = f" {nm.group(1).strip() if nm else ''}; on: {on.group(1).strip() if on else 'see file'}"
            elif p.name == "Makefile":
                info = " targets: " + ", ".join(re.findall(r"^([A-Za-z0-9_-]+):", text, re.M)[:15])
            w(f"- `{m}`{info[:400]}")
        w("")

    if entries:
        w("## Likely entry points")
        out.extend(f"- `{e}`" for e in sorted(set(entries))[:30])
        w("")

    if n8n:
        w("## Automation workflows (n8n)")
        for wf in n8n:
            w(f"- `{wf['file']}`: **{wf['name']}**, {wf['nodes']} nodes")
            if wf["triggers"]:
                w(f"  - starts with: {', '.join(wf['triggers'])}")
            w(f"  - node types: {', '.join(f'{t}×{c}' for t, c in wf['types'])}")
            if wf["urls"]:
                w(f"  - HTTP calls: {', '.join(wf['urls'])}")
            if wf["creds"]:
                w(f"  - credentials used: {', '.join(wf['creds'])}")
            if wf["retry"] or wf["on_error"] or wf["error_wf"]:
                bits = ([f"retry on fail: {', '.join(wf['retry'])}"] if wf["retry"] else []) + \
                       ([f"onError: {', '.join(wf['on_error'])}"] if wf["on_error"] else []) + \
                       ([f"error workflow: {wf['error_wf']}"] if wf["error_wf"] else [])
                w(f"  - error handling: {'; '.join(bits)}")
            w(f"  - nodes: {', '.join(wf['names'])}")
        w("")

    doc_only = code_lines < 100 and bool(docs)
    code_sections_start = len(out)  # everything from here to the outline is about code: dropped for documents
    w("## Inputs: where things come in")
    if env:
        w(f"- Environment variables / secrets ({len(env)}):")
        for k in sorted(env)[:80]:
            w(f"  - `{k}` ({', '.join(env[k])})")
    for f, keys in env_examples.items():
        if keys:
            w(f"- `{f}` lists: {', '.join(keys[:40])}")
    if routes:
        w(f"- HTTP routes ({len(routes)}{'+' if len(routes) >= 80 else ''}):")
        for method, path, where in routes[:60]:
            w(f"  - {method} `{path}` ({where})")
    if cli:
        w("- Command-line options: " + "; ".join(f"`{k}` ({', '.join(v)})" for k, v in list(cli.items())[:30]))
    if chat_cmds:
        w("- Chat and bot commands: " + "; ".join(f"`{k}` ({', '.join(v)})" for k, v in list(chat_cmds.items())[:30]))
    if sched:
        w("- Schedules / timers:")
        for k, v in list(sched.items())[:20]:
            w(f"  - `{k}` ({', '.join(v)})")
    n8n_triggers = [f"{t} in {wf['name'] or wf['file']}" for wf in n8n for t in wf["triggers"]]
    if n8n_triggers:
        w("- Automation triggers (n8n): " + "; ".join(n8n_triggers[:20]))
    n8n_creds = sorted({c for wf in n8n for c in wf["creds"]})
    if n8n_creds:
        w("- Credentials the workflows use (settings and secrets): " + ", ".join(n8n_creds))
    if not (env or routes or cli or sched or env_examples or chat_cmds or n8n_triggers):
        w("- No obvious inputs found by pattern. Read the entry points.")
    w("")

    w("## Outside services and storage (keyword hits, verify by reading)")
    if services:
        w("- Services:")
        for k, v in services.items():
            w(f"  - {k}: {', '.join(f'`{x}`' for x in v)}")
    if hosts:
        w("- Web addresses in code (calls or just links: check which): " +
          ", ".join(f"`{h}`" for h in sorted(hosts, key=lambda h: -len(hosts[h]))[:30]))
    if storage:
        w("- Storage:")
        for k, v in storage.items():
            w(f"  - {k}: {', '.join(f'`{x}`' for x in v)}")
    w("")

    w("## Error handling (evidence for the what-if answers)")
    if err_files:
        w("- Files with the most try/catch: " + ", ".join(f"`{f}` ({n})" for f, n in err_files.most_common(15)))
    else:
        w("- No try/catch blocks found.")
    for k, v in retries.items():
        w(f"- {k}: " + ", ".join(f"`{x}`" for x in v))
    if empty_catch:
        w("- Empty catch / `except: pass` (errors silently swallowed): " + ", ".join(f"`{x}`" for x in empty_catch))
    w("")

    w("## Loose ends")
    if todos:
        w(f"- TODO/FIXME/HACK ({len(todos)}{'+' if len(todos) >= 60 else ''}):")
        out.extend(f"  - {t}" for t in todos[:40])
    else:
        w("- No TODO/FIXME markers.")
    if sizes:
        w("- Largest code files: " + ", ".join(f"`{r}` ({n:,})" for n, r in sorted(sizes, reverse=True)[:12]))
    w(f"- Test files: {len(tests)}" + (" (e.g. " + ", ".join(f"`{t}`" for t in sorted(tests)[:6]) + ")" if tests else ""))
    w("")

    if doc_only:
        del out[code_sections_start:]
        # a project made of documents: the useful survey is what the documents say, section by section
        w("## Document outline")
        for d in sorted(docs, key=lambda d: (d.count("/"), d.lower()))[:25]:
            text = read_text(root / d) if Path(d).suffix.lower() in {".md", ".mdx", ".rst", ".txt"} else None
            if text is None:
                w(f"- `{d}` (not plain text: open it to read)")
                continue
            heads = [l.strip() for l in text.splitlines() if re.match(r"^#{1,3}\s", l)]
            w(f"- `{d}`: {len(text.split()):,} words, {len(heads)} headings")
            out.extend(f"  {'  ' * (h.count('#', 0, 3) - 1)}- {h.lstrip('#').strip()[:100]}" for h in heads[:30])
            if len(heads) > 30:
                w(f"    - … {len(heads) - 30} more headings")
        w("")
    w("_This scan only points at places to read. Confirm everything in the code before it goes into the atlas._")

    report = "\n".join(out) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
        print(f"scan written to {args.out} ({len(report.splitlines())} lines)")
    else:
        sys.stdout.write(report)


if __name__ == "__main__":
    main()
