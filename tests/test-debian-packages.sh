#!/bin/sh
set -eu

root="$(CDPATH='' cd -- "$(dirname "$0")/.." && pwd)"
if [ "$(uname -s)" != Linux ]; then
	exit 0
fi
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT INT TERM
mkdir -p "$tmp/bin"

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
	<"$root/.chezmoiscripts/run_once_before_10-packages.sh.tmpl" >"$tmp/packages.sh"
rg -Fq 'https://raw.githubusercontent.com/mkasberg/ghostty-ubuntu/HEAD/install.sh' "$tmp/packages.sh"
if rg -q 'flatpak|flathub' "$tmp/packages.sh"; then
	printf '%s\n' "Linux package script still references the unavailable Flatpak package." >&2
	exit 1
fi

cat >"$tmp/bin/sudo" <<'EOF'
#!/bin/sh
printf '%s\n' "$*" >>"$TEST_LOG"
if [ "$1" = mktemp ]; then
	printf '%s\n' "$TEST_TMP/${2##*/}.tmp"
	fi
EOF
cat >"$tmp/bin/code" <<'EOF'
#!/bin/sh
exit 0
EOF
cat >"$tmp/bin/ghostty" <<'EOF'
#!/bin/sh
exit 0
EOF
cat >"$tmp/bin/brew" <<'EOF'
#!/bin/sh
exit 0
EOF
cat >"$tmp/bin/fc-list" <<'EOF'
#!/bin/sh
printf '%s\n' "MesloLGS Nerd Font"
EOF
chmod +x "$tmp/bin/sudo" "$tmp/bin/code" "$tmp/bin/ghostty" "$tmp/bin/brew" "$tmp/bin/fc-list"

TEST_LOG="$tmp/log" TEST_TMP="$tmp" PATH="$tmp/bin:$PATH" sh "$tmp/packages.sh"
rg -Fxq 'apt-get install -y --no-upgrade build-essential ca-certificates curl file fontconfig git gnupg procps unzip' "$tmp/log"
if rg -q '#|  ' "$tmp/log"; then
	printf '%s\n' "Package comments or empty arguments reached APT." >&2
	exit 1
fi

rm "$tmp/bin/code"
cat >"$tmp/bin/curl" <<'EOF'
#!/bin/sh
while [ "$#" -gt 0 ]; do
	case "$1" in
	-o)
		shift
		: >"$1"
		;;
	esac
	shift
done
EOF
cat >"$tmp/bin/gpg" <<'EOF'
#!/bin/sh
while [ "$#" -gt 0 ]; do
	case "$1" in
	--output)
		shift
		: >"$1"
		;;
	esac
	shift
done
EOF
cat >"$tmp/bin/dpkg" <<'EOF'
#!/bin/sh
printf '%s\n' amd64
EOF
chmod +x "$tmp/bin/curl" "$tmp/bin/gpg" "$tmp/bin/dpkg"
: >"$tmp/log"
TEST_LOG="$tmp/log" TEST_TMP="$tmp" PATH="$tmp/bin:$PATH" sh "$tmp/packages.sh"
rg -q '^mktemp /etc/apt/keyrings/\.packages\.microsoft\.gpg\.XXXXXX$' "$tmp/log"
rg -q '^mv -f .+ /etc/apt/keyrings/packages\.microsoft\.gpg$' "$tmp/log"
rg -q '^mktemp /etc/apt/sources\.list\.d/\.vscode\.list\.XXXXXX$' "$tmp/log"
rg -q '^mv -f .+ /etc/apt/sources\.list\.d/vscode\.list$' "$tmp/log"
