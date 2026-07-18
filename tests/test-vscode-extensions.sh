#!/bin/sh
set -eu

root="$(CDPATH='' cd -- "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT INT TERM
mkdir -p "$tmp/bin" "$tmp/source"

cat >"$tmp/chezmoi.toml" <<'EOF'
[data]
gitName = "Dotfiles Test"
gitEmail = "dotfiles@example.invalid"
infraTool = "none"
useCorporateCA = false
corporateCAPath = ""
installClaude = false
EOF
chezmoi --source "$root" --config "$tmp/chezmoi.toml" execute-template \
	<"$root/dot_local/bin/executable_dotfiles.tmpl" >"$tmp/dotfiles"

cat >"$tmp/bin/chezmoi" <<EOF
#!/bin/sh
if [ "\$1" = source-path ]; then
	printf '%s\\n' "$tmp/source"
	fi
EOF
cat >"$tmp/bin/code" <<'EOF'
#!/bin/sh
printf '%s\n' "$*" >>"$CODE_LOG"
if [ "$1" = --list-extensions ]; then
	if [ "${CODE_FAIL:-0}" = 1 ]; then
		exit 1
	fi
	printf '%s\n' "$CODE_EXTENSIONS"
	fi
EOF
chmod +x "$tmp/bin/chezmoi" "$tmp/bin/code"

printf '%s\n' z.extension old.extension '' >"$tmp/source/extensions.txt"
: >"$tmp/code.log"
PATH="$tmp/bin:$PATH" CODE_LOG="$tmp/code.log" CODE_EXTENSIONS='new.extension
z.extension
' sh "$tmp/dotfiles" extensions >/dev/null
test "$(cat "$tmp/source/extensions.txt")" = "new.extension
old.extension
z.extension"

PATH="$tmp/bin:$PATH" CODE_LOG="$tmp/code.log" CODE_EXTENSIONS='only.extension' sh "$tmp/dotfiles" extensions --overwrite >/dev/null
test "$(cat "$tmp/source/extensions.txt")" = only.extension

before="$(cat "$tmp/source/extensions.txt")"
if PATH="$tmp/bin:$PATH" CODE_LOG="$tmp/code.log" CODE_FAIL=1 sh "$tmp/dotfiles" extensions >/dev/null 2>&1; then
	printf '%s\n' "Failed VS Code listing unexpectedly succeeded." >&2
	exit 1
fi
test "$(cat "$tmp/source/extensions.txt")" = "$before"
if rg -q -- '--uninstall-extension' "$tmp/code.log"; then
	printf '%s\n' "Extension capture attempted an uninstall." >&2
	exit 1
fi

rm "$tmp/bin/code"
if PATH="$tmp/bin:/usr/bin:/bin" sh "$tmp/dotfiles" extensions >/dev/null 2>&1; then
	printf '%s\n' "Missing VS Code launcher unexpectedly succeeded." >&2
	exit 1
fi
test "$(cat "$tmp/source/extensions.txt")" = "$before"

if PATH="$tmp/bin:$PATH" sh "$tmp/dotfiles" extensions --invalid >/dev/null 2>&1; then
	printf '%s\n' "Invalid extensions option unexpectedly succeeded." >&2
	exit 1
fi
test "$(cat "$tmp/source/extensions.txt")" = "$before"
