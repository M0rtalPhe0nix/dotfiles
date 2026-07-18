#!/bin/sh
set -eu

root="$(CDPATH='' cd -- "$(dirname "$0")/.." && pwd)"
docker build -f "$root/tests/Dockerfile.debian" -t dotfiles-debian-smoke "$root"
docker build --build-arg BASE_IMAGE=ubuntu:24.04 -f "$root/tests/Dockerfile.debian" -t dotfiles-ubuntu-smoke "$root"
