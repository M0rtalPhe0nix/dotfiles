from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from dotfiles_capabilities.catalog import (
    AmbiguousIdentifierError,
    CatalogError,
    UnsupportedSchemaError,
    hash_tree,
    load_catalog_index,
    load_capability_metadata,
    validate_catalog,
    resolve_identifier,
)
from dotfiles_capabilities.cli import main

FIXTURES = Path(__file__).parent / "fixtures" / "capability-catalog"
REPOSITORY_ROOT = Path(__file__).parent.parent
FOUNDATIONAL_CATALOG = REPOSITORY_ROOT / "capability-catalog"

FOUNDATIONAL_CAPABILITIES = {
    "batch-grill-me": [],
    "codebase-design": [],
    "design-an-interface": [],
    "domain-modeling": [],
    "grill-me": ["grilling"],
    "grill-with-docs": ["domain-modeling", "grilling"],
    "grilling": [],
    "improve-codebase-architecture": [
        "codebase-design",
        "domain-modeling",
        "grilling",
    ],
    "ubiquitous-language": [],
    "writing-great-skills": [],
}

WORKFLOW_CAPABILITIES = {
    "code-review": ([], ["setup-matt-pocock-skills"]),
    "handoff": ([], []),
    "implement": (["code-review", "tdd"], []),
    "qa": ([], ["setup-matt-pocock-skills"]),
    "request-refactor-plan": ([], ["setup-matt-pocock-skills"]),
    "setup-matt-pocock-skills": ([], ["domain-modeling"]),
    "tdd": ([], []),
    "teach": ([], []),
    "to-spec": ([], ["setup-matt-pocock-skills"]),
    "to-tickets": ([], ["setup-matt-pocock-skills"]),
    "wayfinder": (
        ["domain-modeling", "grilling"],
        ["setup-matt-pocock-skills"],
    ),
}

TOOLING_CAPABILITIES = {
    "claude-md-improver": ([], [], {"claude": [], "codex": []}),
    "compare-dotfiles": ([], [], {"claude": [], "codex": []}),
    "excalidraw": ([], [], {"claude": [], "codex": []}),
    "feature-diagrammer": (["excalidraw"], [], {"claude": [], "codex": []}),
    "grill-feature-diagrams": (
        ["excalidraw", "grill-me"],
        [],
        {
            "claude": ["feature-diagrammer"],
            "codex": ["feature-diagrammer"],
        },
    ),
    "plugin-creator": (["skill-creator"], [], {"claude": [], "codex": []}),
    "review-agent": ([], [], {"claude": [], "codex": []}),
    "setup-pre-commit": ([], [], {"claude": [], "codex": []}),
    "skill-creator": ([], ["skill-installer"], {"claude": [], "codex": []}),
    "skill-installer": ([], [], {"claude": [], "codex": []}),
    "speckit-diagrams": (["excalidraw"], [], {"claude": [], "codex": []}),
}

TOOLING_SKILLS = set(TOOLING_CAPABILITIES) - {"feature-diagrammer"}


