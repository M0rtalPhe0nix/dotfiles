from __future__ import annotations

import json
import hashlib
import os
import shutil
import stat
import subprocess
import tempfile
from contextlib import ExitStack
from pathlib import Path, PurePosixPath
from typing import Any

from dotfiles_capabilities.catalog import (
    CatalogError,
    hash_tree,
    load_catalog_index,
    resolve_identifier,
    validate_catalog,
)

SCHEMA_VERSION = 1
JOURNAL_SCHEMA_VERSION = 1
JOURNAL_NAME = "dotfiles-capabilities-transaction.json"

CatalogKey = tuple[str, str]
SnapshotKey = tuple[str, str, str]


class ManagerError(Exception):
    """A capability operation could not produce a valid repository state."""


def _git(arguments: list[str], *, cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=cwd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        diagnostic = result.stderr.strip() or result.stdout.strip()
        raise ManagerError(diagnostic or f"git {' '.join(arguments)} failed")
    return result.stdout.strip()


def _checkout(
    url: str,
    commit: str | None,
    stack: ExitStack,
    catalog_path: str = ".",
) -> tuple[Path, str]:
    if not url or "\n" in url:
        raise ManagerError("catalog URL must be a non-empty single-line Git source")
    temporary = Path(stack.enter_context(tempfile.TemporaryDirectory()))
    checkout = temporary / "checkout"
    _git(["clone", "--quiet", "--no-checkout", url, str(checkout)])
    _git(["checkout", "--quiet", commit or "HEAD"], cwd=checkout)
    resolved_commit = _git(["rev-parse", "HEAD"], cwd=checkout)
    snapshot = checkout if catalog_path == "." else checkout / catalog_path
    result = validate_catalog(snapshot, check_index=True)
    if result.errors:
        raise ManagerError("invalid catalog: " + "; ".join(result.errors))
    return snapshot, resolved_commit


def _catalog_descriptor(descriptor: Any) -> CatalogKey:
    if (
        not isinstance(descriptor, dict)
        or "url" not in descriptor
        or not set(descriptor) <= {"url", "path"}
    ):
        raise ManagerError("each catalog must contain url and optional path fields")
    url = descriptor["url"]
    if not isinstance(url, str):
        raise ManagerError("catalog url must be a string")
    path = descriptor.get("path", ".")
    if not isinstance(path, str):
        raise ManagerError("catalog path must be a string")
    portable = PurePosixPath(path)
    if (
        not path
        or "\\" in path
        or portable.is_absolute()
        or ".." in portable.parts
        or (path != "." and portable.as_posix() != path)
    ):
        raise ManagerError("catalog path must be a normalized safe relative path")
    return url, path


def _catalog_url(descriptor: Any) -> str:
    return _catalog_descriptor(descriptor)[0]


def _catalog_lock_entry(url: str, path: str, commit: str) -> dict[str, str]:
    entry = {"url": url}
    if path != ".":
        entry["path"] = path
    entry["commit"] = commit
    return entry


def _capability_source(url: str, path: str, commit: str) -> dict[str, str]:
    return _catalog_lock_entry(url, path, commit)


def _snapshot_key(source: dict[str, Any]) -> SnapshotKey:
    url = source.get("url")
    commit = source.get("commit")
    path = source.get("path", ".")
    if not isinstance(url, str) or not isinstance(commit, str):
        raise ManagerError("locked capability sources require string url and commit")
    _catalog_descriptor({"url": url, "path": path})
    return url, commit, path


def _build_lock(
    manifest: dict[str, Any],
    stack: ExitStack,
    pinned_commits: dict[CatalogKey, str] | None = None,
) -> tuple[dict[str, Any], dict[SnapshotKey, Path]]:
    snapshots: dict[CatalogKey, Path] = {}
    commits: dict[CatalogKey, str] = {}
    indexed: dict[str, tuple[CatalogKey, dict[str, Any]]] = {}

    for descriptor in manifest["catalogs"]:
        key = _catalog_descriptor(descriptor)
        if key in snapshots:
            continue
        url, path = key
        snapshot, commit = _checkout(
            url, (pinned_commits or {}).get(key), stack, path
        )
        snapshots[key] = snapshot
        commits[key] = commit
        index = load_catalog_index(snapshot / "catalog.json")
        for capability in index["capabilities"]:
            identifier = capability["identifier"]
            if identifier in indexed:
                raise ManagerError(f"capability {identifier!r} exists in multiple catalogs")
            indexed[identifier] = (key, capability)

    identifiers = set(indexed)
    roots: list[str] = []
    for reference in manifest["roots"]:
        if not isinstance(reference, str) or reference.count("/") != 2:
            raise ManagerError("manifest roots must use qualified capability identifiers")
        try:
            roots.append(resolve_identifier(reference, identifiers))
        except CatalogError as error:
            raise ManagerError(str(error)) from error

    required_by: dict[str, set[str]] = {}
    companion_by: dict[str, dict[str, set[str]]] = {}
    enabled_tools: dict[str, set[str]] = {}
    resolved: set[str] = set()
    visiting: set[tuple[str, str]] = set()

    def visit(identifier: str, tools: set[str]) -> None:
        new_tools = tools - enabled_tools.get(identifier, set())
        if not new_tools:
            return
        if any((identifier, tool) in visiting for tool in new_tools):
            raise ManagerError(f"dependency cycle includes {identifier}")
        visiting.update((identifier, tool) for tool in new_tools)
        enabled_tools.setdefault(identifier, set()).update(new_tools)
        capability = indexed[identifier][1]
        dependencies = capability["dependencies"].get("required", [])
        for reference in dependencies:
            try:
                dependency = resolve_identifier(reference, identifiers)
            except CatalogError as error:
                raise ManagerError(str(error)) from error
            required_by.setdefault(dependency, set()).add(identifier)
            visit(dependency, new_tools)
        companions = capability["dependencies"].get("companions", {})
        for tool in sorted(new_tools):
            for reference in companions.get(tool, []):
                try:
                    companion = resolve_identifier(reference, identifiers)
                except CatalogError as error:
                    raise ManagerError(str(error)) from error
                companion_by.setdefault(companion, {}).setdefault(tool, set()).add(
                    identifier
                )
                visit(companion, {tool})
        visiting.difference_update((identifier, tool) for tool in new_tools)
        resolved.add(identifier)

    for root in roots:
        visit(root, {"claude", "codex"})

    capabilities: list[dict[str, Any]] = []
    root_set = set(roots)
    for identifier in sorted(resolved):
        (url, path), indexed_capability = indexed[identifier]
        snapshot = snapshots[(url, path)]
        reason: dict[str, Any]
        if identifier in root_set:
            reason = {"kind": "root"}
        elif identifier in required_by:
            reason = {"kind": "required", "by": sorted(required_by[identifier])}
        else:
            reason = {
                "kind": "companion",
                "by": {
                    tool: sorted(parents)
                    for tool, parents in sorted(companion_by[identifier].items())
                },
            }
        capabilities.append(
            _capability_entry(
                identifier,
                url,
                path,
                commits[(url, path)],
                indexed_capability,
                snapshot,
                reason,
                enabled_tools[identifier],
            )
        )

    lock = {
        "schema_version": SCHEMA_VERSION,
        "catalogs": [
            _catalog_lock_entry(url, path, commits[(url, path)])
            for url, path in sorted(snapshots)
        ],
        "capabilities": capabilities,
    }
    return lock, {
        (url, commits[(url, path)], path): snapshot
        for (url, path), snapshot in snapshots.items()
    }


def _locked_snapshots(
    lock: dict[str, Any], stack: ExitStack
) -> dict[SnapshotKey, Path]:
    snapshots: dict[SnapshotKey, Path] = {}
    for capability in lock.get("capabilities", []):
        source = capability.get("source")
        if not isinstance(source, dict):
            raise ManagerError("locked capability source must be an object")
        key = _snapshot_key(source)
        if key in snapshots:
            continue
        url, commit, path = key
        snapshot, actual_commit = _checkout(url, commit, stack, path)
        if actual_commit != commit:
            raise ManagerError(f"catalog {url}: expected commit {commit}, got {actual_commit}")
        snapshots[key] = snapshot
    return snapshots


def _catalog_inventory(
    manifest: dict[str, Any],
    lock: dict[str, Any] | None,
    stack: ExitStack,
) -> tuple[dict[CatalogKey, Path], dict[str, tuple[CatalogKey, dict[str, Any]]]]:
    pinned = _locked_commits(lock)
    snapshots: dict[CatalogKey, Path] = {}
    indexed: dict[str, tuple[CatalogKey, dict[str, Any]]] = {}
    for descriptor in manifest["catalogs"]:
        key = _catalog_descriptor(descriptor)
        url, path = key
        snapshot, _ = _checkout(url, pinned.get(key), stack, path)
        snapshots[key] = snapshot
        for capability in load_catalog_index(snapshot / "catalog.json")["capabilities"]:
            identifier = capability["identifier"]
            if identifier in indexed:
                raise ManagerError(f"capability {identifier!r} exists in multiple catalogs")
            indexed[identifier] = (key, capability)
    return snapshots, indexed


def _destination(project: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise ManagerError(f"unsafe materialization path {relative!r}")
    destination = project.joinpath(*path.parts)
    current = project
    for part in path.parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise ManagerError(f"materialization parent is a symlink: {current}")
    return destination


def _remove_owned(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _write_exclusions(project: Path, paths: list[tuple[str, bool]]) -> None:
    exclude = Path(_git(["rev-parse", "--git-path", "info/exclude"], cwd=project))
    if not exclude.is_absolute():
        exclude = project / exclude
    exclude.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    lines = existing.splitlines()
    additions = sorted(
        f"/{relative.rstrip('/')}{'/' if directory else ''}"
        for relative, directory in paths
    )
    known = set(lines)
    for addition in additions:
        if addition not in known:
            lines.append(addition)
            known.add(addition)
    exclude.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")


def _locked_exclusions(lock: dict[str, Any] | None) -> set[str]:
    if lock is None:
        return set()
    payloads = {
        f"/{target['path'].rstrip('/')}"
        f"{'/' if target.get('directory', target.get('kind') == 'skill') else ''}"
        for capability in lock.get("capabilities", [])
        for target in capability.get("targets", [])
        if isinstance(target.get("path"), str)
    }
    settings = {
        f"/{setting['path']}"
        for capability in lock.get("capabilities", [])
        for target in capability.get("targets", [])
        if isinstance((setting := target.get("settings")), dict)
        and setting.get("file_state") == "generated"
        and isinstance(setting.get("path"), str)
    }
    return payloads | settings


def _reconcile_exclusions(
    project: Path,
    previous_lock: dict[str, Any] | None,
    desired_lock: dict[str, Any] | None,
) -> None:
    removals = _locked_exclusions(previous_lock) - _locked_exclusions(desired_lock)
    if not removals:
        return
    exclude = Path(_git(["rev-parse", "--git-path", "info/exclude"], cwd=project))
    if not exclude.is_absolute():
        exclude = project / exclude
    if not exclude.exists():
        return
    lines = [
        line
        for line in exclude.read_text(encoding="utf-8").splitlines()
        if line not in removals
    ]
    exclude.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")


def _hook_settings(
    lock: dict[str, Any] | None,
) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    if lock is None:
        return []
    return [
        (capability["identifier"], target, settings)
        for capability in lock.get("capabilities", [])
        for target in capability.get("targets", [])
        if isinstance((settings := target.get("settings")), dict)
    ]


def _read_settings(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ManagerError(f"cannot merge hook settings in {path}: {error}") from error
    if not isinstance(document, dict):
        raise ManagerError(f"cannot merge hook settings in {path}: expected an object")
    hooks = document.get("hooks")
    if hooks is not None and not isinstance(hooks, dict):
        raise ManagerError(f"cannot merge hook settings in {path}: hooks must be an object")
    return document


def _settings_entries(document: dict[str, Any], event: str) -> list[Any]:
    hooks = document.get("hooks")
    if not isinstance(hooks, dict):
        return []
    entries = hooks.get(event)
    return entries if isinstance(entries, list) else []


def _is_tracked(project: Path, relative: str) -> bool:
    try:
        _git(["ls-files", "--error-unmatch", "--", relative], cwd=project)
    except ManagerError:
        return False
    return True


def _prepare_hook_settings(
    project: Path,
    previous_lock: dict[str, Any] | None,
    desired_lock: dict[str, Any],
) -> None:
    previous = {
        (identifier, target.get("tool"), target.get("path")): settings
        for identifier, target, settings in _hook_settings(previous_lock)
    }
    path_states = {
        settings["path"]: settings.get("file_state")
        for _, _, settings in _hook_settings(previous_lock)
        if isinstance(settings.get("path"), str)
    }
    documents: dict[str, dict[str, Any]] = {}
    for identifier, target, settings in _hook_settings(desired_lock):
        path = settings["path"]
        document = documents.setdefault(path, _read_settings(project / path))
        prior = previous.get((identifier, target.get("tool"), target.get("path")))
        if prior is not None and prior.get("entry") == settings.get("entry"):
            settings["owned"] = prior.get("owned", True)
        else:
            entries = _settings_entries(document, settings["event"])
            settings["owned"] = settings["entry"] not in entries
        state = path_states.get(path)
        if not isinstance(state, str):
            if _is_tracked(project, path):
                state = "tracked"
            elif (project / path).exists():
                state = "preserved"
            else:
                state = "generated"
        settings["file_state"] = state


def _merge_hook_settings(
    project: Path,
    previous_lock: dict[str, Any] | None,
    desired_lock: dict[str, Any] | None,
    write_json: Any,
) -> None:
    previous_by_path: dict[str, list[dict[str, Any]]] = {}
    desired_by_path: dict[str, list[dict[str, Any]]] = {}
    for _, _, settings in _hook_settings(previous_lock):
        previous_by_path.setdefault(settings["path"], []).append(settings)
    for _, _, settings in _hook_settings(desired_lock):
        desired_by_path.setdefault(settings["path"], []).append(settings)

    for relative in sorted(set(previous_by_path) | set(desired_by_path)):
        path = _destination(project, relative)
        document = _read_settings(path)
        hooks = document.setdefault("hooks", {})
        if not isinstance(hooks, dict):
            raise ManagerError(f"cannot merge hook settings in {path}")
        for settings in previous_by_path.get(relative, []):
            if not settings.get("owned", True):
                continue
            event = settings["event"]
            entries = hooks.get(event)
            if isinstance(entries, list):
                hooks[event] = [item for item in entries if item != settings["entry"]]
                if not hooks[event]:
                    del hooks[event]
        for settings in desired_by_path.get(relative, []):
            event = settings["event"]
            entries = hooks.setdefault(event, [])
            if not isinstance(entries, list):
                raise ManagerError(f"cannot merge hook event {event!r} in {path}")
            if settings["entry"] not in entries:
                entries.append(settings["entry"])
        if not hooks:
            document.pop("hooks", None)
        prior_generated = any(
            settings.get("file_state") == "generated"
            for settings in previous_by_path.get(relative, [])
        )
        if not desired_by_path.get(relative) and prior_generated and not document:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            write_json(path, document)


def _ensure_hook_approvals(
    project: Path,
    lock: dict[str, Any],
    snapshots: dict[SnapshotKey, Path],
    approve_hook: Any,
    write_json: Any,
) -> None:
    approval_path = _journal_path(project).with_name(
        "dotfiles-capabilities-approvals.json"
    )
    approvals = {"schema_version": 1, "hook_hashes": []}
    if approval_path.exists():
        try:
            approvals = json.loads(approval_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ManagerError(f"cannot read local hook approvals: {error}") from error
    if (
        not isinstance(approvals, dict)
        or approvals.get("schema_version") != 1
        or not isinstance(approvals.get("hook_hashes"), list)
    ):
        raise ManagerError("local hook approvals use an unsupported schema")
    approved = {
        item for item in approvals["hook_hashes"] if isinstance(item, str)
    }
    changed = False
    for capability in lock.get("capabilities", []):
        source = capability["source"]
        snapshot = snapshots[_snapshot_key(source)]
        payload = snapshot / capability["catalog_path"]
        for target in capability.get("targets", []):
            if target.get("kind") != "hook":
                continue
            content_hash = target.get("content_hash")
            if not isinstance(content_hash, str) or content_hash in approved:
                continue
            if approve_hook is None or not approve_hook(
                capability["identifier"],
                target["path"],
                content_hash,
                (payload / target["source"]).read_text(
                    encoding="utf-8", errors="replace"
                ),
            ):
                raise ManagerError(
                    f"hook {capability['identifier']} at {target['path']} was not approved"
                )
            approved.add(content_hash)
            changed = True
    if changed:
        write_json(
            approval_path,
            {"schema_version": 1, "hook_hashes": sorted(approved)},
        )


def _materialize(
    project: Path, lock: dict[str, Any], snapshots: dict[SnapshotKey, Path]
) -> None:
    exclusions: list[tuple[str, bool]] = []
    for capability in lock["capabilities"]:
        identifier = capability.get("identifier")
        source_descriptor = capability.get("source")
        if not isinstance(identifier, str) or not isinstance(source_descriptor, dict):
            raise ManagerError("malformed locked capability")
        snapshot = snapshots.get(_snapshot_key(source_descriptor))
        if snapshot is None:
            raise ManagerError(f"{identifier}: locked catalog snapshot is unavailable")
        payload = snapshot / capability["catalog_path"]
        if hash_tree(payload) != capability.get("content_hash"):
            raise ManagerError(f"locked content hash mismatch for {identifier}")
        targets = capability.get("targets")
        if not isinstance(targets, list):
            raise ManagerError(f"{identifier}: malformed locked targets")
        for target in targets:
            relative = target.get("path")
            source = target.get("source")
            state = target.get("state")
            if not isinstance(relative, str) or not isinstance(source, str):
                raise ManagerError(f"{identifier}: malformed locked target")
            destination = _destination(project, relative)
            source_path = payload / source
            if state == "writable-copy":
                _remove_owned(destination)
                destination.parent.mkdir(parents=True, exist_ok=True)
                if source_path.is_dir():
                    shutil.copytree(source_path, destination, symlinks=True)
                    directory = True
                elif source_path.is_file():
                    shutil.copy2(source_path, destination, follow_symlinks=False)
                    directory = False
                else:
                    raise ManagerError(f"{identifier}: locked target source is missing")
                exclusions.append((relative, directory))
            elif state == "relative-symlink":
                writable = next(
                    (
                        candidate
                        for candidate in targets
                        if candidate.get("state") == "writable-copy"
                        and candidate.get("kind") == target.get("kind")
                        and candidate.get("source") == source
                    ),
                    None,
                )
                if writable is None:
                    raise ManagerError(
                        f"{identifier}: relative mirror has no writable source"
                    )
                _remove_owned(destination)
                destination.parent.mkdir(parents=True, exist_ok=True)
                relative_target = os.path.relpath(
                    _destination(project, writable["path"]), destination.parent
                )
                destination.symlink_to(relative_target)
                exclusions.append((relative, False))
            else:
                raise ManagerError(f"{identifier}: unsupported locked target state")
            settings = target.get("settings")
            if (
                isinstance(settings, dict)
                and settings.get("file_state") == "generated"
                and isinstance(settings.get("path"), str)
            ):
                exclusions.append((settings["path"], False))
    _write_exclusions(project, exclusions)


def _locked_commits(lock: dict[str, Any] | None) -> dict[CatalogKey, str]:
    if lock is None:
        return {}
    commits: dict[CatalogKey, str] = {}
    for descriptor in lock.get("catalogs", []):
        if not isinstance(descriptor, dict):
            raise ManagerError("lock catalog entries must be objects")
        url, path = _catalog_descriptor(
            {"url": descriptor.get("url"), "path": descriptor.get("path", ".")}
        )
        commit = descriptor.get("commit")
        if not isinstance(commit, str):
            raise ManagerError("lock catalog entries require string url and commit fields")
        commits[(url, path)] = commit
    return commits


def _capability_entry(
    identifier: str,
    url: str,
    catalog_root: str,
    commit: str,
    indexed_capability: dict[str, Any],
    snapshot: Path,
    reason: dict[str, Any],
    enabled_tools: set[str] | None = None,
) -> dict[str, Any]:
    payload = snapshot / indexed_capability["path"]
    actual_hash = hash_tree(payload)
    if actual_hash != indexed_capability["content_hash"]:
        raise ManagerError(f"catalog content hash mismatch for {identifier}")
    declared_targets = indexed_capability["targets"]
    claude_skills = {
        target["source"]: target
        for target in declared_targets.get("claude", [])
        if target.get("kind") == "skill"
    }
    codex_skills = {
        target["source"]: target
        for target in declared_targets.get("codex", [])
        if target.get("kind") == "skill"
    }
    if set(claude_skills) != set(codex_skills):
        raise ManagerError(f"{identifier}: shared skill targets must exist for both tools")

    targets: list[dict[str, Any]] = []
    for tool in ("claude", "codex"):
        for declaration in declared_targets.get(tool, []):
            kind = declaration["kind"]
            if (
                enabled_tools is not None
                and tool not in enabled_tools
                and kind != "skill"
            ):
                continue
            source = declaration["source"]
            source_path = payload / source
            if kind == "skill" and not source_path.is_dir():
                raise ManagerError(f"{identifier}: skill source must be a directory")
            target: dict[str, Any] = {
                "tool": tool,
                "kind": kind,
                "source": source,
                "path": declaration["destination"],
                "directory": source_path.is_dir(),
                "state": (
                    "relative-symlink"
                    if kind == "skill" and tool == "claude"
                    else "writable-copy"
                ),
            }
            if kind == "hook":
                mode = source_path.lstat().st_mode
                if not stat.S_ISREG(mode):
                    raise ManagerError(f"{identifier}: hook source must be a regular file")
                digest = hashlib.sha256()
                digest.update(b"dotfiles-capability-hook-v1\0")
                digest.update(b"1" if mode & 0o111 else b"0")
                digest.update(source_path.read_bytes())
                settings_path = (
                    ".claude/settings.json"
                    if tool == "claude"
                    else ".codex/hooks.json"
                )
                command = (
                    '"$(git rev-parse --show-toplevel)/'
                    + declaration["destination"]
                    + '"'
                )
                target["content_hash"] = digest.hexdigest()
                target["settings"] = {
                    "path": settings_path,
                    "event": declaration["event"],
                    "entry": {
                        "matcher": declaration["matcher"],
                        "hooks": [{"type": "command", "command": command}],
                    },
                }
            targets.append(target)
    return {
        "identifier": identifier,
        "source": _capability_source(url, catalog_root, commit),
        "content_hash": actual_hash,
        "reason": reason,
        "catalog_path": indexed_capability["path"],
        "targets": targets,
    }


def _update_lock(
    manifest: dict[str, Any],
    lock: dict[str, Any],
    selected: list[str] | None,
    stack: ExitStack,
    catalog_commits: dict[CatalogKey, str] | None = None,
    *,
    refresh_existing_dependencies: bool = True,
    include_reverse_dependents: bool = True,
) -> tuple[dict[str, Any], dict[SnapshotKey, Path]]:
    head_snapshots: dict[CatalogKey, Path] = {}
    head_commits: dict[CatalogKey, str] = {}
    head_index: dict[str, tuple[CatalogKey, dict[str, Any]]] = {}
    for descriptor in manifest["catalogs"]:
        key = _catalog_descriptor(descriptor)
        url, path = key
        snapshot, commit = _checkout(
            url, (catalog_commits or {}).get(key), stack, path
        )
        head_snapshots[key] = snapshot
        head_commits[key] = commit
        for capability in load_catalog_index(snapshot / "catalog.json")["capabilities"]:
            identifier = capability["identifier"]
            if identifier in head_index:
                raise ManagerError(f"capability {identifier!r} exists in multiple catalogs")
            head_index[identifier] = (key, capability)

    locked = {
        capability["identifier"]: capability for capability in lock["capabilities"]
    }
    locked_identifiers = set(locked)
    roots = set(manifest["roots"])
    if selected is None:
        refresh = set(locked_identifiers)
    else:
        refresh = set()
        for reference in selected:
            try:
                identifier = resolve_identifier(reference, roots)
            except CatalogError as error:
                raise ManagerError(str(error)) from error
            refresh.add(identifier)

    reverse: dict[str, set[str]] = {}
    for capability in lock["capabilities"]:
        reason = capability.get("reason", {})
        dependents: list[Any]
        if reason.get("kind") == "required":
            dependents = reason.get("by", [])
        elif reason.get("kind") == "companion" and isinstance(reason.get("by"), dict):
            dependents = [
                item for values in reason["by"].values() for item in values
            ]
        else:
            dependents = []
        for dependent in dependents:
            if isinstance(dependent, str):
                reverse.setdefault(capability["identifier"], set()).add(dependent)

    changed = True
    while changed:
        changed = False
        for identifier in tuple(refresh):
            current = head_index.get(identifier)
            if current is None:
                raise ManagerError(f"updated capability {identifier!r} is absent at catalog HEAD")
            relationship = current[1]["dependencies"]
            companions = relationship.get("companions", {})
            dependencies = [
                *relationship.get("required", []),
                *(companions.get("claude", []) if isinstance(companions, dict) else []),
                *(companions.get("codex", []) if isinstance(companions, dict) else []),
            ]
            for reference in dependencies:
                try:
                    dependency = resolve_identifier(reference, head_index)
                except CatalogError as error:
                    raise ManagerError(str(error)) from error
                if dependency not in refresh and (
                    refresh_existing_dependencies or dependency not in locked
                ):
                    refresh.add(dependency)
                    changed = True
            if include_reverse_dependents:
                for dependent in reverse.get(identifier, set()):
                    if dependent not in refresh:
                        refresh.add(dependent)
                        changed = True

    snapshots: dict[SnapshotKey, Path] = {
        (url, head_commits[(url, path)], path): snapshot
        for (url, path), snapshot in head_snapshots.items()
    }
    historical_index: dict[SnapshotKey, dict[str, dict[str, Any]]] = {}

    def historical(
        identifier: str,
    ) -> tuple[str, str, str, dict[str, Any], Path]:
        locked_capability = locked.get(identifier)
        if locked_capability is None:
            raise ManagerError(f"locked capability {identifier!r} is unavailable")
        source = locked_capability["source"]
        url = source["url"]
        commit = source["commit"]
        path = source.get("path", ".")
        key = (url, commit, path)
        snapshot = snapshots.get(key)
        if snapshot is None:
            snapshot, actual = _checkout(url, commit, stack, path)
            if actual != commit:
                raise ManagerError(f"catalog {url}: expected commit {commit}, got {actual}")
            snapshots[key] = snapshot
        if key not in historical_index:
            historical_index[key] = {
                item["identifier"]: item
                for item in load_catalog_index(snapshot / "catalog.json")["capabilities"]
            }
        capability = historical_index[key].get(identifier)
        if capability is None:
            raise ManagerError(f"{identifier!r} is absent at its locked source commit")
        return url, path, commit, capability, snapshot

    def source(identifier: str) -> tuple[str, str, str, dict[str, Any], Path]:
        if identifier in refresh:
            current = head_index.get(identifier)
            if current is None:
                raise ManagerError(f"updated capability {identifier!r} is absent at catalog HEAD")
            key, capability = current
            url, path = key
            return url, path, head_commits[key], capability, head_snapshots[key]
        return historical(identifier)

    identifiers = locked_identifiers | set(head_index)
    required_by: dict[str, set[str]] = {}
    companion_by: dict[str, dict[str, set[str]]] = {}
    enabled_tools: dict[str, set[str]] = {}
    resolved: set[str] = set()
    visiting: set[tuple[str, str]] = set()

    def visit(identifier: str, tools: set[str]) -> None:
        new_tools = tools - enabled_tools.get(identifier, set())
        if not new_tools:
            return
        if any((identifier, tool) in visiting for tool in new_tools):
            raise ManagerError(f"dependency cycle includes {identifier}")
        visiting.update((identifier, tool) for tool in new_tools)
        enabled_tools.setdefault(identifier, set()).update(new_tools)
        _, _, _, capability, _ = source(identifier)
        for reference in capability["dependencies"].get("required", []):
            try:
                dependency = resolve_identifier(reference, identifiers)
            except CatalogError as error:
                raise ManagerError(str(error)) from error
            required_by.setdefault(dependency, set()).add(identifier)
            visit(dependency, new_tools)
        companions = capability["dependencies"].get("companions", {})
        for tool in sorted(new_tools):
            for reference in companions.get(tool, []):
                try:
                    companion = resolve_identifier(reference, identifiers)
                except CatalogError as error:
                    raise ManagerError(str(error)) from error
                companion_by.setdefault(companion, {}).setdefault(tool, set()).add(
                    identifier
                )
                visit(companion, {tool})
        visiting.difference_update((identifier, tool) for tool in new_tools)
        resolved.add(identifier)

    for identifier in sorted(roots):
        visit(identifier, {"claude", "codex"})

    capabilities = []
    for identifier in sorted(resolved):
        url, path, commit, indexed_capability, snapshot = source(identifier)
        if identifier in roots:
            reason = {"kind": "root"}
        elif identifier in required_by:
            reason = {"kind": "required", "by": sorted(required_by[identifier])}
        else:
            reason = {
                "kind": "companion",
                "by": {
                    tool: sorted(parents)
                    for tool, parents in sorted(companion_by[identifier].items())
                },
            }
        capabilities.append(
            _capability_entry(
                identifier,
                url,
                path,
                commit,
                indexed_capability,
                snapshot,
                reason,
                enabled_tools[identifier],
            )
        )

    catalog_entries = []
    old_catalog_commits = _locked_commits(lock)
    for descriptor in sorted(manifest["catalogs"], key=_catalog_descriptor):
        key = _catalog_descriptor(descriptor)
        url, path = key
        advances = any(
            identifier in refresh and head_index.get(identifier, (None,))[0] == key
            for identifier in resolved
        )
        catalog_entries.append(
            _catalog_lock_entry(
                url,
                path,
                head_commits[key]
                if advances
                else old_catalog_commits.get(key, head_commits[key]),
            )
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "catalogs": catalog_entries,
        "capabilities": capabilities,
    }, snapshots


def _root_identifiers(lock: dict[str, Any]) -> set[str]:
    return {
        capability["identifier"]
        for capability in lock.get("capabilities", [])
        if capability.get("reason", {}).get("kind") == "root"
    }


def _manifest_matches_lock(manifest: dict[str, Any], lock: dict[str, Any]) -> bool:
    catalogs = {_catalog_descriptor(descriptor) for descriptor in manifest["catalogs"]}
    return catalogs == set(_locked_commits(lock)) and set(manifest["roots"]) == (
        _root_identifiers(lock)
    )


def _journal_path(project: Path) -> Path:
    path = Path(_git(["rev-parse", "--git-path", JOURNAL_NAME], cwd=project))
    return path if path.is_absolute() else project / path


def _stage_transaction(
    desired_lock: dict[str, Any],
    snapshots: dict[SnapshotKey, Path],
    write_json: Any,
) -> None:
    with tempfile.TemporaryDirectory() as temporary:
        staged = Path(temporary) / "project"
        staged.mkdir()
        _git(["init", "--quiet"], cwd=staged)
        _materialize(staged, desired_lock, snapshots)
        _merge_hook_settings(staged, None, desired_lock, write_json)
        drift = materialized_drift(staged, desired_lock)
        if drift:
            raise ManagerError("staged capability state is invalid: " + "; ".join(drift))


def _commit_transaction(
    project: Path,
    previous_manifest: dict[str, Any],
    previous_lock: dict[str, Any] | None,
    desired_manifest: dict[str, Any],
    desired_lock: dict[str, Any],
    snapshots: dict[SnapshotKey, Path],
    write_json: Any,
    approve_hook: Any = None,
) -> None:
    _prepare_hook_settings(project, previous_lock, desired_lock)
    _ensure_hook_approvals(
        project, desired_lock, snapshots, approve_hook, write_json
    )
    _stage_transaction(desired_lock, snapshots, write_json)
    journal_path = _journal_path(project)
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(
        journal_path,
        {
            "schema_version": JOURNAL_SCHEMA_VERSION,
            "previous_manifest": previous_manifest,
            "previous_lock": previous_lock,
            "desired_lock": desired_lock,
        },
    )
    _reconcile_exclusions(project, previous_lock, desired_lock)
    _prune_removed_targets(project, previous_lock, desired_lock)
    _materialize(project, desired_lock, snapshots)
    _merge_hook_settings(project, previous_lock, desired_lock, write_json)
    write_json(project / "capabilities.json", desired_manifest)
    # The lock is the commit marker and must remain the final authoritative write.
    write_json(project / "capabilities.lock.json", desired_lock)
    journal_path.unlink()


def recover_transaction(project: Path, write_json: Any) -> bool:
    journal_path = _journal_path(project)
    if not journal_path.exists():
        return False
    try:
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ManagerError(f"cannot recover malformed transaction journal: {error}") from error
    if (
        not isinstance(journal, dict)
        or journal.get("schema_version") != JOURNAL_SCHEMA_VERSION
        or not isinstance(journal.get("previous_manifest"), dict)
        or not isinstance(journal.get("desired_lock"), dict)
        or (
            journal.get("previous_lock") is not None
            and not isinstance(journal.get("previous_lock"), dict)
        )
    ):
        raise ManagerError("cannot recover unsupported transaction journal")

    lock_path = project / "capabilities.lock.json"
    current_lock = None
    if lock_path.exists():
        try:
            current_lock = json.loads(lock_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            current_lock = None
    if current_lock == journal["desired_lock"]:
        journal_path.unlink()
        return True

    previous_lock = journal["previous_lock"]
    _reconcile_exclusions(project, journal["desired_lock"], previous_lock)
    _prune_removed_targets(project, journal["desired_lock"], previous_lock or {
        "capabilities": []
    })
    if previous_lock is not None:
        with ExitStack() as stack:
            snapshots = _locked_snapshots(previous_lock, stack)
            _materialize(project, previous_lock, snapshots)
    _merge_hook_settings(project, journal["desired_lock"], previous_lock, write_json)
    write_json(project / "capabilities.json", journal["previous_manifest"])
    if previous_lock is None:
        lock_path.unlink(missing_ok=True)
    else:
        write_json(lock_path, previous_lock)
    journal_path.unlink()
    return True


def _prune_removed_targets(
    project: Path,
    previous_lock: dict[str, Any] | None,
    desired_lock: dict[str, Any],
) -> None:
    if previous_lock is None:
        return
    desired_paths = {
        target.get("path")
        for capability in desired_lock.get("capabilities", [])
        for target in capability.get("targets", [])
    }
    for capability in previous_lock.get("capabilities", []):
        for target in capability.get("targets", []):
            relative = target.get("path")
            if isinstance(relative, str) and relative not in desired_paths:
                _remove_owned(_destination(project, relative))


def capability_inventory(
    manifest: dict[str, Any], lock: dict[str, Any] | None
) -> list[dict[str, Any]]:
    with ExitStack() as stack:
        _, indexed = _catalog_inventory(manifest, lock, stack)
        identifiers = set(indexed)
        requested = set(manifest["roots"])
        resolved = {
            capability["identifier"]
            for capability in (lock or {}).get("capabilities", [])
        }
        recommended_by: dict[str, set[str]] = {}
        for identifier in resolved:
            indexed_capability = indexed.get(identifier)
            if indexed_capability is None:
                continue
            references = indexed_capability[1]["dependencies"].get("recommended", [])
            for reference in references:
                try:
                    recommendation = resolve_identifier(reference, identifiers)
                except CatalogError:
                    continue
                recommended_by.setdefault(recommendation, set()).add(identifier)

        result: list[dict[str, Any]] = []
        for identifier, (_, capability) in sorted(indexed.items()):
            targets = capability.get("targets", {})
            is_skill = any(
                target.get("kind") == "skill"
                for tool_targets in targets.values()
                for target in tool_targets
            )
            result.append(
                {
                    "identifier": identifier,
                    "kind": "skill" if is_skill else "capability",
                    "requested": identifier in requested,
                    "transitive": identifier in resolved and identifier not in requested,
                    "recommended": identifier in recommended_by,
                    "recommended_by": sorted(recommended_by.get(identifier, set())),
                    "resolved": identifier in resolved,
                }
            )
        return result


def replace_roots(
    project: Path,
    manifest: dict[str, Any],
    lock: dict[str, Any] | None,
    roots: list[str],
    write_json: Any,
    approve_hook: Any = None,
) -> None:
    desired = json.loads(json.dumps(manifest))
    desired["roots"] = sorted(set(roots))
    with ExitStack() as stack:
        existing = lock or {
            "schema_version": SCHEMA_VERSION,
            "catalogs": [],
            "capabilities": [],
        }
        added = sorted(set(desired["roots"]) - _root_identifiers(existing))
        desired_lock, snapshots = _update_lock(
            desired,
            existing,
            added,
            stack,
            catalog_commits=_locked_commits(lock),
            refresh_existing_dependencies=False,
            include_reverse_dependents=False,
        )
        _commit_transaction(
            project,
            manifest,
            lock,
            desired,
            desired_lock,
            snapshots,
            write_json,
            approve_hook,
        )


def select_recommendation(
    project: Path,
    manifest: dict[str, Any],
    lock: dict[str, Any] | None,
    identifier: str,
    write_json: Any,
    approve_hook: Any = None,
) -> None:
    inventory = {item["identifier"]: item for item in capability_inventory(manifest, lock)}
    item = inventory.get(identifier)
    if item is None:
        raise ManagerError(f"unknown capability {identifier!r}")
    if not item["recommended"]:
        raise ManagerError(f"{identifier} is not currently recommended")
    replace_roots(
        project,
        manifest,
        lock,
        [*manifest["roots"], identifier],
        write_json,
        approve_hook,
    )


def snapshot_roots(
    project: Path,
    manifest: dict[str, Any],
    lock: dict[str, Any] | None,
    write_json: Any,
    *,
    skills_only: bool,
    approve_hook: Any = None,
) -> int:
    inventory = capability_inventory(manifest, lock)
    roots = [
        item["identifier"]
        for item in inventory
        if not skills_only or item["kind"] == "skill"
    ]
    replace_roots(project, manifest, lock, roots, write_json, approve_hook)
    return len(roots)


def materialized_drift(project: Path, lock: dict[str, Any]) -> list[str]:
    drift: list[str] = []
    checked_settings: set[tuple[str, str, str]] = set()
    with ExitStack() as stack:
        snapshots = _locked_snapshots(lock, stack)
        for capability in lock["capabilities"]:
            source = capability["source"]
            snapshot = snapshots[_snapshot_key(source)]
            payload = snapshot / capability["catalog_path"]
            for target in capability["targets"]:
                relative = target.get("path")
                source = target.get("source")
                if not isinstance(relative, str) or not isinstance(source, str):
                    raise ManagerError(
                        f"{capability.get('identifier')}: malformed locked target"
                    )
                destination = _destination(project, relative)
                if target.get("state") == "writable-copy":
                    if not destination.exists():
                        drift.append(f"missing {relative}")
                    else:
                        source_path = payload / source
                        if source_path.is_dir():
                            matches = destination.is_dir() and hash_tree(
                                destination
                            ) == hash_tree(source_path)
                        elif source_path.is_file():
                            matches = (
                                destination.is_file()
                                and destination.read_bytes() == source_path.read_bytes()
                                and bool(destination.stat().st_mode & 0o111)
                                == bool(source_path.stat().st_mode & 0o111)
                            )
                        else:
                            matches = False
                        if not matches:
                            drift.append(f"modified {relative}")
                elif target.get("state") == "relative-symlink":
                    writable = next(
                        (
                            candidate
                            for candidate in capability["targets"]
                            if candidate.get("state") == "writable-copy"
                            and candidate.get("source") == source
                        ),
                        None,
                    )
                    if writable is None:
                        raise ManagerError(
                            f"{capability.get('identifier')}: mirror has no writable source"
                        )
                    expected = os.path.relpath(
                        _destination(project, writable["path"]), destination.parent
                    )
                    if not destination.is_symlink():
                        drift.append(f"missing {relative}")
                    elif os.readlink(destination) != expected:
                        drift.append(f"modified {relative}")
                settings = target.get("settings")
                if isinstance(settings, dict):
                    key = (
                        settings["path"],
                        settings["event"],
                        json.dumps(settings["entry"], sort_keys=True),
                    )
                    if key not in checked_settings:
                        checked_settings.add(key)
                        document = _read_settings(project / settings["path"])
                        if settings["entry"] not in _settings_entries(
                            document, settings["event"]
                        ):
                            drift.append(f"modified {settings['path']}")
    return sorted(drift)


def add_capability(
    project: Path,
    manifest: dict[str, Any],
    identifier: str,
    catalog_url: str,
    write_json: Any,
    lock: dict[str, Any] | None = None,
    approve_hook: Any = None,
) -> None:
    desired = json.loads(json.dumps(manifest))
    descriptor = {"url": catalog_url}
    if descriptor not in desired["catalogs"]:
        desired["catalogs"].append(descriptor)
    if identifier not in desired["roots"]:
        desired["roots"].append(identifier)
    desired["roots"].sort()
    with ExitStack() as stack:
        existing = lock or {
            "schema_version": SCHEMA_VERSION,
            "catalogs": [],
            "capabilities": [],
        }
        desired_lock, snapshots = _update_lock(
            desired,
            existing,
            [identifier],
            stack,
            refresh_existing_dependencies=False,
            include_reverse_dependents=False,
        )
        _commit_transaction(
            project,
            manifest,
            lock,
            desired,
            desired_lock,
            snapshots,
            write_json,
            approve_hook,
        )


def remove_capability(
    project: Path,
    manifest: dict[str, Any],
    lock: dict[str, Any] | None,
    identifier: str,
    write_json: Any,
    approve_hook: Any = None,
) -> None:
    desired = json.loads(json.dumps(manifest))
    if identifier not in desired["roots"]:
        raise ManagerError(f"{identifier} is not an explicitly requested capability")
    desired["roots"].remove(identifier)
    with ExitStack() as stack:
        existing = lock or {
            "schema_version": SCHEMA_VERSION,
            "catalogs": [],
            "capabilities": [],
        }
        desired_lock, snapshots = _update_lock(
            desired,
            existing,
            [],
            stack,
            catalog_commits=_locked_commits(lock),
            refresh_existing_dependencies=False,
            include_reverse_dependents=False,
        )
        _commit_transaction(
            project,
            manifest,
            lock,
            desired,
            desired_lock,
            snapshots,
            write_json,
            approve_hook,
        )


def synchronize(
    project: Path,
    manifest: dict[str, Any],
    lock: dict[str, Any] | None,
    write_json: Any,
    approve_hook: Any = None,
) -> None:
    with ExitStack() as stack:
        if lock is None:
            resolved_lock, snapshots = _build_lock(manifest, stack)
        elif not _manifest_matches_lock(manifest, lock):
            added = sorted(set(manifest["roots"]) - _root_identifiers(lock))
            resolved_lock, snapshots = _update_lock(
                manifest,
                lock,
                added,
                stack,
                catalog_commits=_locked_commits(lock),
                refresh_existing_dependencies=False,
                include_reverse_dependents=False,
            )
        else:
            resolved_lock = lock
            snapshots = _locked_snapshots(lock, stack)
        _commit_transaction(
            project,
            manifest,
            lock,
            manifest,
            resolved_lock,
            snapshots,
            write_json,
            approve_hook,
        )


def update_capabilities(
    project: Path,
    manifest: dict[str, Any],
    lock: dict[str, Any] | None,
    selected: list[str] | None,
    write_json: Any,
    approve_hook: Any = None,
) -> None:
    if lock is None:
        raise ManagerError("capability lock is missing; run 'capabilities sync'")
    with ExitStack() as stack:
        desired_lock, snapshots = _update_lock(manifest, lock, selected, stack)
        _commit_transaction(
            project,
            manifest,
            lock,
            manifest,
            desired_lock,
            snapshots,
            write_json,
            approve_hook,
        )


def migrate_state(
    project: Path,
    previous_manifest: dict[str, Any],
    previous_lock: dict[str, Any],
    desired_manifest: dict[str, Any],
    desired_lock: dict[str, Any],
    write_json: Any,
    approve_hook: Any = None,
) -> None:
    with ExitStack() as stack:
        snapshots = _locked_snapshots(desired_lock, stack)
        _commit_transaction(
            project,
            previous_manifest,
            previous_lock,
            desired_manifest,
            desired_lock,
            snapshots,
            write_json,
            approve_hook,
        )
