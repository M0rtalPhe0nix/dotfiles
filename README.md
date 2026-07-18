# dotfiles

Public MIT-licensed dotfiles for Apple Silicon macOS and Debian/Ubuntu desktops. Chezmoi manages configuration and platform differences, Homebrew manages shared tools, and mise manages Node 24 and Python 3.14.

## Bootstrap

Review `bootstrap.sh`, then run:

```sh
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/M0rtalPhe0nix/dotfiles/main/bootstrap.sh)"
```

Inspect the platform branch, prerequisites, managed scope, backup targets, and configured choices without changing the host:

```sh
curl -fsSL https://raw.githubusercontent.com/M0rtalPhe0nix/dotfiles/main/bootstrap.sh | /bin/sh -s -- --preflight
```

The bootstrap first asks whether the host needs a corporate CA certificate, then installs platform prerequisites, Homebrew when needed, and Chezmoi. Before the first apply, existing managed files are archived under `~/.local/state/dotfiles/pre-bootstrap/`. Interactive runs pause for GitHub, Claude Code, and OpenCode authentication when required.

Rerunning bootstrap fast-forwards an existing Chezmoi source clone, regenerates local initialization data, and applies the current configuration. It does not overwrite divergent source changes.

Claude Code installation is optional at the first-run prompt. To skip it without a prompt:

```sh
DOTFILES_SKIP_CLAUDE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/M0rtalPhe0nix/dotfiles/main/bootstrap.sh)"
```

Git author name and email are requested by Chezmoi during initialization and remain in the host-local Chezmoi config. The same prompt lets you install Terraform `1.5.7`, the latest OpenTofu, or neither through mise. Authentication, signing, existing Git LFS settings, secrets, and other machine-specific values are not committed.

The developer baseline always provisions Node, Python, `uv`, `pnpm`, and Ruff through mise. Python, TypeScript, Markdown, and Terraform language servers are optional first-run choices; selected language servers are also mise-managed.

### Corporate CA Certificates

Bootstrap asks whether to configure a corporate CA before installing packages. If selected, it accepts the absolute path to a PEM-encoded certificate. The certificate must contain no private key and remains outside this public repository. Chezmoi copies it to `~/.local/share/dotfiles/`, installs it in the macOS or Debian/Ubuntu system trust store, and creates a combined CA bundle.

The managed shell environment configures OpenSSL-compatible applications, Git, curl, Python, pip, Poetry, uv, npm/Node.js, Cargo, and rustup. Docker uses the host system trust for daemon and registry connections. Images and containers have separate trust stores, so Dockerfiles that access the corporate network must install the CA in the image explicitly.

If the CA is required before Homebrew or Chezmoi can be downloaded, provide it to both the initial curl command and bootstrap:

```sh
export DOTFILES_CORPORATE_CA_PATH=/absolute/path/to/corporate-ca.pem
/bin/bash -c "$(curl --cacert "$DOTFILES_CORPORATE_CA_PATH" -fsSL https://raw.githubusercontent.com/M0rtalPhe0nix/dotfiles/main/bootstrap.sh)"
```

The path and opt-in are stored only in the host-local Chezmoi config. Keep the source PEM at that path so future applies can detect certificate rotation. Restart Docker Desktop and graphical applications after initially installing or rotating the CA.

## GitHub Profiles

Authenticate and record each reusable profile once. The first value is a local alias; the second is the authenticated GitHub login. The optional final value overrides the Git author name, which otherwise defaults to the GitHub login:

```sh
github-profile add personal M0rtalPhe0nix personal@example.com
github-profile add work work-login work@example.com "Your Name"
```

Then select a profile from inside each repository:

```sh
github-profile use work
github-profile current
```

The alias selection, GitHub login, and Git author identity are stored in the repository's local Git config. Interactive `gh` commands and HTTPS Git credentials automatically use that account. Tokens remain in GitHub CLI's credential store; they are never written to the repository or profile files. Explicit `GH_TOKEN` or `GITHUB_TOKEN` values take precedence for `gh`.

## Operations

```sh
dotfiles diff       # Preview managed configuration changes
dotfiles apply      # Converge configuration without upgrading software
dotfiles doctor     # Check tools, auth, fonts, permissions, and managed state
dotfiles extensions # Merge installed VS Code extensions into the managed baseline
dotfiles extensions --overwrite # Replace the managed baseline with installed extensions
dotfiles update     # Update only managed packages, runtimes, extensions, and Zim modules
dotfiles rollback   # Restore pre-bootstrap files without uninstalling packages
```

Put host-specific shell customization in `~/.config/zsh/local.zsh`. Put secrets in `~/.config/zsh/secrets.zsh`; Chezmoi creates it with mode `0600` and never records its contents.

## Managed Environment

- Zsh, ZimFW, Starship, fzf, secure shared history, completions, autosuggestions, syntax highlighting, and history substring search.
- Availability-guarded `eza`, `bat`, `zoxide`, mise, fzf, and Starship integrations.
- Git policy in included fragments, preserving host-managed identity infrastructure, authentication, signing, and unrelated settings, with optional per-repository GitHub profiles.
- Optional corporate CA trust for the operating system and CLI package managers, without committing the certificate or its host-local path.
- Claude Code and OpenCode with high-autonomy permissions plus secret, destructive-command, and external-directory guardrails.
- A guarded Claude post-edit Python formatter that uses mise-managed Ruff when available.
- Canonical reusable skills under `~/.claude/skills`, discovered by Claude Code and OpenCode without duplication.
- A read-only dotfiles comparison skill that mines one public GitHub repository for evidence-backed improvement ideas and a ranked backlog.
- Haiku-powered Claude Code and Luna-powered OpenCode `feature-diagrammer` subagents for validated Excalidraw artifact production after feature discovery.
- VS Code, a managed extension baseline, Ghostty, Catppuccin, and MesloLGS Nerd Font. Extensions outside the baseline are not removed.

No global MCP servers or global AI coding instruction files are installed.

## Validation

Install the validation tools from the Brewfile, then run:

```sh
tests/validate.sh
tests/debian-smoke.sh
tests/zsh-startup.sh
```

`tests/validate.sh` checks shell formatting and lint, rendered JSON, Claude skills/agents/hooks, OpenCode configuration, common secret signatures, temporary-home rendering, and a clean second apply. The Docker test renders and checks package scripts with mocked package commands on Debian and Ubuntu; it does not authenticate or install packages. The startup test requires a warm average below 200 ms.

GitHub Actions are intentionally deferred; version 1 validation is local only.
