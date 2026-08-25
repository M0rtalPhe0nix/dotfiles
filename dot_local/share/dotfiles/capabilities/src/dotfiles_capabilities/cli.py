from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from dotfiles_capabilities.catalog import CatalogError, validate_catalog
from dotfiles_capabilities.manager import (
    ManagerError,
    add_capability,
    capability_inventory,
    materialized_drift,
    migrate_state,
    recover_transaction,
    remove_capability,
    select_recommendation,
    snapshot_roots,
    synchronize,
    update_capabilities,
)

SCHEMA_VERSION = 1
MANIFEST_NAME = "capabilities.json"
LOCK_NAME = "capabilities.lock.json"

EMPTY_MANIFEST: dict[str, Any] = {
    "schema_version": SCHEMA_VERSION,
    "catalogs": [],
    "roots": [],
}
EMPTY_LOCK: dict[str, Any] = {
    "schema_version": SCHEMA_VERSION,
    "catalogs": [],
    "capabilities": [],
}


class CapabilityError(Exception):
    """An error that can be presented directly to a CLI user."""


def _git_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise CapabilityError("not inside a Git worktree")
    return Path(result.stdout.strip())


def _validate_list(document: dict[str, Any], field: str, path: Path) -> None:
    if not isinstance(document.get(field), list):
        raise CapabilityError(f"{path.name}: {field!r} must be a list")


def _load_and_validate(path: Path, kind: str) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CapabilityError(f"cannot read valid JSON from {path.name}: {error}") from error

    if not isinstance(document, dict):
        raise CapabilityError(f"{path.name}: top-level value must be an object")
    version = document.get("schema_version")
    if type(version) is not int:
        raise CapabilityError(
            f"{path.name}: schema_version must be an integer"
        )
    if version > SCHEMA_VERSION:
        raise CapabilityError(
            f"{path.name}: newer schema_version {version} is unsupported; "
            f"expected {SCHEMA_VERSION}"
        )
    if version < SCHEMA_VERSION:
        raise CapabilityError(
            f"{path.name}: schema_version {version} requires explicit migration; "
            "run 'capabilities migrate'"
        )
    _validate_list(document, "catalogs", path)
    _validate_list(document, "roots" if kind == "manifest" else "capabilities", path)
    return document


