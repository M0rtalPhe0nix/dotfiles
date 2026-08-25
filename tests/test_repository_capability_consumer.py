from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


RUNTIME = (
    Path(__file__).parents[1]
    / "dot_local/share/dotfiles/capabilities/src"
)
REPOSITORY = Path(__file__).parents[1]
PORTABLE_CATALOG = {
    "url": "https://github.com/M0rtalPhe0nix/dotfiles.git",
    "path": "capability-catalog",
}
CATALOG_COMMIT = "f6447b97b0f75bfdf71c8c8aacb361d7f5bd036b"


class PortableCatalogDescriptorTests(unittest.TestCase):
    def test_add_consumes_a_catalog_in_a_portable_repository_subdirectory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            catalog = source / "capability-catalog"
            capability = catalog / "example"
            project = root / "consumer"
            (capability / "skill").mkdir(parents=True)
            project.mkdir()
            (capability / "skill/SKILL.md").write_text("example\n", encoding="utf-8")
            (capability / "capability.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "identifier": "acme/portable/example",
                        "description": "Example repository-local skill",
                        "dependencies": {
                            "required": [],
                            "recommended": [],
                            "companions": {"claude": [], "codex": []},
                        },
                        "targets": {
                            "claude": [
                                {
                                    "kind": "skill",
                                    "source": "skill",
                                    "destination": ".claude/skills/example",
                                }
                            ],
                            "codex": [
                                {
                                    "kind": "skill",
                                    "source": "skill",
                                    "destination": ".agents/skills/example",
                                }
                            ],
                        },
                    }
                ),
                encoding="utf-8",
            )
            self._git(source, "init", "-q")
            self._git(source, "config", "user.name", "Consumer Test")
            self._git(source, "config", "user.email", "consumer@example.invalid")
            validated = self._run("validate", str(catalog), cwd=source)
            self.assertEqual(validated.returncode, 0, validated.stderr)
            self._git(source, "add", ".")
            self._git(source, "commit", "-qm", "catalog snapshot")
            commit = self._git(source, "rev-parse", "HEAD")
            self._git(project, "init", "-q")
            initialized = self._run("init", cwd=project)
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            synchronized = self._run(
                "add",
                "--catalog",
                str(source),
                "--catalog-path",
                "capability-catalog",
                "acme/portable/example",
                cwd=project,
            )

            self.assertEqual(synchronized.returncode, 0, synchronized.stderr)
            manifest = json.loads((project / "capabilities.json").read_text())
            self.assertEqual(
                manifest["catalogs"],
                [{"url": str(source), "path": "capability-catalog"}],
            )
            lock = json.loads((project / "capabilities.lock.json").read_text())
            self.assertEqual(
                lock["catalogs"],
                [
                    {
                        "url": str(source),
                        "path": "capability-catalog",
                        "commit": commit,
                    }
                ],
            )
            self.assertEqual(
                lock["capabilities"][0]["source"],
                {
                    "url": str(source),
                    "path": "capability-catalog",
                    "commit": commit,
                },
            )
            self.assertTrue((project / ".agents/skills/example/SKILL.md").is_file())
            self.assertEqual(
                os.readlink(project / ".claude/skills/example"),
                "../../.agents/skills/example",
            )

    @staticmethod
    def _git(repository: Path, *arguments: str) -> str:
        return subprocess.run(
            ["git", "-C", str(repository), *arguments],
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        ).stdout.strip()

    @staticmethod
    def _run(*arguments: str, cwd: Path) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(RUNTIME)
        return subprocess.run(
            [sys.executable, "-m", "dotfiles_capabilities", *arguments],
            cwd=cwd,
            env=environment,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )


