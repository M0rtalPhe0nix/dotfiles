# Task Completion

- Run the relevant suite; normally `tests/validate.sh`, plus `tests/debian-smoke.sh` for Linux/bootstrap changes and `tests/zsh-startup.sh` for shell startup changes.
- Minimum quality gates: ShellCheck, shfmt, JSON/OpenCode config validation, secret scan, temporary macOS rendering, clean second Chezmoi apply, and Debian rendering/syntax checks.
- Run `git diff --check` before completion.
- Zsh warm startup average must remain below 200 ms on the primary Mac.
- Update README when user-facing commands, bootstrap behavior, managed tools, or choices change; add regression coverage for bootstrap/template/path/platform bug fixes.