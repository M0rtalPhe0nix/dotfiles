#!/bin/sh
set -eu

root="$(CDPATH='' cd -- "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT INT TERM

shellcheck \
	"$root/bootstrap.sh" \
	"$root/capability-catalog/python-format/hook.sh" \
	"$root/capability-catalog/rtk-guardrail/hook.sh" \
	"$root/tests/render-macos.sh" \
	"$root/tests/debian-smoke.sh" \
	"$root/tests/release-host-smoke.sh" \
	"$root/tests/test-bootstrap-preflight.sh" \
	"$root/tests/test-bootstrap-ref.sh" \
	"$root/tests/test-capabilities-init.sh" \
	"$root/tests/test-capabilities-sync.sh" \
	"$root/tests/test-global-capability-migration.sh" \
	"$root/tests/test-debian-packages.sh" \
	"$root/tests/test-macos-preferences.sh" \
	"$root/tests/test-validate-ai-artifacts.sh" \
	"$root/tests/test-vscode-extensions.sh" \
	"$root/tests/validate-ai-artifacts.sh" \
	"$root/tests/validate.sh"
shfmt -d \
	"$root/bootstrap.sh" \
	"$root/capability-catalog/python-format/hook.sh" \
	"$root/capability-catalog/rtk-guardrail/hook.sh" \
	"$root/tests/render-macos.sh" \
	"$root/tests/debian-smoke.sh" \
	"$root/tests/release-host-smoke.sh" \
	"$root/tests/test-bootstrap-preflight.sh" \
	"$root/tests/test-bootstrap-ref.sh" \
	"$root/tests/test-capabilities-init.sh" \
	"$root/tests/test-capabilities-sync.sh" \
	"$root/tests/test-global-capability-migration.sh" \
	"$root/tests/test-debian-packages.sh" \
	"$root/tests/test-macos-preferences.sh" \
	"$root/tests/test-validate-ai-artifacts.sh" \
	"$root/tests/test-vscode-extensions.sh" \
	"$root/tests/validate-ai-artifacts.sh" \
	"$root/tests/validate.sh"

ruff check "$root/dot_local/share/dotfiles/capabilities/src" \
	"$root/tests/test_capability_catalog.py" \
	"$root/tests/test_capability_hooks.py" \
	"$root/tests/test_capability_update.py" \
	"$root/tests/test_capability_workflow.py"

PYTHONPATH="$root/dot_local/share/dotfiles/capabilities/src${PYTHONPATH:+:$PYTHONPATH}" \
	python3 "$root/tests/test_capability_catalog.py"
PYTHONPATH="$root/dot_local/share/dotfiles/capabilities/src${PYTHONPATH:+:$PYTHONPATH}" \
	python3 "$root/tests/test_capability_hooks.py"
PYTHONPATH="$root/dot_local/share/dotfiles/capabilities/src${PYTHONPATH:+:$PYTHONPATH}" \
	python3 "$root/tests/test_capability_update.py"
PYTHONPATH="$root/dot_local/share/dotfiles/capabilities/src${PYTHONPATH:+:$PYTHONPATH}" \
	python3 "$root/tests/test_capability_workflow.py"

test "$(sed -n '1p' "$root/.chezmoiscripts/run_once_after_20-zimfw.sh")" = '#!/usr/bin/env zsh'

for file in \
	"$root/opencode.json" \
	"$root/dot_config/opencode/opencode.json" \
	"$root/dot_config/opencode/tui.json" \
	"$root/Library/Application Support/Code/User/settings.json" \
	"$root/Library/Application Support/Code/User/keybindings.json" \
	"$root/dot_config/Code/User/settings.json" \
	"$root/dot_config/Code/User/keybindings.json"; do
	jq empty "$file"
done

