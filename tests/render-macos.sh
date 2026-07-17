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
EOF

chezmoi --source "$root" --destination "$tmp/home" --config "$tmp/chezmoi.toml" apply --exclude=scripts
chezmoi --source "$root" --destination "$tmp/home" --config "$tmp/chezmoi.toml" apply --exclude=scripts

if [ -n "$(chezmoi --source "$root" --destination "$tmp/home" --config "$tmp/chezmoi.toml" diff --exclude=scripts)" ]; then
	printf '%s\n' "Second apply produced a diff." >&2
	exit 1
fi

test -f "$tmp/home/.zshrc"
test -x "$tmp/home/.local/bin/dotfiles"
test -f "$tmp/home/.claude/skills/excalidraw/SKILL.md"
test -f "$tmp/home/.config/zsh/local.zsh"
test "$(stat -f %Lp "$tmp/home/.config/zsh/secrets.zsh")" = 600
test ! -e "$tmp/home/create_dot_config"
test ! -e "$tmp/home/create_private_dot_config"
printf '%s\n' "macOS render and idempotence passed"
