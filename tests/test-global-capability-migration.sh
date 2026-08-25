#!/bin/sh
set -eu

root="$(CDPATH='' cd -- "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT INT TERM
home="$tmp/home"
state="$tmp/state"
mkdir -p "$home/.claude/skills/code-review" "$home/.claude/agents" "$home/.claude/hooks" "$home/.local/bin" "$tmp/bin"

sort "$root/global-capabilities.managed" >"$tmp/actual-managed"
test "$(wc -l <"$tmp/actual-managed")" -eq "$(sort -u "$root/global-capabilities.managed" | wc -l)"
rg -Fxq '.claude/skills/code-review' "$tmp/actual-managed"
rg -Fxq '.claude/skills/grilling' "$tmp/actual-managed"
rg -Fxq '.claude/agents/feature-diagrammer.md' "$tmp/actual-managed"
rg -Fxq '.claude/hooks/post-edit-fmt.sh' "$tmp/actual-managed"
if rg -v '^\.claude/(skills/[A-Za-z0-9._-]+|agents/feature-diagrammer\.md|hooks/post-edit-fmt\.sh)$' "$tmp/actual-managed"; then
	printf '%s\n' "Managed capability manifest contains an unsafe or unrelated path." >&2
	exit 1
fi

cat >"$tmp/chezmoi.toml" <<'EOF'
[data]
gitName = "Dotfiles Test"
gitEmail = "dotfiles@example.invalid"
infraTool = "none"
useCorporateCA = false
corporateCAPath = ""
installClaude = true
EOF

chezmoi --source "$root" --config "$tmp/chezmoi.toml" execute-template \
	<"$root/.chezmoiscripts/run_once_before_00-backup.sh.tmpl" >"$tmp/backup.sh"
chezmoi --source "$root" --config "$tmp/chezmoi.toml" execute-template \
	<"$root/.chezmoiscripts/run_once_before_01-remove-global-capabilities.sh.tmpl" >"$tmp/remove-global-capabilities.sh"
chezmoi --source "$root" --config "$tmp/chezmoi.toml" execute-template \
	<"$root/dot_local/bin/executable_dotfiles.tmpl" >"$tmp/dotfiles"
chmod +x "$tmp/backup.sh" "$tmp/remove-global-capabilities.sh" "$tmp/dotfiles"

cat >"$tmp/bin/chezmoi" <<EOF
#!/bin/sh
if [ "\${1:-}" = source-path ]; then
	printf '%s\n' "$root"
	exit 0
fi
exit 1
EOF
chmod +x "$tmp/bin/chezmoi"

ln -s "$root/.claude/skills/grilling" "$home/.claude/skills/grilling"
printf '%s\n' "locally modified managed skill" >"$home/.claude/skills/code-review/SKILL.md"
ln -s /opt/user/skill "$home/.claude/skills/user-link"
mkdir -p "$home/.claude/skills/user-directory"
printf '%s\n' "unmanaged directory" >"$home/.claude/skills/user-directory/SKILL.md"
printf '%s\n' "modified managed agent" >"$home/.claude/agents/feature-diagrammer.md"
printf '%s\n' "modified managed hook" >"$home/.claude/hooks/post-edit-fmt.sh"
printf '%s\n' "installed software stays" >"$home/.local/bin/software-sentinel"

HOME="$home" XDG_STATE_HOME="$state" "$tmp/backup.sh" >"$tmp/backup-output"
backup="$state/dotfiles/pre-bootstrap/latest"
test -d "$backup"
rg -Fxq '.claude/skills/grilling' "$backup/managed-capabilities"
rg -Fxq '.claude/agents/feature-diagrammer.md' "$backup/managed-capabilities"
rg -Fxq '.claude/hooks/post-edit-fmt.sh' "$backup/managed-capabilities"
rg -Fxq '.claude/skills/user-link -> /opt/user/skill' "$backup/suspicious-skill-symlinks"
test -L "$home/.claude/skills/user-link"

HOME="$home" XDG_STATE_HOME="$state" "$tmp/remove-global-capabilities.sh" >"$tmp/removal-output"
test ! -e "$home/.claude/skills/grilling"
test ! -e "$home/.claude/skills/code-review"
test ! -e "$home/.claude/agents/feature-diagrammer.md"
test ! -e "$home/.claude/hooks/post-edit-fmt.sh"
test -L "$home/.claude/skills/user-link"
test -d "$home/.claude/skills/user-directory"
test -f "$home/.local/bin/software-sentinel"
rg -Fq 'Removed 4 managed global capability artifacts' "$tmp/removal-output"

chezmoi --source "$root" --destination "$home" --config "$tmp/chezmoi.toml" apply --exclude=scripts
chezmoi --source "$root" --destination "$home" --config "$tmp/chezmoi.toml" apply --exclude=scripts
test ! -e "$home/.claude/skills/grilling"
test ! -e "$home/.claude/skills/code-review"
test ! -e "$home/.claude/agents/feature-diagrammer.md"
test ! -e "$home/.claude/hooks/post-edit-fmt.sh"
test -z "$(chezmoi --source "$root" --destination "$home" --config "$tmp/chezmoi.toml" diff --exclude=scripts)"

printf 'n\n' | HOME="$home" XDG_STATE_HOME="$state" PATH="$tmp/bin:$PATH" \
	"$tmp/dotfiles" capabilities cleanup-unmanaged-global >"$tmp/declined-output"
rg -Fxq '.claude/skills/user-link -> /opt/user/skill' "$tmp/declined-output"
test -L "$home/.claude/skills/user-link"

printf 'y\n' | HOME="$home" XDG_STATE_HOME="$state" PATH="$tmp/bin:$PATH" \
	"$tmp/dotfiles" capabilities cleanup-unmanaged-global >"$tmp/accepted-output"
test ! -e "$home/.claude/skills/user-link"
test -d "$home/.claude/skills/user-directory"
test ! -e "$home/.claude/skills/grilling"
test ! -e "$home/.claude/skills/code-review"
HOME="$home" XDG_STATE_HOME="$state" PATH="$tmp/bin:$PATH" "$tmp/dotfiles" rollback >"$tmp/rollback-output"

test -L "$home/.claude/skills/grilling"
rg -Fxq 'locally modified managed skill' "$home/.claude/skills/code-review/SKILL.md"
test "$(cat "$home/.claude/agents/feature-diagrammer.md")" = "modified managed agent"
test "$(cat "$home/.claude/hooks/post-edit-fmt.sh")" = "modified managed hook"
test "$(readlink "$home/.claude/skills/user-link")" = /opt/user/skill
test "$(cat "$home/.local/bin/software-sentinel")" = "installed software stays"
rg -Fq 'installed packages were retained' "$tmp/rollback-output"

printf '%s\n' "global capability migration backup and rollback passed"
