from __future__ import annotations

import json
import hashlib
import os
import re
import stat
import struct
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

CAPABILITY_SCHEMA_VERSION = 1
CATALOG_SCHEMA_VERSION = 1
CAPABILITY_METADATA_NAME = "capability.json"
CATALOG_INDEX_NAME = "catalog.json"

_IDENTIFIER_SEGMENT = r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?"
_IDENTIFIER = re.compile(
    rf"^{_IDENTIFIER_SEGMENT}/{_IDENTIFIER_SEGMENT}/{_IDENTIFIER_SEGMENT}$"
)


class CatalogError(ValueError):
    """A portable catalog contract was not satisfied."""


class UnsupportedSchemaError(CatalogError):
    """A document uses a schema version this CLI cannot consume."""


class UnknownIdentifierError(CatalogError):
    """A capability reference does not exist in the catalog."""


class AmbiguousIdentifierError(CatalogError):
    """A short capability reference has more than one match."""


@dataclass(frozen=True)
class ValidationResult:
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    index: dict[str, Any] | None = None

    @property
    def status(self) -> str:
        if self.errors:
            return "FAIL"
        if self.warnings:
            return "PASS-WITH-WARNINGS"
        return "PASS"


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CatalogError(f"{path}: malformed metadata: {error}") from error
    if not isinstance(document, dict):
        raise CatalogError(f"{path}: top-level value must be an object")
    return document


def _require_schema_version(
    document: dict[str, Any], expected: int, path: Path
) -> None:
    version = document.get("schema_version")
    if type(version) is not int:
        raise UnsupportedSchemaError(f"{path}: schema_version must be an integer")
    if version > expected:
        raise UnsupportedSchemaError(
            f"{path}: newer schema_version {version} is unsupported; expected {expected}"
        )
    if version < expected:
        raise UnsupportedSchemaError(
            f"{path}: older schema_version {version} requires explicit migration"
        )


def load_capability_metadata(path: Path) -> dict[str, Any]:
    document = _load_json_object(path)
    _require_schema_version(document, CAPABILITY_SCHEMA_VERSION, path)
    identifier = document.get("identifier")
    if not isinstance(identifier, str) or not _IDENTIFIER.fullmatch(identifier):
        raise CatalogError(
            f"{path}: identifier must have the form owner/repository/name"
        )
    return document


def load_catalog_index(path: Path) -> dict[str, Any]:
    document = _load_json_object(path)
    _require_schema_version(document, CATALOG_SCHEMA_VERSION, path)
    capabilities = document.get("capabilities")
    if not isinstance(capabilities, list):
        raise CatalogError(f"{path}: capabilities must be a list")
    identifiers: set[str] = set()
    for position, capability in enumerate(capabilities):
        field = f"{path}: capabilities[{position}]"
        if not isinstance(capability, dict):
            raise CatalogError(f"{field} must be an object")
        identifier = capability.get("identifier")
        if not isinstance(identifier, str) or not _IDENTIFIER.fullmatch(identifier):
            raise CatalogError(f"{field}.identifier must have the form owner/repository/name")
        if identifier in identifiers:
            raise CatalogError(f"{field}.identifier duplicates {identifier!r}")
        identifiers.add(identifier)
        relative_path = capability.get("path")
        if not isinstance(relative_path, str) or not _portable_path(relative_path):
            raise CatalogError(f"{field}.path must be a portable relative path")
        content_hash = capability.get("content_hash")
        if not isinstance(content_hash, str) or not re.fullmatch(
            r"[0-9a-f]{64}", content_hash
        ):
            raise CatalogError(f"{field}.content_hash must be a SHA-256 digest")
        if not isinstance(capability.get("description"), str):
            raise CatalogError(f"{field}.description must be a string")
        if not isinstance(capability.get("dependencies"), dict):
            raise CatalogError(f"{field}.dependencies must be an object")
        if not isinstance(capability.get("targets"), dict):
            raise CatalogError(f"{field}.targets must be an object")
    return document


