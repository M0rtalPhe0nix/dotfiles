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
test -f "$tmp/home/.inputrc"
rg -qx 'set completion-ignore-case on' "$tmp/home/.inputrc"
rg -qx 'set visible-stats on' "$tmp/home/.inputrc"
rg -qx 'set show-all-if-ambiguous on' "$tmp/home/.inputrc"
rg -qx '"\\e\[A": history-search-backward' "$tmp/home/.inputrc"
rg -qx '"\\e\[B": history-search-forward' "$tmp/home/.inputrc"
if rg -q 'CORPORATE_CA|CA_BUNDLE|CAINFO|PIP_CERT|UV_NATIVE_TLS' "$tmp/home/.zshrc"; then
	printf '%s\n' "Corporate CA environment rendered when it was disabled." >&2
	exit 1
fi
test -x "$tmp/home/.local/bin/dotfiles"
test -x "$tmp/home/.local/bin/github-profile"
test -x "$tmp/home/.local/bin/git-credential-gh-profile"
test "$(git config --file "$tmp/home/.config/git/dotfiles.gitconfig" --get core.untrackedCache)" = true
for skill_file in "$root"/.claude/skills/*/SKILL.md; do
	skill="$(basename "$(dirname "$skill_file")")"
	test -f "$tmp/home/.claude/skills/$skill/SKILL.md"
done
test -f "$tmp/home/.claude/agents/feature-diagrammer.md"
test -x "$tmp/home/.claude/hooks/post-edit-fmt.sh"
test ! -e "$tmp/home/.claude/skills/marksman-lsp"
test ! -e "$tmp/home/.claude/skills/terraform-lsp"
jq -e '.hooks.PostToolUse[0].matcher == "Write|Edit|MultiEdit"' "$tmp/home/.claude/settings.json" >/dev/null
test -f "$tmp/home/.config/opencode/agent/feature-diagrammer.md"
test -f "$tmp/home/.config/zsh/local.zsh"
test "$(stat -f %Lp "$tmp/home/.config/zsh/secrets.zsh")" = 600
test -f "$tmp/home/.config/git/ignore"
test "$(git config --file "$tmp/home/.config/git/dotfiles.gitconfig" --get core.excludesFile)" = \~/.config/git/ignore
for pattern in .DS_Store Desktop.ini Thumbs.db '._*' .Spotlight-V100 .Trashes; do
	rg -Fxq "$pattern" "$tmp/home/.config/git/ignore"
done
test "$(wc -l <"$tmp/home/.config/git/ignore")" -eq 6
test ! -e "$tmp/home/create_dot_config"
test ! -e "$tmp/home/create_private_dot_config"
printf '%s\n' "macOS render and idempotence passed"
