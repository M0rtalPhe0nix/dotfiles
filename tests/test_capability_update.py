from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

RUNTIME = Path(__file__).parents[1] / "dot_local/share/dotfiles/capabilities/src"
sys.path.insert(0, str(RUNTIME))

from dotfiles_capabilities import cli  # noqa: E402


class CapabilityUpdateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.catalog = self.root / "catalog"
        self.project = self.root / "project"
        self.catalog.mkdir()
        self.project.mkdir()
        self._git(self.catalog, "init", "-q")
        self._git(self.catalog, "config", "user.name", "Capability Test")
        self._git(self.catalog, "config", "user.email", "capability@example.invalid")
        self._git(self.project, "init", "-q")
        self._capability("base", required=[], body="base v1\n")
        self._capability("feature", required=["base"], body="feature v1\n")
        self._capability("consumer", required=["base"], body="consumer v1\n")
        self._capability("unrelated", required=[], body="unrelated v1\n")
        self.initial_commit = self._catalog_commit("initial catalog")
        self.assertEqual(self._run("init").returncode, 0)
        for root in ("feature", "consumer", "unrelated"):
            added = self._run(
                "add", "--catalog", str(self.catalog), f"acme/update/{root}"
            )
            self.assertEqual(added.returncode, 0, added.stderr)

    @staticmethod
    def _git(repository: Path, *arguments: str) -> str:
        return subprocess.run(
            ["git", "-C", str(repository), *arguments],
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        ).stdout.strip()

    def _capability(self, name: str, *, required: list[str], body: str) -> None:
        payload = self.catalog / name
        (payload / "skill").mkdir(parents=True, exist_ok=True)
        (payload / "skill/SKILL.md").write_text(body, encoding="utf-8")
        (payload / "capability.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "identifier": f"acme/update/{name}",
                    "description": f"{name} capability",
                    "dependencies": {
                        "required": required,
                        "recommended": [],
                        "companions": {"claude": [], "codex": []},
                    },
                    "targets": {
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
                }
            ),
            encoding="utf-8",
        )

    def _catalog_commit(self, message: str) -> str:
        validated = self._run("validate", str(self.catalog), project=self.catalog)
        self.assertEqual(validated.returncode, 0, validated.stderr)
        self._git(self.catalog, "add", ".")
        self._git(self.catalog, "commit", "-qm", message)
        return self._git(self.catalog, "rev-parse", "HEAD")

    def _run(
        self, *arguments: str, project: Path | None = None
    ) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(RUNTIME)
        return subprocess.run(
            [sys.executable, "-m", "dotfiles_capabilities", *arguments],
            cwd=project or self.project,
            env=environment,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def test_selective_update_refreshes_the_affected_shared_subgraph(self) -> None:
        for name in ("base", "feature", "consumer", "unrelated"):
            (self.catalog / name / "skill/SKILL.md").write_text(
                f"{name} v2\n", encoding="utf-8"
            )
        updated_commit = self._catalog_commit("update every payload")

        updated = self._run("update", "acme/update/feature")

        self.assertEqual(updated.returncode, 0, updated.stderr)
        lock = json.loads((self.project / "capabilities.lock.json").read_text())
        commits = {
            item["identifier"]: item["source"]["commit"]
            for item in lock["capabilities"]
        }
        self.assertEqual(commits["acme/update/feature"], updated_commit)
        self.assertEqual(commits["acme/update/base"], updated_commit)
        self.assertEqual(commits["acme/update/consumer"], updated_commit)
        self.assertEqual(commits["acme/update/unrelated"], self.initial_commit)
        self.assertEqual(
            (self.project / ".agents/skills/unrelated/SKILL.md").read_text(),
            "unrelated v1\n",
        )

        (self.catalog / "feature/skill/SKILL.md").write_text(
            "feature v3\n", encoding="utf-8"
        )
        self._catalog_commit("advance after selective update")
        synchronized = self._run("sync")
        self.assertEqual(synchronized.returncode, 0, synchronized.stderr)
        synchronized_lock = json.loads(
            (self.project / "capabilities.lock.json").read_text()
        )
        self.assertEqual(
            {
                item["identifier"]: item["source"]["commit"]
                for item in synchronized_lock["capabilities"]
            },
            commits,
        )
        self.assertEqual(
            (self.project / ".agents/skills/feature/SKILL.md").read_text(),
            "feature v2\n",
        )

    def test_full_update_refreshes_resolved_graph_without_adopting_new_roots(self) -> None:
        for name in ("base", "feature", "consumer", "unrelated"):
            (self.catalog / name / "skill/SKILL.md").write_text(
                f"{name} v2\n", encoding="utf-8"
            )
        self._capability("new", required=[], body="new v1\n")
        updated_commit = self._catalog_commit("update graph and add catalog entry")
        manifest_before = json.loads(
            (self.project / "capabilities.json").read_text()
        )

        updated = self._run("update", "--all")

        self.assertEqual(updated.returncode, 0, updated.stderr)
        manifest_after = json.loads((self.project / "capabilities.json").read_text())
        self.assertEqual(manifest_after["roots"], manifest_before["roots"])
        lock = json.loads((self.project / "capabilities.lock.json").read_text())
        self.assertEqual(
            {item["source"]["commit"] for item in lock["capabilities"]},
            {updated_commit},
        )
        self.assertNotIn(
            "acme/update/new",
            {item["identifier"] for item in lock["capabilities"]},
        )
        self.assertFalse((self.project / ".agents/skills/new").exists())

    def test_next_command_recovers_when_interrupted_before_final_lock_write(self) -> None:
        (self.catalog / "feature/skill/SKILL.md").write_text(
            "feature v2\n", encoding="utf-8"
        )
        self._catalog_commit("update feature")
        lock_path = self.project / "capabilities.lock.json"
        lock_before = lock_path.read_text(encoding="utf-8")
        real_write = cli._write_json
        writes: list[str] = []

        def interrupt_lock(path: Path, document: dict[str, object]) -> None:
            writes.append(path.name)
            if path.name == "capabilities.lock.json":
                raise OSError("simulated interruption before lock commit")
            real_write(path, document)

        previous_cwd = Path.cwd()
        try:
            os.chdir(self.project)
            with (
                mock.patch.object(cli, "_write_json", side_effect=interrupt_lock),
                redirect_stdout(StringIO()),
                redirect_stderr(StringIO()),
            ):
                interrupted = cli.main(["update", "--all"])
        finally:
            os.chdir(previous_cwd)

        self.assertEqual(interrupted, 1)
        self.assertEqual(writes[-1], "capabilities.lock.json")
        self.assertEqual(lock_path.read_text(encoding="utf-8"), lock_before)
        journal = self.project / ".git/dotfiles-capabilities-transaction.json"
        self.assertTrue(journal.is_file())
        self.assertEqual(
            (self.project / ".agents/skills/feature/SKILL.md").read_text(),
            "feature v2\n",
        )

        recovered = self._run("sync")

        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        self.assertFalse(journal.exists())
        self.assertEqual(lock_path.read_text(encoding="utf-8"), lock_before)
        self.assertEqual(
            (self.project / ".agents/skills/feature/SKILL.md").read_text(),
            "feature v1\n",
        )

    def test_supported_old_schema_requires_explicit_migration(self) -> None:
        manifest_path = self.project / "capabilities.json"
        lock_path = self.project / "capabilities.lock.json"
        manifest = json.loads(manifest_path.read_text())
        lock = json.loads(lock_path.read_text())
        manifest["schema_version"] = 0
        lock["schema_version"] = 0
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        lock_path.write_text(json.dumps(lock), encoding="utf-8")

        rejected = self._run("sync")

        self.assertEqual(rejected.returncode, 1)
        self.assertIn("requires explicit migration", rejected.stderr)

        migrated = self._run("migrate")

        self.assertEqual(migrated.returncode, 0, migrated.stderr)
        migrated_manifest = json.loads(manifest_path.read_text())
        migrated_lock = json.loads(lock_path.read_text())
        self.assertEqual(migrated_manifest["schema_version"], 1)
        self.assertEqual(migrated_lock["schema_version"], 1)
        self.assertEqual(migrated_manifest["roots"], manifest["roots"])
        self.assertEqual(
            [item["identifier"] for item in migrated_lock["capabilities"]],
            [item["identifier"] for item in lock["capabilities"]],
        )

    def test_newer_schema_is_rejected_clearly(self) -> None:
        manifest_path = self.project / "capabilities.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["schema_version"] = 2
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        rejected = self._run("migrate")

        self.assertEqual(rejected.returncode, 1)
        self.assertIn("newer schema_version 2", rejected.stderr)


if __name__ == "__main__":
    unittest.main()
