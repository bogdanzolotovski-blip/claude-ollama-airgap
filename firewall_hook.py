#!/usr/bin/env python3
"""Claude PreToolUse adapter. Standard library only; never logs scanned content."""
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

LIMIT = 1024 * 1024


def evaluate(event, scanner, timeout=30):
    if event.get("hook_event_name") != "PreToolUse" or not isinstance(event.get("tool_input"), dict):
        raise ValueError("Expected Claude PreToolUse event with tool_input")
    text = json.dumps(event["tool_input"], ensure_ascii=False)
    if len(text.encode()) > LIMIT - 100:
        raise ValueError("Oversized tool input")
    process = subprocess.run([scanner], input=json.dumps({"text": text}),
                             capture_output=True, text=True, timeout=timeout, check=True)
    if len(process.stdout) > 16384:
        raise ValueError("Oversized scanner response")
    result = json.loads(process.stdout)
    if result.get("status") != "success" or result.get("decision") not in ("allow", "block", "human_in_the_loop_required"):
        raise ValueError("Invalid scanner response")
    return result["decision"]


def verdict(decision, mode):
    if mode == "enforce" and decision != "allow":
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                       "permissionDecisionReason": "Local LlamaFirewall: tool input rejected or scanner unavailable"}}
    # Never return allow: native Claude permissions and other hooks still apply.
    return {}


def main():
    os.umask(0o077)
    root = Path(__file__).resolve().parent
    mode, decision = "enforce", "error"  # Bad/missing config does not silently disable the gate.
    try:
        config = json.loads((root / "firewall.json").read_text())
        mode = config["mode"]
        if mode not in ("monitor", "enforce"):
            raise ValueError("Invalid mode")
        raw = sys.stdin.buffer.read(LIMIT + 1)
        if len(raw) > LIMIT:
            raise ValueError("Oversized hook payload")
        event = json.loads(raw)
        decision = evaluate(event, config["scanner"])
    except Exception:
        decision = "error"
    try:
        log = root / "firewall.ndjson"
        with log.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"time": datetime.now(timezone.utc).isoformat(), "event": "PreToolUse",
                                     "decision": decision, "mode": mode}) + "\n")
    except OSError:
        decision = "error"
    print(json.dumps(verdict(decision, mode)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
