---
description: Map this project into an Obsidian atlas, record its plan, refresh it, or share it
argument-hint: "[plan | refresh | share | check]"
---

Use the project-atlas skill for the project in the current working directory.

What to do depends on the argument: "$ARGUMENTS"

- Empty or `map`: map the project into its atlas. If an atlas already exists, refresh it.
- `plan`: record what the user sets out to build (the plan), at the start of a project or before it drifts further.
- `refresh`: refresh the existing atlas, then summarise what changed since last time.
- `share`: export the atlas as one HTML file plus PNG images, for someone who doesn't use Obsidian.
- `check`: look at the atlas canvases as images and report layout problems.
- Anything else: treat it as what to map, for example a sub-folder or one part of the project.
