# Release Testing Guide

Use this guide to validate a release candidate on disposable machines. The automated suite catches rendering and regression errors; this guide covers the real package installation, authentication, graphical application, and recovery workflows that cannot safely run in a container.

## Preconditions

- Start from a disposable VM, test user account, or machine snapshot. Bootstrap, `dotfiles update`, and `dotfiles rollback` modify the user environment and may install or upgrade software.
- Record the candidate branch and commit before testing.
- Test the candidate on Apple Silicon macOS, Debian, and Ubuntu. Use a supported desktop release for each Linux distribution.
- Use a network that can reach the package sources. Test a corporate CA separately and only with a non-sensitive test certificate.

## Automated Gate

Run these commands from the candidate checkout before host testing:

```sh
git diff --check
tests/validate.sh
tests/debian-smoke.sh
tests/zsh-startup.sh
```

All commands must exit successfully. Record the Zsh startup average; it must remain below 200 ms.

## Candidate Bootstrap

`DOTFILES_REF` lets bootstrap install a branch other than `main`. It defaults to `main` and is intended for disposable release-test machines.

```sh
branch=integration/stable-release
curl -fsSL "https://raw.githubusercontent.com/M0rtalPhe0nix/dotfiles/$branch/bootstrap.sh" | DOTFILES_REF="$branch" /bin/sh
git -C "$(chezmoi source-path)" rev-parse HEAD
```

Verify the reported commit is the candidate commit. Complete GitHub, Claude Code, and OpenCode authentication when prompted, unless the scenario explicitly tests `DOTFILES_SKIP_CLAUDE=1`.

Run `bootstrap.sh --preflight` before the first install and verify it reports the expected platform branch, managed VS Code target, and backup targets.

## Host Smoke Test

After restarting the terminal, run the smoke test from the candidate source:

```sh
"$(chezmoi source-path)/tests/release-host-smoke.sh"
```

It checks the supported platform, `dotfiles doctor`, configuration drift, Readline and Git settings, secret permissions, VS Code launcher, portable `o` command, and shared Claude skills.

## Repeat And Recovery

Run bootstrap again with the same `DOTFILES_REF` value. It must fast-forward or report that it is current, without discarding local source changes. Re-run the host smoke test.

On a separate disposable test account, create a sentinel `~/.zshrc` before bootstrap. After bootstrap completes, run:

```sh
dotfiles rollback
grep -Fxq 'release-test-sentinel' ~/.zshrc
dotfiles apply
```

The sentinel proves the pre-bootstrap backup was restored. `dotfiles rollback` deliberately retains installed software. Run the host smoke test again after `dotfiles apply`.

## Manual Platform Checks

On every platform:

- Run `dotfiles apply`, then confirm `dotfiles diff` has no output.
- Run `dotfiles extensions` after installing one non-baseline VS Code extension. Confirm it preserves existing baseline entries and adds the new extension without uninstalling anything.
- Run `dotfiles update` only on a disposable machine. Confirm Homebrew, mise, Zim, VS Code extensions, and the platform package path complete, then re-run the smoke test.
- Confirm Ghostty uses MesloLGS Nerd Font and Starship icons render correctly.
- Confirm GitHub, Claude Code, and OpenCode report authenticated status through `dotfiles doctor`.

On macOS:

- Confirm VS Code reads settings from `~/Library/Application Support/Code/User`.
- Run `dotfiles preferences`, first decline and then accept. Verify the documented text-substitution, Finder, and keyboard settings with `defaults read` and relaunch Finder.

On Debian and Ubuntu:

- Confirm the Microsoft VS Code repository is installed and `code --version` succeeds.
- Confirm `ghostty --version` succeeds and the application launches in the desktop session.
- Confirm the MesloLGS font is visible with `fc-list | grep -i 'MesloLGS Nerd Font'`.

## Optional Scenarios

- Run a fresh bootstrap with `DOTFILES_SKIP_CLAUDE=1`; Claude Code must not install or require authentication.
- Use each supported infrastructure choice (`none`, Terraform, OpenTofu) and optional language-server selection, then run `dotfiles doctor`.
- Test a corporate CA only in an isolated environment. Confirm the supplied PEM has no private key, package downloads work, and `dotfiles doctor` validates the installed trust files.

Record the platform version, candidate commit, command outputs, failures, and any manual observations before approving the release.
