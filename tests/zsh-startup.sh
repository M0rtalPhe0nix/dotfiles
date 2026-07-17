#!/bin/zsh
set -eu
zmodload zsh/datetime

root="${0:A:h:h}"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT INT TERM
home="$tmp/home"
mkdir -p "$home/.zim"

cat >"$tmp/chezmoi.toml" <<'EOF'
[data]
gitName = "Dotfiles Test"
gitEmail = "dotfiles@example.invalid"
EOF

chezmoi --source "$root" --destination "$home" --config "$tmp/chezmoi.toml" apply --exclude=scripts
curl -fsSL https://raw.githubusercontent.com/zimfw/zimfw/master/zimfw.zsh -o "$home/.zim/zimfw.zsh"
HOME="$home" ZDOTDIR="$home" ZIM_HOME="$home/.zim" zsh "$home/.zim/zimfw.zsh" install >/dev/null
HOME="$home" ZDOTDIR="$home" ZIM_HOME="$home/.zim" zsh -lic exit

total=0.0
repeat 5; do
	start=$EPOCHREALTIME
	HOME="$home" ZDOTDIR="$home" ZIM_HOME="$home/.zim" zsh -lic exit
	elapsed=$(( EPOCHREALTIME - start ))
	total=$(( total + elapsed ))
done
average=$(( total / 5.0 ))
printf 'Managed warm Zsh startup average: %.3f s\n' "$average"
(( average < 0.200 ))
