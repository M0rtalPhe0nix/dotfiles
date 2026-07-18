#!/bin/sh
set -eu

command -v jq >/dev/null 2>&1 || exit 0
command -v ruff >/dev/null 2>&1 || exit 0

input="$(cat)"
file="$(printf '%s' "$input" | jq -r '.tool_input.file_path // .tool_input.path // empty' 2>/dev/null || true)"

case "$file" in
"" | *.py) ;;
*) exit 0 ;;
esac

[ -f "$file" ] && [ ! -L "$file" ] || exit 0

if ! output="$(ruff format -- "$file" 2>&1)"; then
	jq -n \
		--arg reason "ruff format failed on $file. Inspect and fix:\n\n$output" \
		'{decision: "block", reason: $reason, suppressOutput: true}'
fi
