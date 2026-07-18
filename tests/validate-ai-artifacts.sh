#!/bin/sh
set -eu

root="$(CDPATH='' cd -- "$(dirname "$0")/.." && pwd)"
json=false

while [ "$#" -gt 0 ]; do
	case "$1" in
	--json) json=true ;;
	--root)
		shift
		root="$1"
		;;
	*)
		printf '%s\n' "usage: validate-ai-artifacts.sh [--json] [--root PATH]" >&2
		exit 2
		;;
	esac
	shift
done

tmp="$(mktemp -d)"
errors="$tmp/errors"
warnings="$tmp/warnings"
hooks="$tmp/hooks"
trap 'rm -rf "$tmp"' EXIT INT TERM
: >"$errors"
: >"$warnings"
: >"$hooks"

error() {
	printf '%s\n' "$1" >>"$errors"
}

frontmatter() {
	awk '
		NR == 1 {
			if ($0 != "---") exit 1
			next
		}
		$0 == "---" {
			found = 1
			exit
		}
		{ print }
		END {
			if (!found) exit 1
		}
	' "$1"
}

yaml_value() {
	frontmatter "$1" | yq -r "$2" 2>/dev/null
}

validate_skill() {
	skill_file="$1"
	skill_dir="$(basename "$(dirname "$skill_file")")"
	relative="${skill_file#"$root"/}"
	metadata="$(frontmatter "$skill_file" 2>/dev/null || true)"
	if [ -z "$metadata" ] || ! printf '%s\n' "$metadata" | yq -e '.' >/dev/null 2>&1; then
		error "$relative: malformed YAML frontmatter"
		return
	fi
	name="$(printf '%s\n' "$metadata" | yq -r '.name // ""')"
	description="$(printf '%s\n' "$metadata" | yq -r '.description // ""')"
	[ "$name" = "$skill_dir" ] || error "$relative: name must match skill directory"
	[ -n "$description" ] || error "$relative: description is required"

	symlink="$root/dot_claude/skills/symlink_$skill_dir.tmpl"
	if [ ! -f "$symlink" ]; then
		error "$relative: managed skill symlink is missing"
	elif [ "$(cat "$symlink")" != "{{ .chezmoi.sourceDir }}/.claude/skills/$skill_dir" ]; then
		error "${symlink#"$root"/}: unexpected skill target"
	fi

	agent_manifest="$(dirname "$skill_file")/agents/openai.yaml"
	if [ -f "$agent_manifest" ] && ! yq -e '.interface.display_name != "" and .interface.short_description != ""' "$agent_manifest" >/dev/null 2>&1; then
		error "${agent_manifest#"$root"/}: invalid OpenAI agent interface"
	fi
}

validate_agent() {
	agent="$1"
	relative="${agent#"$root"/}"
	metadata="$(frontmatter "$agent" 2>/dev/null || true)"
	if [ -z "$metadata" ] || ! printf '%s\n' "$metadata" | yq -e '.' >/dev/null 2>&1; then
		error "$relative: malformed YAML frontmatter"
		return
	fi
	name="$(printf '%s\n' "$metadata" | yq -r '.name // ""')"
	[ "$name" = "$(basename "$agent" .md)" ] || error "$relative: name must match filename"
	for field in description tools model permissionMode; do
		value="$(printf '%s\n' "$metadata" | yq -r ".${field} // \"\"")"
		[ -n "$value" ] || error "$relative: $field is required"
	done
	skills="$(printf '%s\n' "$metadata" | yq -r '.skills[]?')"
	[ -n "$skills" ] || error "$relative: at least one skill is required"
	while IFS= read -r skill; do
		[ -n "$skill" ] || continue
		[ -f "$root/.claude/skills/$skill/SKILL.md" ] || error "$relative: unknown skill $skill"
		[ -f "$root/dot_claude/skills/symlink_$skill.tmpl" ] || error "$relative: skill $skill is not managed"
	done <<EOF
$skills
EOF
}