class SchemaContractTests(unittest.TestCase):
    def test_newer_capability_schema_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            metadata = Path(temporary) / "capability.json"
            metadata.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "identifier": "acme/tools/example",
                        "description": "Example capability",
                        "dependencies": {
                            "required": [],
                            "recommended": [],
                            "companions": {"claude": [], "codex": []},
                        },
                        "targets": {"claude": [], "codex": []},
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(UnsupportedSchemaError, "newer schema_version 2"):
                load_capability_metadata(metadata)

    def test_short_identifier_resolves_only_when_unambiguous(self) -> None:
        identifiers = {
            "acme/tools/format",
            "elsewhere/recipes/review",
        }
        self.assertEqual(
            resolve_identifier("format", identifiers),
            "acme/tools/format",
        )

        with self.assertRaises(AmbiguousIdentifierError):
            resolve_identifier(
                "format",
                identifiers | {"elsewhere/recipes/format"},
            )

    def test_newer_generated_catalog_schema_is_rejected_by_consumers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            index = Path(temporary) / "catalog.json"
            index.write_text(
                json.dumps({"schema_version": 2, "capabilities": []}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(UnsupportedSchemaError, "newer schema_version 2"):
                load_catalog_index(index)


class TreeHashContractTests(unittest.TestCase):
    def test_hash_tracks_paths_types_executable_bits_links_and_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script = root / "run.sh"
            script.write_bytes(b"#!/bin/sh\nprintf 'ok\\n'\n")
            script.chmod(0o644)
            (root / "nested").mkdir()
            (root / "nested" / "data.txt").write_bytes(b"payload")
            (root / "current").symlink_to("nested/data.txt")
            original = hash_tree(root)

            script.chmod(0o755)
            executable = hash_tree(root)
            self.assertNotEqual(executable, original)

            script.chmod(0o644)
            (root / "current").unlink()
            (root / "current").symlink_to("run.sh")
            linked_elsewhere = hash_tree(root)
            self.assertNotEqual(linked_elsewhere, original)

            (root / "current").unlink()
            (root / "current").symlink_to("nested/data.txt")
            (root / "nested" / "data.txt").write_bytes(b"changed")
            changed_bytes = hash_tree(root)
            self.assertNotEqual(changed_bytes, original)

            (root / "nested" / "data.txt").write_bytes(b"payload")
            os.rename(root / "nested" / "data.txt", root / "nested" / "renamed.txt")
            renamed = hash_tree(root)
            self.assertNotEqual(renamed, original)


class CatalogValidationContractTests(unittest.TestCase):
    def test_public_upstream_provenance_is_validated_and_indexed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog = Path(temporary) / "catalog"
            shutil.copytree(FIXTURES / "valid", catalog)
            metadata_path = catalog / "format/capability.json"
            metadata = json.loads(metadata_path.read_text())
            metadata["upstream"] = {
                "repository": "example/portable-skills",
                "source_type": "github",
                "path": "skills/format/SKILL.md",
                "content_hash": "a" * 64,
            }
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

            result = validate_catalog(catalog, write_index=True)

            self.assertEqual(result.status, "PASS", "\n".join(result.errors))
            indexed = load_catalog_index(catalog / "catalog.json")
            formatted = next(
                item
                for item in indexed["capabilities"]
                if item["identifier"] == "acme/portable-ai/format"
            )
            self.assertEqual(formatted["upstream"], metadata["upstream"])

    def test_tooling_family_is_a_valid_dependency_and_companion_closure(self) -> None:
        result = validate_catalog(FOUNDATIONAL_CATALOG, check_index=True)

        self.assertEqual(result.status, "PASS", "\n".join(result.errors))
        self.assertEqual(result.warnings, ())
        self.assertIsNotNone(result.index)
        by_name = {
            item["identifier"].rsplit("/", 1)[-1]: item
            for item in result.index["capabilities"]
        }
        self.assertLessEqual(set(TOOLING_CAPABILITIES), set(by_name))
        for name, (required, recommended, companions) in TOOLING_CAPABILITIES.items():
            capability = by_name[name]
            self.assertEqual(
                capability["dependencies"],
                {
                    "required": required,
                    "recommended": recommended,
                    "companions": companions,
                },
            )
            if name == "feature-diagrammer":
                self.assertEqual(
                    capability["targets"],
                    {
                        "claude": [
                            {
                                "kind": "agent",
                                "source": "feature-diagrammer.md",
                                "destination": ".claude/agents/feature-diagrammer.md",
                            }
                        ],
                        "codex": [
                            {
                                "kind": "agent",
                                "source": "feature-diagrammer-codex.md",
                                "destination": ".codex/agents/feature-diagrammer.md",
                            }
                        ],
                    },
                )
            else:
                self.assertEqual(
                    capability["targets"],
                    {
                        "claude": [
                            {
                                "kind": "skill",
                                "source": "skill",
                                "destination": f".claude/skills/{name}",
                            }
                        ],
                        "codex": [
                            {
                                "kind": "skill",
                                "source": "skill",
                                "destination": f".agents/skills/{name}",
                            }
                        ],
                    },
                )

            payload = FOUNDATIONAL_CATALOG / name
            for path in payload.rglob("*"):
                if not path.is_file() or path.suffix not in {".md", ".yaml", ".yml"}:
                    continue
                instructions = path.read_text(encoding="utf-8")
                for forbidden in (
                    "~/.codex/skills",
                    "~/.claude/skills",
                    "$CODEX_HOME/skills",
                    "${CODEX_HOME:-$HOME/.codex}/skills",
                    "/Users/",
                ):
                    self.assertNotIn(forbidden, instructions, str(path))

        installer = FOUNDATIONAL_CATALOG / "skill-installer" / "skill"
        self.assertFalse((installer / "scripts" / "install-skill-from-github.py").exists())
        installer_instructions = (installer / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("dotfiles skills add --catalog", installer_instructions)
        self.assertIn("Never install into a global", installer_instructions)

    def test_tooling_skills_use_writable_codex_copies_and_claude_mirrors(self) -> None:
        for name in TOOLING_SKILLS:
            canonical = FOUNDATIONAL_CATALOG / name / "skill"
            self.assertTrue((canonical / "SKILL.md").is_file())
            codex = REPOSITORY_ROOT / ".agents/skills" / name
            claude = REPOSITORY_ROOT / ".claude/skills" / name
            self.assertTrue(codex.is_dir(), str(codex))
            self.assertFalse(codex.is_symlink(), str(codex))
            self.assertEqual(hash_tree(codex), hash_tree(canonical))
            self.assertTrue(claude.is_symlink(), str(claude))
            self.assertEqual(os.readlink(claude), f"../../.agents/skills/{name}")
            self.assertEqual(claude.resolve(), codex.resolve())

    def test_workflow_family_is_a_valid_dependency_closure(self) -> None:
        result = validate_catalog(FOUNDATIONAL_CATALOG, check_index=True)

        self.assertEqual(result.status, "PASS", "\n".join(result.errors))
        self.assertEqual(result.warnings, ())
        self.assertIsNotNone(result.index)
        by_name = {
            item["identifier"].rsplit("/", 1)[-1]: item
            for item in result.index["capabilities"]
        }
        self.assertLessEqual(set(WORKFLOW_CAPABILITIES), set(by_name))
        for name, (required, recommended) in WORKFLOW_CAPABILITIES.items():
            capability = by_name[name]
            self.assertEqual(
                capability["dependencies"],
                {
                    "required": required,
                    "recommended": recommended,
                    "companions": {"claude": [], "codex": []},
                },
            )
            self.assertEqual(
                capability["targets"],
                {
                    "claude": [
                        {
                            "kind": "skill",
                            "source": "skill",
                            "destination": f".claude/skills/{name}",
                        }
                    ],
                    "codex": [
                        {
                            "kind": "skill",
                            "source": "skill",
                            "destination": f".agents/skills/{name}",
                        }
                    ],
                },
            )

            payload = FOUNDATIONAL_CATALOG / name / "skill"
            for path in payload.rglob("*"):
                if not path.is_file() or path.suffix not in {".md", ".yaml", ".yml"}:
                    continue
                instructions = path.read_text(encoding="utf-8")
                for forbidden in (
                    "~/.claude/skills",
                    "~/.agents/skills",
                    "/Users/",
                    "`/research`",
                    "the /prototype skill",
                    "`/grilling`",
                    "`/domain-modeling`",
                    "`/setup-matt-pocock-skills`",
                ):
                    self.assertNotIn(forbidden, instructions, str(path))

    def test_workflow_skills_use_writable_codex_copies_and_claude_mirrors(self) -> None:
        for name in WORKFLOW_CAPABILITIES:
            canonical = FOUNDATIONAL_CATALOG / name / "skill"
            self.assertTrue((canonical / "SKILL.md").is_file())
            codex = REPOSITORY_ROOT / ".agents/skills" / name
            claude = REPOSITORY_ROOT / ".claude/skills" / name
            self.assertTrue(codex.is_dir(), str(codex))
            self.assertFalse(codex.is_symlink(), str(codex))
            self.assertEqual(hash_tree(codex), hash_tree(canonical))
            self.assertTrue(claude.is_symlink(), str(claude))
            self.assertEqual(os.readlink(claude), f"../../.agents/skills/{name}")
            self.assertEqual(claude.resolve(), codex.resolve())

    def test_foundational_family_is_a_valid_dependency_closure(self) -> None:
        result = validate_catalog(FOUNDATIONAL_CATALOG, check_index=True)

        self.assertEqual(result.status, "PASS", "\n".join(result.errors))
        self.assertEqual(result.warnings, ())
        self.assertIsNotNone(result.index)
        by_name = {
            item["identifier"].rsplit("/", 1)[-1]: item
            for item in result.index["capabilities"]
        }
        self.assertLessEqual(set(FOUNDATIONAL_CAPABILITIES), set(by_name))
        for name, required in FOUNDATIONAL_CAPABILITIES.items():
            capability = by_name[name]
            self.assertEqual(
                capability["dependencies"],
                {
                    "required": required,
                    "recommended": [],
                    "companions": {"claude": [], "codex": []},
                },
            )
            self.assertEqual(
                capability["targets"],
                {
                    "claude": [
                        {
                            "kind": "skill",
                            "source": "skill",
                            "destination": f".claude/skills/{name}",
                        }
                    ],
                    "codex": [
                        {
                            "kind": "skill",
                            "source": "skill",
                            "destination": f".agents/skills/{name}",
                        }
                    ],
                },
            )

            payload = FOUNDATIONAL_CATALOG / name / "skill"
            for path in payload.rglob("*"):
                if not path.is_file() or path.suffix not in {".md", ".yaml", ".yml"}:
                    continue
                instructions = path.read_text(encoding="utf-8")
                for forbidden in ("~/.claude/skills", "~/.agents/skills", "/Users/"):
                    self.assertNotIn(forbidden, instructions, str(path))

    def test_foundational_skills_use_writable_codex_copies_and_claude_mirrors(self) -> None:
        for name in FOUNDATIONAL_CAPABILITIES:
            canonical = FOUNDATIONAL_CATALOG / name / "skill"
            self.assertTrue((canonical / "SKILL.md").is_file())
            codex = REPOSITORY_ROOT / ".agents/skills" / name
            claude = REPOSITORY_ROOT / ".claude/skills" / name
            self.assertTrue(codex.is_dir(), str(codex))
            self.assertFalse(codex.is_symlink(), str(codex))
            self.assertEqual(hash_tree(codex), hash_tree(canonical))
            self.assertTrue(claude.is_symlink(), str(claude))
            self.assertEqual(os.readlink(claude), f"../../.agents/skills/{name}")
            self.assertEqual(claude.resolve(), codex.resolve())

    def test_valid_fixture_generates_a_deterministic_index(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog = Path(temporary) / "catalog"
            shutil.copytree(FIXTURES / "valid", catalog)

            result = validate_catalog(catalog, write_index=True)

            self.assertEqual(result.status, "PASS")
            index = json.loads((catalog / "catalog.json").read_text(encoding="utf-8"))
            self.assertEqual(index["schema_version"], 1)
            self.assertEqual(
                [item["identifier"] for item in index["capabilities"]],
                ["acme/portable-ai/format", "acme/portable-ai/review"],
            )
            self.assertTrue(
                all(len(item["content_hash"]) == 64 for item in index["capabilities"])
            )

            (catalog / "catalog.json").write_text("manually maintained", encoding="utf-8")
            second = validate_catalog(catalog, write_index=True)
            self.assertEqual(second.status, "PASS")
            self.assertEqual(
                json.loads((catalog / "catalog.json").read_text(encoding="utf-8")),
                index,
            )

            checked = validate_catalog(catalog, check_index=True)
            self.assertEqual(checked.status, "PASS")
            (catalog / "catalog.json").write_text(
                json.dumps({"schema_version": 1, "capabilities": []}),
                encoding="utf-8",
            )
            stale = validate_catalog(catalog, check_index=True)
            self.assertEqual(stale.status, "FAIL")
            self.assertIn("generated catalog index is stale", "\n".join(stale.errors))

    def test_invalid_fixture_reports_graph_and_target_errors(self) -> None:
        result = validate_catalog(FIXTURES / "invalid")

        self.assertEqual(result.status, "FAIL")
        diagnostics = "\n".join(result.errors)
        self.assertIn("malformed metadata", diagnostics)
        self.assertIn("duplicate identifier", diagnostics)
        self.assertIn("missing required dependency", diagnostics)
        self.assertIn("dependency cycle", diagnostics)
        self.assertIn("destination must be a portable project-relative path", diagnostics)

    def test_cli_emits_the_shared_machine_readable_validation_vocabulary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog = Path(temporary) / "catalog"
            shutil.copytree(FIXTURES / "valid", catalog)
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                exit_code = main(["validate", str(catalog), "--json"])

            self.assertEqual(exit_code, 0)
            result = json.loads(output.getvalue())
            self.assertEqual(result, {"status": "PASS", "errors": [], "warnings": []})
            self.assertTrue((catalog / "catalog.json").is_file())

    def test_target_specific_companions_do_not_create_cross_tool_cycles(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog = Path(temporary) / "catalog"
            shutil.copytree(FIXTURES / "valid", catalog)
            format_path = catalog / "format" / "capability.json"
            review_path = catalog / "review" / "capability.json"
            format_metadata = json.loads(format_path.read_text(encoding="utf-8"))
            review_metadata = json.loads(review_path.read_text(encoding="utf-8"))
            review_metadata["dependencies"]["required"] = []
            format_metadata["dependencies"]["companions"]["claude"] = ["review"]
            review_metadata["dependencies"]["companions"]["codex"] = ["format"]
            format_path.write_text(json.dumps(format_metadata), encoding="utf-8")
            review_path.write_text(json.dumps(review_metadata), encoding="utf-8")

            result = validate_catalog(catalog)

            self.assertEqual(result.status, "PASS")

    def test_malformed_generated_index_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            index_path = Path(temporary) / "catalog.json"
            index_path.write_text(
                json.dumps({"schema_version": 1, "capabilities": [{}]}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(CatalogError, "identifier"):
                load_catalog_index(index_path)


if __name__ == "__main__":
    unittest.main()
