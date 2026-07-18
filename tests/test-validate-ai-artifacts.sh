#!/bin/sh
set -eu

root="$(CDPATH='' cd -- "$(dirname "$0")/.." && pwd)"

sh "$root/tests/validate-ai-artifacts.sh" --root "$root"
sh "$root/tests/validate-ai-artifacts.sh" --json --root "$root" | jq -e '.status == "PASS" and (.errors | length == 0)'
sh "$root/tests/validate-ai-artifacts.sh" --root "$root/tests/fixtures/ai-artifacts/valid"

for fixture in invalid-frontmatter invalid-wiring; do
	if sh "$root/tests/validate-ai-artifacts.sh" --root "$root/tests/fixtures/ai-artifacts/$fixture" >/dev/null 2>&1; then
		printf '%s\n' "$fixture fixture unexpectedly passed." >&2
		exit 1
	fi
	sh "$root/tests/validate-ai-artifacts.sh" --json --root "$root/tests/fixtures/ai-artifacts/$fixture" |
		jq -e '.status == "FAIL" and (.errors | length > 0)' >/dev/null
done
