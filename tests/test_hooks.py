import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from configure_claude import merge
from firewall_hook import evaluate, verdict
from bundle_common import sha256
from verify_kit import verify
from pdn_scan import local_findings, scan, RULES


class HookTests(unittest.TestCase):
    def test_pdn_labeled_fixtures_and_non_pii(self):
        samples = {"ru_passport_labeled": "Паспорт: 00 00 000000", "ru_snils_labeled": "СНИЛС: 000-000-000 00",
                   "ru_inn_labeled": "ИНН: 000000000000", "ru_phone": "+7 (000) 000-00-00",
                   "private_key": "-----BEGIN PRIVATE KEY-----"}
        for rule, text in samples.items():
            with self.subTest(rule=rule):
                self.assertIn(rule, local_findings(text, list(RULES)))
        for text in ("Explain a Python loop", "build 123456789012", "ИНН: 123", "IPv4 192.168.1.1"):
            self.assertEqual(local_findings(text, list(RULES)), [])
        self.assertIn("ru_inn_labeled", local_findings("ИНН: ００００００００００００", list(RULES)))
        with self.assertRaises(ValueError):
            local_findings("safe", ["unknown"])

    def test_pdn_scanner_chain_and_error_propagation(self):
        policy = {"version": 1, "enabled_rules": list(RULES)}
        with patch("pdn_scan.subprocess.run") as process:
            result = scan("ИНН: 000000000000", policy, "scanner")
            self.assertEqual(result["decision"], "block")
            process.assert_not_called()
        with patch("pdn_scan.subprocess.run", return_value=subprocess.CompletedProcess([], 0,
                   '{"status":"success","decision":"allow","reason":"must not be exported"}', "")):
            result = scan("safe fixture", policy, "scanner")
            self.assertEqual(result["decision"], "allow")
            self.assertNotIn("reason", result)
        for output in ('invalid', '{"status":"error","decision":"allow"}', '{"status":"success","decision":"unknown"}'):
            with patch("pdn_scan.subprocess.run", return_value=subprocess.CompletedProcess([], 0, output, "")):
                with self.assertRaises(ValueError):
                    scan("safe fixture", policy, "scanner")
        with patch("pdn_scan.subprocess.run", side_effect=subprocess.TimeoutExpired("scanner", 20)):
            with self.assertRaises(subprocess.TimeoutExpired):
                scan("safe fixture", policy, "scanner")

    def test_prompt_hook_protocol_and_preserving_merge(self):
        settings = {"env": {"EXISTING": "keep"}, "hooks": {"UserPromptSubmit": [{"hooks": [{"command": "numbat"}]}]}}
        for _ in range(2):
            settings = merge(settings, "/our/hook --event UserPromptSubmit", "enforce", "UserPromptSubmit")
        self.assertEqual(len(settings["hooks"]["UserPromptSubmit"]), 2)
        self.assertEqual(settings["env"], {"EXISTING": "keep"})
        self.assertEqual(verdict("block", "enforce", "UserPromptSubmit")["decision"], "block")
        self.assertEqual(verdict("block", "monitor", "UserPromptSubmit"), {})
        with patch("firewall_hook.subprocess.run", return_value=subprocess.CompletedProcess([], 0, '{"status":"success","decision":"block"}', "")) as process:
            self.assertEqual(evaluate({"hook_event_name": "UserPromptSubmit", "prompt": "ИНН: 000000000000"}, "scanner"), "block")
            self.assertEqual(json.loads(process.call_args.kwargs["input"])["text"], "ИНН: 000000000000")
            evaluate({"hook_event_name": "PreToolUse", "tool_input": {"nested": ["ИНН:\n000000000000"]}}, "scanner")
            self.assertIn("ИНН:\n000000000000", json.loads(process.call_args.kwargs["input"])["text"])

    def test_complete_kit_inventory_and_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "claude-linux-x64").mkdir()
            (root / "claude-linux-x64/claude").write_bytes(b"fixture native")
            (root / "controls.bin").write_bytes(b"fixture controls")
            (root / "versions.lock.json").write_text(json.dumps({
                "controls_archive": "controls.bin", "controls_sha256": sha256(root / "controls.bin"),
                "claude_linux_x64_sha256": sha256(root / "claude-linux-x64/claude")}))
            manifest = {"kind": "claude-ollama-complete-offline", "files": {
                p.relative_to(root).as_posix(): sha256(p) for p in root.rglob("*") if p.is_file()}}
            (root / "KIT-MANIFEST.json").write_text(json.dumps(manifest))
            verify(root)
            (root / "controls.bin").write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                verify(root)

    def test_preserving_idempotent_merge(self):
        original = {"env": {"EXISTING": "keep"}, "permissions": {"ask": ["Bash"]},
                    "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "numbat"}]}],
                              "PostToolUse": [{"hooks": [{"command": "existing"}]}]}}
        updated = merge(copy.deepcopy(original), "/our/hook", "monitor")
        updated = merge(updated, "/our/hook", "enforce")
        self.assertEqual(updated["env"], original["env"])
        self.assertEqual(updated["permissions"], original["permissions"])
        self.assertEqual(updated["hooks"]["PostToolUse"], original["hooks"]["PostToolUse"])
        self.assertEqual(len(updated["hooks"]["PreToolUse"]), 2)
        self.assertEqual(updated["hooks"]["PreToolUse"][-1]["hooks"][0]["onFailure"], "block")

    def test_verdict_never_autoapproves(self):
        for mode in ("monitor", "enforce"):
            self.assertEqual(verdict("allow", mode), {})
        self.assertEqual(verdict("block", "monitor"), {})
        for decision in ("error", "block", "human_in_the_loop_required"):
            self.assertEqual(verdict(decision, "enforce")["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_protocol_errors(self):
        event = {"hook_event_name": "PreToolUse", "tool_input": {"command": "printf fixture"}}
        with patch("firewall_hook.subprocess.run", return_value=subprocess.CompletedProcess([], 0, '{"status":"success","decision":"allow"}', "")):
            self.assertEqual(evaluate(event, "scanner"), "allow")
        with patch("firewall_hook.subprocess.run", return_value=subprocess.CompletedProcess([], 0, 'invalid', "")):
            with self.assertRaises(ValueError):
                evaluate(event, "scanner")
        with patch("firewall_hook.subprocess.run", side_effect=subprocess.TimeoutExpired("scanner", 30)):
            with self.assertRaises(subprocess.TimeoutExpired):
                evaluate(event, "scanner")
        with self.assertRaises(ValueError):
            evaluate({"hook_event_name": "PostToolUse"}, "scanner")

    def test_adapter_missing_config_denies(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            hook = Path(tmp) / "firewall_hook.py"
            shutil.copy2(ROOT / "firewall_hook.py", hook)
            response = subprocess.run([sys.executable, str(hook)], input="{}", text=True, capture_output=True, check=True)
            self.assertEqual(json.loads(response.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")
            (Path(tmp) / "firewall.json").write_text('{"mode":"invalid","scanner":"unused"}')
            response = subprocess.run([sys.executable, str(hook)], input="{}", text=True, capture_output=True, check=True)
            self.assertEqual(json.loads(response.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")


if __name__ == "__main__":
    unittest.main()
