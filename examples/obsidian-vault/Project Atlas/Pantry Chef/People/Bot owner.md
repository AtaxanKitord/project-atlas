---
generator: "project-atlas"
project: "Pantry Chef"
atlas: "node"
kind: "actor"
status: "core"
tags:
  - "atlas/person"
---
# Bot owner

> [!example] 👤 Person
> Runs the VPS, sets the keys and reads the logs when something goes wrong.

## Connections
**Sends to**
- [[Project Atlas/Pantry Chef/Settings/API keys|API keys]]: sets

```mermaid
flowchart LR
  n0(["Bot owner"])
  n1["API keys"]
  n0 -->|"sets"| n1
```


---
Back to: [[Project Atlas/Pantry Chef/Pantry Chef|Pantry Chef]] · [[Project Atlas/Pantry Chef/1 Big Picture.canvas|1 Big Picture]] · [[Project Atlas/Pantry Chef/2 Flows.canvas|2 Flows]] · [[Project Atlas/Pantry Chef/3 What If.canvas|3 What If]] · [[Project Atlas/Pantry Chef/4 Plan vs Reality.canvas|4 Plan vs Reality]]

## My notes
%% atlas:my-notes - anything below this line is kept when the atlas is regenerated %%
