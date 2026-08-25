from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


RUNTIME = Path(__file__).parents[1] / "dot_local/share/dotfiles/capabilities/src"


class CapabilityHookTests(unittest.TestCase):
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
        self._git(self.project, "config", "user.name", "Capability Test")
        self._git(self.project, "config", "user.email", "capability@example.invalid")
        (self.project / ".claude").mkdir()
        (self.project / ".codex").mkdir()
        self.claude_unrelated = {
            "matcher": "Write",
            "hooks": [{"type": "command", "command": "echo unrelated-claude"}],
        }
        self.codex_unrelated = {
            "hooks": [{"type": "command", "command": "echo unrelated-codex"}]
        }
        (self.project / ".claude/settings.json").write_text(
            json.dumps({"permissions": {"allow": ["Read"]}, "hooks": {"PostToolUse": [self.claude_unrelated]}}),
            encoding="utf-8",
        )
        (self.project / ".codex/hooks.json").write_text(
            json.dumps({"description": "tracked", "hooks": {"Stop": [self.codex_unrelated]}}),
            encoding="utf-8",
        )
        self._git(self.project, "add", ".codex/hooks.json")
        self._git(self.project, "commit", "-qm", "track Codex hooks")
        self._create_hook_capability()
        self._create_companion_capabilities()
        validated = self._run("validate", str(self.catalog), project=self.catalog)
        self.assertEqual(validated.returncode, 0, validated.stderr)
        self._git(self.catalog, "add", ".")
        self._git(self.catalog, "commit", "-qm", "hook capability")
        self.assertEqual(self._run("init").returncode, 0)

    @staticmethod
    def _git(repository: Path, *arguments: str) -> str:
        return subprocess.run(
            ["git", "-C", str(repository), *arguments],
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        ).stdout.strip()

    def _create_hook_capability(self) -> None:
        payload = self.catalog / "guard"
        payload.mkdir()
        (payload / "guard.sh").write_text(
            "#!/bin/sh\nset -eu\nprintf '%s\\n' guarded\n", encoding="utf-8"
        )
        (payload / "guard.sh").chmod(0o755)
        (payload / "agent.md").write_text("Guard agent\n", encoding="utf-8")
        (payload / "helper.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        (payload / "helper.sh").chmod(0o755)
        (payload / "reference.md").write_text("Guard reference\n", encoding="utf-8")
        (payload / "asset.txt").write_text("guard asset\n", encoding="utf-8")

        def targets(tool: str) -> list[dict[str, object]]:
            base = ".claude" if tool == "claude" else ".codex"
            return [
                {
                    "kind": "hook",
                    "source": "guard.sh",
                    "destination": f"{base}/hooks/guard.sh",
                    "executable": True,
                    "event": "PreToolUse",
                    "matcher": "Bash",
                },
                {
                    "kind": "agent",
                    "source": "agent.md",
                    "destination": f"{base}/agents/guard.md",
                },
                {
                    "kind": "script",
                    "source": "helper.sh",
                    "destination": f"{base}/scripts/helper.sh",
                    "executable": True,
                },
                {
                    "kind": "reference",
                    "source": "reference.md",
                    "destination": f"{base}/references/guard.md",
                },
                {
                    "kind": "asset",
                    "source": "asset.txt",
                    "destination": f"{base}/assets/guard.txt",
                },
            ]

        (payload / "capability.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "identifier": "acme/hooks/guard",
                    "description": "Guard shell use",
                    "dependencies": {
                        "required": [],
                        "recommended": [],
                        "companions": {"claude": [], "codex": []},
                    },
                    "targets": {"claude": targets("claude"), "codex": targets("codex")},
                }
            ),
            encoding="utf-8",
        )

    def _create_companion_capabilities(self) -> None:
        agent = self.catalog / "companion-agent"
        agent.mkdir()
        (agent / "agent.md").write_text("Companion agent\n", encoding="utf-8")
        (agent / "capability.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "identifier": "acme/hooks/companion-agent",
                    "description": "Tool-specific companion agent",
                    "dependencies": {
                        "required": [],
                        "recommended": [],
                        "companions": {"claude": [], "codex": []},
                    },
                    "targets": {
                        "claude": [
                            {
                                "kind": "agent",
                                "source": "agent.md",
                                "destination": ".claude/agents/companion.md",
                            }
                        ],
                        "codex": [
                            {
                                "kind": "agent",
                                "source": "agent.md",
                                "destination": ".codex/agents/companion.md",
                            }
                        ],
                    },
                }
            ),
            encoding="utf-8",
        )
        root = self.catalog / "companion-root"
        (root / "skill").mkdir(parents=True)
        (root / "skill/SKILL.md").write_text("Companion root\n", encoding="utf-8")
        (root / "capability.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "identifier": "acme/hooks/companion-root",
                    "description": "Root with target companions",
                    "dependencies": {
                        "required": [],
                        "recommended": [],
                        "companions": {
                            "claude": ["companion-agent"],
                            "codex": ["companion-agent"],
                        },
                    },
                    "targets": {
                        "claude": [
                            {
                                "kind": "skill",
                                "source": "skill",
                                "destination": ".claude/skills/companion-root",
                            }
                        ],
                        "codex": [
                            {
                                "kind": "skill",
                                "source": "skill",
                                "destination": ".agents/skills/companion-root",
                            }
                        ],
                    },
                }
            ),
            encoding="utf-8",
        )

    def _run(
        self,
        *arguments: str,
        project: Path | None = None,
        input_text: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(RUNTIME)
        return subprocess.run(
            [sys.executable, "-m", "dotfiles_capabilities", *arguments],
            cwd=project or self.project,
            env=environment,
            check=False,
            input=input_text,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def test_approved_hook_and_companion_payloads_merge_without_taking_settings(self) -> None:
        added = self._run(
            "add",
            "--catalog",
            str(self.catalog),
            "acme/hooks/guard",
            input_text="y\n",
        )

        self.assertEqual(added.returncode, 0, added.stderr)
        for relative in (
            ".claude/hooks/guard.sh",
            ".codex/hooks/guard.sh",
            ".claude/agents/guard.md",
            ".codex/agents/guard.md",
            ".claude/scripts/helper.sh",
            ".codex/scripts/helper.sh",
            ".claude/references/guard.md",
            ".codex/references/guard.md",
            ".claude/assets/guard.txt",
            ".codex/assets/guard.txt",
        ):
            self.assertTrue((self.project / relative).is_file(), relative)
        claude = json.loads((self.project / ".claude/settings.json").read_text())
        codex = json.loads((self.project / ".codex/hooks.json").read_text())
        self.assertEqual(claude["permissions"], {"allow": ["Read"]})
        self.assertIn(self.claude_unrelated, claude["hooks"]["PostToolUse"])
        self.assertIn(self.codex_unrelated, codex["hooks"]["Stop"])
        claude_command = claude["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        codex_command = codex["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        self.assertEqual(
            claude_command,
            '"$(git rev-parse --show-toplevel)/.claude/hooks/guard.sh"',
        )
        self.assertEqual(
            codex_command,
            '"$(git rev-parse --show-toplevel)/.codex/hooks/guard.sh"',
        )
        approvals = json.loads(
            (self.project / ".git/dotfiles-capabilities-approvals.json").read_text()
        )
        self.assertEqual(approvals["schema_version"], 1)
        self.assertEqual(len(approvals["hook_hashes"]), 1)
        self.assertEqual(
            self._git(self.project, "ls-files", ".codex/hooks.json"),
            ".codex/hooks.json",
        )

        claude["hooks"]["PreToolUse"] = [
            {
                "matcher": "Bash",
                "hooks": [{"type": "command", "command": "echo local-extra"}],
            }
        ]
        (self.project / ".claude/settings.json").write_text(
            json.dumps(claude), encoding="utf-8"
        )

        synchronized = self._run("sync")

        self.assertEqual(synchronized.returncode, 0, synchronized.stderr)
        synchronized_claude = json.loads(
            (self.project / ".claude/settings.json").read_text()
        )
        pre_tool_commands = [
            entry["hooks"][0]["command"]
            for entry in synchronized_claude["hooks"]["PreToolUse"]
        ]
        self.assertIn("echo local-extra", pre_tool_commands)
        self.assertIn(
            '"$(git rev-parse --show-toplevel)/.claude/hooks/guard.sh"',
            pre_tool_commands,
        )

        lock_path = self.project / "capabilities.lock.json"
        lock_before = lock_path.read_text(encoding="utf-8")
        changed_hook = self.catalog / "guard/guard.sh"
        changed_hook.write_text(
            "#!/bin/sh\nset -eu\nprintf '%s\\n' guarded-v2\n", encoding="utf-8"
        )
        changed_hook.chmod(0o755)
        validated = self._run("validate", str(self.catalog), project=self.catalog)
        self.assertEqual(validated.returncode, 0, validated.stderr)
        self._git(self.catalog, "add", ".")
        self._git(self.catalog, "commit", "-qm", "change approved hook")

        denied = self._run("update", "acme/hooks/guard", input_text="n\n")

        self.assertEqual(denied.returncode, 1)
        self.assertIn("was not approved", denied.stderr)
        self.assertEqual(lock_path.read_text(encoding="utf-8"), lock_before)
        self.assertNotIn(
            "guarded-v2",
            (self.project / ".codex/hooks/guard.sh").read_text(),
        )

        approved = self._run("update", "acme/hooks/guard", input_text="y\n")

        self.assertEqual(approved.returncode, 0, approved.stderr)
        self.assertIn(
            "guarded-v2",
            (self.project / ".codex/hooks/guard.sh").read_text(),
        )
        approvals = json.loads(
            (self.project / ".git/dotfiles-capabilities-approvals.json").read_text()
        )
        self.assertEqual(len(approvals["hook_hashes"]), 2)

        removed = self._run("remove", "acme/hooks/guard")

        self.assertEqual(removed.returncode, 0, removed.stderr)
        self.assertFalse((self.project / ".claude/hooks/guard.sh").exists())
        self.assertFalse((self.project / ".codex/hooks/guard.sh").exists())
        claude_after = json.loads((self.project / ".claude/settings.json").read_text())
        codex_after = json.loads((self.project / ".codex/hooks.json").read_text())
        self.assertEqual(
            claude_after["hooks"],
            {
                "PostToolUse": [self.claude_unrelated],
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {"type": "command", "command": "echo local-extra"}
                        ],
                    }
                ],
            },
        )
        self.assertEqual(codex_after["hooks"], {"Stop": [self.codex_unrelated]})

    def test_target_specific_companions_are_resolved_and_materialized(self) -> None:
        added = self._run(
            "add",
            "--catalog",
            str(self.catalog),
            "acme/hooks/companion-root",
        )

        self.assertEqual(added.returncode, 0, added.stderr)
        self.assertTrue((self.project / ".claude/agents/companion.md").is_file())
        self.assertTrue((self.project / ".codex/agents/companion.md").is_file())
        lock = json.loads((self.project / "capabilities.lock.json").read_text())
        companion = next(
            item
            for item in lock["capabilities"]
            if item["identifier"] == "acme/hooks/companion-agent"
        )
        self.assertEqual(
            companion["reason"],
            {
                "kind": "companion",
                "by": {
                    "claude": ["acme/hooks/companion-root"],
                    "codex": ["acme/hooks/companion-root"],
                },
            },
        )

    def test_catalog_rejects_a_missing_required_tool_implementation(self) -> None:
        metadata_path = self.catalog / "guard/capability.json"
        metadata = json.loads(metadata_path.read_text())
        metadata["targets"]["codex"] = []
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        validated = self._run("validate", str(self.catalog), project=self.catalog)

        self.assertEqual(validated.returncode, 1)
        self.assertIn("targets.codex must be a non-empty list", validated.stdout)


