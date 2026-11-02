"""Verify project identity, file preservation, and explicit meeting switching."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ZOOM = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("project_agent", ZOOM / "project_agent.py")
project_agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(project_agent)


class ProjectAgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "project with spaces"
        self.project.mkdir()
        self.state = self.root / "agent-state"
        self.state.mkdir()
        self.config = self.state / "openclaw.json"
        self.config.write_text(json.dumps({"agents": {"entries": {}}}))

    def test_same_canonical_folder_reuses_identity_and_distinct_folders_do_not(self):
        alternate = self.root / "another" / self.project.name
        alternate.mkdir(parents=True)
        first = project_agent.project_identity(self.project)
        self.assertEqual(first, project_agent.project_identity(self.project / ".." / self.project.name))
        self.assertNotEqual(first[1], project_agent.project_identity(alternate)[1])
        with self.assertRaises(ValueError):
            project_agent.project_identity(Path(self.root.anchor))

    def test_prepare_preserves_project_and_existing_managed_context(self):
        project_readme = self.project / "README.md"
        project_readme.write_text("User-owned project content")

        def apply(operations):
            cfg = json.loads(self.config.read_text())
            for operation in operations:
                if operation["path"] == "agents.defaults.skipBootstrap":
                    cfg["agents"].setdefault("defaults", {})["skipBootstrap"] = operation["value"]
                    continue
                agent_id = operation["path"].removeprefix("agents.entries.")
                cfg["agents"]["entries"][agent_id] = operation["value"]
            self.config.write_text(json.dumps(cfg))

        with mock.patch.object(project_agent, "STATE", self.state), mock.patch.object(project_agent, "apply_batch", side_effect=apply) as applied:
            first = project_agent.prepare(self.project)
            managed = Path(first["contextDir"])
            (managed / "AGENTS.md").write_text("User-customized agent context")
            second = project_agent.prepare(self.project)
            self.assertEqual(first, second)
            self.assertEqual(applied.call_count, 1)
            self.assertEqual((managed / "AGENTS.md").read_text(), "User-customized agent context")
            self.assertTrue((self.state / "skills/project-work/SKILL.md").is_file())
        self.assertEqual(list(self.project.iterdir()), [project_readme])
        self.assertEqual(project_readme.read_text(), "User-owned project content")
        config = json.loads(self.config.read_text())["agents"]["entries"][first["agentId"]]
        self.assertEqual(config["cwd"], str(self.project.resolve()))
        self.assertEqual(config["workspace"], str(self.project.resolve()))
        self.assertTrue(config["tools"]["fs"]["workspaceOnly"])
        self.assertEqual(config["tools"]["exec"]["mode"], "auto")
        self.assertFalse(config["tools"]["elevated"]["enabled"])

    def test_other_active_project_is_not_silently_replaced(self):
        status = json.dumps({"sessions": [{"id": "meeting-a", "state": "active", "agentId": "another-project"}]})
        with mock.patch.object(project_agent, "cli", return_value=status), mock.patch.object(project_agent, "prepare") as prepare:
            with self.assertRaisesRegex(ValueError, "Another project is active"):
                project_agent.select(self.project)
            prepare.assert_not_called()

    def test_project_switch_cannot_abandon_another_meeting(self):
        status = json.dumps({"sessions": [{"id": "meeting-a", "state": "active",
                                           "url": "https://zoom.us/j/11111111111", "agentId": "other"}]})
        with mock.patch.object(project_agent, "cli", return_value=status), mock.patch.object(project_agent, "prepare") as prepare:
            with self.assertRaisesRegex(ValueError, "another meeting"):
                project_agent.select(self.project, switch=True, meeting_url="https://example.zoom.us/j/22222222222")
            prepare.assert_not_called()


if __name__ == "__main__":
    unittest.main()
