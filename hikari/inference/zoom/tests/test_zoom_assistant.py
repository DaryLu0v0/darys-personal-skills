"""Offline boundary tests for the Zoom starter; no OpenClaw process is run.

Run from inference/zoom with:
    python3 -B -m unittest discover -s tests -v
"""
from __future__ import annotations

import copy
import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock


STARTER_PATH = Path(__file__).resolve().parents[1] / "zoom_assistant.py"
SPEC = importlib.util.spec_from_file_location("zoom_assistant_under_test", STARTER_PATH)
assert SPEC is not None and SPEC.loader is not None
starter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(starter)


class ZoomAssistantTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory(prefix="zoom-starter-test-")
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.brief = self.directory / "brief.txt"
        self.brief.write_text("Project Δ: measured result remains unverified.", encoding="utf-8")

    def patch(self, **kwargs):
        return starter.make_patch(self.brief.read_text(encoding="utf-8"), "existing-project", **kwargs)

    @staticmethod
    def config(patch):
        return patch["plugins"]["entries"]["zoom-meetings"]["config"]

    def patch_file(self):
        path = self.directory / "zoom.patch.json"
        patch = self.patch()
        path.write_text(json.dumps(patch, ensure_ascii=False), encoding="utf-8")
        return path, patch

    @staticmethod
    def run_main(arguments):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = starter.main(arguments)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_prepared_patch_is_confined_to_zoom_and_reuses_existing_agent(self):
        patch = self.patch()
        self.assertEqual(set(patch), {"plugins"})
        self.assertEqual(set(patch["plugins"]), {"entries"})
        self.assertEqual(set(patch["plugins"]["entries"]), {"zoom-meetings"})
        entry = patch["plugins"]["entries"]["zoom-meetings"]
        self.assertIs(entry["enabled"], True)
        config = self.config(patch)
        self.assertIs(config["enabled"], True)
        self.assertEqual(config["realtime"]["agentId"], "existing-project")
        self.assertEqual(config["defaultMode"], "bidi")
        self.assertTrue(config["chrome"]["guestName"].startswith("Digital Student"))
        self.assertEqual(config["chrome"]["audioFormat"], "pcm16-24khz")
        self.assertIn("audioInputCommand", config["chrome"])
        self.assertIsNone(config["chrome"]["audioInputCommand"])
        self.assertEqual(config["realtime"]["toolPolicy"], "safe-read-only")
        starter.validate_patch(patch)

    def test_routes_preserve_project_context_and_use_native_delegation_wording(self):
        for route, model, voice in (
            ("api", "gpt-live-1", "marin"),
            ("codex", "gpt-live-1-codex", "cove"),
        ):
            with self.subTest(route=route):
                realtime = self.config(self.patch(route=route))["realtime"]
                self.assertEqual(realtime["model"], model)
                self.assertEqual(realtime["providers"]["openai"]["model"], model)
                self.assertEqual(realtime["providers"]["openai"]["voice"], voice)
                self.assertEqual(realtime["introMessage"], "")
                self.assertTrue(realtime["instructions"].endswith(self.brief.read_text(encoding="utf-8")))
                if route == "api":
                    self.assertIn("<|SpawnThinking|>", realtime["instructions"])
                else:
                    self.assertNotIn("<|SpawnThinking|>", realtime["instructions"])
                    self.assertIn("native backend delegation", realtime["instructions"])

    def test_exact_brief_character_limit_preserves_unicode_and_final_marker(self):
        brief = "🧪" * (starter.MAX_BRIEF_CHARS - 1) + "🔚"
        self.brief.write_text("\ufeff" + brief, encoding="utf-8")
        self.assertEqual(starter.read_brief(self.brief), brief)
        patch = starter.make_patch(starter.read_brief(self.brief), "existing-project")
        self.assertTrue(self.config(patch)["realtime"]["instructions"].endswith(brief))

    def test_oversized_empty_and_nul_briefs_fail_without_truncation(self):
        cases = (
            "x" * (starter.MAX_BRIEF_CHARS + 1),
            "x" * (starter.MAX_BRIEF_CHARS * 4 + 1),
            " \n\t ",
            "project\x00context",
        )
        for text in cases:
            with self.subTest(length=len(text), nul="\x00" in text):
                self.brief.write_text(text, encoding="utf-8")
                before = self.brief.read_bytes()
                with self.assertRaises(starter.StarterError):
                    starter.read_brief(self.brief)
                self.assertEqual(self.brief.read_bytes(), before)

    def test_supported_zoom_links_preserve_invitation_credentials(self):
        links = (
            "https://zoom.us/j/12345678901",
            "https://example.zoom.us/j/12345678901?pwd=Secret%2BPass%3D&omn=42",
            "https://us02web.zoom.us:443/j/12345678901/",
        )
        for link in links:
            with self.subTest(link=link):
                self.assertEqual(starter.checked_zoom_url(link), link)

    def test_untrusted_or_malformed_zoom_destinations_are_rejected(self):
        links = (
            "http://zoom.us/j/123",
            "https://zoom.us.evil.example/j/123",
            "https://evilzoom.us/j/123",
            "https://user:password@zoom.us/j/123",
            "https://zoom.us:444/j/123",
            "https://zoom.us:notaport/j/123",
            "https://zoom.us/j/123#fragment",
            "https://zoom.us/wc/123/join",
            "https://zoom.us/j/not-a-number",
            "https://zoom.us/j/123?pwd=line\nbreak",
            "https://[broken/j/123",
            "//zoom.us/j/123",
        )
        for link in links:
            with self.subTest(link=link):
                with self.assertRaises(starter.StarterError):
                    starter.checked_zoom_url(link)

    def test_invalid_identifiers_fail_with_actionable_errors(self):
        for value in (None, False, 7, [], {}, "", "--option", "../agent", "has spaces", "x" * 129):
            with self.subTest(value=value):
                with self.assertRaises(starter.StarterError):
                    starter.checked_id(value)
        self.assertEqual(starter.checked_id("project-1.node:main"), "project-1.node:main")

    def test_patch_scope_rejects_changes_to_other_configuration(self):
        base = self.patch()
        cases = []
        patch = copy.deepcopy(base)
        patch["agents"] = {"list": []}
        cases.append(patch)
        patch = copy.deepcopy(base)
        patch["plugins"]["allow"] = ["zoom-meetings"]
        cases.append(patch)
        patch = copy.deepcopy(base)
        patch["plugins"]["entries"]["other-plugin"] = {"enabled": False}
        cases.append(patch)
        patch = copy.deepcopy(base)
        patch["plugins"]["entries"]["zoom-meetings"]["enabled"] = False
        cases.append(patch)
        cases.extend((None, [], {"plugins": {"entries": None}}))
        for index, patch in enumerate(cases):
            with self.subTest(case=index):
                with self.assertRaises(starter.StarterError):
                    starter.validate_patch(patch)

    def test_pinned_schema_rejects_unknown_fields_and_wrong_types(self):
        cases = (
            (("unknownSetting",), True),
            (("realtime", "unknownSetting"), "x"),
            (("chrome", "launch"), "true"),
            (("chrome", "waitForInCallMs"), True),
            (("chrome", "waitForInCallMs"), 0),
            (("chrome", "waitForInCallMs"), float("nan")),
            (("chrome", "waitForInCallMs"), float("inf")),
            (("chrome", "audioBackend"), "unsupported"),
            (("chrome", "audioInputCommand"), [7]),
            (("chrome", "audioInputCommand"), [None]),
            (("realtime", "voiceProvider"), []),
            (("realtime", "providers", "openai"), []),
        )
        for path, value in cases:
            with self.subTest(path=path, value=value):
                patch = self.patch()
                target = self.config(patch)
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                with self.assertRaises(starter.StarterError):
                    starter.validate_patch(patch)

    def test_null_required_containers_are_rejected_instead_of_crashing(self):
        for path in (
            ("chrome",),
            ("realtime",),
            ("realtime", "providers"),
            ("realtime", "providers", "openai"),
        ):
            with self.subTest(path=path):
                patch = self.patch()
                target = self.config(patch)
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = None
                with self.assertRaises(starter.StarterError):
                    starter.validate_patch(patch)

    def test_voice_audio_and_delegation_contracts_are_enforced(self):
        cases = (
            ("api", ("realtime", "providers", "openai", "voice"), "cove"),
            ("codex", ("realtime", "providers", "openai", "voice"), "marin"),
            ("api", ("realtime", "providers", "openai", "voice"), "unknown-voice"),
            ("api", ("chrome", "audioFormat"), "g711-ulaw-8khz"),
            ("api", ("chrome", "audioFormat"), None),
            ("api", ("chrome", "audioInputCommand"), ["capture-custom-audio"]),
            ("api", ("realtime", "toolPolicy"), "owner"),
            ("api", ("enabled",), False),
            ("api", ("defaultMode",), "agent"),
            ("api", ("realtime", "instructions"), "  "),
        )
        for route, path, value in cases:
            with self.subTest(route=route, path=path, value=value):
                patch = self.patch(route=route)
                target = self.config(patch)
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                with self.assertRaises(starter.StarterError):
                    starter.validate_patch(patch)

    def test_provider_model_cannot_override_the_selected_route_after_merge(self):
        for route, wrong_model in (("api", "gpt-live-1-codex"), ("codex", "gpt-live-1")):
            for supplied_model in (wrong_model, None, "missing"):
                with self.subTest(route=route, provider_model=supplied_model):
                    patch = self.patch(route=route)
                    provider = self.config(patch)["realtime"]["providers"]["openai"]
                    if supplied_model == "missing":
                        del provider["model"]
                    else:
                        provider["model"] = supplied_model
                    with self.assertRaises(starter.StarterError):
                        starter.validate_patch(patch)

    def test_prepare_refuses_overwrite_until_force_is_explicit(self):
        output = self.directory / "already-exists.json"
        output.write_text("keep this existing file\n", encoding="utf-8")
        args = ["prepare", "--brief", str(self.brief), "--agent", "existing-project", "--output", str(output)]
        with mock.patch.object(starter, "invoke") as invoke:
            code, _, _ = self.run_main(args)
            self.assertEqual(code, 1)
            self.assertEqual(output.read_text(encoding="utf-8"), "keep this existing file\n")
            code, _, _ = self.run_main([*args, "--force"])
            self.assertEqual(code, 0)
            starter.load_patch(output)
            invoke.assert_not_called()

    def test_prepare_and_validate_roundtrip_is_entirely_offline(self):
        output = self.directory / "nested" / "zoom.patch.json"
        with mock.patch.object(starter, "invoke") as invoke, mock.patch.object(starter.subprocess, "run") as run:
            code, _, _ = self.run_main([
                "prepare", "--brief", str(self.brief), "--agent", "existing-project",
                "--chrome-node", "desktop-node", "--output", str(output),
            ])
            self.assertEqual(code, 0)
            self.assertEqual(self.config(starter.load_patch(output))["chromeNode"]["node"], "desktop-node")
            code, _, _ = self.run_main(["validate", "--patch", str(output)])
            self.assertEqual(code, 0)
            invoke.assert_not_called()
            run.assert_not_called()

    def test_apply_dry_run_never_sends_a_write(self):
        path, patch = self.patch_file()
        original = path.read_bytes()
        with mock.patch.object(starter, "invoke", return_value={"ok": True}) as invoke:
            code, _, _ = self.run_main(["apply", "--patch", str(path), "--dry-run"])
        self.assertEqual(code, 0)
        invoke.assert_called_once_with("openclaw", ["config", "patch", "--stdin", "--dry-run", "--json"], 120.0, payload=patch)
        self.assertEqual(path.read_bytes(), original)

    def test_failed_apply_preflight_stops_before_any_write(self):
        path, _ = self.patch_file()
        with mock.patch.object(starter, "invoke", side_effect=starter.StarterError("schema rejected")) as invoke:
            code, _, error = self.run_main(["apply", "--patch", str(path)])
        self.assertEqual(code, 1)
        self.assertIn("schema rejected", error)
        self.assertEqual(invoke.call_count, 1)
        self.assertIn("--dry-run", invoke.call_args.args[1])

    def test_apply_obeys_upstream_json_flag_and_stdin_contract(self):
        path, patch = self.patch_file()
        with mock.patch.object(starter, "invoke", side_effect=[{"ok": True}, "applied\n", {"valid": True}]) as invoke:
            code, _, _ = self.run_main(["apply", "--patch", str(path)])
        self.assertEqual(code, 0)
        calls = invoke.call_args_list
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0].args[1], ["config", "patch", "--stdin", "--dry-run", "--json"])
        self.assertEqual(calls[1].args[1], ["config", "patch", "--stdin"])
        self.assertEqual(calls[2].args[1], ["config", "validate", "--json"])
        self.assertEqual(calls[0].kwargs["payload"], patch)
        self.assertEqual(calls[1].kwargs["payload"], patch)
        self.assertIs(calls[1].kwargs["machine"], False)

    def test_invoke_keeps_argv_and_unicode_stdin_out_of_a_shell(self):
        executable = "/opt/with spaces/openclaw"
        argv = ["zoommeetings", "speak", "session-1", "--", "$(do-not-run) `do-not-run` ; $HOME ' quoted"]
        payload = {"instructions": "研究\nLiteral $(nothing) and `nothing` and a quote: \""}
        result = subprocess.CompletedProcess([], 0, '{"ok": true}', "")
        with mock.patch.object(starter, "executable_path", return_value=executable), mock.patch.object(starter.subprocess, "run", return_value=result) as run:
            self.assertEqual(starter.invoke("openclaw", argv, 13.5, payload=payload), {"ok": True})
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0], [executable, *argv])
        self.assertIs(run.call_args.kwargs["shell"], False)
        self.assertEqual(json.loads(run.call_args.kwargs["input"]), payload)
        self.assertIn("研究", run.call_args.kwargs["input"])
        self.assertEqual(run.call_args.kwargs["timeout"], 13.5)

    def test_unsuccessful_or_malformed_upstream_results_are_failures(self):
        cases = (
            (0, '{"ok": false}'),
            (0, '{"valid": false}'),
            (0, '{"found": false}'),
            (0, "not JSON"),
            (2, '{"ok": true}'),
        )
        for returncode, stdout in cases:
            with self.subTest(returncode=returncode, stdout=stdout):
                result = subprocess.CompletedProcess([], returncode, stdout, "")
                with mock.patch.object(starter, "executable_path", return_value="/bin/openclaw"), mock.patch.object(starter.subprocess, "run", return_value=result) as run, redirect_stderr(io.StringIO()):
                    with self.assertRaises(starter.StarterError):
                        starter.invoke("openclaw", ["zoommeetings", "status", "session-1"], 5)
                run.assert_called_once()

    def test_meeting_argv_matches_plugin_join_and_positional_speak_contract(self):
        parser = starter.build_parser()
        url = "https://example.zoom.us/j/12345678901?pwd=literal%2Bpass"
        join = parser.parse_args(["join", url, "--transport", "chrome-node"])
        self.assertEqual(starter.meeting_command("join", join), ["zoommeetings", "join", url, "--mode", "bidi", "--transport", "chrome-node"])
        speak = parser.parse_args(["speak", "session-1", "--", "--literal-message"])
        self.assertEqual(starter.meeting_command("speak", speak), ["zoommeetings", "speak", "session-1", "--", "--literal-message"])
        status = parser.parse_args(["status"])
        self.assertEqual(starter.meeting_command("status", status), ["zoommeetings", "status"])
        leave = parser.parse_args(["leave", "session-1"])
        self.assertEqual(starter.meeting_command("leave", leave), ["zoommeetings", "leave", "session-1"])

    def test_join_timeout_is_reported_without_retry_or_other_meeting_action(self):
        timeout = subprocess.TimeoutExpired(["openclaw", "zoommeetings", "join"], 1)
        with mock.patch.object(starter, "invoke", side_effect=timeout) as invoke:
            code, _, error = self.run_main(["--timeout", "1", "join", "https://zoom.us/j/12345678901"])
        self.assertEqual(code, 1)
        self.assertEqual(invoke.call_count, 1)
        self.assertEqual(invoke.call_args.args[1][:2], ["zoommeetings", "join"])
        self.assertIn("inspect status before retrying", error)


if __name__ == "__main__":
    unittest.main()
