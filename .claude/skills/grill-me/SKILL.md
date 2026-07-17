---
name: grill-me
description: Interview the user relentlessly to stress-test a plan or design until reaching shared understanding and resolving every material branch of the decision tree. Use when the user asks to be grilled, wants a plan or design interrogated, challenged, pressure-tested, or clarified through a rigorous one-question-at-a-time interview.
---

# Grill Me

Interrogate the plan methodically until its goals, constraints, decisions, dependencies, risks, and success criteria are mutually understood.

## Workflow

1. Inspect the available context and codebase before asking anything. If a question can be answered through files, configuration, history, tests, or other safe read-only exploration, investigate it directly instead of asking the user.
2. Build and continuously update an internal decision tree. Start with foundational choices that constrain downstream decisions, then walk each unresolved branch in dependency order.
3. Ask exactly one question per response. Do not bundle subquestions or present a questionnaire.
4. For every question, provide a concrete recommended answer and briefly explain why it is the best default given the evidence and constraints.
5. Make the decision explicit. State the relevant context, the question, and the recommendation clearly enough that the user can accept, reject, or modify it.
6. Incorporate each answer into the working understanding. Resolve contradictions and ambiguous dependencies before moving deeper into the tree.
7. Challenge assumptions, edge cases, failure modes, ownership, sequencing, tradeoffs, observability, security, migration, rollback, testing, and success measures when material to the plan.
8. Continue until no material branch remains unresolved. Do not stop merely because the high-level design sounds plausible.
9. Finish with a concise synthesis of the shared plan, settled decisions, assumptions, remaining risks, and any deliberately deferred choices.

## Question Tooling

- Use the harness's structured user-question tool for every interview question when one is available. Known equivalents include OpenCode's `question`, Claude Code's `AskUserQuestion`, and Codex's `request_user_input`.
- If the tool accepts multiple questions, submit exactly one. Never use a multi-question invocation to bypass the one-question-at-a-time workflow.
- Put the recommended answer first and label it `(Recommended)` when the tool supports choices. Use the option description to give the short rationale and key tradeoff.
- Keep the choices focused on materially different decisions. Include two or three choices when required by the tool, and rely on its free-form or custom-answer path so the user can reject or modify the offered choices.
- Do not repeat the question in normal assistant text before or after the tool call. The tool call is the response for that turn.
- If no structured question tool is available, ask the question in plain text using the fallback response shape below.

## Question Discipline

- Prefer the highest-leverage unresolved decision.
- Avoid questions whose answers will not change the plan.
- Distinguish facts discoverable from the codebase from judgments only the user can make.
- When evidence conflicts with the user's premise, explain the evidence and ask about the resulting decision rather than silently accepting the premise.
- Recommend one answer, even when several are viable. Mention the most important tradeoff without turning the question into a menu.
- Treat “I don't know” as a branch to resolve: propose a default, experiment, or decision criterion.
- Revisit earlier decisions when a later answer invalidates them.

## Plain-Text Fallback

Use this compact form only when the current harness has no structured user-question tool:

**Question:** One decision-focused question.

**Recommended answer:** One specific recommendation with a short rationale.

Ask no second question until the user answers the first.
