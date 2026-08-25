#!/bin/sh
set -eu

command -v rtk >/dev/null 2>&1 || exit 0
exec rtk hook claude
