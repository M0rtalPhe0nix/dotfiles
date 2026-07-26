#!/bin/sh
set -eu

command -v mise >/dev/null 2>&1 || exit 0

mise exec -- uv tool install --python 3.13 'headroom-ai[all]'

headroom_bin="$HOME/.local/bin/headroom"
if [ -x "$headroom_bin" ] && command -v claude >/dev/null 2>&1; then
	"$headroom_bin" mcp install --agent claude
fi
