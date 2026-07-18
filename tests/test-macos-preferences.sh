#!/bin/sh
set -eu

root="$(CDPATH='' cd -- "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT INT TERM

cat >"$tmp/chezmoi.toml" <<'EOF'
[data]
gitName = "Dotfiles Test"
gitEmail = "dotfiles@example.invalid"
infraTool = "none"
useCorporateCA = false
corporateCAPath = ""
installClaude = false
EOF

chezmoi --source "$root" --config "$tmp/chezmoi.toml" execute-template \
	<"$root/dot_local/bin/executable_dotfiles.tmpl" >"$tmp/dotfiles"
sh -n "$tmp/dotfiles"

mkdir -p "$tmp/bin"
cat >"$tmp/bin/uname" <<'EOF'
#!/bin/sh
printf '%s\n' "${DOTFILES_TEST_OS:-Darwin}"
EOF
cat >"$tmp/bin/defaults" <<'EOF'
#!/bin/sh
printf '%s\n' "$*" >>"$DOTFILES_DEFAULTS_LOG"
EOF
chmod +x "$tmp/bin/uname" "$tmp/bin/defaults"

if DOTFILES_TEST_OS=Linux PATH="$tmp/bin:$PATH" sh "$tmp/dotfiles" preferences >"$tmp/linux.out" 2>&1; then
	printf '%s\n' "Preferences command ran outside Darwin." >&2
	exit 1
fi
rg -Fq "macOS preferences are only available on Darwin." "$tmp/linux.out"

: >"$tmp/defaults.log"
printf 'no\n' | DOTFILES_DEFAULTS_LOG="$tmp/defaults.log" PATH="$tmp/bin:$PATH" \
	sh "$tmp/dotfiles" preferences >"$tmp/declined.out"
test ! -s "$tmp/defaults.log"
rg -Fq "No macOS preferences were changed." "$tmp/declined.out"

printf 'yes\n' | DOTFILES_DEFAULTS_LOG="$tmp/defaults.log" PATH="$tmp/bin:$PATH" \
	sh "$tmp/dotfiles" preferences >"$tmp/applied.out"
for setting in \
	"write -g NSAutomaticCapitalizationEnabled -bool false" \
	"write -g NSAutomaticDashSubstitutionEnabled -bool false" \
	"write -g NSAutomaticPeriodSubstitutionEnabled -bool false" \
	"write -g NSAutomaticQuoteSubstitutionEnabled -bool false" \
	"write -g NSAutomaticSpellingCorrectionEnabled -bool false" \
	"write com.apple.finder AppleShowAllExtensions -bool true" \
	"write com.apple.finder ShowPathbar -bool true" \
	"write com.apple.finder ShowStatusBar -bool true" \
	"write -g InitialKeyRepeat -int 15" \
	"write -g KeyRepeat -int 2"; do
	rg -Fxq "$setting" "$tmp/defaults.log"
done
test "$(wc -l <"$tmp/defaults.log" | tr -d ' ')" = 10
for preference in \
	NSAutomaticCapitalizationEnabled \
	NSAutomaticDashSubstitutionEnabled \
	NSAutomaticPeriodSubstitutionEnabled \
	NSAutomaticQuoteSubstitutionEnabled \
	NSAutomaticSpellingCorrectionEnabled \
	AppleShowAllExtensions \
	ShowPathbar \
	ShowStatusBar \
	InitialKeyRepeat \
	KeyRepeat; do
	rg -Fq "$preference" "$root/README.md"
done
rg -Fq "dotfiles preferences" "$root/README.md"
rg -Fq "confirmation" "$root/README.md"
rg -Fq "bootstrap or \`dotfiles apply\`" "$root/README.md"
printf '%s\n' "macOS preferences command passed"
