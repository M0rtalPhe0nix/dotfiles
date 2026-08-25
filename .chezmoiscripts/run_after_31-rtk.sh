#!/bin/sh
set -eu

command -v rtk >/dev/null 2>&1 || exit 0

rtk init --global --opencode

settings="$HOME/.claude/settings.json"
if [ -f "$settings" ] && [ -n "$(tail -c 1 "$settings")" ]; then
	printf '\n' >>"$settings"
fi
