---
generator: "project-atlas"
project: "Pantry Chef"
atlas: "node"
kind: "component"
status: "core"
files:
  - "src/format.js"
tags:
  - "atlas/part"
---
# Reply formatter

> [!abstract] 🧩 Part · Stage [[Project Atlas/Pantry Chef/Stages/4 Reply in a thread.canvas|4 · Reply in a thread]]
> Turns the recipes into a tidy Discord thread with one message per recipe.

## Connections
**Gets from**
- [[Project Atlas/Pantry Chef/Parts/Recipe writer|Recipe writer]]: 3 recipes

**Sends to**
- [[Project Atlas/Pantry Chef/Outside Services/Discord API|Discord API]]: thread messages
- [[Project Atlas/Pantry Chef/Outputs/Recipe thread|Recipe thread]]: recipes

```mermaid
flowchart LR
  n0["Recipe writer"]
  n1(["Reply formatter"])
  n2["Discord API"]
  n3["Recipe thread"]
  n0 -->|"3 recipes"| n1
  n1 -->|"thread messages"| n2
  n1 -->|"recipes"| n3
```

## Part of these flows
- [[Project Atlas/Pantry Chef/Flows/Ask for a recipe|Ask for a recipe]], step 6: posts each recipe in a thread

## What can go wrong here
- ❌ [[Project Atlas/Pantry Chef/What If/What if the bot restarts while writing a reply|What if the bot restarts while writing a reply?]]

## Where it lives
- `src/format.js`


---
Back to: [[Project Atlas/Pantry Chef/Pantry Chef|Pantry Chef]] · [[Project Atlas/Pantry Chef/1 Big Picture.canvas|1 Big Picture]] · [[Project Atlas/Pantry Chef/2 Flows.canvas|2 Flows]] · [[Project Atlas/Pantry Chef/3 What If.canvas|3 What If]] · [[Project Atlas/Pantry Chef/4 Plan vs Reality.canvas|4 Plan vs Reality]]

## My notes
%% atlas:my-notes - anything below this line is kept when the atlas is regenerated %%
