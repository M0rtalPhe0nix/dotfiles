from __future__ import annotations

import json
import os
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


class PortableCatalogDescriptorTests(unittest.TestCase):
    def test_sync_consumes_a_catalog_in_a_portable_repository_subdirectory(self) -> None:
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
            (project / "capabilities.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "catalogs": [
                            {"url": str(source), "path": "capability-catalog"}
                        ],
                        "roots": ["acme/portable/example"],
                    }
                ),
                encoding="utf-8",
            )

            synchronized = self._run("sync", cwd=project)

            self.assertEqual(synchronized.returncode, 0, synchronized.stderr)
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


if __name__ == "__main__":
    unittest.main()
