# Core

- Public `M0rtalPhe0nix/dotfiles` repository managed by Chezmoi; targets Apple Silicon macOS and Debian/Ubuntu desktops.
- Treat every tracked file as public; never add secrets, machine identifiers, credentials, or host-local settings.
- Host-local shell files `~/.config/zsh/local.zsh` and mode-0600 `secrets.zsh` must remain unmanaged.
- Chezmoi source naming and lifecycle invariants are documented in `CLAUDE.md`.
- Tooling and platform details: `mem:tech_stack`.
- Repository-specific practices: `mem:conventions`.
- Validation requirements: `mem:task_completion`.