#!/usr/bin/env zsh
set -eu

zim_home="${ZIM_HOME:-${ZDOTDIR:-$HOME}/.zim}"
if [[ ! -e "$zim_home/zimfw.zsh" ]]; then
	mkdir -p "$zim_home"
	curl -fsSL https://raw.githubusercontent.com/zimfw/zimfw/master/zimfw.zsh -o "$zim_home/zimfw.zsh"
fi
ZIM_HOME="$zim_home" zsh "$zim_home/zimfw.zsh" install
