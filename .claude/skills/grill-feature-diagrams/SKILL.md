---
name: grill-feature-diagrams
description: Elicit a feature exhaustively through a rigorous one-question-at-a-time interview, synthesize an approved feature brief, then delegate creation of a detailed portfolio of editable Excalidraw diagrams to a low-cost model. Use when a user wants to explore, define, visualize, or hand off a product or software feature and needs both deep requirements discovery and architecture, workflow, data, state, sequence, rollout, or operational diagrams.
---

# Grill Feature Diagrams

Turn an underspecified feature request into an approved, traceable set of editable Excalidraw diagrams. Keep discovery with the main agent and delegate artifact production only after the user settles all material decisions.

## Workflow

### 1. Establish Context

1. Inspect relevant workspace files, existing architecture, conventions, and prior discussion before asking questions.
2. Load and follow the `grill-me` skill for the complete interview. If the harness cannot load skills by name, read its `SKILL.md` from the available shared skill directory.
3. Maintain an internal coverage ledger. Mark each applicable area as discovered, decided, assumed, deferred, or not applicable:
   - problem, outcomes, users, stakeholders, and success measures
   - scope, non-goals, dependencies, constraints, and priorities
   - primary journeys, alternate flows, states, and lifecycle
   - functional rules, business rules, permissions, and ownership
   - data entities, relationships, retention, privacy, and migration
   - APIs, events, integrations, boundaries, and compatibility
   - failure modes, recovery, idempotency, concurrency, and edge cases
   - performance, scale, availability, security, accessibility, and localization
   - observability, analytics, support, operations, and audit needs
   - rollout, feature flags, rollback, testing, and acceptance criteria
   - diagram audiences, desired depth, output location, and confidentiality

Ask only questions whose answers can change the feature brief or diagram portfolio. Do not replace user decisions with generic assumptions merely to finish sooner.

### 2. Complete the Interview

Follow `grill-me` strictly: ask exactly one decision-focused question per turn, recommend an answer, and continue until every material branch in the coverage ledger is settled or deliberately deferred.

Before diagramming, present a concise synthesis containing:

- goals and success measures
- personas and stakeholders
- scope and non-goals
- requirements and acceptance criteria
- key flows, states, data, integrations, and system boundaries
- non-functional requirements and operational concerns
- settled decisions, explicit assumptions, deferred choices, and risks
- proposed diagram portfolio and output location

Ask one final question requesting approval or corrections. Do not start artifact generation until the user approves the synthesis.

### 3. Design the Diagram Portfolio

Choose diagrams because they explain a material part of the approved feature. Prefer a small, complete portfolio over overlapping diagrams. Select from:

- context or stakeholder map for actors and external boundaries
- user journey or service blueprint for end-to-end experience
- system architecture for components, trust zones, and data flow
- sequence diagrams for critical synchronous or event-driven interactions
- state machine for lifecycle, transitions, guards, and terminal states
- domain or data model for entities, relationships, ownership, and cardinality
- permissions matrix or access flow for role-sensitive behavior
- failure and recovery flow for retries, compensation, degradation, and rollback
- deployment, rollout, or migration diagram for delivery sequencing
- observability map for signals, alerts, dashboards, and operational ownership

Give each diagram a distinct question to answer. Use consistent names, colors, boundaries, and identifiers across the set. Include legends and concise annotations where the visual alone would be ambiguous. Preserve traceability to requirements or settled decisions with short IDs when useful.

### 4. Delegate Economically

Delegate diagram production to one worker subagent after approval. Do not delegate the interactive interview.

1. Use the `feature-diagrammer` subagent when available. It is the preferred worker and has its low-cost model and artifact guardrails configured already; do not override its model.
2. Otherwise, use the harness's model selector when available. Prefer Claude Haiku or GPT-5.6 Luna. If both are configured, use the cheapest available option suitable for file and tool work.
3. Never invent a model ID or claim a model was selected when the harness does not expose model selection. Inspect available models or configuration first when possible.
4. If neither preferred model is available, choose the cheapest configured worker model. If no low-cost worker or model selector exists, ask the user whether to continue on the current model before generating artifacts.
5. Give the worker the approved synthesis, relevant workspace paths, diagram portfolio, output location, naming conventions, and confidentiality/network constraints. Do not pass the full interview transcript unless a settled detail is absent from the synthesis.
6. Instruct the worker to load and follow the `excalidraw` skill, create real editable `.excalidraw` files, generate previews, run its scene validator and visual quality gate, and return artifact paths plus validation results.
7. Tell the worker not to ask the user questions. It must report any blocking ambiguity to the main agent instead of guessing.

Use a worker prompt shaped like this:

```text
Use the excalidraw skill to create the approved diagram portfolio below.

Feature brief: <approved synthesis>
Portfolio: <diagram names and the question each answers>
Relevant sources: <workspace paths>
Output directory: <path>
Constraints: <network, confidentiality, naming, and style constraints>

Create editable .excalidraw scenes and previews, keep terminology and visual
language consistent across the set, validate every scene, run the visual quality
gate, and return artifact paths and validation results. Do not ask the user or
invent unresolved requirements; report blockers to the parent agent.
```

### 5. Verify and Deliver

1. Inspect the worker's returned artifacts and validation results.
2. Check that every approved diagram exists, answers its stated question, agrees with the brief, and uses consistent terminology.
3. Send focused corrections back to the same worker when possible. Do not recreate its work in parallel.
4. Deliver a compact index listing each diagram, what it explains, its editable file, and its preview or web link.
5. State which worker model was actually used. If model selection could not be verified, say so plainly.
6. Summarize deferred decisions and assumptions that should trigger future diagram updates.

Do not present generated diagrams as authoritative when they conflict with the approved brief. Correct the artifacts first.
