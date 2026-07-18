#!/bin/sh
set -eu

REPO="M0rtalPhe0nix/dotfiles"
corporate_ca_path="${DOTFILES_CORPORATE_CA_PATH:-}"
corporate_ca_choice="${DOTFILES_CONFIGURE_CORPORATE_CA:-}"
apt_ca_bundle=""
existing_source=false
chezmoi_command=""

usage() {
	printf '%s\n' "usage: bootstrap.sh [--preflight]"
}

preflight() {
	os="$(uname -s)"
	arch="$(uname -m)"
	supported=true

	printf '%s\n' "dotfiles bootstrap preflight"
	case "$os" in
	Darwin)
		printf '%s\n' "platform: macOS ($arch)"
		if [ "$arch" != arm64 ]; then
			printf '%s\n' "status: unsupported; Apple Silicon macOS is required"
			supported=false
		else
			printf '%s\n' "branch: macOS Homebrew, Ghostty cask, VS Code application settings"
		fi
		vscode_target="Library/Application Support/Code/User"
		;;
	Linux)
		linux_id="unknown"
		if [ -r /etc/os-release ]; then
			linux_id="$(sed -n 's/^ID=//p' /etc/os-release | tr -d '"' | sed -n '1p')"
		fi
		printf '%s\n' "platform: Linux ($linux_id, $arch)"
		case "$linux_id" in
		debian | ubuntu) printf '%s\n' "branch: APT prerequisites, Homebrew, documented Ghostty package, VS Code user settings" ;;
		*)
			printf '%s\n' "status: unsupported; Debian or Ubuntu is required"
			supported=false
			;;
		esac
		vscode_target=".config/Code/User"
		;;
	*)
		printf '%s\n' "platform: $os ($arch)"
		printf '%s\n' "status: unsupported operating system"
		supported=false
		vscode_target="unavailable"
		;;
	esac

	printf '%s\n' "commands:"
	for command in curl git brew chezmoi jq sudo; do
		if command -v "$command" >/dev/null 2>&1; then
			printf 'ok   %s\n' "$command"
		else
			printf 'MISS %s\n' "$command"
		fi
	done
	if [ "$os" = Linux ]; then
		if command -v apt-get >/dev/null 2>&1; then
			printf '%s\n' "ok   apt-get"
		else
			printf '%s\n' "MISS apt-get"
		fi
	fi

	if [ "$existing_source" = true ]; then
		printf '%s\n' "chezmoi source: initialized"
		if command -v jq >/dev/null 2>&1; then
			data="$($chezmoi_command data --format=json 2>/dev/null || true)"
			if [ -n "$data" ]; then
				printf '%s\n' "configuration:"
				for key in infraTool useCorporateCA installClaude installPythonLsp installTypeScriptLsp installMarkdownLsp installTerraformLsp; do
					value="$(printf '%s' "$data" | jq -r --arg key "$key" '.[$key] // "unset"' 2>/dev/null || true)"
					printf '%s: %s\n' "$key" "${value:-unset}"
				done
			fi
		fi
	else
		printf '%s\n' "chezmoi source: not initialized"
		printf '%s\n' "configuration: unavailable until Chezmoi initialization"
	fi

	printf '%s\n' "managed VS Code target: $vscode_target"
	printf '%s\n' "pre-bootstrap backup targets:"
	cat <<EOF
.zshrc
.zimrc
.config/starship.toml
.config/mise/config.toml
.config/zsh/local.zsh
.config/zsh/secrets.zsh
.config/git/dotfiles.gitconfig
.config/git/identity.gitconfig
.config/opencode/opencode.json
.claude/settings.json
.claude/skills
.config/ghostty/config
.local/share/dotfiles/corporate-ca.pem
.local/share/dotfiles/ca-bundle.pem
$vscode_target/settings.json
$vscode_target/keybindings.json
EOF
	printf '%s\n' "phases:"
	printf '%s\n' "1. Detect platform and validate the optional corporate CA."
	printf '%s\n' "2. Install platform prerequisites and Homebrew when absent."
	printf '%s\n' "3. Initialize or fast-forward the Chezmoi source, then apply it."
	printf '%s\n' "4. Back up managed conflicts before corporate CA, packages, runtimes, and extensions phases."
	printf '%s\n' "5. Authenticate interactively only after apply."

	[ "$supported" = true ] || return 2
}

case "$#" in
0) ;;
1)
	case "$1" in
	--preflight) preflight_requested=true ;;
	*)
		usage >&2
		exit 2
		;;
	esac
	;;
*)
	usage >&2
	exit 2
	;;
esac

for chezmoi_command in "$(command -v chezmoi 2>/dev/null || true)" /opt/homebrew/bin/chezmoi /home/linuxbrew/.linuxbrew/bin/chezmoi; do
	if [ -x "$chezmoi_command" ] && [ -d "$($chezmoi_command source-path 2>/dev/null)/.git" ]; then
		existing_source=true
		break
	fi
done

if [ "${preflight_requested:-false}" = true ]; then
	preflight
	exit $?
fi

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
