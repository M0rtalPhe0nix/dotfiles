#!/bin/sh
set -eu

root="$(CDPATH='' cd -- "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT INT TERM
home="$tmp/home"
catalog="$tmp/catalog"
repository="$tmp/repository"
mkdir -p "$home" "$tmp/bin" "$catalog/grilling/skill" "$catalog/grill-me/skill" "$repository"

cat >"$tmp/chezmoi.toml" <<'EOF'
[data]
gitName = "Dotfiles Test"
gitEmail = "dotfiles@example.invalid"
infraTool = "none"
useCorporateCA = false
corporateCAPath = ""
installClaude = false
EOF

chezmoi --source "$root" --destination "$home" --config "$tmp/chezmoi.toml" apply --exclude=scripts

cat >"$tmp/bin/mise" <<'EOF'
#!/bin/sh
set -eu
[ "$1" = exec ] && [ "$2" = -- ]
shift 2
exec "$@"
EOF
chmod +x "$tmp/bin/mise"
dotfiles="$home/.local/bin/dotfiles"

cat >"$catalog/grilling/skill/SKILL.md" <<'EOF'
---
name: grilling
description: Ask rigorous questions one at a time.
---

Grill the user one question at a time.
EOF
cat >"$catalog/grilling/capability.json" <<'EOF'
{
  "schema_version": 1,
  "identifier": "acme/portable-ai/grilling",
  "description": "Rigorous one-question-at-a-time interviews",
  "dependencies": {
    "required": [],
    "recommended": [],
    "companions": {"claude": [], "codex": []}
  },
  "targets": {
    "claude": [{"kind": "skill", "source": "skill", "destination": ".claude/skills/grilling"}],
    "codex": [{"kind": "skill", "source": "skill", "destination": ".agents/skills/grilling"}]
  }
}
EOF
cat >"$catalog/grill-me/skill/SKILL.md" <<'EOF'
---
name: grill-me
description: Stress-test a plan through grilling.
---

Use the grilling skill to stress-test a plan.
EOF
cat >"$catalog/grill-me/capability.json" <<'EOF'
{
  "schema_version": 1,
  "identifier": "acme/portable-ai/grill-me",
  "description": "Entry point for plan grilling",
  "dependencies": {
    "required": ["acme/portable-ai/grilling"],
    "recommended": [],
    "companions": {"claude": [], "codex": []}
  },
  "targets": {
    "claude": [{"kind": "skill", "source": "skill", "destination": ".claude/skills/grill-me"}],
    "codex": [{"kind": "skill", "source": "skill", "destination": ".agents/skills/grill-me"}]
  }
}
EOF

PATH="$tmp/bin:$PATH" HOME="$home" "$dotfiles" capabilities validate "$catalog"
git -C "$catalog" init -q
git -C "$catalog" config user.name "Capability Test"
git -C "$catalog" config user.email "capability@example.invalid"
git -C "$catalog" add .
git -C "$catalog" commit -qm "Create local catalog"
catalog_commit="$(git -C "$catalog" rev-parse HEAD)"

git -C "$repository" init -q
PATH="$tmp/bin:$PATH" HOME="$home" sh -c 'cd "$1" && "$2" capabilities init' sh "$repository" "$dotfiles"
rm "$repository/capabilities.lock.json"
PATH="$tmp/bin:$PATH" HOME="$home" sh -c 'cd "$1" && "$2" capabilities add --catalog "$3" acme/portable-ai/grill-me' sh "$repository" "$dotfiles" "$catalog"

manifest="$repository/capabilities.json"
lock="$repository/capabilities.lock.json"
jq -e --arg catalog "$catalog" '
  .schema_version == 1 and
  .catalogs == [{"url": $catalog}] and
  .roots == ["acme/portable-ai/grill-me"]
