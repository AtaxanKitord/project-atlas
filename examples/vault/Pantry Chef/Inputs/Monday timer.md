---
generator: "project-atlas"
project: "Pantry Chef"
atlas: "node"
kind: "input"
status: "core"
files:
  - "src/schedule.js"
tags:
  - "atlas/input"
---
# Monday timer

> [!info] 📥 Input
> Fires every Monday at 9:00.

## Connections
**Sends to**
- [[Pantry Chef/Parts/Weekly stats|Weekly stats]]: tick

```mermaid
flowchart LR
  n0(["Monday timer"])
  n1["Weekly stats"]
  n0 -->|"tick"| n1
```

## Part of these flows
- [[Pantry Chef/Flows/Monday stats|Monday stats]], step 1: fires

## Where it lives
- `src/schedule.js`


---
Back to: [[Pantry Chef/Pantry Chef|Pantry Chef]] · [[Pantry Chef/1 Big Picture.canvas|1 Big Picture]] · [[Pantry Chef/2 Flows.canvas|2 Flows]] · [[Pantry Chef/3 What If.canvas|3 What If]] · [[Pantry Chef/4 Plan vs Reality.canvas|4 Plan vs Reality]]

## My notes
%% atlas:my-notes - anything below this line is kept when the atlas is regenerated %%
