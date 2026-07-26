# Conventions

- Prefer the smallest correct change; preserve behavior unless intentionally replacing it.
- Use Chezmoi source-state names (`dot_`, `private_`, `executable_`, `create_`, `symlink_`) and add `.tmpl` only for actual templates.
- Keep repository-only tests/docs/manifests out of the managed target set.
- Guard shell integrations and command replacements on command availability.
- Keep shared history private, mode 0600, and exclude commands beginning with a space.
- `dotfiles apply` must not upgrade software; upgrades belong in `dotfiles update`.
- Bootstrap must be repeat-safe, preserve divergence, and never uninstall packages during bootstrap or rollback.