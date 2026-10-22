#!/usr/bin/env python3
"""Claude prompt/tool adapter. Standard library only; never logs scanned content."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

LIMIT = 1024 * 1024


def evaluate(event, scanner, timeout=30):
    if event.get("hook_event_name") == "UserPromptSubmit" and isinstance(event.get("prompt"), str):
        text = event["prompt"]
    elif event.get("hook_event_name") == "PreToolUse" and isinstance(event.get("tool_input"), dict):
        # Scan string values directly: JSON escaping can hide newlines and Unicode.
        def strings(value):
            if isinstance(value, str):
                yield value
            elif isinstance(value, dict):
                for item in value.values():
                    yield from strings(item)
            elif isinstance(value, list):
                for item in value:
                    yield from strings(item)
        text = "\n".join(strings(event["tool_input"]))
    else:
        raise ValueError("Expected prompt or tool input event")
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


def verdict(decision, mode, event_name="PreToolUse"):
    if mode == "enforce" and decision != "allow":
        if event_name == "UserPromptSubmit":
            return {"decision": "block", "reason": "Local LlamaFirewall: prompt rejected or scanner unavailable"}
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                       "permissionDecisionReason": "Local LlamaFirewall: tool input rejected or scanner unavailable"}}
    # Never return allow: native Claude permissions and other hooks still apply.
    return {}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", choices=["PreToolUse", "UserPromptSubmit"], default="PreToolUse")
    args = parser.parse_args()
    os.umask(0o077)
    root = Path(__file__).resolve().parent
    mode, decision = "enforce", "error"  # Bad/missing config does not silently disable the gate.
    try:
        config = json.loads((root / "firewall.json").read_text())
        configured_mode = config["mode"]
        if configured_mode not in ("monitor", "enforce"):
            raise ValueError("Invalid mode")
        mode = configured_mode
        raw = sys.stdin.buffer.read(LIMIT + 1)
        if len(raw) > LIMIT:
            raise ValueError("Oversized hook payload")
        event = json.loads(raw)
        if event.get("hook_event_name") != args.event:
            raise ValueError("Unexpected event type")
        decision = evaluate(event, config["scanner"])
    except Exception:
        decision = "error"
    try:
        log = root / "firewall.ndjson"
        with log.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"time": datetime.now(timezone.utc).isoformat(), "event": args.event,
                                     "decision": decision, "mode": mode}) + "\n")
    except OSError:
        decision = "error"
    print(json.dumps(verdict(decision, mode, args.event)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
