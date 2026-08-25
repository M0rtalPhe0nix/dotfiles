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


class CapabilityWorkflowTests(unittest.TestCase):
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
        self._capability(
            "feature", required=["base"], recommended=["other"], body="feature v1\n"
        )
        self._capability("other", required=[], body="other v1\n")
        self._catalog_commit("initial catalog")
        self._run("init")

    @staticmethod
    def _git(repository: Path, *arguments: str) -> str:
        return subprocess.run(
            ["git", "-C", str(repository), *arguments],
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        ).stdout.strip()

    def _capability(
        self,
        name: str,
        *,
        required: list[str],
        body: str,
        recommended: list[str] | None = None,
    ) -> None:
        payload = self.catalog / name
        (payload / "skill").mkdir(parents=True, exist_ok=True)
        (payload / "skill/SKILL.md").write_text(body, encoding="utf-8")
        (payload / "capability.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "identifier": f"acme/workflow/{name}",
                    "description": f"{name} capability",
                    "dependencies": {
                        "required": required,
                        "recommended": recommended or [],
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
        result = self._run("validate", str(self.catalog), project=self.catalog)
        self.assertEqual(result.returncode, 0, result.stderr)
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

    def test_remove_prunes_the_explicit_root_and_unreachable_dependency(self) -> None:
        added = self._run(
            "add", "--catalog", str(self.catalog), "acme/workflow/feature"
        )
        self.assertEqual(added.returncode, 0, added.stderr)

        removed = self._run("remove", "acme/workflow/feature")

        self.assertEqual(removed.returncode, 0, removed.stderr)
        manifest = json.loads((self.project / "capabilities.json").read_text())
        lock = json.loads((self.project / "capabilities.lock.json").read_text())
        self.assertEqual(manifest["roots"], [])
        self.assertEqual(lock["capabilities"], [])
        self.assertFalse((self.project / ".agents/skills/feature").exists())
        self.assertFalse((self.project / ".agents/skills/base").exists())

    def test_sync_reconciles_direct_manifest_edits_at_the_pinned_commit(self) -> None:
        added = self._run(
            "add", "--catalog", str(self.catalog), "acme/workflow/feature"
        )
        self.assertEqual(added.returncode, 0, added.stderr)
        lock_path = self.project / "capabilities.lock.json"
        pinned = json.loads(lock_path.read_text())["catalogs"][0]["commit"]

        (self.catalog / "other/skill/SKILL.md").write_text(
            "other v2\n", encoding="utf-8"
        )
        self._catalog_commit("change unrelated capability")
        manifest_path = self.project / "capabilities.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["roots"] = ["acme/workflow/other"]
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        synchronized = self._run("sync")

        self.assertEqual(synchronized.returncode, 0, synchronized.stderr)
        lock = json.loads(lock_path.read_text())
        self.assertEqual(lock["catalogs"][0]["commit"], pinned)
        self.assertEqual(
            [item["identifier"] for item in lock["capabilities"]],
            ["acme/workflow/other"],
        )
        self.assertEqual(
            (self.project / ".agents/skills/other/SKILL.md").read_text(),
            "other v1\n",
        )
        self.assertFalse((self.project / ".agents/skills/feature").exists())

    def test_list_and_recommendation_selection_explain_desired_state(self) -> None:
        self._run("add", "--catalog", str(self.catalog), "acme/workflow/feature")

        listed = self._run("list", "--json")

        self.assertEqual(listed.returncode, 0, listed.stderr)
        inventory = {item["identifier"]: item for item in json.loads(listed.stdout)}
        self.assertTrue(inventory["acme/workflow/feature"]["requested"])
        self.assertTrue(inventory["acme/workflow/feature"]["resolved"])
        self.assertTrue(inventory["acme/workflow/base"]["transitive"])
        self.assertTrue(inventory["acme/workflow/base"]["resolved"])
        self.assertTrue(inventory["acme/workflow/other"]["recommended"])
        self.assertFalse(inventory["acme/workflow/other"]["resolved"])

        selected = self._run("recommend", "acme/workflow/other")

        self.assertEqual(selected.returncode, 0, selected.stderr)
        manifest = json.loads((self.project / "capabilities.json").read_text())
        self.assertEqual(
            manifest["roots"],
            ["acme/workflow/feature", "acme/workflow/other"],
        )

    def test_diff_reports_drift_until_sync_restores_the_lock(self) -> None:
        self._run("add", "--catalog", str(self.catalog), "acme/workflow/feature")
        materialized = self.project / ".agents/skills/feature/SKILL.md"
        materialized.write_text("experiment\n", encoding="utf-8")

        drift = self._run("diff")

        self.assertEqual(drift.returncode, 1)
        self.assertIn(".agents/skills/feature", drift.stdout)
        self.assertEqual(self._run("sync").returncode, 0)
        clean = self._run("diff")
        self.assertEqual(clean.returncode, 0, clean.stdout + clean.stderr)
        self.assertIn("no materialized drift", clean.stdout.lower())

    def test_skill_and_capability_snapshots_store_expanded_names(self) -> None:
        self._run("add", "--catalog", str(self.catalog), "acme/workflow/feature")
        self._run("remove", "acme/workflow/feature")

        snapshotted = self._run("skills", "snapshot")

        self.assertEqual(snapshotted.returncode, 0, snapshotted.stderr)
        manifest_path = self.project / "capabilities.json"
        roots = json.loads(manifest_path.read_text())["roots"]
        self.assertEqual(
            roots,
            [
                "acme/workflow/base",
                "acme/workflow/feature",
                "acme/workflow/other",
            ],
        )
        self.assertNotIn("*", roots)
        listed = self._run("skills", "list", "--json")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertTrue(all(item["kind"] == "skill" for item in json.loads(listed.stdout)))

        capability_snapshot = self._run("snapshot")
        self.assertEqual(capability_snapshot.returncode, 0, capability_snapshot.stderr)


if __name__ == "__main__":
    unittest.main()