test ! -e "$root/dot_claude/agents/feature-diagrammer.md"
test ! -e "$root/dot_claude/hooks/executable_post-edit-fmt.sh"
if find "$root/dot_claude/skills" -type f -print 2>/dev/null | rg -q .; then
	printf '%s\n' "Retired global Claude skill sources remain managed by Chezmoi." >&2
	exit 1
fi

jq -e '
	.lsp.pyright.command == ["pyright-langserver", "--stdio"] and
	.lsp.typescript.command == ["typescript-language-server", "--stdio"] and
	.lsp.marksman.command == ["marksman", "server"] and
	.lsp.terraform.command == ["terraform-ls", "serve"] and
	.mcp.headroom.command == ["headroom", "mcp", "serve"] and
	.mcp.headroom.enabled == true and
	.mcp.serena.command == ["uvx", "--from", "git+https://github.com/oraios/serena", "serena", "start-mcp-server", "--project-from-cwd", "--context", "agent", "--open-web-dashboard", "False"] and
	.mcp.serena.enabled == true and
	(.plugin | index("@dietrichgebert/ponytail")) != null
' "$root/dot_config/opencode/opencode.json" >/dev/null
test "$(jq -r '.plugin[]' "$root/dot_config/opencode/tui.json")" = "./clear-tui.ts"
rg -Fq 'api.keymap.dispatchCommand("session.new")' "$root/dot_config/opencode/clear-tui.ts"
test -f "$root/dot_config/opencode/command/revise-claude-md.md"

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
	"$root/.chezmoiscripts/run_once_before_01-remove-global-capabilities.sh.tmpl" \
	"$root/.chezmoiscripts/run_before_05-corporate-ca.sh.tmpl" \
	"$root/.chezmoiscripts/run_once_before_10-packages.sh.tmpl" \
	"$root/.chezmoiscripts/run_once_after_10-git-config.sh" \
	"$root/.chezmoiscripts/run_after_30-mise.sh" \
	"$root/.chezmoiscripts/run_after_31-rtk.sh" \
	"$root/.chezmoiscripts/run_after_32-headroom.sh" \
	"$root/.chezmoiscripts/run_after_35-claude-plugins.sh.tmpl" \
	"$root/.chezmoiscripts/run_once_after_40-vscode-extensions.sh.tmpl" \
	"$root/dot_local/bin/executable_dotfiles.tmpl" \
	"$root/dot_local/bin/executable_github-profile" \
	"$root/dot_local/bin/executable_git-credential-gh-profile"; do
	output="$tmp/$(basename "$source" .tmpl)"
	chezmoi --source "$root" --config "$tmp/chezmoi.toml" execute-template <"$source" >"$output"
	shellcheck "$output"
	shfmt -d "$output"
done

sh "$root/tests/test-bootstrap-preflight.sh"
sh "$root/tests/test-bootstrap-ref.sh"
sh "$root/tests/test-capabilities-init.sh"
sh "$root/tests/test-capabilities-sync.sh"
sh "$root/tests/test-global-capability-migration.sh"
sh "$root/tests/test-vscode-extensions.sh"
sh "$root/tests/test-debian-packages.sh"
sh "$root/tests/test-macos-preferences.sh"
sh "$root/tests/test-validate-ai-artifacts.sh"
zsh -f "$root/tests/test-zsh-open-helper.sh"

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
rg -q 'uv tool upgrade headroom-ai' "$tmp/dotfiles-all-lsps"
rg -q 'uv headroom' "$tmp/dotfiles-all-lsps"
rg -q 'headroom rtk' "$tmp/dotfiles-all-lsps"
if rg -q 'rtk init --global --hook-only|rtk hook claude' "$root/.chezmoiscripts/run_after_31-rtk.sh"; then
	printf '%s\n' "The retired global Claude RTK hook is still configured." >&2
	exit 1
fi
rg -q 'rtk init --global --opencode' "$root/.chezmoiscripts/run_after_31-rtk.sh"
chezmoi --source "$root" --config "$tmp/chezmoi-all-lsps.toml" execute-template \
	<"$root/dot_claude/private_settings.json.tmpl" >"$tmp/claude-settings-all-lsps.json"
