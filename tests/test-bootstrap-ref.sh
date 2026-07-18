#!/bin/sh
set -eu

root="$(CDPATH='' cd -- "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT INT TERM
mkdir -p "$tmp/bin" "$tmp/home" "$tmp/source"

cat >"$tmp/bin/uname" <<'EOF'
#!/bin/sh
case "$1" in
-s) printf '%s\n' Darwin ;;
-m) printf '%s\n' arm64 ;;
esac
EOF
cat >"$tmp/bin/chezmoi" <<EOF
#!/bin/sh
if [ "\$1" = source-path ]; then
	printf '%s\n' "$tmp/source"
else
	printf 'chezmoi %s\\n' "\$*" >>"$tmp/commands"
fi
EOF
cat >"$tmp/bin/brew" <<EOF
#!/bin/sh
printf 'brew %s\\n' "\$*" >>"$tmp/commands"
EOF
chmod +x "$tmp/bin/uname" "$tmp/bin/chezmoi" "$tmp/bin/brew"

HOME="$tmp/home" PATH="$tmp/bin:$PATH" DOTFILES_REF=integration/stable-release \
	sh "$root/bootstrap.sh" >"$tmp/output"

rg -Fxq 'brew install chezmoi' "$tmp/commands"
rg -Fxq 'chezmoi init --apply --branch integration/stable-release https://github.com/M0rtalPhe0nix/dotfiles.git' "$tmp/commands"
