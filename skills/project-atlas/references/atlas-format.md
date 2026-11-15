# atlas.json format

`render_atlas.py` reads one JSON file that describes the project. This page lists every field, what it is for, and how to write it well. A complete small example is at the end.

Contents: [Top level](#top-level) · [project](#project) · [nodes](#nodes) · [links](#links) · [stages](#stages) · [flows](#flows) · [scenarios](#scenarios) · [reality](#reality) · [glossary](#glossary) · [labels](#labels) · [Example](#example)

General rules:

- Text fields accept Markdown (bold, lists, `code`). Don't write `[[wikilinks]]` yourself: the renderer creates every link from the ids, with the right vault paths.
- Write for the project's owner, who may not be a programmer and may never have read the code. Short sentences, plain words, jargon explained once (or put in the glossary).
- Ids are short kebab-case strings (`photo-editor`). Keep them stable when you refresh an atlas, so links and the owner's notes stay attached.

## Top level

```json
{
  "atlas_version": 1,
  "project":   { },
  "nodes":     [ ],
  "links":     [ ],
  "stages":    [ ],
  "flows":     [ ],
  "scenarios": [ ],
  "reality":   { },
  "glossary":  [ ],
  "labels":    { }
}
```

Only `project` and `nodes` are required, but an atlas without stages, links, flows, scenarios and reality is thin; the renderer warns about each missing part.

## project

| Field | Required | What to write |
|---|---|---|
| `name` | yes | The project's name as the owner calls it. Becomes the folder and home note name. |
| `one_liner` | yes | One sentence: what it does and for whom. |
| `summary` | yes | One to three short paragraphs: what it is, how it works at a high level, its current state. |
| `intent` | | What it was meant to be at the start. (Can live in `reality.intent` instead.) |
| `intent_source` | | Where the intent came from: `"the user"`, `"first message of this conversation"`, `"README"`, `"first commits"`, `"inferred from …"`. |
| `audience` | | Who uses it. |
| `stack` | | List of languages, frameworks, platforms and main services. |
| `how_to_run` | | Markdown: how to start it, taken from the README or manifests and checked. |
| `source` | | Path or URL of the project. |

## nodes

Each node is one thing on the map, and gets its own note.

| Field | Required | What to write |
|---|---|---|
| `id` | yes | Unique kebab-case id. |
| `kind` | yes | One of the kinds below. |
| `name` | yes | Plain-language name, one to four words: "Photo editor", not `img_proc_v2.py`. |
| `summary` | yes | One sentence: what it does. |
| `details` | | Markdown: how it works, rules it enforces, quirks, and for `config` nodes the variable names and what each controls. |
| `files` | | List of paths, optionally `path:line` or `path#function`; for documents, `file.md#Section heading`. |
| `status` | | `core` (default), `extra`, `unfinished`, `unused` or `risky`. |
| `tags` | | Extra Obsidian tags. |

### Kinds

| Kind | Means | Examples | On the Big Picture |
|---|---|---|---|
| `actor` | A person or role who uses or runs it | Customer, Admin, Shop owner | "Starts here" card |
| `input` | A way things come in | Telegram messages, `POST /orders`, CSV upload, nightly schedule, CLI command | "Starts here" card |
| `config` | Settings and secrets it needs | API keys, model settings, `.env`, feature flags | "What it relies on" row |
| `component` | A part that does the work | Order parser, Image editor, Worker loop, Admin page | Listed on its stage's card |
| `store` | Where data is kept | Postgres, a jobs folder, browser localStorage, a Google Sheet | "Uses" line of the stages that touch it, and "What it relies on" |
| `external` | An outside service it relies on | OpenAI API, Stripe, Telegram Bot API, an SMTP server | Same as `store` |
| `output` | What comes out | ZIP sent to the customer, daily email, web page, invoice PDF | "Comes out" card |

A service that is both the way in and the way out (a chat platform, say) can be one `external` node, or an `input` node plus an `output` node when that makes the journey easier to follow.

### Status

| Status | Means | Badge on the map |
|---|---|---|
| `core` | Part of the plan and working. | none |
| `extra` | Grew in along the way, beyond the original idea. Not bad, just not planned. | ➕ added along the way |
| `unfinished` | Started but incomplete: TODOs, stubs, disabled paths. | 🚧 unfinished |
| `unused` | Present but nothing uses it: dead code, leftover files, unused settings. | 💤 unused |
| `risky` | Works, but fragile or dangerous: no validation, secrets in code, no backups. | ⚠️ risky |

## links

```json
{ "from": "intake", "to": "job-store", "label": "new job record" }
```

- Direction follows the data or the call: Customer → Telegram messages → Intake → Job store.
- For a request and its response, one link in the direction of the request is enough, unless the response is the point.
- A link means "hands something to" or "calls". Don't connect everything to everything; the map gets unreadable fast. About 1.5 links per node is plenty; leave secondary relations to the node's `details`.
- **Platforms that only carry messages are not hops.** When input arrives through a platform (a chat app, a payment provider's webhook, email), link the `input` node straight to the part that handles it. Link the `external` node only where the project's own code calls it (to download a file, send a reply, charge a card). Routing every message through the platform node clutters the notes and the graph view and says nothing new.
- Link a `config` node to the parts that read it.
- `label` is optional but makes the notes much easier to read. Keep it to a few words.

Links are not drawn on the Big Picture; that canvas only shows the stages. They power each node's note ("Gets from", "Sends to" and a small diagram of just its neighbours), the "Uses" line on each stage card, and Obsidian's graph view.

## stages

Stages are the backbone of the **Big Picture** canvas: the project told as a short story, read left to right, from "Starts here" to "Comes out". A person can hold about five chunks in mind at once, so this is where the project gets simple enough to grasp in ten seconds. Everything else (every link, every file) is one click away in the notes.

```json
{ "id": "edit", "name": "Edit the photos", "summary": "OpenAI puts each photo on a white background; the helper squares it.",
  "nodes": ["image-wf", "image-finish"], "passes": "white, square photos" }
```

| Field | Required | What to write |
|---|---|---|
| `id` | | Unique kebab-case id. |
| `name` | yes | What happens in this stage, as a short verb phrase: "Take the order", "Edit the photos", "Send it back". Not a technology name. |
| `summary` | | One or two sentences in plain words. |
| `nodes` | | The parts (`component` nodes only) that do this stage's work. Each part belongs to one stage. |
| `passes` | | What this stage hands to the next one, in two to five words; shown as the last line of the stage card. |
| `lane` | | `main` (default) for the story, or `background` for things that run on their own: housekeeping jobs, admin tools, developer tools. |
| `uses` | | Extra stores or outside services to list on the card. Usually not needed: the renderer finds them from the links. |

- Write **3 to 6 main stages** in the order things happen for the user. Fewer and the map says nothing; more and it stops being a picture.
- Every part should be in a stage. Parts left out are collected under "Other parts" with a warning.
- People, inputs, outputs, storage, outside services and settings are placed automatically; don't put them in stages.
- Without any stages the renderer falls back to numbered "Step n" stages worked out from the links. That works, but named stages tell the story much better.

## flows

```json
{
  "id": "order-to-delivery",
  "name": "From photos to finished ZIP",
  "trigger": "A customer sends /new, then photos, then /done",
  "summary": "The main journey: …",
  "steps": [
    { "node": "customer", "action": "sends product photos", "to": "telegram-in", "data": "photos" },
    { "node": "intake", "action": "checks each photo and saves it to the job" }
  ],
  "result": "The customer receives one ZIP with edited photos and product texts"
}
```

- `node`: who acts in this step. `action`: what it does, short and in the present tense. `to` (optional): who it hands over to. `data` (optional): what it hands over; shown on the step's card.
- Three to twelve steps per flow. Put the main happy path first, then the next most important journeys (admin tasks, scheduled jobs, error recovery).

## scenarios

```json
{
  "id": "openai-down",
  "question": "What if the OpenAI API is down?",
  "category": "outside service",
  "trigger_node": "openai",
  "affects": ["image-editor", "worker"],
  "flows": ["order-to-delivery"],
  "what_happens": "The image editor retries 3 times, 20 s apart. After that the photo is marked failed and the job continues without it.",
  "user_sees": "The ZIP arrives with fewer photos; report.txt lists the failed ones.",
  "handled": "partly",
  "evidence": "`workflows/03-image-edit.json`, node \"Edit image\" (retryOnFail, maxTries 3)",
  "fix": "Tell the customer in the Telegram reply which photos failed, not only in report.txt.",
  "severity": "high"
}
```

| Field | What to write |
|---|---|
| `question` | Start with "What if" (or its equivalent in the atlas's language). It becomes the note's title. |
| `category` | A few words: outside service, bad input, settings, timing, crash, growth, cost, user behaviour. |
| `trigger_node` | The node where the problem starts. |
| `affects` | The nodes the problem travels through. |
| `flows` | Ids of the flows it can break. |
| `what_happens` | The chain of consequences as the code behaves today. Be specific: numbers, timings, what is retried, what is lost. |
| `user_sees` | What the end user or owner notices. "Nothing; it fails silently" is an important finding. |
| `handled` | `yes`, `partly`, `no` or `unknown`. |
| `evidence` | Where you saw the handling (or its absence): file, function, workflow node, config value. Required for `yes`. |
| `fix` | A concrete, small fix when it is not fully handled. |
| `severity` | `high`, `medium` or `low`: the impact on users, money or data. |

## reality

```json
{
  "intent": "A Telegram bot that turns phone photos of products into shop-ready images.",
  "intent_source": "first message of this conversation",
  "verdict": "The core idea works end to end, and the project grew a lot around it: …",
  "plan_check": [
    { "item": "White-background photos", "status": "built", "nodes": ["image-editor"] },
    { "item": "Prices in the product sheet", "status": "missing", "note": "No price field anywhere." }
  ],
  "as_planned": [ { "title": "White-background photos", "text": "…", "nodes": ["image-editor"] } ],
  "added":      [ { "title": "Persian product texts", "text": "…", "nodes": ["content-writer"] } ],
  "unfinished": [ ],
  "missing":    [ ],
  "unused":     [ ],
  "risks":      [ ],
  "questions":  [ "Should failed photos be retried later automatically?" ]
}
```

Each list item is `{ "title", "text", "nodes", "files" }` (only `title` is required) or just a string.

| Field | What to write |
|---|---|
| `intent` | What the owner set out to build, in their terms. Leave it out when a plan was recorded: the recorded plan's goal is used. |
| `intent_source` | Where that came from (see `project.intent_source`). |
| `verdict` | Two to four sentences: how close the result is to the plan, and the single most important thing to know. |
| `plan_check` | Only when a plan was recorded (`plan.json` in the atlas folder): one entry per must-have and nice-to-have, with `item` (the plan's wording), `status` (`built`, `partly`, `missing`, `changed` = built differently, or `dropped` = deliberately left out), an optional `note` and `nodes`. It is shown first on Plan vs Reality, with a score such as "5 of 7 built". |
| `as_planned` | Parts of the plan that exist and work. |
| `added` | What grew in that wasn't in the plan (including anything the recorded plan put out of scope). Keep the tone neutral: many additions are good; the point is that the owner knows they exist and what they cost to keep. |
| `unfinished` | Started but not done. |
| `missing` | Planned but not there at all. |
| `unused` | Leftovers: safe to delete, or worth reviving. |
| `risks` | Things that could hurt: security, data loss, cost, single points of failure. |
| `questions` | Decisions only the owner can make, or facts you could not find. |

## glossary

```json
[ { "term": "Lease", "meaning": "A time-limited lock a worker takes on a job so two workers never process it at once." } ]
```

Project jargon the owner will meet in the notes. Optional; when present it gets its own note.

## labels

All fixed text (headings, folder names, card titles, canvas names) is English by default. For an atlas in another language, override the keys you need. Unlisted keys stay English, so translate at least the folders, canvases, group titles and headings.

| Group | Keys |
|---|---|
| Folders | `folder.actor`, `folder.input`, `folder.config`, `folder.component`, `folder.store`, `folder.external`, `folder.output`, `folder.flow`, `folder.scenario`, `folder.stage` |
| Kind badges | `kind.actor` … `kind.output`, `kind.flow`, `kind.scenario` |
| Big Picture | `card.start`, `card.out`, `card.parts`, `card.uses`, `card.used_by`, `card.passes`, `card.from_stage` (keeps `{n}`), `card.in`, `card.out_short`, `group.background`, `group.relies`, `group.store`, `group.external`, `group.config`, `stage.other`, `stage.auto` (keeps `{n}`), `legend.read` |
| Stage canvases | `card.stage_parts`, `card.comes_from`, `card.goes_to`, `card.prev`, `card.next` |
| Status badges | `status.extra`, `status.unfinished`, `status.unused`, `status.risky` |
| Handled / severity | `handled.yes`, `handled.partly`, `handled.no`, `handled.unknown`, `severity.high`, `severity.medium`, `severity.low` |
| File names | `canvas.system`, `canvas.flows`, `canvas.whatif`, `canvas.reality`, `note.reality`, `note.glossary`, `note.plan`, `note.changes` |
| Home note | `h.read`, `h.glance`, `open.system`, `h.stages`, `h.background`, `h.flows`, `h.whatif`, `h.how_to_run`, `h.stack`, `h.audience`, `h.source`, `h.glossary`, `h.my_notes`, `read.system`, `read.flows`, `read.whatif`, `read.reality`, `read.plan`, `read.changes`, `glance.plan`, `glance.plan_value`, `glance.changes` |
| Item notes | `h.connections`, `h.gets_from`, `h.sends_to`, `h.in_flows`, `h.can_go_wrong`, `h.in_code`, `h.stage`, `step` |
| Flow notes | `h.trigger`, `h.steps`, `h.result`, `h.sequence`, `h.related_whatif` |
| Scenario notes | `h.what_happens`, `h.user_sees`, `h.handled`, `h.evidence`, `h.fix`, `h.affects`, `h.category` |
| Plan vs Reality | `h.intent`, `h.verdict`, `h.plan_check`, `h.as_planned`, `h.added`, `h.unfinished`, `h.missing`, `h.unused`, `h.risks`, `h.questions`, `intent_source`, `intent.from_plan`, `plan.built`, `plan.partly`, `plan.missing`, `plan.changed`, `plan.dropped` |
| Changes note | `changes.title`, `changes.intro`, `changes.since`, `changes.first`, `changes.none`, `changes.parts`, `changes.stages`, `changes.whatif`, `changes.plan`, `changes.reality`, `changes.new`, `changes.gone`, `changes.renamed`, `changes.moved`, `changes.better`, `changes.worse`, `changes.status`, `changes.counts`, `changes.n_new`, `changes.n_gone`, `changes.n_better`, `changes.n_worse` |
| Cards and footer | `card.trigger`, `card.result`, `card.legend`, `card.nav`, `legend.status` (repeats the four status badges, so translate it together with them), `footer` (keeps `{date}` and `{my_notes}`), `back` |

Example (Spanish, partial):

```json
"labels": {
  "folder.component": "Partes", "folder.input": "Entradas", "folder.scenario": "Qué pasa si",
  "canvas.system": "1 Visión general", "canvas.whatif": "3 Qué pasa si",
  "card.start": "Empieza aquí", "card.out": "Sale", "h.my_notes": "Mis notas"
}
```

## Example

A small but complete atlas for a recipe bot. Real atlases usually have more nodes and scenarios.

```json
{
  "atlas_version": 1,
  "project": {
    "name": "Pantry Chef",
    "one_liner": "A Discord bot that suggests dinner recipes from what is in your fridge.",
    "summary": "People list their ingredients in a Discord channel. The bot asks Claude for three recipes that use them, saves each request, and replies in the thread.\n\nIt runs as one Node.js process on a small VPS.",
    "intent": "A bot that turns a list of ingredients into a recipe.",
    "intent_source": "README",
    "audience": "A private Discord server of about 40 friends",
    "stack": ["Node.js 22", "discord.js", "Claude API", "SQLite"],
    "how_to_run": "`npm install`, fill `.env` from `.env.example`, then `npm start`.",
    "source": "~/code/pantry-chef"
  },
  "nodes": [
    { "id": "member", "kind": "actor", "name": "Server member", "summary": "Writes what is in their fridge." },
    { "id": "discord-msg", "kind": "input", "name": "!cook command", "summary": "A Discord message starting with !cook and a list of ingredients.", "files": ["src/bot.js:14"] },
    { "id": "keys", "kind": "config", "name": "API keys", "summary": "Discord token and Claude API key.", "details": "`DISCORD_TOKEN`, `ANTHROPIC_API_KEY` in `.env`." },
    { "id": "parser", "kind": "component", "name": "Ingredient reader", "summary": "Splits the message into a clean ingredient list.", "files": ["src/parse.js"] },
    { "id": "chef", "kind": "component", "name": "Recipe writer", "summary": "Asks Claude for three recipes and formats them.", "files": ["src/chef.js"] },
    { "id": "stats", "kind": "component", "name": "Weekly stats", "summary": "Posts the most-used ingredients every Monday.", "files": ["src/stats.js"], "status": "extra" },
    { "id": "db", "kind": "store", "name": "Request history", "summary": "SQLite file with every request and reply.", "files": ["data/pantry.db"], "status": "risky", "details": "No backups and no size limit." },
    { "id": "claude", "kind": "external", "name": "Claude API", "summary": "Writes the recipes." },
    { "id": "reply", "kind": "output", "name": "Recipe reply", "summary": "Three recipes posted in a thread under the message." }
  ],
  "links": [
    { "from": "member", "to": "discord-msg", "label": "ingredients" },
    { "from": "discord-msg", "to": "parser", "label": "raw text" },
    { "from": "parser", "to": "chef", "label": "ingredient list" },
    { "from": "chef", "to": "claude", "label": "prompt" },
    { "from": "chef", "to": "db", "label": "request + reply" },
    { "from": "chef", "to": "reply", "label": "3 recipes" },
    { "from": "db", "to": "stats", "label": "last week's requests" },
    { "from": "keys", "to": "chef", "label": "API key" }
  ],
  "stages": [
    { "id": "read", "name": "Read the fridge list", "summary": "The !cook message is cleaned into a list of ingredients.", "nodes": ["parser"], "passes": "ingredient list" },
    { "id": "cook", "name": "Write the recipes", "summary": "Claude suggests three recipes; the request and answer are saved.", "nodes": ["chef"], "passes": "3 recipes" },
    { "id": "weekly", "name": "Weekly stats", "summary": "Every Monday the most-used ingredients are posted.", "nodes": ["stats"], "lane": "background" }
  ],
  "flows": [
    {
      "id": "cook",
      "name": "Ask for a recipe",
      "trigger": "A member writes `!cook eggs, spinach, feta`",
      "summary": "The main journey from a fridge list to three recipes.",
      "steps": [
        { "node": "member", "action": "writes !cook with their ingredients", "to": "discord-msg", "data": "message" },
        { "node": "parser", "action": "cleans the list and drops duplicates", "to": "chef", "data": "ingredient list" },
        { "node": "chef", "action": "asks Claude for three recipes", "to": "claude", "data": "prompt" },
        { "node": "chef", "action": "saves the request and the answer", "to": "db" },
        { "node": "chef", "action": "posts the recipes in a thread", "to": "reply" }
      ],
      "result": "Three recipes in a thread under the member's message"
    }
  ],
  "scenarios": [
    {
      "id": "claude-down",
      "question": "What if the Claude API is down?",
      "category": "outside service",
      "trigger_node": "claude",
      "affects": ["chef"],
      "flows": ["cook"],
      "what_happens": "The call throws; `chef.js` catches it and replies with a short apology. Nothing is retried.",
      "user_sees": "\"The chef is out, try again in a minute.\"",
      "handled": "partly",
      "evidence": "`src/chef.js:41` try/catch around the API call",
      "fix": "Retry once after 5 seconds before apologising.",
      "severity": "medium"
    },
    {
      "id": "db-grows",
      "question": "What if the request history grows for a year?",
      "category": "growth",
      "trigger_node": "db",
      "affects": ["stats"],
      "what_happens": "Every reply is stored in full and nothing is ever deleted, so the file grows without limit. Weekly stats scan the whole table.",
      "user_sees": "Nothing at first; later the Monday post gets slow and the disk fills up.",
      "handled": "no",
      "evidence": "No delete or cleanup anywhere in `src/`",
      "fix": "Delete requests older than 90 days in the weekly stats job.",
      "severity": "low"
    }
  ],
  "reality": {
    "intent": "A bot that turns a list of ingredients into a recipe.",
    "intent_source": "README",
    "verdict": "The core idea works. Two things grew around it: a stored history and a weekly stats post. The history has no backups or limits.",
    "as_planned": [ { "title": "Recipes from ingredients", "text": "Works end to end with three suggestions.", "nodes": ["chef"] } ],
    "added": [ { "title": "Weekly stats post", "text": "Not in the plan; reads the whole history every Monday.", "nodes": ["stats", "db"] } ],
    "risks": [ { "title": "History is never backed up", "nodes": ["db"] } ],
    "questions": [ "Do you want to keep every request forever, or only for a few months?" ]
  },
  "glossary": [ { "term": "Thread", "meaning": "A Discord sub-conversation attached to one message." } ]
}
```