jq -e '.enabledPlugins["ponytail@ponytail"] and .enabledPlugins["claude-md-management@claude-plugins-official"] and .enabledPlugins["pyright-lsp@claude-plugins-official"] and .enabledPlugins["typescript-lsp@claude-plugins-official"]' "$tmp/claude-settings-all-lsps.json" >/dev/null
jq -e 'has("hooks") | not' "$tmp/claude-settings-all-lsps.json" >/dev/null
jq -e '.extraKnownMarketplaces.ponytail.source.repo == "DietrichGebert/ponytail"' "$tmp/claude-settings-all-lsps.json" >/dev/null
jq -e '.extraKnownMarketplaces["claude-plugins-official"].source.repo == "anthropics/claude-plugins-official"' "$tmp/claude-settings-all-lsps.json" >/dev/null
chezmoi --source "$root" --config "$tmp/chezmoi-all-lsps.toml" execute-template \
	<"$root/.chezmoiscripts/run_after_35-claude-plugins.sh.tmpl" >"$tmp/claude-plugins-all-lsps"
rg -q 'install_plugin claude-md-management@claude-plugins-official' "$tmp/claude-plugins-all-lsps"
rg -q 'install_plugin ponytail@ponytail' "$tmp/claude-plugins-all-lsps"
rg -q 'install_plugin pyright-lsp@claude-plugins-official' "$tmp/claude-plugins-all-lsps"
rg -q 'install_plugin typescript-lsp@claude-plugins-official' "$tmp/claude-plugins-all-lsps"
all_lsp_managed="$(chezmoi --source "$root" --config "$tmp/chezmoi-all-lsps.toml" managed)"
if printf '%s\n' "$all_lsp_managed" | rg -q '^\.claude/(skills|agents/feature-diagrammer\.md|hooks/post-edit-fmt\.sh)'; then
	printf '%s\n' "Chezmoi still manages a retired global Claude capability artifact." >&2
	exit 1
fi

update_body="$(sed -n '/^update() {/,/^}/p' "$root/dot_local/bin/executable_dotfiles.tmpl")"
if printf '%s\n' "$update_body" | rg -q 'dotfiles_capabilities|capabilities[[:space:]]+sync'; then
	printf '%s\n' "dotfiles update must not synchronize repository capabilities." >&2
	exit 1
fi
rg -Fxq 'apply) chezmoi apply ;;' "$root/dot_local/bin/executable_dotfiles.tmpl"

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
if [ "$(uname -s)" = Darwin ]; then
	rg -q 'security add-trusted-cert' "$tmp/corporate-ca.sh"
else
	rg -q 'dotfiles-corporate-ca\.crt' "$tmp/corporate-ca.sh"
fi
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
	sh "$root/dot_local/bin/executable_github-profile" add personal personal-user "personal@example.invalid" "Personal User"
PATH="$tmp/bin:$PATH" XDG_CONFIG_HOME="$tmp/config" \
	sh -c 'cd "$1" && exec sh "$2" use work' sh "$tmp/profile-repo" "$root/dot_local/bin/executable_github-profile"
test "$(git -C "$tmp/profile-repo" config --local --get user.email)" = "work@example.invalid"
test "$(git -C "$tmp/profile-repo" config --local --get github.profile)" = work
test "$(git -C "$tmp/profile-repo" config --local --get github.user)" = work-user
profile_list="$(PATH="$tmp/bin:$PATH" XDG_CONFIG_HOME="$tmp/config" \
	sh -c 'cd "$1" && exec sh "$2" list' sh "$tmp/profile-repo" "$root/dot_local/bin/executable_github-profile")"
printf '%s\n' "$profile_list" | rg -q '^  personal$'
printf '%s\n' "$profile_list" | rg -q '^\* work$'
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
