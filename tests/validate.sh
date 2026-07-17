#!/bin/sh
set -eu

root="$(CDPATH='' cd -- "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT INT TERM

shellcheck "$root/bootstrap.sh" "$root/tests/render-macos.sh" "$root/tests/debian-smoke.sh" "$root/tests/validate.sh"
shfmt -d "$root/bootstrap.sh" "$root/tests/render-macos.sh" "$root/tests/debian-smoke.sh" "$root/tests/validate.sh"

for file in \
	"$root/opencode.json" \
	"$root/dot_claude/settings.json" \
	"$root/dot_config/opencode/opencode.json" \
	"$root/Library/Application Support/Code/User/settings.json" \
	"$root/Library/Application Support/Code/User/keybindings.json" \
	"$root/dot_config/Code/User/settings.json" \
	"$root/dot_config/Code/User/keybindings.json"; do
	jq empty "$file"
done

if command -v opencode >/dev/null 2>&1; then
	OPENCODE_CONFIG="$root/dot_config/opencode/opencode.json" OPENCODE_DISABLE_PROJECT_CONFIG=1 opencode debug config >/dev/null
fi

cat >"$tmp/chezmoi.toml" <<'EOF'
[data]
gitName = "Dotfiles Test"
gitEmail = "dotfiles@example.invalid"
installClaude = true
EOF
for source in \
	"$root/run_once_before_00-backup.sh.tmpl" \
	"$root/run_once_before_10-packages.sh.tmpl" \
	"$root/run_once_after_10-git-config.sh.tmpl" \
	"$root/run_after_30-mise.sh.tmpl" \
	"$root/run_once_after_40-vscode-extensions.sh.tmpl" \
	"$root/dot_local/bin/executable_dotfiles.tmpl"; do
	output="$tmp/$(basename "$source" .tmpl)"
	chezmoi --source "$root" --config "$tmp/chezmoi.toml" execute-template <"$source" >"$output"
	shellcheck "$output"
	shfmt -d "$output"
done

cat >"$tmp/chezmoi-skip-claude.toml" <<'EOF'
[data]
gitName = "Dotfiles Test"
gitEmail = "dotfiles@example.invalid"
installClaude = false
EOF
chezmoi --source "$root" --config "$tmp/chezmoi-skip-claude.toml" execute-template \
	<"$root/run_once_before_10-packages.sh.tmpl" >"$tmp/packages-without-claude.sh"
if rg -q 'claude\.ai/install' "$tmp/packages-without-claude.sh"; then
	printf '%s\n' "Claude installer rendered when installation was disabled." >&2
	exit 1
fi

if rg -n --hidden --glob '!.git/**' --glob '!tests/validate.sh' \
	'(ghp_[A-Za-z0-9]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN (RSA |OPENSSH )?PRIVATE KEY-----)' "$root"; then
	printf '%s\n' "Potential secret detected." >&2
	exit 1
fi

"$root/tests/render-macos.sh"
