#!/bin/sh
set -eu

root="$(CDPATH='' cd -- "$(dirname "$0")/.." && pwd)"
docker build -f "$root/tests/Dockerfile.debian" -t dotfiles-debian-smoke "$root"
