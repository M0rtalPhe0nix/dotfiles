# Coding Agent Instructions

## Repository Purpose

This is the public MIT-licensed `M0rtalPhe0nix/dotfiles` repository. It targets Apple Silicon macOS and Debian/Ubuntu desktops. Chezmoi manages files and platform differences, Homebrew manages shared CLI tools, apt manages Linux prerequisites, and mise manages Node and Python.

## Safety Rules

- Never commit secrets, credentials, tokens, private keys, machine identifiers, or host-specific values.
- Keep Git authentication, signing, and unrelated host settings unmanaged.
- Preserve `~/.config/zsh/local.zsh` and mode-`0600` `~/.config/zsh/secrets.zsh` as host-local files.
- Do not add global MCP servers or global AI coding instructions unless the project requirements explicitly change.
- Do not make bootstrap uninstall packages or make rollback uninstall packages.
- Do not make `dotfiles apply` upgrade software. Upgrades belong exclusively in `dotfiles update`.
- Preserve extra VS Code extensions; manage only the extension baseline.
- Treat this repository as public even before changes are pushed.

## Chezmoi Conventions

- Use Chezmoi source-state names such as `dot_zshrc`, `dot_config/`, `private_`, `executable_`, `create_`, and `symlink_` correctly.
- Put attributes on the source path component they modify. For example, use `dot_config/zsh/create_private_secrets.zsh`, not `create_private_dot_config/zsh/secrets.zsh`.
- Add `.tmpl` only when a file contains Chezmoi template expressions.
- Keep platform-specific target exclusions in `.chezmoiignore`.
- Keep repository-only files such as tests, manifests, documentation, and canonical skill sources out of the managed target set.
- Existing reusable skills remain canonical under `.claude/skills` in the source and are exposed as managed symlinks under `~/.claude/skills`.
- Initialization data must remain public-safe. Git identity and installation choices belong in the local Chezmoi config, not committed files.

## Operational Invariants

- `bootstrap.sh` must support first installation and safe repeat execution.
- Repeat bootstrap must fast-forward the existing source with `git pull --ff-only`; never discard divergent local changes.
- Backup managed conflicts before the first apply.
- `dotfiles rollback` restores pre-bootstrap files without uninstalling software.
- `DOTFILES_SKIP_CLAUDE=1` must skip Claude Code installation, authentication, and doctor requirements.
- Authentication may be interactive, but non-interactive rendering and validation must remain possible.
- Shell integrations and opinionated command replacements must be guarded by command availability.
- Shared shell history must remain private, mode `0600`, and exclude commands beginning with a space.
- The warm managed Zsh startup average must remain below 200 ms on the primary Mac.

## Platform Rules

- macOS support is limited to Apple Silicon.
- Linux support is limited to Debian and Ubuntu desktops.
- Homebrew installs shared CLI tools on both platforms.
- apt installs Linux prerequisites and VS Code.
- Ghostty is a Homebrew cask on macOS and uses Ghostty's documented Ubuntu package installer on supported Linux releases.
- MesloLGS Nerd Font must be provisioned and used consistently by Ghostty, VS Code, and Starship.
- Keep macOS and Linux VS Code target paths separate.

## AI Configuration

- Claude Code settings live in `dot_claude/settings.json`.
- OpenCode settings live in `dot_config/opencode/opencode.json`.
- Both tools should have high autonomy with explicit guardrails for secrets, destructive commands, and external directories.
- Validate OpenCode configuration against its published schema; unknown keys can prevent startup.
- Do not duplicate shared skills into tool-specific directories.

## Validation

Run the local validation suite after relevant changes:

```sh
tests/validate.sh
tests/debian-smoke.sh
tests/zsh-startup.sh
```

At minimum, changes must pass:

- ShellCheck and shfmt.
- JSON validation.
- OpenCode configuration validation.
- Secret scanning.
- Chezmoi rendering into a temporary macOS home.
- A clean second Chezmoi apply.
- Debian Docker rendering and shell syntax checks for Linux templates.
- Shared skill availability under the rendered `~/.claude/skills` path.

Use `git diff --check` before committing. Do not publish changes that have not passed the relevant local tests.

## Editing Guidance

- Prefer the smallest correct change.
- Preserve existing behavior unless the requested change intentionally replaces it.
- Update README documentation when commands, bootstrap behavior, managed tools, or user-facing choices change.
- Add regression coverage for fixed bootstrap, template, path-encoding, or platform bugs.
- Do not create GitHub Actions workflows; version 1 intentionally uses local tests only.

## Agent skills

### Issue tracker

Issues and PRDs are tracked in GitHub Issues for `M0rtalPhe0nix/dotfiles`. See `docs/agents/issue-tracker.md`.

### Domain docs

This repository uses a single-context domain-doc layout. See `docs/agents/domain.md`.