def resolve_identifier(reference: str, identifiers: Iterable[str]) -> str:
    available = set(identifiers)
    if "/" in reference:
        if not _IDENTIFIER.fullmatch(reference):
            raise UnknownIdentifierError(
                f"invalid capability identifier {reference!r}; expected owner/repository/name"
            )
        if reference not in available:
            raise UnknownIdentifierError(f"unknown capability {reference!r}")
        return reference

    matches = sorted(identifier for identifier in available if identifier.rsplit("/", 1)[-1] == reference)
    if not matches:
        raise UnknownIdentifierError(f"unknown capability short name {reference!r}")
    if len(matches) > 1:
        raise AmbiguousIdentifierError(
            f"ambiguous capability short name {reference!r}: {', '.join(matches)}"
        )
    return matches[0]


def _hash_field(digest: Any, value: bytes) -> None:
    digest.update(struct.pack(">Q", len(value)))
    digest.update(value)


def hash_tree(root: Path) -> str:
    """Hash a filesystem tree without following symlinks.

    Each sorted entry contributes its POSIX relative path, entry type, executable
    state, and type-specific payload. File payloads are raw bytes and symlink
    payloads are their targets, so the digest does not depend on traversal order.
    """
    if not root.is_dir():
        raise CatalogError(f"{root}: capability payload must be a directory")

    entries: list[tuple[str, Path]] = []

    def collect(directory: Path) -> None:
        for entry in os.scandir(directory):
            path = Path(entry.path)
            relative = path.relative_to(root).as_posix()
            entries.append((relative, path))
            if entry.is_dir(follow_symlinks=False):
                collect(path)

    collect(root)
    digest = hashlib.sha256()
    digest.update(b"dotfiles-capability-tree-v1\0")
    for relative, path in sorted(entries):
        mode = path.lstat().st_mode
        if stat.S_ISREG(mode):
            entry_type = b"file"
            payload = path.read_bytes()
        elif stat.S_ISDIR(mode):
            entry_type = b"directory"
            payload = b""
        elif stat.S_ISLNK(mode):
            entry_type = b"symlink"
            payload = os.readlink(path).encode("utf-8", errors="surrogateescape")
        else:
            raise CatalogError(f"{path}: unsupported payload entry type")
        _hash_field(digest, relative.encode("utf-8", errors="surrogateescape"))
        _hash_field(digest, entry_type)
        digest.update(b"1" if entry_type == b"file" and mode & 0o111 else b"0")
        _hash_field(digest, payload)
    return digest.hexdigest()


def _string_list(value: Any, field: str, errors: list[str]) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        errors.append(f"{field} must be a list of non-empty capability identifiers")
        return []
    return value


def _portable_path(value: str, *, allow_dot: bool = False) -> bool:
    if not value or value.startswith("~") or "\\" in value:
        return False
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        return False
    return allow_dot or value != "."


