#!/bin/sh
set -eu

root="$(CDPATH='' cd -- "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT INT TERM

shellcheck \
	"$root/bootstrap.sh" \
	"$root/dot_claude/hooks/executable_post-edit-fmt.sh" \
	"$root/tests/render-macos.sh" \
	"$root/tests/debian-smoke.sh" \
	"$root/tests/test-bootstrap-preflight.sh" \
	"$root/tests/test-claude-post-edit-hook.sh" \
	"$root/tests/test-debian-packages.sh" \
	"$root/tests/test-macos-preferences.sh" \
	"$root/tests/test-validate-ai-artifacts.sh" \
	"$root/tests/test-vscode-extensions.sh" \
	"$root/tests/validate-ai-artifacts.sh" \
	"$root/tests/validate.sh"
shfmt -d \
	"$root/bootstrap.sh" \
	"$root/dot_claude/hooks/executable_post-edit-fmt.sh" \
	"$root/tests/render-macos.sh" \
	"$root/tests/debian-smoke.sh" \
	"$root/tests/test-bootstrap-preflight.sh" \
	"$root/tests/test-claude-post-edit-hook.sh" \
	"$root/tests/test-debian-packages.sh" \
	"$root/tests/test-macos-preferences.sh" \
	"$root/tests/test-validate-ai-artifacts.sh" \
	"$root/tests/test-vscode-extensions.sh" \
	"$root/tests/validate-ai-artifacts.sh" \
	"$root/tests/validate.sh"

test "$(sed -n '1p' "$root/.chezmoiscripts/run_once_after_20-zimfw.sh")" = '#!/usr/bin/env zsh'

for file in \
	"$root/opencode.json" \
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
useCorporateCA = false
corporateCAPath = ""
installClaude = true
EOF
for source in \
	"$root/.chezmoiscripts/run_once_before_00-backup.sh.tmpl" \
	"$root/.chezmoiscripts/run_before_05-corporate-ca.sh.tmpl" \
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

sh "$root/tests/test-claude-post-edit-hook.sh"
sh "$root/tests/test-bootstrap-preflight.sh"
sh "$root/tests/test-vscode-extensions.sh"
sh "$root/tests/test-debian-packages.sh"
sh "$root/tests/test-macos-preferences.sh"
sh "$root/tests/test-validate-ai-artifacts.sh"

cat >"$tmp/chezmoi-skip-claude.toml" <<'EOF'
[data]
gitName = "Dotfiles Test"
gitEmail = "dotfiles@example.invalid"
infraTool = "none"
useCorporateCA = false
corporateCAPath = ""
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
useCorporateCA = false
corporateCAPath = ""
installClaude = false
EOF
chezmoi --source "$root" --config "$tmp/chezmoi-opentofu.toml" execute-template \
	<"$root/dot_config/mise/config.toml.tmpl" >"$tmp/mise-opentofu.toml"
rg -q '^opentofu = "latest"$' "$tmp/mise-opentofu.toml"
if rg -q '^terraform =' "$tmp/mise-opentofu.toml"; then
	printf '%s\n' "Terraform rendered for the OpenTofu selection." >&2
	exit 1
fi

cat >"$tmp/chezmoi-all-lsps.toml" <<'EOF'
[data]
gitName = "Dotfiles Test"
gitEmail = "dotfiles@example.invalid"
infraTool = "none"
useCorporateCA = false
corporateCAPath = ""
installClaude = true
installPythonLsp = true
installTypeScriptLsp = true
installMarkdownLsp = true
installTerraformLsp = true
EOF
chezmoi --source "$root" --config "$tmp/chezmoi-all-lsps.toml" execute-template \
	<"$root/dot_config/mise/config.toml.tmpl" >"$tmp/mise-all-lsps.toml"
rg -q '^uv = "latest"$' "$tmp/mise-all-lsps.toml"
rg -q '^pnpm = "latest"$' "$tmp/mise-all-lsps.toml"
rg -q '^ruff = "latest"$' "$tmp/mise-all-lsps.toml"
rg -q '^"npm:pyright" = "latest"$' "$tmp/mise-all-lsps.toml"
rg -q '^"npm:typescript-language-server" = "latest"$' "$tmp/mise-all-lsps.toml"
rg -q '^"aqua:artempyanykh/marksman" = "latest"$' "$tmp/mise-all-lsps.toml"
rg -q '^"aqua:hashicorp/terraform-ls" = "latest"$' "$tmp/mise-all-lsps.toml"
chezmoi --source "$root" --config "$tmp/chezmoi-all-lsps.toml" execute-template \
	<"$root/dot_local/bin/executable_dotfiles.tmpl" >"$tmp/dotfiles-all-lsps"
rg -q 'pyright-langserver' "$tmp/dotfiles-all-lsps"
rg -q 'typescript-language-server' "$tmp/dotfiles-all-lsps"
rg -q 'marksman' "$tmp/dotfiles-all-lsps"
rg -q 'terraform-ls' "$tmp/dotfiles-all-lsps"
chezmoi --source "$root" --config "$tmp/chezmoi-all-lsps.toml" execute-template \
	<"$root/dot_claude/settings.json.tmpl" >"$tmp/claude-settings-all-lsps.json"
jq -e '.enabledPlugins["pyright-lsp@claude-plugins-official"] and .enabledPlugins["typescript-lsp@claude-plugins-official"]' "$tmp/claude-settings-all-lsps.json" >/dev/null

cat >"$tmp/chezmoi-corporate-ca.toml" <<'EOF'
[data]
gitName = "Dotfiles Test"
gitEmail = "dotfiles@example.invalid"
infraTool = "none"
useCorporateCA = true
corporateCAPath = "/tmp/Corporate CA.pem"
installClaude = false
EOF
chezmoi --source "$root" --config "$tmp/chezmoi-corporate-ca.toml" execute-template \
	<"$root/.chezmoiscripts/run_before_05-corporate-ca.sh.tmpl" >"$tmp/corporate-ca.sh"
shellcheck "$tmp/corporate-ca.sh"
shfmt -d "$tmp/corporate-ca.sh"
rg -q 'dotfiles-corporate-ca\.crt' "$tmp/corporate-ca.sh"
chezmoi --source "$root" --config "$tmp/chezmoi-corporate-ca.toml" execute-template \
	<"$root/dot_zshrc.tmpl" >"$tmp/zshrc-corporate-ca"
rg -q '^export PIP_CERT=' "$tmp/zshrc-corporate-ca"
rg -q '^export UV_NATIVE_TLS=true$' "$tmp/zshrc-corporate-ca"
rg -q '^export GIT_SSL_CAINFO=' "$tmp/zshrc-corporate-ca"
rg -q '^export NPM_CONFIG_CAFILE=' "$tmp/zshrc-corporate-ca"
rg -q '^export CARGO_HTTP_CAINFO=' "$tmp/zshrc-corporate-ca"

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
