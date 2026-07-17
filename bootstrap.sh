#!/bin/sh
set -eu

REPO="M0rtalPhe0nix/dotfiles"
corporate_ca_path="${DOTFILES_CORPORATE_CA_PATH:-}"
corporate_ca_choice="${DOTFILES_CONFIGURE_CORPORATE_CA:-}"
apt_ca_bundle=""
existing_source=false

for chezmoi_command in "$(command -v chezmoi 2>/dev/null || true)" /opt/homebrew/bin/chezmoi /home/linuxbrew/.linuxbrew/bin/chezmoi; do
	if [ -x "$chezmoi_command" ] && [ -d "$($chezmoi_command source-path 2>/dev/null)/.git" ]; then
		existing_source=true
		break
	fi
done

if [ -z "$corporate_ca_path" ] && [ -z "$corporate_ca_choice" ] && [ "$existing_source" = false ] && [ -t 0 ]; then
	printf '%s' "Configure a corporate CA certificate? [y/N] "
	read -r configure_corporate_ca
	case "$configure_corporate_ca" in
	[yY] | [yY][eE][sS])
		printf '%s' "Absolute path to the corporate CA PEM file: "
		read -r corporate_ca_path
		DOTFILES_CONFIGURE_CORPORATE_CA=1
		DOTFILES_CORPORATE_CA_PATH="$corporate_ca_path"
		export DOTFILES_CONFIGURE_CORPORATE_CA DOTFILES_CORPORATE_CA_PATH
		;;
	*)
		DOTFILES_CONFIGURE_CORPORATE_CA=0
		export DOTFILES_CONFIGURE_CORPORATE_CA
		;;
	esac
fi

if [ -n "$corporate_ca_path" ]; then
	case "$corporate_ca_path" in
	/*) ;;
	*)
		printf '%s\n' "DOTFILES_CORPORATE_CA_PATH must be an absolute path." >&2
		exit 1
		;;
	esac
	if [ ! -r "$corporate_ca_path" ]; then
		printf '%s\n' "Corporate CA is not readable: $corporate_ca_path" >&2
		exit 1
	fi
	if grep -q -- 'PRIVATE KEY' "$corporate_ca_path" || ! grep -q -- '-----BEGIN CERTIFICATE-----' "$corporate_ca_path"; then
		printf '%s\n' "Corporate CA must be a PEM certificate without a private key." >&2
		exit 1
	fi
fi

apt_get() {
	if [ -n "$apt_ca_bundle" ]; then
		sudo apt-get -o "Acquire::https::CaInfo=$apt_ca_bundle" "$@"
	else
		sudo apt-get "$@"
	fi
}

case "$(uname -s)" in
Darwin)
	if [ -n "$corporate_ca_path" ]; then
		sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain "$corporate_ca_path"
	fi
	;;
Linux)
	if ! command -v apt-get >/dev/null 2>&1; then
		printf '%s\n' "Only Debian and Ubuntu Linux are supported." >&2
		exit 1
	fi
	if [ -n "$corporate_ca_path" ] && [ -r /etc/ssl/certs/ca-certificates.crt ]; then
		apt_ca_bundle="$(mktemp)"
		trap 'rm -f "$apt_ca_bundle"' EXIT INT TERM
		cat /etc/ssl/certs/ca-certificates.crt "$corporate_ca_path" >"$apt_ca_bundle"
	fi
	apt_get update
	apt_get install -y build-essential ca-certificates curl file git procps unzip
	if [ -n "$corporate_ca_path" ]; then
		sudo install -m 0644 "$corporate_ca_path" /usr/local/share/ca-certificates/dotfiles-corporate-ca.crt
		sudo update-ca-certificates
	fi
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
source_dir="$(chezmoi source-path)"
if [ -d "$source_dir/.git" ]; then
	git -C "$source_dir" pull --ff-only origin main
	chezmoi init
	chezmoi apply
else
	chezmoi init --apply "https://github.com/${REPO}.git"
fi

if [ -t 0 ]; then
	gh auth status >/dev/null 2>&1 || gh auth login
	if [ "${DOTFILES_SKIP_CLAUDE:-0}" = 1 ]; then
		install_claude=false
	else
		install_claude="$(chezmoi data --format=json | jq -r '.installClaude // true')"
	fi
	if [ "$install_claude" = true ]; then
		claude auth status >/dev/null 2>&1 || claude auth login
	fi
	opencode auth list 2>/dev/null | grep -q . || opencode auth login
fi

printf '%s\n' "Bootstrap complete. Restart the terminal, then run: dotfiles doctor"
