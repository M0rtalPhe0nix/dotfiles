---
name: speckit-diagrams
description: Turn GitHub Spec Kit feature artifacts into editable Excalidraw diagrams and local previews. Use when the user asks to visualize, diagram, map, explain visually, or create an architecture, workflow, data model, story map, traceability map, or implementation roadmap from Spec Kit files such as spec.md, plan.md, research.md, data-model.md, contracts/, or tasks.md.
---

# Spec Kit Diagrams

Convert the current Spec Kit feature into a small set of decision-useful, editable diagrams by composing the installed `excalidraw` skill.

## Dependency

Before generating anything, read `${CODEX_HOME:-$HOME/.codex}/skills/excalidraw/SKILL.md` completely and read only the Excalidraw references it routes to for the selected layout. If the skill is absent, stop and ask the user to install `fabricioartur/codex-excalidraw-skill`.

Treat this skill's privacy and artifact-selection rules as overrides when they conflict with the base skill.

## Resolve the Feature

1. Work from the repository root containing `.specify/`.
2. If the user names a feature directory, use it.
3. Otherwise run `.specify/scripts/bash/check-prerequisites.sh --json --paths-only` and use `FEATURE_DIR`.
4. If no current feature is resolved, inspect `specs/`. Use the only feature when exactly one exists; otherwise ask the user which feature to visualize.
5. Never invent missing artifacts. State which available files informed each view.

## Read the Artifacts

Read all relevant files in the resolved feature directory:

- `spec.md`: actors, user journeys, priority, requirements, edge cases, and success criteria.
- `plan.md`: architecture, technology choices, boundaries, constraints, and project structure.
- `research.md`: decisions, alternatives, and rejected options.
- `data-model.md`: entities, relationships, states, and validation rules.
- `contracts/`: external interfaces, endpoints, events, schemas, and error behavior.
- `tasks.md`: phases, dependencies, parallel work, and user-story coverage.

Use codebase inspection to verify named components and integrations when implementation already exists.

## Choose Views

Generate only views supported by available information. When the user does not name a view, select up to three complementary diagrams:

1. **User journey** from `spec.md`: actors, triggers, happy path, decisions, failure paths, and measurable outcome. Prefer swimlanes or a staged flow.
2. **System architecture** from `plan.md`, contracts, and verified code: users/channels, application components, data stores, external services, trust boundaries, and major data flows. Prefer layered zones.
3. **Domain model** from `data-model.md`: entities, cardinality, ownership, lifecycle states, and invariants. Prefer an ER-style layout.
4. **Requirement traceability** from `spec.md` plus `tasks.md`: user stories and functional requirements mapped to implementation phases or task groups. Show missing coverage clearly.
5. **Implementation roadmap** from `tasks.md`: dependency-ordered phases, parallelizable groups, milestones, and critical path. Prefer columns or a dependency graph.
6. **Decision map** from `research.md`: decision, drivers, selected option, rejected alternatives, and consequences.

Split overloaded visuals instead of creating one unreadable canvas. Do not copy paragraphs into nodes; use short labels and preserve identifiers such as `US1`, `FR-003`, and `T012` for traceability.

## Generate Artifacts

1. Create `FEATURE_DIR/diagrams/` when output is requested.
2. For each view, first create a compact JSON source at `diagrams/<view>-diagram-spec.json` containing the title, source artifact paths, nodes, edges, groups, and any layout notes.
3. Use the base Excalidraw skill to create:
   - `diagrams/<view>.excalidraw`
   - `diagrams/<view>-preview.svg`
   - `diagrams/<view>-preview.html`
4. Use `generate_excalidraw.py` for simple node-edge views. Use direct Excalidraw scene composition and the base skill's architecture-zone, swimlane, or composed-layout guidance when a generic graph would obscure meaning.
5. Run `validate_scene.py` on every `.excalidraw` file and apply the base skill's visual quality gate.
6. Visually inspect every SVG preview. Fix overlaps, clipped labels, ambiguous arrows, tiny text, and excessive density before delivery.

## Privacy and Safety

- Default to local-only generation. Pass `--no-web-link` or omit `--web-link` in every base script call.
- Do not upload specifications, diagrams, financial information, code-derived architecture, or other project content to Excalidraw or any external service unless the user explicitly requests a shareable web link in the current turn.
- If the user requests a web link, explain that the encrypted scene is stored on Excalidraw's public JSON service and that possession of the full URL grants decryption access.
- Open preview HTML only when its SVG was generated from trusted project artifacts; do not embed or open arbitrary third-party SVG because the preview page inserts SVG markup directly.
- Never call `session_state.py clear`.
- Store persistent outputs only under the resolved feature's `diagrams/` directory unless the user chooses another location.
- Preserve the source artifact files; this skill is read-only with respect to `spec.md`, `plan.md`, `data-model.md`, contracts, and `tasks.md`.

## Delivery

Show the preview images, link the editable `.excalidraw` files and source JSON files, and summarize:

- which Spec Kit artifacts were used;
- what each diagram communicates;
- any ambiguity, contradiction, or missing coverage discovered while visualizing;
- whether all outputs remained local or a web link was explicitly created.