class CatalogHookPayloadTests(unittest.TestCase):
    def test_rtk_guardrail_forwards_claude_and_codex_events(self) -> None:
        hook = Path(__file__).parents[1] / "capability-catalog/rtk-guardrail/hook.sh"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            binary = root / "bin"
            binary.mkdir()
            log = root / "rtk.log"
            fake = binary / "rtk"
            fake.write_text(
                "#!/bin/sh\nprintf '%s\\n' \"$*\" >>\"$RTK_TEST_LOG\"\ncat >/dev/null\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            environment = os.environ.copy()
            environment["PATH"] = f"{binary}:{environment['PATH']}"
            environment["RTK_TEST_LOG"] = str(log)
            for event in (
                {"hook_event_name": "PreToolUse", "tool_name": "Bash"},
                {"hook_event_name": "PreToolUse", "tool_name": "Bash", "turn_id": "codex"},
            ):
                result = subprocess.run(
                    [str(hook)],
                    input=json.dumps(event),
                    env=environment,
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(log.read_text().splitlines(), ["hook claude", "hook claude"])

    def test_python_formatter_accepts_claude_paths_and_codex_patch_input(self) -> None:
        hook = Path(__file__).parents[1] / "capability-catalog/python-format/hook.sh"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sample.py"
            events = (
                {"tool_input": {"file_path": "sample.py"}},
                {
                    "tool_input": {
                        "command": "*** Begin Patch\n*** Update File: sample.py\n*** End Patch"
                    }
                },
            )
            for event in events:
                source.write_text("value=  1\n", encoding="utf-8")
                result = subprocess.run(
                    [str(hook)],
                    input=json.dumps(event),
                    cwd=root,
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(source.read_text(), "value = 1\n")


if __name__ == "__main__":
    unittest.main()
