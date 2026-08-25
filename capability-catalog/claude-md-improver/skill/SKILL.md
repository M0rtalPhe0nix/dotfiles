---
name: claude-md-improver
description: Audit and improve CLAUDE.md project instructions. Use when the user asks to check, audit, update, improve, or maintain CLAUDE.md files or project memory.
---

# CLAUDE.md Improver

Audit CLAUDE.md files against the current codebase and propose concise, targeted improvements. This is an OpenCode-compatible adaptation of Anthropic's `claude-md-management` plugin skill.

## Workflow

1. Discover `CLAUDE.md`, `.claude.md`, and `.claude.local.md` files with Glob. Include root, package, and nested instruction files.
2. Inspect the repository's manifests, scripts, tests, configuration, and architecture. Verify documented commands rather than assuming they work.
3. Score each instruction file from 0 to 100 using these criteria:
   - Commands and workflows: 20
   - Architecture clarity: 20
   - Non-obvious patterns and gotchas: 15
   - Conciseness: 15
   - Currency: 15
   - Actionability: 15
4. Present a quality report before editing. For every file, include its score, specific issues, and recommended additions or removals.
5. Show a focused diff and ask for approval before changing any instruction file.
6. Apply only approved changes while preserving the existing structure and voice.

## Update Rules

- Add project-specific commands, architecture, testing patterns, environment requirements, and recurring gotchas.
- Remove stale or contradicted guidance.
- Keep each concept as short as practical because instruction files consume context.
- Do not add generic best practices, obvious facts, one-off fixes, secrets, or host-specific values.
- Put shared guidance in `CLAUDE.md` and personal guidance in `.claude.local.md`.
- Never edit an instruction file before presenting the report and receiving approval.

## Report Format

```markdown
## CLAUDE.md Quality Report

### Summary
- Files found: X
- Average score: X/100
- Files needing updates: X

### ./CLAUDE.md
**Score: XX/100 (Grade: X)**

| Criterion | Score | Notes |
|---|---:|---|
| Commands and workflows | X/20 | ... |
| Architecture clarity | X/20 | ... |
| Non-obvious patterns | X/15 | ... |
| Conciseness | X/15 | ... |
| Currency | X/15 | ... |
| Actionability | X/15 | ... |

**Issues:** ...

**Recommended changes:** ...
```

Use grades A for 90-100, B for 70-89, C for 50-69, D for 30-49, and F below 30.
