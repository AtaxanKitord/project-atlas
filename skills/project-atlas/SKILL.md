---
name: project-atlas
description: Map a project into an Obsidian atlas — a one-page Big Picture canvas of its stages, a canvas per stage, flows, a what-if board of failure cases with evidence from the code, plan vs reality, a log of how the project drifts over time, and linked notes for the graph view. Load this skill first, before exploring any files, whenever someone wants to understand, explain, map, diagram or document a whole project, repo, app, bot or automation (n8n, scripts, workflows) — "what did we actually build?", "explain this project end to end", "map or diagram this repo or my workflows", handing a codebase over to someone, comparing the original idea with what the project became (scope creep), wrapping up after vibe coding, recording a plan before building, refreshing an atlas, or a visual overview to share with a client, even if they never say Obsidian or atlas. Not for a single diagram, a README, a code review or an Obsidian how-to question.
argument-hint: "[plan | refresh | share | check]"
---

# Project Atlas

What someone has in mind at the start of a project and what ends up in the folder are rarely the same. Features get added along the way, helper scripts appear, settings and secrets pile up, error paths are half-done, and nobody writes any of it down. This is especially true after vibe coding, where an AI wrote most of the code and the owner may never have read it.

This skill reads the project as it really is and draws it as an **atlas** inside Obsidian, so the owner can *see* their project:

