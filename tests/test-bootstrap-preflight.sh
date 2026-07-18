#!/bin/sh
set -eu

root="$(CDPATH='' cd -- "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT INT TERM
mkdir -p "$tmp/bin" "$tmp/home" "$tmp/source/.git"

cat >"$tmp/bin/uname" <<'EOF'
#!/bin/sh
case "$1" in
-s) printf '%s\n' Darwin ;;
-m) printf '%s\n' arm64 ;;
esac
EOF
cat >"$tmp/bin/chezmoi" <<EOF
#!/bin/sh
printf '%s\n' "chezmoi \$*" >>"$tmp/commands"
case "\$1" in
source-path) printf '%s\\n' "$tmp/source" ;;
data) printf '%s\\n' '{"infraTool":"none","useCorporateCA":false,"installClaude":true}' ;;
esac
EOF
for command in curl git brew sudo; do
	cat >"$tmp/bin/$command" <<EOF
#!/bin/sh
printf '%s\\n' "$command \$*" >>"$tmp/commands"
exit 99
EOF
	chmod +x "$tmp/bin/$command"
done
chmod +x "$tmp/bin/uname" "$tmp/bin/chezmoi"

HOME="$tmp/home" PATH="$tmp/bin:$PATH" sh "$root/bootstrap.sh" --preflight >"$tmp/output"
rg -Fq 'branch: macOS Homebrew, Ghostty cask, VS Code application settings' "$tmp/output"
rg -Fq 'chezmoi source: initialized' "$tmp/output"
rg -Fq 'managed VS Code target: Library/Application Support/Code/User' "$tmp/output"
rg -Fq 'pre-bootstrap backup targets:' "$tmp/output"
rg -Fq '.config/git/ignore' "$tmp/output"
rg -Fq 'phases:' "$tmp/output"
test "$(cat "$tmp/commands")" = "chezmoi source-path
chezmoi data --format=json"
test -z "$(ls -A "$tmp/home")"

if HOME="$tmp/home" PATH="$tmp/bin:$PATH" sh "$root/bootstrap.sh" --preflight unexpected >/dev/null 2>&1; then
	printf '%s\n' "Unexpected preflight argument unexpectedly succeeded." >&2
	exit 1
fi
