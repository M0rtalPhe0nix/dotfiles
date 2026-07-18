#!/bin/sh
set -eu

root="$(CDPATH='' cd -- "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT INT TERM
hook="$root/dot_claude/hooks/executable_post-edit-fmt.sh"
mkdir -p "$tmp/bin"

printf '%s\n' 'print("ok")' >"$tmp/example.py"
printf '%s\n' 'text' >"$tmp/example.txt"
ln -s "$tmp/example.py" "$tmp/example-link.py"

printf '%s' '{"tool_input":{"file_path":"'"$tmp"'/example.txt"}}' | PATH="$tmp/bin:$PATH" sh "$hook" >"$tmp/non-python"
test ! -s "$tmp/non-python"

printf '%s' '{"tool_input":{"file_path":"'"$tmp"'/example.py"}}' | PATH="$tmp/bin:$PATH" sh "$hook" >"$tmp/no-ruff"
test ! -s "$tmp/no-ruff"

cat >"$tmp/bin/ruff" <<'EOF'
#!/bin/sh
printf '%s\n' "$@" >>"$RUFF_LOG"
if [ "${RUFF_FAIL:-0}" = 1 ]; then
	printf '%s\n' "invalid syntax" >&2
	exit 1
fi
EOF
chmod +x "$tmp/bin/ruff"

: >"$tmp/ruff.log"
printf '%s' '{"tool_input":{"file_path":"'"$tmp"'/example.py"}}' |
	PATH="$tmp/bin:$PATH" RUFF_LOG="$tmp/ruff.log" sh "$hook" >"$tmp/python"
test ! -s "$tmp/python"
test "$(cat "$tmp/ruff.log")" = "format
--
$tmp/example.py"

: >"$tmp/ruff.log"
printf '%s' '{"tool_input":{"file_path":"'"$tmp"'/example-link.py"}}' |
	PATH="$tmp/bin:$PATH" RUFF_LOG="$tmp/ruff.log" sh "$hook" >"$tmp/symlink"
test ! -s "$tmp/symlink"
test ! -s "$tmp/ruff.log"

printf '%s' '{"tool_input":{"file_path":"'"$tmp"'/example.py"}}' |
	PATH="$tmp/bin:$PATH" RUFF_LOG="$tmp/ruff.log" RUFF_FAIL=1 sh "$hook" >"$tmp/failure"
jq -e '.decision == "block" and .suppressOutput == true and (.reason | contains("invalid syntax"))' "$tmp/failure" >/dev/null
