# Dotfiles

An opinionated, public workstation setup for Apple Silicon macOS and Debian or Ubuntu desktops. It sets up a capable terminal, editor, developer tools, and AI coding tools while keeping credentials and machine-specific configuration out of Git.

This is the configuration I use. Fork it and make it yours rather than expecting it to suit every workstation unchanged.

## What You Get

- Zsh with ZimFW, Starship, fzf, zoxide, completions, and private shared history.
- Homebrew-managed command-line tools including `gh`, `mise`, `ripgrep`, `fd`, `bat`, `eza`, `delta`, and shell tooling.
- Node, Python, `uv`, `pnpm`, and Ruff through mise, with optional language servers and Terraform or OpenTofu.
- VS Code, Ghostty, MesloLGS Nerd Font, Catppuccin styling, and a baseline of extensions. Existing extensions are retained.
- Git defaults that leave authentication, signing, and unrelated host configuration alone, plus optional per-repository GitHub profiles.
- Claude Code and OpenCode with shared skills and practical safety guardrails. No global MCP servers or global AI instruction files are installed.

Chezmoi owns configuration and platform differences. Homebrew supplies shared tools on both platforms; apt installs Linux prerequisites and VS Code.

## Supported Platforms

- Apple Silicon macOS.
- Debian and Ubuntu desktops.

Ghostty is installed as a Homebrew cask on macOS. On Linux, its package installer supports Ubuntu 24.04+ and Debian Trixie; install Ghostty manually on older Debian releases before bootstrapping.

## Install

Read the bootstrap script before granting it access to your machine. The preflight command reports the platform branch, available prerequisites, managed paths, and bootstrap phases without making changes:

```sh
curl -fsSL https://raw.githubusercontent.com/M0rtalPhe0nix/dotfiles/main/bootstrap.sh | /bin/sh -s -- --preflight
```

When ready, run the installer:

```sh
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/M0rtalPhe0nix/dotfiles/main/bootstrap.sh)"
```

On first use, it:

1. Asks for Git author details and optional developer tooling choices.
2. Installs platform prerequisites, Homebrew, and Chezmoi when needed.
3. Saves any files that conflict with managed paths under `~/.local/state/dotfiles/pre-bootstrap/`.
4. Applies configuration, packages, runtimes, fonts, and the VS Code extension baseline.
5. Offers interactive GitHub, Claude Code, and OpenCode authentication.

Restart the terminal after bootstrap, then confirm the result:

```sh
dotfiles doctor
```

Rerunning bootstrap is safe: it fast-forwards the existing Chezmoi source and reapplies configuration. It refuses to discard divergent source changes.

### Skip Claude Code

Claude Code is an optional first-run choice. Skip its installation and authentication non-interactively with:

```sh
DOTFILES_SKIP_CLAUDE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/M0rtalPhe0nix/dotfiles/main/bootstrap.sh)"
```

## Daily Use

```sh
dotfiles diff                   # Preview managed-file changes
dotfiles apply                  # Apply configuration only; does not upgrade software
dotfiles doctor                 # Check tools, authentication, fonts, permissions, and drift
dotfiles update                 # Update managed packages, runtimes, extensions, and Zim modules
dotfiles rollback               # Restore pre-bootstrap files; keeps installed software
dotfiles extensions             # Merge installed VS Code extensions into the baseline
dotfiles extensions --overwrite # Replace the baseline with installed extensions
dotfiles preferences            # Confirm and apply curated macOS preferences
```

`dotfiles apply` deliberately does not update software. Use `dotfiles update` when you intend to upgrade packages and runtimes.

### macOS Preferences

`dotfiles preferences` is an opt-in Darwin-only command. It never runs during bootstrap or `dotfiles apply`, and asks for confirmation before changing anything. Entering anything other than `y`, `Y`, `yes`, or `YES` leaves preferences unchanged.

The command has a deliberately small, developer-focused scope. It applies only these reversible user preferences:

- Disables automatic capitalization, dash, period, quote, and spelling substitutions (`NSAutomaticCapitalizationEnabled`, `NSAutomaticDashSubstitutionEnabled`, `NSAutomaticPeriodSubstitutionEnabled`, `NSAutomaticQuoteSubstitutionEnabled`, and `NSAutomaticSpellingCorrectionEnabled`) to avoid code being altered while typing.
- Shows Finder filename extensions, the path bar, and the status bar (`AppleShowAllExtensions`, `ShowPathbar`, and `ShowStatusBar`). Relaunch Finder to see these visibility settings.
- Sets the initial keyboard repeat delay to `15` and repeat rate to `2` (`InitialKeyRepeat` and `KeyRepeat`).

It does not manage other macOS, locale, host, or application preferences. Running the command again safely writes the same values.

## Local Configuration

Keep personal changes out of this repository:

- Put machine-specific Zsh customizations in `~/.config/zsh/local.zsh`.
- Put secrets in `~/.config/zsh/secrets.zsh`. Chezmoi creates this file with mode `0600` and never tracks its contents.
- Git identity choices are stored in local Chezmoi data. GitHub tokens remain in the GitHub CLI credential store.

## GitHub Profiles

Use profiles when different repositories need different Git authors and GitHub accounts. Authenticate each account once, then add a local profile:

```sh
github-profile add personal M0rtalPhe0nix personal@example.com
github-profile add work work-login work@example.com "Your Name"
```

Select a profile from within a repository:

```sh
github-profile use work
github-profile current
github-profile list
```

The selected identity and GitHub account are saved in that repository's local Git config. Profile definitions are local files with restricted permissions; tokens are never written to them.

## Corporate CA Certificates

Bootstrap can install a PEM-encoded corporate CA into the system and common CLI trust stores. The certificate and its path remain local, never in this public repository.

If the CA is required to download Homebrew or Chezmoi, provide it before bootstrap:

```sh
export DOTFILES_CORPORATE_CA_PATH=/absolute/path/to/corporate-ca.pem
/bin/bash -c "$(curl --cacert "$DOTFILES_CORPORATE_CA_PATH" -fsSL https://raw.githubusercontent.com/M0rtalPhe0nix/dotfiles/main/bootstrap.sh)"
```

The certificate must not contain a private key. Keep the source PEM at that path so later applies can detect rotations. Restart graphical applications and Docker Desktop after an initial installation or rotation; containers require their own CA setup.

## Repository Development

Run the local checks after changing managed configuration or bootstrap behavior:

```sh
tests/validate.sh
tests/debian-smoke.sh
tests/zsh-startup.sh
```

The checks cover shell formatting and linting, rendered configuration and JSON, OpenCode configuration, secret signatures, Chezmoi rendering and a second clean apply, Debian/Ubuntu package-script smoke tests, and Zsh startup time. Validation is intentionally local; this repository has no GitHub Actions workflow.

## License

[MIT](LICENSE)
