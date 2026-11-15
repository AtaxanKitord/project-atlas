---
generator: "project-atlas"
project: "Pantry Chef"
atlas: "node"
kind: "actor"
status: "core"
tags:
  - "atlas/person"
---
# Server member

> [!example] 👤 Person
> Writes what is in their fridge and saves recipes they like.

## Connections
**Sends to**
- [[Project Atlas/Pantry Chef/Inputs/!cook command|!cook command]]: ingredients
- [[Project Atlas/Pantry Chef/Inputs/!fav command|!fav command]]: keep this one

```mermaid
flowchart LR
  n0(["Server member"])
  n1["!cook command"]
  n2["!fav command"]
  n0 -->|"ingredients"| n1
  n0 -->|"keep this one"| n2
```

## Part of these flows
- [[Project Atlas/Pantry Chef/Flows/Ask for a recipe|Ask for a recipe]], step 1: writes !cook with their ingredients
- [[Project Atlas/Pantry Chef/Flows/Save a favourite|Save a favourite]], step 1: replies !fav to a recipe


---
Back to: [[Project Atlas/Pantry Chef/Pantry Chef|Pantry Chef]] · [[Project Atlas/Pantry Chef/1 Big Picture.canvas|1 Big Picture]] · [[Project Atlas/Pantry Chef/2 Flows.canvas|2 Flows]] · [[Project Atlas/Pantry Chef/3 What If.canvas|3 What If]] · [[Project Atlas/Pantry Chef/4 Plan vs Reality.canvas|4 Plan vs Reality]]

## My notes
%% atlas:my-notes - anything below this line is kept when the atlas is regenerated %%