class RepositoryConsumerContractTests(unittest.TestCase):
    def test_manifest_explicitly_requests_every_skill_and_local_hook(self) -> None:
        catalog = json.loads((REPOSITORY / "capability-catalog/catalog.json").read_text())
        expected_roots = sorted(
            capability["identifier"]
            for capability in catalog["capabilities"]
            if any(
                target["kind"] == "skill"
                for targets in capability["targets"].values()
                for target in targets
            )
            or capability["identifier"].endswith(
                ("/rtk-guardrail", "/python-format")
            )
        )

        manifest = json.loads((REPOSITORY / "capabilities.json").read_text())

        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["catalogs"], [PORTABLE_CATALOG])
        self.assertEqual(manifest["roots"], expected_roots)
        self.assertTrue(all("*" not in root for root in manifest["roots"]))

    def test_lock_and_materialization_make_the_repository_self_contained(self) -> None:
        catalog = json.loads((REPOSITORY / "capability-catalog/catalog.json").read_text())
        indexed = {
            capability["identifier"]: capability
            for capability in catalog["capabilities"]
        }
        manifest = json.loads((REPOSITORY / "capabilities.json").read_text())
        lock = json.loads((REPOSITORY / "capabilities.lock.json").read_text())

        self.assertFalse((REPOSITORY / "skills-lock.json").exists())
        self.assertEqual(
            lock["catalogs"], [{**PORTABLE_CATALOG, "commit": CATALOG_COMMIT}]
        )
        self.assertEqual(
            {capability["identifier"] for capability in lock["capabilities"]},
            set(indexed),
        )
        for capability in lock["capabilities"]:
            identifier = capability["identifier"]
            self.assertEqual(
                capability["source"], {**PORTABLE_CATALOG, "commit": CATALOG_COMMIT}
            )
            self.assertEqual(capability["content_hash"], indexed[identifier]["content_hash"])
            expected_reason = "root" if identifier in manifest["roots"] else "companion"
            self.assertEqual(capability["reason"]["kind"], expected_reason)
            for target in capability["targets"]:
                destination = REPOSITORY / target["path"]
                if target["state"] == "relative-symlink":
                    self.assertTrue(destination.is_symlink(), target["path"])
                    writable = next(
                        candidate
                        for candidate in capability["targets"]
                        if candidate["state"] == "writable-copy"
                        and candidate["source"] == target["source"]
                    )
                    expected = os.path.relpath(
                        REPOSITORY / writable["path"], destination.parent
                    )
                    self.assertEqual(os.readlink(destination), expected)
                else:
                    self.assertTrue(destination.exists(), target["path"])
                    self.assertFalse(destination.is_symlink(), target["path"])
                    self.assertTrue(
                        destination.stat().st_mode & stat.S_IWUSR, target["path"]
                    )
                ignored = subprocess.run(
                    ["git", "check-ignore", "--no-index", "-q", target["path"]],
                    cwd=REPOSITORY,
                    check=False,
                )
                self.assertEqual(ignored.returncode, 0, target["path"])
                tracked = subprocess.run(
                    ["git", "ls-files", "--error-unmatch", "--", target["path"]],
                    cwd=REPOSITORY,
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self.assertNotEqual(tracked.returncode, 0, target["path"])

        for state_file in ("capabilities.json", "capabilities.lock.json"):
            ignored = subprocess.run(
                ["git", "check-ignore", "--no-index", "-q", state_file],
                cwd=REPOSITORY,
                check=False,
            )
            self.assertNotEqual(ignored.returncode, 0, state_file)

        expected_exclusions = {
            f"/{target['path'].rstrip('/')}"
            f"{'/' if target['state'] == 'writable-copy' and target.get('directory') else ''}"
            for capability in lock["capabilities"]
            for target in capability["targets"]
        }
        expected_exclusions.update(
            f"/{target['settings']['path']}"
            for capability in lock["capabilities"]
            for target in capability["targets"]
            if target.get("settings", {}).get("file_state") == "generated"
        )
        actual_exclusions = {
            line
            for line in (REPOSITORY / ".git/info/exclude").read_text().splitlines()
            if line and not line.startswith("#")
        }
        self.assertEqual(actual_exclusions, expected_exclusions)

        claude_settings = json.loads(
            (REPOSITORY / ".claude/settings.json").read_text()
        )
        codex_settings = json.loads((REPOSITORY / ".codex/hooks.json").read_text())
        self.assertEqual(set(claude_settings["hooks"]), {"PostToolUse", "PreToolUse"})
        self.assertEqual(set(codex_settings["hooks"]), {"PostToolUse", "PreToolUse"})
        self.assertTrue((REPOSITORY / ".claude/agents/feature-diagrammer.md").is_file())
        self.assertTrue((REPOSITORY / ".codex/agents/feature-diagrammer.md").is_file())


if __name__ == "__main__":
    unittest.main()
