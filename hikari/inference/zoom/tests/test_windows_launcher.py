"""Check Windows-to-WSL argument and credential boundaries without starting WSL."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ZOOM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ZOOM))
spec = importlib.util.spec_from_file_location("windows_launcher", ZOOM / "windows_launcher.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class WindowsLauncherTests(unittest.TestCase):
    @mock.patch.object(launcher, "linux_path", return_value="/mnt/e/Hikari/local_runtime.sh")
    def test_invite_is_one_literal_argument(self, _):
        invite = "https://example.zoom.us/j/12345678901?pwd=a%26b&extra=$(ignored)"
        command = launcher.build_command("join", invite)
        self.assertEqual(command[-2:], ["join", invite])
        self.assertIn("--exec", command)
        self.assertNotIn("-c", command)

    def test_invalid_url_or_missing_session_never_launches(self):
        for action, value in [("join", "https://example.org"), ("leave", ""), ("join", None)]:
            with self.subTest(action=action, value=value), self.assertRaises(ValueError):
                launcher.build_command(action, value)

    def test_key_is_forwarded_only_through_environment(self):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test-only-key", "WSLENV": "EXISTING/p:OPENAI_API_KEY/p"}, clear=True):
            env = launcher.child_environment()
            self.assertEqual(env["WSLENV"], "EXISTING/p:OPENAI_API_KEY/u")
            self.assertEqual(env["OPENAI_API_KEY"], "test-only-key")
            self.assertEqual(os.environ["WSLENV"], "EXISTING/p:OPENAI_API_KEY/p")

    def test_session_is_read_from_result_without_claiming_admission(self):
        self.assertEqual(launcher.returned_session('Version\n{"session":{"id":"zoom-123","active":true}}'), "zoom-123")
        self.assertIsNone(launcher.returned_session('{"found":false}'))
        self.assertEqual(launcher.result_objects('log\n{\n "events":[\n {"sessionId":"event-not-session"}\n ]\n}\n{"next":true}'),
                         [{"events":[{"sessionId":"event-not-session"}]}, {"next": True}])

    def test_allocated_session_is_not_reported_as_in_call(self):
        text = '{"session":{"id":"zoom-123","active":true,"chrome":{"health":{"inCall":false}}}}'
        self.assertNotIn("Hikari is in the meeting", launcher.readable_result("join", 0, text))
        admitted = text.replace('"inCall":false', '"inCall":true')
        self.assertIn("Hikari is in the meeting", launcher.readable_result("status", 0, admitted))

    def test_admission_without_voice_bridge_is_clearly_blocked(self):
        result = {"session":{"id":"zoom-123", "state":"active", "chrome":{"health":{
            "inCall":True, "speechReady":False,
            "speechBlockedReason":"audio-bridge-unavailable"}}}}
        message = launcher.readable_result("status", 0, json.dumps(result))
        self.assertIn("voice is not ready", message)
        self.assertIn("Connect voice", message)
        result["session"]["chrome"]["health"]["speechReady"] = True
        self.assertNotIn("voice connection is ready", launcher.readable_result("status", 0, json.dumps(result)))
        result["session"]["chrome"]["audioBridge"] = {"type":"command-pair"}
        self.assertIn("voice connection is ready", launcher.readable_result("status", 0, json.dumps(result)))

    @mock.patch.object(launcher, "linux_path", return_value="/mnt/e/Hikari/local_runtime.sh")
    def test_voice_connection_is_an_explicit_speech_request(self, _):
        command = launcher.build_command("voice", "zoom-123")
        self.assertEqual(command[-3:-1], ["speak", "zoom-123"])
        with self.assertRaises(ValueError):
            launcher.build_command("voice", None)

    def test_status_rediscovers_only_an_unambiguous_active_session(self):
        sessions = [{"id":"old", "state":"ended"}, {"id":"new", "state":"active"}]
        self.assertEqual(launcher.returned_session(json.dumps({"sessions":sessions})), "new")
        sessions.append({"id":"another", "state":"active"})
        self.assertIsNone(launcher.returned_session(json.dumps({"sessions":sessions})))

    def test_project_arguments_are_literal_and_switch_requires_project(self):
        with tempfile.TemporaryDirectory(prefix="hikari project ") as folder:
            with mock.patch.object(launcher, "linux_path", side_effect=lambda path: "/mnt/e/" + path.name):
                command = launcher.build_command("join", "https://zoom.us/j/12345678901",
                                                 project=folder, switch_project=True)
                self.assertEqual(command[-4:], ["join-project", "/mnt/e/" + Path(folder).name,
                                               "https://zoom.us/j/12345678901", "--switch"])
        with self.assertRaises(ValueError):
            launcher.build_command("join", "https://zoom.us/j/12345678901", switch_project=True)
        with self.assertRaises(ValueError):
            launcher.build_command("prepare")


if __name__ == "__main__":
    unittest.main()
