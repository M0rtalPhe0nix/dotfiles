# dotfiles

Public MIT-licensed dotfiles for Apple Silicon macOS and Debian/Ubuntu desktops. Chezmoi manages configuration and platform differences, Homebrew manages shared tools, and mise manages Node 24 and Python 3.14.

## Bootstrap

Review `bootstrap.sh`, then run:

```sh
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/M0rtalPhe0nix/dotfiles/main/bootstrap.sh)"
```

The bootstrap installs platform prerequisites, Homebrew when needed, and Chezmoi. Before the first apply, existing managed files are archived under `~/.local/state/dotfiles/pre-bootstrap/`. Interactive runs pause for GitHub, Claude Code, and OpenCode authentication when required.

Claude Code installation is optional at the first-run prompt. To skip it without a prompt:

```sh
DOTFILES_SKIP_CLAUDE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/M0rtalPhe0nix/dotfiles/main/bootstrap.sh)"
```

Git author name and email are requested by Chezmoi during initialization and remain in the host-local Chezmoi config. Authentication, signing, existing Git LFS settings, secrets, and other machine-specific values are not committed.

## Operations

```sh
dotfiles diff       # Preview managed configuration changes
dotfiles apply      # Converge configuration without upgrading software
dotfiles doctor     # Check tools, auth, fonts, permissions, and managed state
dotfiles update     # Update only managed packages, runtimes, extensions, and Zim modules
dotfiles rollback   # Restore pre-bootstrap files without uninstalling packages
```

Put host-specific shell customization in `~/.config/zsh/local.zsh`. Put secrets in `~/.config/zsh/secrets.zsh`; Chezmoi creates it with mode `0600` and never records its contents.

## Managed Environment

- Zsh, ZimFW, Starship, fzf, secure shared history, completions, autosuggestions, syntax highlighting, and history substring search.
- Availability-guarded `eza`, `bat`, `zoxide`, mise, fzf, and Starship integrations.
- Git policy in included fragments, preserving host-managed identity infrastructure, authentication, signing, and unrelated settings.
- Claude Code and OpenCode with high-autonomy permissions plus secret, destructive-command, and external-directory guardrails.
- Canonical reusable skills under `~/.claude/skills`, discovered by Claude Code and OpenCode without duplication.
- VS Code, a managed extension baseline, Ghostty, Catppuccin, and MesloLGS Nerd Font. Extensions outside the baseline are not removed.

No global MCP servers or global AI coding instruction files are installed.

## Validation

Install the validation tools from the Brewfile, then run:

```sh
tests/validate.sh
tests/debian-smoke.sh
tests/zsh-startup.sh
```

`tests/validate.sh` checks shell formatting and lint, JSON, OpenCode configuration, common secret signatures, temporary-home rendering, and a clean second apply. The Docker test renders on Debian without running package or authentication scripts. The startup test requires a warm average below 200 ms.

GitHub Actions are intentionally deferred; version 1 validation is local only.
