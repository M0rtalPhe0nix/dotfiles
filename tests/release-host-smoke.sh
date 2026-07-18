#!/bin/sh
set -eu

fail() {
	printf '%s\n' "$*" >&2
	exit 1
}

case "$(uname -s)" in
Darwin)
	[ "$(uname -m)" = arm64 ] || fail "Apple Silicon macOS is required."
	vscode_config="$HOME/Library/Application Support/Code/User/settings.json"
	;;
Linux)
	[ -r /etc/os-release ] || fail "Cannot identify the Linux distribution."
	# shellcheck disable=SC1091
	. /etc/os-release
	case "${ID:-}" in
	debian | ubuntu) ;;
	*) fail "Debian or Ubuntu is required." ;;
	esac
	vscode_config="$HOME/.config/Code/User/settings.json"
	;;
*) fail "Unsupported operating system: $(uname -s)" ;;
esac

source_dir="$(chezmoi source-path)"
[ -d "$source_dir/.git" ] || fail "Chezmoi source is not a Git repository: $source_dir"
dotfiles_bin="$HOME/.local/bin/dotfiles"
[ -x "$dotfiles_bin" ] || fail "Managed dotfiles command is missing: $dotfiles_bin"

"$dotfiles_bin" doctor

if drift="$("$dotfiles_bin" diff)"; then
	:
else
	fail "dotfiles diff failed."
fi
if [ -n "$drift" ]; then
	printf '%s\n' "$drift" >&2
	fail "Managed files have drifted."
fi

test -f "$HOME/.inputrc"
grep -Fxq 'set completion-ignore-case on' "$HOME/.inputrc"
grep -Fxq 'set visible-stats on' "$HOME/.inputrc"
test "$(git config --file "$HOME/.config/git/dotfiles.gitconfig" --get core.untrackedCache)" = true
tilde='~'
expected_excludes_file="$tilde/.config/git/ignore"
test "$(git config --file "$HOME/.config/git/dotfiles.gitconfig" --get core.excludesFile)" = "$expected_excludes_file"
test -f "$HOME/.config/git/ignore"
test -f "$vscode_config"

mode="$(stat -f %Lp "$HOME/.config/zsh/secrets.zsh" 2>/dev/null || stat -c %a "$HOME/.config/zsh/secrets.zsh")"
test "$mode" = 600
zsh -lic 'command -v o >/dev/null'
code --list-extensions >/dev/null

for skill_file in "$source_dir"/.claude/skills/*/SKILL.md; do
	skill="$(basename "$(dirname "$skill_file")")"
	test -f "$HOME/.claude/skills/$skill/SKILL.md"
done

printf '%s\n' "Release host smoke test passed."