def _write_json(path: Path, document: dict[str, Any]) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(document, stream, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _project_root() -> Path:
    root = _git_root()
    recover_transaction(root, _write_json)
    return root


def _approve_hook(
    identifier: str, path: str, content_hash: str, content: str
) -> bool:
    print(f"Hook approval required: {identifier} -> {path}")
    print(f"SHA-256: {content_hash}")
    print("--- hook content ---")
    print(content, end="" if content.endswith("\n") else "\n")
    print("--- end hook content ---")
    try:
        response = input("Approve this hook content locally? [y/N] ")
    except EOFError:
        return False
    return response.strip().lower() in {"y", "yes"}


def initialize() -> int:
    root = _project_root()
    manifest = root / MANIFEST_NAME
    lock = root / LOCK_NAME

    if manifest.exists():
        _load_and_validate(manifest, "manifest")
    if lock.exists():
        _load_and_validate(lock, "lock")

    if not manifest.exists():
        _write_json(manifest, EMPTY_MANIFEST)
    if not lock.exists():
        _write_json(lock, EMPTY_LOCK)

    print(f"Initialized capabilities in {root}")
    return 0


def validate_catalog_command(
    path: Path, *, machine_readable: bool, write_index: bool
) -> int:
    result = validate_catalog(
        path, write_index=write_index, check_index=not write_index
    )
    if machine_readable:
        print(
            json.dumps(
                {
                    "status": result.status,
                    "errors": list(result.errors),
                    "warnings": list(result.warnings),
                },
                sort_keys=True,
            )
        )
    else:
        print(result.status)
        for diagnostic in (*result.errors, *result.warnings):
            print(diagnostic)
    return 1 if result.errors else 0


def add(identifier: str, catalog_url: str) -> int:
    root = _project_root()
    manifest_path = root / MANIFEST_NAME
    lock_path = root / LOCK_NAME
    if not manifest_path.is_file():
        raise CapabilityError("capability state is not initialized; run 'capabilities init'")
    manifest = _load_and_validate(manifest_path, "manifest")
    lock = _load_and_validate(lock_path, "lock") if lock_path.exists() else None
    print(f"Plan: request {identifier} and synchronize its required capabilities")
    add_capability(
        root, manifest, identifier, catalog_url, _write_json, lock, _approve_hook
    )
    print(f"Result: added {identifier} and synchronized capabilities in {root}")
    return 0


def remove(identifier: str) -> int:
    root = _project_root()
    manifest_path = root / MANIFEST_NAME
    lock_path = root / LOCK_NAME
    if not manifest_path.is_file():
        raise CapabilityError("capability state is not initialized; run 'capabilities init'")
    manifest = _load_and_validate(manifest_path, "manifest")
    lock = _load_and_validate(lock_path, "lock") if lock_path.exists() else None
    print(f"Plan: remove requested capability {identifier} and prune unreachable dependencies")
    remove_capability(root, manifest, lock, identifier, _write_json, _approve_hook)
    print(f"Result: removed {identifier} and synchronized capabilities in {root}")
    return 0


def sync() -> int:
    root = _project_root()
    manifest_path = root / MANIFEST_NAME
    lock_path = root / LOCK_NAME
    if not manifest_path.is_file():
        raise CapabilityError("capability state is not initialized; run 'capabilities init'")
    manifest = _load_and_validate(manifest_path, "manifest")
    lock = _load_and_validate(lock_path, "lock") if lock_path.exists() else None
    print("Plan: reconcile desired roots and restore materialized capabilities")
    synchronize(root, manifest, lock, _write_json, _approve_hook)
    print(f"Result: synchronized capabilities in {root}")
    return 0


def update(identifiers: list[str], *, update_all: bool) -> int:
    root = _project_root()
    manifest_path = root / MANIFEST_NAME
    lock_path = root / LOCK_NAME
    if not manifest_path.is_file():
        raise CapabilityError("capability state is not initialized; run 'capabilities init'")
    manifest = _load_and_validate(manifest_path, "manifest")
    lock = _load_and_validate(lock_path, "lock") if lock_path.exists() else None
    selection = None if update_all else identifiers
    label = "the entire resolved graph" if update_all else ", ".join(identifiers)
    print(f"Plan: update {label} from current catalog content")
    update_capabilities(
        root, manifest, lock, selection, _write_json, _approve_hook
    )
    print(f"Result: updated capabilities in {root}")
    return 0


def _migration_document(path: Path, kind: str) -> tuple[dict[str, Any], bool]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CapabilityError(f"cannot read valid JSON from {path.name}: {error}") from error
    if not isinstance(document, dict):
        raise CapabilityError(f"{path.name}: top-level value must be an object")
    version = document.get("schema_version")
    if type(version) is not int:
        raise CapabilityError(f"{path.name}: schema_version must be an integer")
    if version > SCHEMA_VERSION:
        raise CapabilityError(
            f"{path.name}: newer schema_version {version} is unsupported; "
            f"expected {SCHEMA_VERSION}"
        )
    if version < 0:
        raise CapabilityError(f"{path.name}: unsupported older schema_version {version}")
    migrated = version == 0
    if migrated:
        document = json.loads(json.dumps(document))
        document["schema_version"] = SCHEMA_VERSION
    _validate_list(document, "catalogs", path)
    _validate_list(document, "roots" if kind == "manifest" else "capabilities", path)
    return document, migrated


def migrate() -> int:
    root = _project_root()
    manifest_path = root / MANIFEST_NAME
    lock_path = root / LOCK_NAME
    if not manifest_path.is_file() or not lock_path.is_file():
        raise CapabilityError("capability state is incomplete; run 'capabilities init'")
    manifest, manifest_changed = _migration_document(manifest_path, "manifest")
    lock, lock_changed = _migration_document(lock_path, "lock")
    previous_manifest = json.loads(json.dumps(manifest))
    previous_lock = json.loads(json.dumps(lock))
    if manifest_changed:
        previous_manifest["schema_version"] = 0
    if lock_changed:
        previous_lock["schema_version"] = 0
    if not manifest_changed and not lock_changed:
        print("Capability state already uses the current schema")
        return 0
    print("Plan: explicitly migrate capability state to schema_version 1")
    migrate_state(
        root,
        previous_manifest,
        previous_lock,
        manifest,
        lock,
        _write_json,
        _approve_hook,
    )
    print(f"Result: migrated capability state in {root}")
    return 0


def list_command(*, skills_only: bool, machine_readable: bool) -> int:
    root = _project_root()
    manifest_path = root / MANIFEST_NAME
    lock_path = root / LOCK_NAME
    if not manifest_path.is_file():
        raise CapabilityError("capability state is not initialized; run 'capabilities init'")
    manifest = _load_and_validate(manifest_path, "manifest")
    lock = _load_and_validate(lock_path, "lock") if lock_path.exists() else None
    inventory = capability_inventory(manifest, lock)
    if skills_only:
        inventory = [item for item in inventory if item["kind"] == "skill"]
    if machine_readable:
        print(json.dumps(inventory, sort_keys=True))
        return 0
    print("IDENTIFIER\tREQUESTED\tTRANSITIVE\tRECOMMENDED\tRESOLVED")
    for item in inventory:
        values = (
            item["identifier"],
            *("yes" if item[field] else "no" for field in (
                "requested",
                "transitive",
                "recommended",
                "resolved",
            )),
        )
        print("\t".join(values))
    return 0


def recommend(identifier: str) -> int:
    root = _project_root()
    manifest_path = root / MANIFEST_NAME
    lock_path = root / LOCK_NAME
    if not manifest_path.is_file():
        raise CapabilityError("capability state is not initialized; run 'capabilities init'")
    manifest = _load_and_validate(manifest_path, "manifest")
    lock = _load_and_validate(lock_path, "lock") if lock_path.exists() else None
    print(f"Plan: promote recommended capability {identifier} to an explicit root")
    select_recommendation(
        root, manifest, lock, identifier, _write_json, _approve_hook
    )
    print(f"Result: requested {identifier} and synchronized capabilities in {root}")
    return 0


def snapshot(*, skills_only: bool, catalog_url: str | None) -> int:
    root = _project_root()
    manifest_path = root / MANIFEST_NAME
    lock_path = root / LOCK_NAME
    if not manifest_path.is_file():
        raise CapabilityError("capability state is not initialized; run 'capabilities init'")
    manifest = _load_and_validate(manifest_path, "manifest")
    if catalog_url is not None and {"url": catalog_url} not in manifest["catalogs"]:
        manifest = json.loads(json.dumps(manifest))
        manifest["catalogs"].append({"url": catalog_url})
    lock = _load_and_validate(lock_path, "lock") if lock_path.exists() else None
    label = "skills" if skills_only else "capabilities"
    print(f"Plan: snapshot every current catalog {label} as explicit roots")
    count = snapshot_roots(
        root,
        manifest,
        lock,
        _write_json,
        skills_only=skills_only,
        approve_hook=_approve_hook,
    )
    print(f"Result: snapshotted {count} {label} and synchronized capabilities in {root}")
    return 0


def diff_command() -> int:
    root = _project_root()
    lock_path = root / LOCK_NAME
    if not lock_path.is_file():
        raise CapabilityError("capability lock is missing; run 'capabilities sync'")
    lock = _load_and_validate(lock_path, "lock")
    drift = materialized_drift(root, lock)
    if drift:
        print("Materialized drift:")
        for change in drift:
            print(change)
        return 1
    print("No materialized drift")
    return 0


def _parser(*, skills_only: bool) -> argparse.ArgumentParser:
    group = "skills" if skills_only else "capabilities"
    snapshot_kind = "skill" if skills_only else "capability"
    parser = argparse.ArgumentParser(prog=f"dotfiles {group}")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="initialize capability state in the Git worktree")
    add_parser = commands.add_parser(
        "add", help="add a qualified capability and synchronize its required graph"
    )
    add_parser.add_argument("identifier")
    add_parser.add_argument("--catalog", required=True, dest="catalog_url")
    remove_parser = commands.add_parser(
        "remove", help="remove an explicit root and prune unreachable dependencies"
    )
    remove_parser.add_argument("identifier")
    commands.add_parser("sync", help="restore materialized capabilities from the lock")
    update_parser = commands.add_parser(
        "update", help="refresh selected roots or the entire resolved graph"
    )
    update_parser.add_argument("identifiers", nargs="*")
    update_parser.add_argument("--all", action="store_true", dest="update_all")
    commands.add_parser("migrate", help="explicitly migrate supported older schemas")
    list_parser = commands.add_parser(
        "list", help="explain requested, transitive, recommended, and resolved state"
    )
    list_parser.add_argument("--json", action="store_true", dest="machine_readable")
    recommend_parser = commands.add_parser(
        "recommend", help="promote a current recommendation to an explicit root"
    )
    recommend_parser.add_argument("identifier")
    snapshot_parser = commands.add_parser(
        "snapshot", help=f"request every {snapshot_kind} currently in the catalogs"
    )
    snapshot_parser.add_argument("--catalog", dest="catalog_url")
    commands.add_parser("diff", help="report drift in materialized capability paths")
    validate = commands.add_parser(
        "validate", help="validate capability metadata and regenerate its catalog index"
    )
    validate.add_argument("path", nargs="?", default=".", type=Path)
    validate.add_argument("--json", action="store_true", dest="machine_readable")
    validate.add_argument(
        "--check",
        action="store_false",
        dest="write_index",
        help="validate without rewriting the generated catalog index",
    )
    validate.set_defaults(write_index=True)
    return parser


