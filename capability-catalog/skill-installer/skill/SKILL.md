---
name: skill-installer
description: Manage repository-local skills through the dotfiles capability workflow. Use when a user asks to list, add, remove, restore, or update skills for the current Git repository.
metadata:
  short-description: Manage repository-local capability-backed skills
---

# Repository-local Skill Installer

Manage skills as explicit desired state in the current Git worktree. Never install into a global Codex or Claude skill directory and never copy a skill payload manually.

Use the `dotfiles skills` alias, which delegates to the dependency-aware capability manager:

- Initialize the current Git worktree with `dotfiles skills init` when it has no capability manifest.
- Explain requested, transitive, recommended, and resolved skills with `dotfiles skills list`.
- Add a qualified skill with `dotfiles skills add --catalog <portable-git-url> <owner/repository/name>`.
- Remove an explicitly selected skill with `dotfiles skills remove <owner/repository/name>`.
- Restore locked generated content with `dotfiles skills sync`.
- Update selected skills with `dotfiles skills update <identifier>...`, or the complete graph with `dotfiles skills update --all`.
- Promote a recommendation with `dotfiles skills recommend <identifier>`.
- Select every current skill in a catalog explicitly with `dotfiles skills snapshot --catalog <portable-git-url>`.

Operate only on the Git worktree discovered from the current directory. The manifest and lock are tracked; materialized `.agents/skills` payloads and relative `.claude/skills` mirrors are generated repository state. Synchronization is authoritative and may overwrite experiments, so show drift with `dotfiles skills diff` when the user wants to inspect changes first.

When the user supplies an arbitrary GitHub skill directory rather than a capability catalog, explain that it must first be represented by portable `capability.json` metadata in a Git catalog. Do not fall back to the removed global download scripts.
