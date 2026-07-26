# Suggested Commands

- Full local validation: `tests/validate.sh`
- Debian smoke validation: `tests/debian-smoke.sh`
- Managed Zsh startup/performance validation: `tests/zsh-startup.sh`
- Whitespace validation: `git diff --check`
- Apply selected targets from this checkout rather than another configured source: `chezmoi --source "$PWD" apply <targets>`
- Render a template from this checkout: `chezmoi --source "$PWD" execute-template < <template>`