def main(arguments: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if arguments is None else arguments)
    skills_only = bool(arguments and arguments[0] == "skills")
    if skills_only:
        arguments.pop(0)
    parser = _parser(skills_only=skills_only)
    namespace = parser.parse_args(arguments)
    try:
        if namespace.command == "init":
            return initialize()
        if namespace.command == "add":
            return add(namespace.identifier, namespace.catalog_url)
        if namespace.command == "remove":
            return remove(namespace.identifier)
        if namespace.command == "sync":
            return sync()
        if namespace.command == "update":
            if not namespace.update_all and not namespace.identifiers:
                parser.error("update requires root names or --all")
            if namespace.update_all and namespace.identifiers:
                parser.error("update --all does not accept root names")
            return update(namespace.identifiers, update_all=namespace.update_all)
        if namespace.command == "migrate":
            return migrate()
        if namespace.command == "list":
            return list_command(
                skills_only=skills_only,
                machine_readable=namespace.machine_readable,
            )
        if namespace.command == "recommend":
            return recommend(namespace.identifier)
        if namespace.command == "snapshot":
            return snapshot(
                skills_only=skills_only,
                catalog_url=namespace.catalog_url,
            )
        if namespace.command == "diff":
            return diff_command()
        if namespace.command == "validate":
            return validate_catalog_command(
                namespace.path,
                machine_readable=namespace.machine_readable,
                write_index=namespace.write_index,
            )
    except (CapabilityError, ManagerError, CatalogError, OSError) as error:
        print(f"dotfiles capabilities: {error}", file=sys.stderr)
        return 1
    parser.error(f"unknown command: {namespace.command}")
    return 2
