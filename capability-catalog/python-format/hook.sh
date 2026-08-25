#!/bin/sh
set -eu

command -v jq >/dev/null 2>&1 || exit 0
command -v ruff >/dev/null 2>&1 || exit 0

input="$(cat)"
files="$(printf '%s' "$input" | jq -r '
  .tool_input.file_path // .tool_input.path // empty,
  (.tool_input.command // empty | split("\n")[] |
    select(test("^\\*\\*\\* (Add|Update) File: ")) |
    sub("^\\*\\*\\* (Add|Update) File: "; ""))
' 2>/dev/null | LC_ALL=C sort -u)"

printf '%s\n' "$files" | while IFS= read -r file; do
	case "$file" in
	"" | *.py) ;;
	*) continue ;;
	esac
	[ -f "$file" ] && [ ! -L "$file" ] || continue
	if ! output="$(ruff format -- "$file" 2>&1)"; then
		jq -n \
			--arg reason "ruff format failed on $file. Inspect and fix:\n\n$output" \
			'{decision: "block", reason: $reason, suppressOutput: true}'
		exit 2
	fi
done
