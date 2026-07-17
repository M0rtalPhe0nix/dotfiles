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
infraTool = "terraform"
installClaude = true
EOF
for source in \
	"$root/.chezmoiscripts/run_once_before_00-backup.sh.tmpl" \
	"$root/.chezmoiscripts/run_once_before_10-packages.sh.tmpl" \
	"$root/.chezmoiscripts/run_once_after_10-git-config.sh" \
	"$root/.chezmoiscripts/run_after_30-mise.sh" \
	"$root/.chezmoiscripts/run_once_after_40-vscode-extensions.sh.tmpl" \
	"$root/dot_local/bin/executable_dotfiles.tmpl" \
	"$root/dot_local/bin/executable_github-profile" \
	"$root/dot_local/bin/executable_git-credential-gh-profile"; do
	output="$tmp/$(basename "$source" .tmpl)"
	chezmoi --source "$root" --config "$tmp/chezmoi.toml" execute-template <"$source" >"$output"
	shellcheck "$output"
	shfmt -d "$output"
done

cat >"$tmp/chezmoi-skip-claude.toml" <<'EOF'
[data]
gitName = "Dotfiles Test"
gitEmail = "dotfiles@example.invalid"
infraTool = "none"
installClaude = false
EOF
chezmoi --source "$root" --config "$tmp/chezmoi-skip-claude.toml" execute-template \
	<"$root/.chezmoiscripts/run_once_before_10-packages.sh.tmpl" >"$tmp/packages-without-claude.sh"
if rg -q 'claude\.ai/install' "$tmp/packages-without-claude.sh"; then
	printf '%s\n' "Claude installer rendered when installation was disabled." >&2
	exit 1
fi

chezmoi --source "$root" --config "$tmp/chezmoi.toml" execute-template \
	<"$root/dot_config/mise/config.toml.tmpl" >"$tmp/mise-terraform.toml"
rg -q '^terraform = "1\.5\.7"$' "$tmp/mise-terraform.toml"
if rg -q '^opentofu =' "$tmp/mise-terraform.toml"; then
	printf '%s\n' "OpenTofu rendered for the Terraform selection." >&2
	exit 1
fi

chezmoi --source "$root" --config "$tmp/chezmoi-skip-claude.toml" execute-template \
	<"$root/dot_config/mise/config.toml.tmpl" >"$tmp/mise-none.toml"
if rg -q '^(terraform|opentofu) =' "$tmp/mise-none.toml"; then
	printf '%s\n' "An infrastructure tool rendered for the none selection." >&2
	exit 1
fi

cat >"$tmp/chezmoi-opentofu.toml" <<'EOF'
[data]
gitName = "Dotfiles Test"
gitEmail = "dotfiles@example.invalid"
infraTool = "opentofu"
installClaude = false
EOF
chezmoi --source "$root" --config "$tmp/chezmoi-opentofu.toml" execute-template \
	<"$root/dot_config/mise/config.toml.tmpl" >"$tmp/mise-opentofu.toml"
rg -q '^opentofu = "latest"$' "$tmp/mise-opentofu.toml"
if rg -q '^terraform =' "$tmp/mise-opentofu.toml"; then
	printf '%s\n' "Terraform rendered for the OpenTofu selection." >&2
	exit 1
fi

mkdir -p "$tmp/bin" "$tmp/profile-repo"
cat >"$tmp/bin/gh" <<'EOF'
#!/bin/sh
if [ "$1 $2" = "auth token" ]; then
	printf '%s\n' "test-token"
	exit 0
fi
exit 1
EOF
chmod +x "$tmp/bin/gh"
cp "$root/dot_local/bin/executable_git-credential-gh-profile" "$tmp/bin/git-credential-gh-profile"
chmod +x "$tmp/bin/git-credential-gh-profile"
git -C "$tmp/profile-repo" init -q
PATH="$tmp/bin:$PATH" XDG_CONFIG_HOME="$tmp/config" \
	sh "$root/dot_local/bin/executable_github-profile" add work work-user "work@example.invalid" "Work User"
PATH="$tmp/bin:$PATH" XDG_CONFIG_HOME="$tmp/config" \
	sh -c 'cd "$1" && exec sh "$2" use work' sh "$tmp/profile-repo" "$root/dot_local/bin/executable_github-profile"
test "$(git -C "$tmp/profile-repo" config --local --get user.email)" = "work@example.invalid"
test "$(git -C "$tmp/profile-repo" config --local --get github.profile)" = work
test "$(git -C "$tmp/profile-repo" config --local --get github.user)" = work-user
credential="$(printf 'protocol=https\nhost=github.com\n\n' | PATH="$tmp/bin:$PATH" \
	git -C "$tmp/profile-repo" credential fill)"
printf '%s\n' "$credential" | rg -q '^username=work-user$'
printf '%s\n' "$credential" | rg -q '^password=test-token$'

if rg -n --hidden --glob '!.git/**' --glob '!tests/validate.sh' \
	'(ghp_[A-Za-z0-9]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN (RSA |OPENSSH )?PRIVATE KEY-----)' "$root"; then
	printf '%s\n' "Potential secret detected." >&2
	exit 1
fi

"$root/tests/render-macos.sh"