' "$manifest" >/dev/null
jq -e --arg catalog "$catalog" --arg commit "$catalog_commit" '
  .schema_version == 1 and
  .catalogs == [{"url": $catalog, "commit": $commit}] and
  (.capabilities | length == 2) and
  ([.capabilities[].identifier] | sort) == ["acme/portable-ai/grill-me", "acme/portable-ai/grilling"] and
  (.capabilities[] | select(.identifier == "acme/portable-ai/grill-me") |
    .source == {"url": $catalog, "commit": $commit} and
    .reason == {"kind": "root"} and
    (.content_hash | test("^[0-9a-f]{64}$")) and
    (.targets | map({tool, path, state}) | sort_by(.tool)) == [
      {"tool": "claude", "path": ".claude/skills/grill-me", "state": "relative-symlink"},
      {"tool": "codex", "path": ".agents/skills/grill-me", "state": "writable-copy"}
    ]) and
  (.capabilities[] | select(.identifier == "acme/portable-ai/grilling") |
    .reason == {"kind": "required", "by": ["acme/portable-ai/grill-me"]})
' "$lock" >/dev/null

for name in grill-me grilling; do
	test -f "$repository/.agents/skills/$name/SKILL.md"
	test -w "$repository/.agents/skills/$name/SKILL.md"
	test -L "$repository/.claude/skills/$name"
	test "$(readlink "$repository/.claude/skills/$name")" = "../../.agents/skills/$name"
done

sed '/^[[:space:]]*#/d; /^[[:space:]]*$/d' "$repository/.git/info/exclude" >"$tmp/excludes.actual"
cat >"$tmp/excludes.expected" <<'EOF'
/.agents/skills/grill-me/
/.agents/skills/grilling/
/.claude/skills/grill-me
/.claude/skills/grilling
EOF
diff -u "$tmp/excludes.expected" "$tmp/excludes.actual"

printf '%s\n' "drift" >"$repository/.agents/skills/grill-me/SKILL.md"
printf '%s\n' "unexpected" >"$repository/.agents/skills/grill-me/UNEXPECTED.md"
rm "$repository/.claude/skills/grilling"
mkdir -p "$repository/.claude/skills/grilling"
printf '%s\n' "collision" >"$repository/.claude/skills/grilling/SKILL.md"

PATH="$tmp/bin:$PATH" HOME="$home" sh -c 'cd "$1" && "$2" capabilities sync' sh "$repository" "$dotfiles"
cmp "$catalog/grill-me/skill/SKILL.md" "$repository/.agents/skills/grill-me/SKILL.md"
test ! -e "$repository/.agents/skills/grill-me/UNEXPECTED.md"
test -L "$repository/.claude/skills/grilling"
test "$(readlink "$repository/.claude/skills/grilling")" = "../../.agents/skills/grilling"
test "$(git -C "$repository" status --short)" = "?? capabilities.json
?? capabilities.lock.json"

failed_repository="$tmp/failed-repository"
mkdir -p "$failed_repository" "$tmp/outside-agents"
git -C "$failed_repository" init -q
PATH="$tmp/bin:$PATH" HOME="$home" sh -c 'cd "$1" && "$2" capabilities init' sh "$failed_repository" "$dotfiles"
rm "$failed_repository/capabilities.lock.json"
ln -s "$tmp/outside-agents" "$failed_repository/.agents"
if PATH="$tmp/bin:$PATH" HOME="$home" \
	sh -c 'cd "$1" && "$2" capabilities add --catalog "$3" acme/portable-ai/grill-me' \
	sh "$failed_repository" "$dotfiles" "$catalog" >"$tmp/failed.stdout" 2>"$tmp/failed.stderr"; then
	printf '%s\n' "capability add unexpectedly succeeded after materialization failure" >&2
	exit 1
fi
rg -q 'materialization parent is a symlink' "$tmp/failed.stderr"
test ! -e "$failed_repository/capabilities.lock.json"
jq -e '.catalogs == [] and .roots == []' "$failed_repository/capabilities.json" >/dev/null
test -z "$(find "$tmp/outside-agents" -mindepth 1 -print -quit)"

printf '%s\n' "capability add and synchronization passed"
