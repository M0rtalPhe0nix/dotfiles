# Tech Stack

- Chezmoi owns source-to-home rendering and templates.
- Homebrew installs shared macOS/Linux CLI tools; apt installs Linux prerequisites; mise manages Node and Python.
- Shell configuration is Zsh with Zim; prompt is Starship.
- Shell scripts are checked with ShellCheck and shfmt; JSON with jq; local tests are shell scripts under `tests/`.
- macOS support is Apple Silicon only; Linux support is Debian/Ubuntu desktop only.