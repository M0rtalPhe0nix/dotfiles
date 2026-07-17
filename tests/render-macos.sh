#!/bin/sh
set -eu

root="$(CDPATH='' cd -- "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT INT TERM
mkdir -p "$tmp/home"

cat >"$tmp/chezmoi.toml" <<'EOF'
[data]
gitName = "Dotfiles Test"
gitEmail = "dotfiles@example.invalid"
infraTool = "none"
useCorporateCA = false
corporateCAPath = ""
installClaude = true
EOF

chezmoi --source "$root" --destination "$tmp/home" --config "$tmp/chezmoi.toml" apply --exclude=scripts
chezmoi --source "$root" --destination "$tmp/home" --config "$tmp/chezmoi.toml" apply --exclude=scripts

if [ -n "$(chezmoi --source "$root" --destination "$tmp/home" --config "$tmp/chezmoi.toml" diff --exclude=scripts)" ]; then
	printf '%s\n' "Second apply produced a diff." >&2
	exit 1
fi

test -f "$tmp/home/.zshrc"
if rg -q 'CORPORATE_CA|CA_BUNDLE|CAINFO|PIP_CERT|UV_NATIVE_TLS' "$tmp/home/.zshrc"; then
	printf '%s\n' "Corporate CA environment rendered when it was disabled." >&2
	exit 1
fi
test -x "$tmp/home/.local/bin/dotfiles"
test -x "$tmp/home/.local/bin/github-profile"
test -x "$tmp/home/.local/bin/git-credential-gh-profile"
test -f "$tmp/home/.claude/skills/excalidraw/SKILL.md"
test -f "$tmp/home/.config/zsh/local.zsh"
test "$(stat -f %Lp "$tmp/home/.config/zsh/secrets.zsh")" = 600
test ! -e "$tmp/home/create_dot_config"
test ! -e "$tmp/home/create_private_dot_config"
printf '%s\n' "macOS render and idempotence passed"