| Piece | Answers |
|---|---|
| **Home note** (named after the project) | What is this, in plain words? It opens with the project's story as a diagram. |
| **1 Big Picture** canvas | The whole project on one page, left to right: where it starts, the 3–6 stages it goes through, what comes out, what it relies on. |
| **Stages/** canvases | One zoom-in per stage: its parts, where things come from and go to. Opened from the stage titles. |
| **2 Flows** canvas | What happens, step by step, when someone uses it? |
| **3 What If** canvas | A board from "not handled" to "handled": a service is down, input is bad, a key is missing…? |
| **4 Plan vs Reality** canvas + note | Did I build what I meant to? A checklist against the recorded plan, plus what got added, what is unfinished, left over or risky. |
| **0 Plan** note | The plan, recorded at the start of the project (optional, see below). |
| **Changes** note | What changed each time the atlas was refreshed: the drift, over time. |
| **One note per item**, all linked | Each note shows that item's own connections in a small diagram; Obsidian's graph view shows them all. |

**The canvases exist to make the project feel simpler, not to show everything at once.** A canvas full of cards and crossing arrows makes a project feel more confusing than it is, which defeats the point. So each canvas shows only a few large ideas with very few arrows, and every name on it is a link to where the detail lives: Big Picture → stage → note. Keep this in mind for every choice of names, stages and wording.

You do the understanding; the bundled scripts do the mechanical parts, so the output is valid and consistent every time:

| Script | Does |
|---|---|
| `scripts/find_vaults.py` | Lists the Obsidian vaults on this computer and any atlases already in them. |
| `scripts/scan_project.py` | Surveys a project folder and points at what to read. |
| `scripts/save_plan.py` | Records the plan (`plan.json` + "0 Plan" note) at the start of a project. |
| `scripts/render_atlas.py` | Turns your `atlas.json` into notes and canvases, keeps a history snapshot and writes the Changes note. |
| `scripts/export_atlas.py` | `--check`: renders the canvases as images and reports layout problems. Default: one shareable HTML file (+ PNGs). |

Your real output is one file, `atlas.json`. Its format is in `references/atlas-format.md`; read that before writing it. The scripts need only Python 3.8+ (`python` or `python3`, whichever exists); images need Chrome, Edge or Chromium.

## What does the user want?

| They say (or pass as argument) | Do |
|---|---|
| map it / explain it / what did we build (default) | The full workflow below. If an atlas already exists, it is a refresh. |
| `plan` / "I'm starting…", "record my plan" | [Record the plan](#recording-the-plan). |
| `refresh` / "update the atlas" | The workflow below on the existing atlas, then tell them what changed (the newest entry of the Changes note). |
| `share` / "send this to my client" | [Share it](#sharing). |
| `check` | Run step 5's check on the existing atlas and fix what it finds. |

## Workflow

### 1. Decide what to map and where to put it

**What.** Default to the project in the current working directory. If the user names a folder, a repo or one part of a project, map that. If the "project" lives in the conversation (a plan, a workflow, a business process) rather than in code, map it from the conversation and any documents, and skip the scanner. If the folder holds several separate projects (the scan says so when sub-folders have their own manifest or `.git`), ask which one to map, or map each into its own atlas: one atlas for unrelated projects tells no story. A folder of documents (a strategy, a plan, a process) is a project too; see [Projects made of documents](#projects-made-of-documents).

**Where.** Run `python scripts/find_vaults.py --text`.
- A vault already holds this project's atlas or a plan for it → use that folder.
- A vault already holds other atlases → put this one next to them (same parent folder).
- Exactly one vault → propose `<vault>/Project Atlas/<Project name>/`. If the vault itself is only for atlases (it is called something like "Project Atlas"), use `<vault>/<Project name>/` instead of doubling the name.
- Several vaults → ask which one.
- No vault → ask where to write, and suggest a new folder that they can later open in Obsidian with *Open folder as vault*.

Don't write the atlas into the project's own repository unless the user asks: it is a view of the project for its owner, not part of the codebase.

**Existing atlas.** If the target folder already has an `atlas.json`, this is a refresh: load it, update what changed, and keep the `id`s of things that still exist so links, history and the user's own notes stay attached.

If you need to ask anything here (where to write) or in step 3 (the original intent), ask it all in one short message so the user is interrupted once.

### 2. Survey

```bash
python scripts/scan_project.py <project-folder> --out <temp-dir>/scan.md
```

Write the scan to a temporary or scratch location, never into the project. Read it: folders and sizes, stack and run scripts, entry points, environment variables, HTTP routes, CLI options, schedules, automation workflows (n8n), outside services, storage, error handling, TODOs, and how the git history began. It is built from keyword matches, so it has false positives and misses things. Treat it as a list of places to look, and confirm everything by reading the code.

### 3. Read for understanding

Read enough to explain every part honestly, roughly in this order:

1. README and docs: the claimed purpose. Docs drift too, so check them against the code.
2. Entry points: where execution starts.
3. Every place input enters: routes, bot and webhook handlers, CLI options, uploads, schedules, environment variables, config files.
4. The core logic and data models; where data is stored and read back.
5. Calls to outside services and how each failure is handled: try/catch, retries, timeouts, validation, fallbacks. This is the evidence for the What If canvas.
6. Outputs: what gets written, sent, shown or charged.

For a big project (hundreds of files), map modules and features, not files. Breadth beats depth: the owner should find *every* part of their project on the map, even if each gets only two sentences.

**Find the original intent.** Plan vs Reality is often the reason people run this skill. If the atlas folder has a `plan.json`, that recorded plan is the intent: check every must-have (and nice-to-have) against the project in `reality.plan_check`, and list anything built that the plan put out of scope under `added`. Without a recorded plan, in order of trust: what the user tells you now; the first messages of this conversation, if the project was built here; the README, the first commits and early docs. If none of these is clear, ask one question: "In a sentence or two, what did you originally set out to build?" If they'd rather skip it, infer the intent and say so in `intent_source` (for example `"inferred from the README and first commits"`).

**Stay factual.** Everything in the atlas must trace back to the code, the docs or the user's own words. The owner will trust this map, so a confident wrong statement does more harm than a gap. When you could not verify something, say so ("unknown: check what `send()` does on a timeout") instead of guessing.

### 4. Write atlas.json

Read `references/atlas-format.md`, then write `atlas.json` to a temporary location. The essentials:

- **Nodes** are the things on the map. Each has one kind: `actor` (people and roles), `input`, `config` (settings and secrets), `component` (the parts that do the work), `store`, `external` (outside services) or `output`.
- **Name things in plain words** that a non-programmer understands ("Photo editor", "Order queue", "Customer") and put the file paths in `files`. The owner may not know their own code; the atlas is where they learn it.
- **Aim for 8–30 nodes.** Fewer and the map says nothing; more and nobody can read it. Merge small helpers into the part they serve, and split a part only when its halves do different jobs. Group environment variables into a few `config` nodes ("API keys", "Model settings") and list the variable names in `details`.
- **Stages** are the backbone of the Big Picture: 3–6 main stages that tell the project as a short story in the order things happen ("Take the order" → "Edit the photos" → "Send it back"), each holding one to five parts. Name them with verbs, not technologies, and say in `passes` what each stage hands to the next. Things that run on their own (housekeeping, admin or developer tools) go in `background` stages. If someone could read only the stage names and still explain the project to a friend, the stages are right.
- **Links** say who hands what to whom. The `label` is the thing handed over ("photos", "order JSON", "reply text"). Keep them sparse (about 1.5 per node), and link an outside service only where the project's own code calls it: a chat app or webhook provider that merely delivers the input is not a hop between the input and the part that handles it.
- **Flows**: the 2–6 journeys that matter most, the main happy path first, as ordered steps.
- **Scenarios** ("what if"): 6–15 realistic ones, each grounded in the code. Use the checklist below.
- **Reality**: the intent, a short verdict, the `plan_check` (when a plan was recorded), and the lists `as_planned`, `added`, `unfinished`, `missing`, `unused`, `risks`, `questions`. Also set `status` on nodes (`extra`, `unfinished`, `unused`, `risky`) so the badges show on the map.
- **Language**: write the atlas in the language the person is talking to you in, not the language of the project's code or documents (unless they ask for another). For a non-English atlas, also fill `labels` so headings, card titles and folder names match (the keys are in the reference).

#### What-if checklist

Walk through these and keep the ones that apply to this project:

- Each important outside service is down, slow, rate-limited, or returns something unexpected.
- The input is empty, huge, malformed, in an unexpected format or language, duplicated, or hostile.
- A setting or secret is missing, wrong or expired.
- Two things happen at once: a double click, two users, a webhook delivered twice, a job that overlaps the next run.
- The process restarts or crashes halfway: is work lost, repeated or resumed?
- Data grows for a year: disk, database, logs, cost.
- Something costs money per call: can a loop or a retry storm run up a bill?
- A user does something the builder did not plan for.

For each scenario, find what the code actually does and set `handled` to `yes`, `partly`, `no` or `unknown`. A `yes` needs `evidence` that points at the code or config that handles it. When it is not fully handled, `fix` gives a concrete, small suggestion.

### 5. Render, then look at it

```bash
python scripts/render_atlas.py <temp-dir>/atlas.json --out "<vault>/Project Atlas/<Project name>"
```

- `--vault <path>`: the vault root. Needed when `--out` is not inside a folder that already has `.obsidian` (for example a brand-new vault). Links are written as paths from the vault root, so this must be right.
- `--setup-graph`: adds colour groups for the atlas tags to the vault's graph view (people, inputs, parts, storage… each in its own colour). It edits `.obsidian/graph.json`, so offer it once per vault rather than doing it silently. It is a sensible default for a new vault made for atlases.
- `--dry-run`: validate only. `--no-registry`: don't record where this atlas lives (the plugin's refresh reminder uses that record).

The script validates the atlas first. Fix every error it reports and run it again. Read the warnings too: a node with no links, or a scenario marked handled without evidence, usually means something is missing from your understanding, not just from the file.

**Then look at what you made**, the way the user will see it:

```bash
python scripts/export_atlas.py "<atlas folder>" --check --out <temp-dir>/check
```

It renders every canvas as a PNG (with Obsidian's font size) and lists cards whose text does not fit, cards that overlap and arrows that pass behind a card. Fix every listed problem: shorten the text, split the card's content, or rethink the links that make an arrow cross. Renders less than an hour apart count as one version, so this polishing does not show up as changes in the project's history (`--history-window` sets the gap). Then open the Big Picture image and one stage image and ask yourself: could someone who has never seen this project explain it after ten seconds with the Big Picture? Are the stage names plain and in the right order? Is any card a wall of text? If not, rename, regroup or shorten, render again and look again. If no browser is installed, the check says so; then read the Big Picture canvas's card texts instead.

### 6. Hand it over

Tell the user where the atlas is and how to open it. The render prints an `obsidian://` link to the home note; it works when the vault is registered in Obsidian (for a new folder they first use *Open folder as vault*). Then give a short tour in chat, about a dozen lines at most, because the atlas holds the details:

- what the project is, in one sentence;
- the two or three most surprising things in Plan vs Reality (and the plan checklist score, if there is a plan);
- the what-ifs that are not handled and matter most;
- the questions you have for them.

If no plan was recorded, mention once that next time they can record the plan at the start (`plan`), so the atlas can check the result against it.

## Projects made of documents

A strategy, a plan or a process written down in documents maps well too. The scan gives an outline of the documents instead of code sections. Then:

- **Kinds**: people and roles → `actor`; channels and incoming requests → `input`; activities and workstreams → `component`; logs, lists, spreadsheets, CRMs → `store`; platforms and tools → `external`; deliverables and results → `output`; rules, prices and assumptions → `config` (rename that group with `labels`: `group.config`, `folder.config` and `kind.config`, for example "Rules and assumptions").
- **Evidence** points at a document and its section ("`90-day-strategy.md`, Weekly rhythm"), and the what-ifs fit the domain: a channel stops working, a key person is away, results come slower than planned, costs rise, two documents disagree.
- **Plan vs Reality needs a reality.** Documents describe intentions, so ask the owner what has actually been done so far. If nothing has happened yet, the documents are the plan: offer to record them with `save_plan.py`, so a later atlas can check progress against them. Contradictions between documents go in `risks` or `questions`.

## Recording the plan

At the start of a project (or as early as possible), record what the owner sets out to build, so Plan vs Reality later compares against their real plan instead of a guess. Keep it to two minutes for them:

1. Draft the plan from what they have said, in their words: `goal` (one to three sentences), `for_whom`, `must_have`, `nice_to_have`, `out_of_scope`, `stages` (the story they expect, 3–6 steps), `done_when`. The format is at the top of `scripts/save_plan.py`.
2. Show the draft in a few lines and ask them to correct it. Out of scope is worth a question: it is what most often creeps in later.
3. Decide where the atlas will live (step 1 above) and save:

```bash
python scripts/save_plan.py <temp-dir>/plan.json --out "<vault>/Project Atlas/<Project name>"
```

Saving again keeps the earlier version in `history/`, so the plan can change honestly. Tell them that when the project is done (or any time) they can ask to map it, and the atlas will check every must-have against what was built.

## Refreshing an atlas

Running the renderer again on the same folder rewrites the generated notes and canvases:

- Every time the atlas content changes, a snapshot goes to `history/` and the **Changes** note lists what changed since the previous one: parts added, removed, renamed or moved between stages, what-ifs that got better or worse, plan items built, new risks. Tell the user the newest entry.
- Anything the user wrote under **My notes** at the bottom of a note is kept.
- Notes for things that no longer exist are deleted, unless the user wrote in them.
- Cards the user moved by hand on a canvas go back to the computed layout; mention this if they say they rearranged a canvas.
- Files in the folder that the skill did not create are never overwritten.

## Sharing

To show the atlas to someone without Obsidian (a client, a teammate, a README):

```bash
python scripts/export_atlas.py "<atlas folder>" --out "<folder the user chooses>" --png
```

It writes one self-contained HTML file (every canvas with zoom and tabs; every note opens in a side panel) and, with `--png`, an image of each canvas. "My notes" sections and the project's local folder path are left out unless `--include-my-notes` or `--include-paths` is passed: they may be private, so ask before including them. Diagrams inside notes need an internet connection to draw in the HTML file; everything else works offline.
