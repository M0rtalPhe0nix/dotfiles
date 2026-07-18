#!/usr/bin/env zsh
set -eu

root="${0:A:h:h}"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT INT TERM
home="$tmp/home"
mkdir -p "$home/.zim" "$tmp/open-bin" "$tmp/xdg-bin" "$tmp/command-bin" "$tmp/no-opener-bin"

cat >"$tmp/chezmoi.toml" <<'EOF'
[data]
gitName = "Dotfiles Test"
gitEmail = "dotfiles@example.invalid"
infraTool = "none"
installClaude = false
EOF
chezmoi --source "$root" --destination "$home" --config "$tmp/chezmoi.toml" apply --exclude=scripts

cat >"$tmp/open-bin/open" <<'EOF'
#!/bin/sh
printf '%s\n' "$@" >"$OPEN_LOG"
EOF
chmod +x "$tmp/open-bin/open"

(
  export HOME="$home" XDG_CONFIG_HOME="$home/.config" ZDOTDIR="$home" PATH="$tmp/open-bin" OPEN_LOG="$tmp/open.log"
  unhash -m '*'
  mkdir() { /bin/mkdir "$@"; }
  chmod() { /bin/chmod "$@"; }
  touch() { /usr/bin/touch "$@"; }
  source "$home/.zshrc"
  (( $+functions[o] ))
  o
  [[ "$(<"$tmp/open.log")" == '.' ]]
  o first 'second path'
  [[ "$(<"$tmp/open.log")" == $'first\nsecond path' ]]
)

cat >"$tmp/xdg-bin/xdg-open" <<'EOF'
#!/bin/sh
printf '%s\n' "$@" >"$OPEN_LOG"
EOF
chmod +x "$tmp/xdg-bin/xdg-open"

(
  export HOME="$home" XDG_CONFIG_HOME="$home/.config" ZDOTDIR="$home" PATH="$tmp/xdg-bin" OPEN_LOG="$tmp/xdg-open.log"
  unhash -m '*'
  mkdir() { /bin/mkdir "$@"; }
  chmod() { /bin/chmod "$@"; }
  touch() { /usr/bin/touch "$@"; }
  source "$home/.zshrc"
  o target
  [[ "$(<"$tmp/xdg-open.log")" == target ]]
)

cat >"$tmp/command-bin/o" <<'EOF'
#!/bin/sh
exit 0
EOF
chmod +x "$tmp/command-bin/o"

(
  export HOME="$home" XDG_CONFIG_HOME="$home/.config" ZDOTDIR="$home" PATH="$tmp/command-bin"
  unhash -m '*'
  mkdir() { /bin/mkdir "$@"; }
  chmod() { /bin/chmod "$@"; }
  touch() { /usr/bin/touch "$@"; }
  source "$home/.zshrc"
  (( ! $+functions[o] ))
)

(
  export HOME="$home" XDG_CONFIG_HOME="$home/.config" ZDOTDIR="$home" PATH="$tmp/no-opener-bin"
  unhash -m '*'
  mkdir() { /bin/mkdir "$@"; }
  chmod() { /bin/chmod "$@"; }
  touch() { /usr/bin/touch "$@"; }
  source "$home/.zshrc"
  status=0
  o >"$tmp/no-opener.stdout" 2>"$tmp/no-opener.stderr" || status=$?
  (( status == 127 ))
  [[ "$(<"$tmp/no-opener.stderr")" == 'o: no supported opener available (expected open or xdg-open).' ]]
)
