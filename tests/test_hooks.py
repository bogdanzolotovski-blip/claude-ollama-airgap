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


class HookTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