validate_settings_file() {
	settings="$1"
	relative="${settings#"$root"/}"
	if ! jq -e '.permissions | (.allow | type == "array") and (.ask | type == "array") and (.deny | type == "array")' "$settings" >/dev/null 2>&1; then
		error "$relative: invalid permissions structure"
	fi
	if ! jq -e '
		.hooks.PostToolUse |
		type == "array" and length > 0 and
		all(
			.matcher == "Write|Edit|MultiEdit" and
			(.hooks | type == "array" and length > 0 and all(.type == "command" and (.command | type == "string")))
		)
	' "$settings" >/dev/null 2>&1; then
		error "$relative: invalid PostToolUse hook structure"
		return
	fi
	jq -r '.hooks.PostToolUse[] | .hooks[] | .command' "$settings" |
		while IFS= read -r command; do
			case "$command" in
			"~"/.claude/hooks/*) ;;
			*)
				error "$relative: hook command must use ~/.claude/hooks/"
				continue
				;;
			esac
			hook_name="$(printf '%s' "$command" | sed 's#^~/.claude/hooks/##')"
			case "$hook_name" in
			"" | */* | *[!A-Za-z0-9._-]*)
				error "$relative: unsafe hook command"
				continue
				;;
			esac
			hook="$root/dot_claude/hooks/executable_$hook_name"
			if [ ! -f "$hook" ]; then
				error "$relative: managed hook $hook_name is missing"
				continue
			fi
			printf '%s\n' "$hook_name" >>"$hooks"
			if rg -q '(~/.aws|~/.ssh|secrets\.zsh|\.env)' "$hook"; then
				error "${hook#"$root"/}: reads a protected secret path"
			fi
		done
}

validate_settings() {
	settings_template="$root/dot_claude/settings.json.tmpl"
	settings_json="$root/dot_claude/settings.json"
	if [ -f "$settings_template" ]; then
		for mode in minimal all-lsps; do
			config="$tmp/$mode.toml"
			output="$tmp/$mode.json"
			cat >"$config" <<EOF
[data]
installPythonLsp = $([ "$mode" = all-lsps ] && printf true || printf false)
installTypeScriptLsp = $([ "$mode" = all-lsps ] && printf true || printf false)
EOF
			if ! chezmoi --source "$root" --config "$config" execute-template <"$settings_template" >"$output" || ! jq empty "$output"; then
				error "${settings_template#"$root"/}: does not render valid JSON for $mode"
			else
				validate_settings_file "$output"
			fi
		done
	elif [ -f "$settings_json" ]; then
		validate_settings_file "$settings_json"
	else
		error "dot_claude/settings.json: missing"
	fi
}

for skill_file in "$root"/.claude/skills/*/SKILL.md; do
	[ -f "$skill_file" ] || continue
	validate_skill "$skill_file"
done

for agent in "$root"/dot_claude/agents/*.md; do
	[ -f "$agent" ] || continue
	validate_agent "$agent"
done

validate_settings

for hook in "$root"/dot_claude/hooks/executable_*; do
	[ -f "$hook" ] || continue
	hook_name="${hook##*/executable_}"
	if ! rg -Fxq "$hook_name" "$hooks"; then
		error "${hook#"$root"/}: orphan managed hook"
	fi
done

if [ -s "$errors" ]; then
	status="FAIL"
elif [ -s "$warnings" ]; then
	status="PASS-WITH-WARNINGS"
else
	status="PASS"
fi

if [ "$json" = true ]; then
	errors_json="$(jq -Rsc 'split("\n") | map(select(length > 0))' "$errors")"
	warnings_json="$(jq -Rsc 'split("\n") | map(select(length > 0))' "$warnings")"
	jq -n --arg status "$status" --argjson errors "$errors_json" --argjson warnings "$warnings_json" \
		'{status: $status, errors: $errors, warnings: $warnings}'
else
	printf '%s\n' "$status"
	cat "$errors" "$warnings"
fi

[ "$status" != FAIL ]
