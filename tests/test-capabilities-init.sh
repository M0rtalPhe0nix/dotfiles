#!/bin/sh
set -eu

root="$(CDPATH='' cd -- "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT INT TERM
mkdir -p "$tmp/home" "$tmp/bin" "$tmp/repository/nested" "$tmp/outside"

cat >"$tmp/chezmoi.toml" <<'EOF'
[data]
gitName = "Dotfiles Test"
gitEmail = "dotfiles@example.invalid"
infraTool = "none"
useCorporateCA = false
corporateCAPath = ""
installClaude = false
EOF

chezmoi --source "$root" --destination "$tmp/home" --config "$tmp/chezmoi.toml" apply --exclude=scripts

cat >"$tmp/bin/mise" <<'EOF'
#!/bin/sh
set -eu
if [ "$#" -lt 3 ] || [ "$1" != "exec" ] || [ "$2" != "--" ]; then
	printf '%s\n' "unexpected mise invocation: $*" >&2
	exit 1
fi
shift 2
printf '%s\n' "$*" >"$MISE_INVOCATION_LOG"
exec "$@"
EOF
chmod +x "$tmp/bin/mise"

git -C "$tmp/repository" init -q
dotfiles="$tmp/home/.local/bin/dotfiles"
invocation_log="$tmp/mise-invocation"

PATH="$tmp/bin:$PATH" HOME="$tmp/home" MISE_INVOCATION_LOG="$invocation_log" \
	sh -c 'cd "$1" && exec "$2" capabilities init' sh "$tmp/repository/nested" "$dotfiles"

manifest="$tmp/repository/capabilities.json"
lock="$tmp/repository/capabilities.lock.json"
test -f "$manifest"
test -f "$lock"
test ! -e "$tmp/repository/nested/capabilities.json"
jq -e '.schema_version == 1 and .catalogs == [] and .roots == []' "$manifest" >/dev/null
jq -e '.schema_version == 1 and .catalogs == [] and .capabilities == []' "$lock" >/dev/null
rg -q '^uv run --project .*/\.local/share/dotfiles/capabilities --locked python -m dotfiles_capabilities init$' "$invocation_log"

manifest_before="$(cksum "$manifest")"
lock_before="$(cksum "$lock")"
PATH="$tmp/bin:$PATH" HOME="$tmp/home" MISE_INVOCATION_LOG="$invocation_log" \
	sh -c 'cd "$1" && exec "$2" capabilities init' sh "$tmp/repository" "$dotfiles"
test "$(cksum "$manifest")" = "$manifest_before"
test "$(cksum "$lock")" = "$lock_before"

skills_list="$(PATH="$tmp/bin:$PATH" HOME="$tmp/home" MISE_INVOCATION_LOG="$invocation_log" \
	sh -c 'cd "$1" && exec "$2" skills list --json' sh "$tmp/repository" "$dotfiles")"
printf '%s\n' "$skills_list" | jq -e 'type == "array" and length == 0' >/dev/null

if PATH="$tmp/bin:$PATH" HOME="$tmp/home" MISE_INVOCATION_LOG="$invocation_log" \
	sh -c 'cd "$1" && exec "$2" capabilities init' sh "$tmp/outside" "$dotfiles" \
	>"$tmp/outside.stdout" 2>"$tmp/outside.stderr"; then
	printf '%s\n' "capabilities init unexpectedly succeeded outside Git" >&2
	exit 1
fi
rg -qi 'not inside a Git worktree' "$tmp/outside.stderr"
test ! -e "$tmp/outside/capabilities.json"
test ! -e "$tmp/outside/capabilities.lock.json"

test -f "$tmp/home/.local/share/dotfiles/capabilities/pyproject.toml"
test -f "$tmp/home/.local/share/dotfiles/capabilities/uv.lock"
test -f "$tmp/home/.local/share/dotfiles/capabilities/src/dotfiles_capabilities/__main__.py"

printf '%s\n' "capability initialization passed"