def _validate_metadata(path: Path, document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    prefix = str(path)
    if not isinstance(document.get("description"), str) or not document["description"].strip():
        errors.append(f"{prefix}: description must be a non-empty string")

    dependencies = document.get("dependencies")
    if not isinstance(dependencies, dict):
        errors.append(f"{prefix}: dependencies must be an object")
    else:
        _string_list(
            dependencies.get("required"), f"{prefix}: dependencies.required", errors
        )
        _string_list(
            dependencies.get("recommended"),
            f"{prefix}: dependencies.recommended",
            errors,
        )
        companions = dependencies.get("companions")
        if not isinstance(companions, dict):
            errors.append(f"{prefix}: dependencies.companions must be an object")
        else:
            unknown = sorted(set(companions) - {"claude", "codex"})
            if unknown:
                errors.append(
                    f"{prefix}: unsupported companion targets: {', '.join(unknown)}"
                )
            for tool in ("claude", "codex"):
                _string_list(
                    companions.get(tool),
                    f"{prefix}: dependencies.companions.{tool}",
                    errors,
                )

    targets = document.get("targets")
    if not isinstance(targets, dict):
        errors.append(f"{prefix}: targets must be an object")
        return errors
    unknown_targets = sorted(set(targets) - {"claude", "codex"})
    if unknown_targets:
        errors.append(f"{prefix}: unsupported targets: {', '.join(unknown_targets)}")
    capability_root = path.parent.resolve()
    for tool in ("claude", "codex"):
        declarations = targets.get(tool)
        if not isinstance(declarations, list) or not declarations:
            errors.append(f"{prefix}: targets.{tool} must be a non-empty list")
            continue
        for position, declaration in enumerate(declarations):
            field = f"{prefix}: targets.{tool}[{position}]"
            if not isinstance(declaration, dict):
                errors.append(f"{field} must be an object")
                continue
            kind = declaration.get("kind")
            if kind not in {"skill", "agent", "hook", "script", "asset", "reference"}:
                errors.append(f"{field}.kind is invalid")
            source = declaration.get("source")
            if not isinstance(source, str) or not _portable_path(source, allow_dot=True):
                errors.append(f"{field}.source must be a portable relative path")
            else:
                source_path = path.parent / source
                try:
                    contained = source_path.resolve().is_relative_to(capability_root)
                except OSError:
                    contained = False
                if not contained or not os.path.lexists(source_path):
                    errors.append(f"{field}.source must exist inside the capability")
            destination = declaration.get("destination")
            kind_prefixes = {
                "claude": {
                    "skill": (".claude/skills/",),
                    "agent": (".claude/agents/",),
                    "hook": (".claude/hooks/",),
                    "script": (".claude/",),
                    "asset": (".claude/",),
                    "reference": (".claude/",),
                },
                "codex": {
                    "skill": (".agents/skills/",),
                    "agent": (".codex/agents/",),
                    "hook": (".codex/hooks/",),
                    "script": (".codex/",),
                    "asset": (".agents/", ".codex/"),
                    "reference": (".agents/", ".codex/"),
                },
            }
            valid_prefixes = kind_prefixes[tool].get(kind, ())
            if (
                not isinstance(destination, str)
                or not _portable_path(destination)
                or not destination.startswith(valid_prefixes)
            ):
                errors.append(
                    f"{field}.destination must be a portable project-relative path for {tool}"
                )
            if "executable" in declaration and type(declaration["executable"]) is not bool:
                errors.append(f"{field}.executable must be a boolean")
            if kind in {"hook", "script"} and declaration.get("executable") is not True:
                errors.append(f"{field}.executable must be true for {kind} targets")
            if kind == "hook":
                supported_events = {
                    "PermissionRequest",
                    "PostCompact",
                    "PostToolUse",
                    "PreCompact",
                    "PreToolUse",
                    "SessionEnd",
                    "SessionStart",
                    "Stop",
                    "SubagentStart",
                    "SubagentStop",
                    "UserPromptSubmit",
                }
                event = declaration.get("event")
                if event not in supported_events:
                    errors.append(f"{field}.event is not a supported hook event")
                matcher = declaration.get("matcher")
                if not isinstance(matcher, str) or not matcher:
                    errors.append(f"{field}.matcher must be a non-empty string")
                if isinstance(source, str) and (path.parent / source).is_dir():
                    errors.append(f"{field}.source must be an executable hook file")
    return errors


def _relationships(document: dict[str, Any], tool: str | None = None) -> list[str]:
    dependencies = document.get("dependencies")
    if not isinstance(dependencies, dict):
        return []
    if tool is None:
        value = dependencies.get("required")
    else:
        companions = dependencies.get("companions")
        value = companions.get(tool) if isinstance(companions, dict) else None
    return value if isinstance(value, list) else []


def _dependency_cycles(graph: dict[str, list[str]]) -> list[str]:
    errors: list[str] = []
    state: dict[str, int] = {}
    stack: list[str] = []

    def visit(identifier: str) -> None:
        state[identifier] = 1
        stack.append(identifier)
        for dependency in graph.get(identifier, []):
            if state.get(dependency, 0) == 0:
                visit(dependency)
            elif state.get(dependency) == 1:
                start = stack.index(dependency)
                cycle = stack[start:] + [dependency]
                diagnostic = f"dependency cycle: {' -> '.join(cycle)}"
                if diagnostic not in errors:
                    errors.append(diagnostic)
        stack.pop()
        state[identifier] = 2

    for identifier in sorted(graph):
        if state.get(identifier, 0) == 0:
            visit(identifier)
    return errors


def _write_json(path: Path, document: dict[str, Any]) -> None:
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(document, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def validate_catalog(
    root: Path, *, write_index: bool = False, check_index: bool = False
) -> ValidationResult:
    root = root.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    if not root.is_dir():
        return ValidationResult((f"{root}: catalog directory does not exist",), ())

    documents: list[tuple[Path, dict[str, Any]]] = []
    metadata_paths = sorted(root.rglob(CAPABILITY_METADATA_NAME))
    if not metadata_paths:
        return ValidationResult((f"{root}: catalog contains no capability metadata",), ())
    for path in metadata_paths:
        try:
            document = load_capability_metadata(path)
        except CatalogError as error:
            errors.append(str(error))
            continue
        errors.extend(_validate_metadata(path, document))
        documents.append((path, document))

    by_identifier: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path, document in documents:
        identifier = document["identifier"]
        if identifier in by_identifier:
            first = by_identifier[identifier][0]
            errors.append(f"duplicate identifier {identifier!r}: {first} and {path}")
        else:
            by_identifier[identifier] = (path, document)

    destinations: dict[tuple[str, str], str] = {}
    for _, document in documents:
        targets = document.get("targets")
        if not isinstance(targets, dict):
            continue
        for tool in ("claude", "codex"):
            declarations = targets.get(tool)
            if not isinstance(declarations, list):
                continue
            for declaration in declarations:
                if not isinstance(declaration, dict):
                    continue
                destination = declaration.get("destination")
                if not isinstance(destination, str):
                    continue
                owner = destinations.setdefault((tool, destination), document["identifier"])
                if owner != document["identifier"]:
                    errors.append(
                        f"duplicate {tool} target destination {destination!r}: "
                        f"{owner} and {document['identifier']}"
                    )

    required_graph: dict[str, list[str]] = {
        identifier: [] for identifier in by_identifier
    }
    companion_graphs: dict[str, dict[str, list[str]]] = {
        tool: {identifier: [] for identifier in by_identifier}
        for tool in ("claude", "codex")
    }
    for identifier, (_, document) in sorted(by_identifier.items()):
        for relation, missing_level in (("required", "error"), ("recommended", "warning")):
            dependencies = document.get("dependencies")
            values = dependencies.get(relation) if isinstance(dependencies, dict) else []
            if not isinstance(values, list):
                continue
            for reference in values:
                if not isinstance(reference, str):
                    continue
                try:
                    resolved = resolve_identifier(reference, by_identifier)
                except CatalogError as error:
                    diagnostic = f"{identifier}: missing {relation} dependency {reference!r}: {error}"
                    (errors if missing_level == "error" else warnings).append(diagnostic)
                    continue
                if relation == "required":
                    required_graph[identifier].append(resolved)
        for tool in ("claude", "codex"):
            for reference in _relationships(document, tool):
                if not isinstance(reference, str):
                    continue
                try:
                    resolved = resolve_identifier(reference, by_identifier)
                except CatalogError as error:
                    errors.append(
                        f"{identifier}: missing {tool} companion {reference!r}: {error}"
                    )
                    continue
                companion_graphs[tool][identifier].append(resolved)
    required_cycles = _dependency_cycles(required_graph)
    errors.extend(required_cycles)
    for tool, companions in companion_graphs.items():
        graph = {
            identifier: required_graph[identifier] + companions[identifier]
            for identifier in required_graph
        }
        for cycle in _dependency_cycles(graph):
            if cycle not in required_cycles:
                errors.append(f"{tool} {cycle}")

    index: dict[str, Any] | None = None
    if not errors:
        capabilities: list[dict[str, Any]] = []
        for identifier, (path, document) in sorted(by_identifier.items()):
            try:
                content_hash = hash_tree(path.parent)
            except (CatalogError, OSError) as error:
                errors.append(f"{path.parent}: cannot hash capability payload: {error}")
                continue
            capabilities.append(
                {
                    "identifier": identifier,
                    "path": path.parent.relative_to(root).as_posix(),
                    "content_hash": content_hash,
                    "description": document["description"],
                    "dependencies": document["dependencies"],
                    "targets": document["targets"],
                }
            )
        index = {
            "schema_version": CATALOG_SCHEMA_VERSION,
            "capabilities": capabilities,
        }
        index_path = root / CATALOG_INDEX_NAME
        if errors:
            index = None
        elif check_index:
            if not index_path.is_file():
                errors.append(f"{index_path}: generated catalog index is missing")
            else:
                try:
                    existing = load_catalog_index(index_path)
                except CatalogError as error:
                    errors.append(str(error))
                else:
                    if existing != index:
                        errors.append(f"{index_path}: generated catalog index is stale")
        elif write_index:
            try:
                _write_json(index_path, index)
            except OSError as error:
                errors.append(f"{index_path}: cannot write generated catalog index: {error}")
    if errors:
        index = None
    return ValidationResult(tuple(errors), tuple(warnings), index)
