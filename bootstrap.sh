#!/bin/sh
set -eu

REPO="M0rtalPhe0nix/dotfiles"

case "$(uname -s)" in
Darwin) ;;
Linux)
	if ! command -v apt-get >/dev/null 2>&1; then
		printf '%s\n' "Only Debian and Ubuntu Linux are supported." >&2
		exit 1
	fi
	sudo apt-get update
	sudo apt-get install -y build-essential ca-certificates curl file git procps unzip
	;;
*)
	printf '%s\n' "Unsupported operating system: $(uname -s)" >&2
	exit 1
	;;
esac

if ! command -v brew >/dev/null 2>&1; then
	NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
	if [ -x /opt/homebrew/bin/brew ]; then
		eval "$(/opt/homebrew/bin/brew shellenv)"
	elif [ -x /home/linuxbrew/.linuxbrew/bin/brew ]; then
		eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"
	fi
fi

brew install chezmoi
chezmoi init --apply "https://github.com/${REPO}.git"

if [ -t 0 ]; then
	gh auth status >/dev/null 2>&1 || gh auth login
	if [ "$(chezmoi execute-template '{{ .installClaude }}')" = true ]; then
		claude auth status >/dev/null 2>&1 || claude auth login
	fi
	opencode auth list 2>/dev/null | grep -q . || opencode auth login
fi

printf '%s\n' "Bootstrap complete. Restart the terminal, then run: dotfiles doctor"
