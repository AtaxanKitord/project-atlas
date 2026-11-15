---
generator: "project-atlas"
project: "Pantry Chef"
atlas: "flow"
tags:
  - "atlas/flow"
---
# Ask for a recipe

> [!abstract] 🔁 Flow
> The main journey, from a fridge list to three recipes.

**Starts when:** A member writes `!cook eggs, spinach, feta`

## Step by step
1. [[Project Atlas/Pantry Chef/People/Server member|Server member]]: writes !cook with their ingredients → [[Project Atlas/Pantry Chef/Parts/Message router|Message router]] *(message)*
2. [[Project Atlas/Pantry Chef/Parts/Cost guard|Cost guard]]: checks they have asked fewer than 20 times today
3. [[Project Atlas/Pantry Chef/Parts/Ingredient reader|Ingredient reader]]: cleans the list and drops duplicates → [[Project Atlas/Pantry Chef/Parts/Recipe writer|Recipe writer]] *(ingredient list)*
4. [[Project Atlas/Pantry Chef/Parts/Recipe writer|Recipe writer]]: asks Claude for three recipes → [[Project Atlas/Pantry Chef/Outside Services/Claude API|Claude API]] *(prompt)*
5. [[Project Atlas/Pantry Chef/Parts/Recipe writer|Recipe writer]]: saves the request and the answer → [[Project Atlas/Pantry Chef/Storage/Request history|Request history]]
6. [[Project Atlas/Pantry Chef/Parts/Reply formatter|Reply formatter]]: posts each recipe in a thread → [[Project Atlas/Pantry Chef/Outputs/Recipe thread|Recipe thread]]

**Ends with:** Three recipes in a thread under the member's message

## Who talks to whom
```mermaid
sequenceDiagram
  participant p0 as Server member
  participant p1 as Message router
  participant p2 as Cost guard
  participant p3 as Ingredient reader
  participant p4 as Recipe writer
  participant p5 as Claude API
  participant p6 as Request history
  participant p7 as Reply formatter
  participant p8 as Recipe thread
  p0->>p1: writes !cook with their ingredients
  Note over p2: checks they have asked fewer than 20 times today
  p3->>p4: cleans the list and drops duplicates
  p4->>p5: asks Claude for three recipes
  p4->>p6: saves the request and the answer
  p7->>p8: posts each recipe in a thread
```

## What can go wrong
- ⚠️ [[Project Atlas/Pantry Chef/What If/What if the Claude API is down|What if the Claude API is down?]]
- ✅ [[Project Atlas/Pantry Chef/What If/What if someone sends !cook 200 times|What if someone sends !cook 200 times?]]


---
Back to: [[Project Atlas/Pantry Chef/Pantry Chef|Pantry Chef]] · [[Project Atlas/Pantry Chef/1 Big Picture.canvas|1 Big Picture]] · [[Project Atlas/Pantry Chef/2 Flows.canvas|2 Flows]] · [[Project Atlas/Pantry Chef/3 What If.canvas|3 What If]] · [[Project Atlas/Pantry Chef/4 Plan vs Reality.canvas|4 Plan vs Reality]]

## My notes
%% atlas:my-notes - anything below this line is kept when the atlas is regenerated %%
