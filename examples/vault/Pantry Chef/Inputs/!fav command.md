---
generator: "project-atlas"
project: "Pantry Chef"
atlas: "node"
kind: "input"
status: "core"
files:
  - "src/bot.js:31"
tags:
  - "atlas/input"
---
# !fav command

> [!info] 📥 Input
> A reply to one of the bot's recipes, saying 'keep this one'.

## Connections
**Gets from**
- [[Pantry Chef/People/Server member|Server member]]: keep this one

**Sends to**
- [[Pantry Chef/Parts/Message router|Message router]]: reply

```mermaid
flowchart LR
  n0["Server member"]
  n1(["!fav command"])
  n2["Message router"]
  n0 -->|"keep this one"| n1
  n1 -->|"reply"| n2
```

## Where it lives
- `src/bot.js:31`


---
Back to: [[Pantry Chef/Pantry Chef|Pantry Chef]] · [[Pantry Chef/1 Big Picture.canvas|1 Big Picture]] · [[Pantry Chef/2 Flows.canvas|2 Flows]] · [[Pantry Chef/3 What If.canvas|3 What If]] · [[Pantry Chef/4 Plan vs Reality.canvas|4 Plan vs Reality]]

## My notes
%% atlas:my-notes - anything below this line is kept when the atlas is regenerated %%
