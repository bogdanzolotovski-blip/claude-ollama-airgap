#!/usr/bin/env python3
"""Opt-in, preserving merge of our PreToolUse hook into Claude settings."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as output:
        json.dump(value, output, indent=2)
        output.write("\n")
        temporary = Path(output.name)
    temporary.chmod(0o600)
    os.replace(temporary, path)


def merge(settings, command, mode, event_name="PreToolUse"):
    if not isinstance(settings, dict):
        raise ValueError("Claude settings must be an object")
    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("hooks must be an object")
    groups = hooks.setdefault(event_name, [])
    if not isinstance(groups, list):
        raise ValueError("PreToolUse must be an array")
    kept = []
    for group in groups:
        if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
            raise ValueError("Unexpected existing hook structure; no changes made")
        remaining = [item for item in group["hooks"] if item.get("command") != command]
        if remaining:
            kept.append(dict(group, hooks=remaining))
    kept.append({"matcher": "*", "hooks": [{"type": "command", "command": command,
                                            "timeout": 40, "onFailure": "block" if mode == "enforce" else "continue"}]})
    hooks[event_name] = kept
    return settings


def configure(args):
    base_python = str(Path(getattr(sys, "_base_executable", sys.executable)).resolve())
    version = subprocess.check_output([args.claude, "--version"], text=True, timeout=30)
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", version)
    if not match or tuple(map(int, match.groups())) < (2, 1, 295):
        raise ValueError("Requires Claude Code >=2.1.295 for onFailure:block; use the pinned official native version")
    scanner = args.scanner.expanduser().resolve()
    if not scanner.is_file():
        raise ValueError("Install agent-controls first; scanner missing: " + str(scanner))
    root = args.root.expanduser().resolve()
    settings_path = args.settings.expanduser().resolve()
    old = settings_path.read_text() if settings_path.is_file() else "{}"
    settings = json.loads(old)
    command = shlex.quote(base_python) + " -I " + shlex.quote(str(root / "firewall_hook.py"))
    updated = merge(settings, command, args.mode)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    hook_source = Path(__file__).with_name("firewall_hook.py")
    if hook_source.resolve() != (root / "firewall_hook.py").resolve():
        shutil.copy2(hook_source, root / "firewall_hook.py")
    if Path(__file__).resolve() != (root / "configure_claude.py").resolve():
        shutil.copy2(Path(__file__), root / "configure_claude.py")
    if args.local_pdn:
        for name in ("pdn_scan.py", "pdn_policy.json"):
            source = Path(__file__).with_name(name)
            target = root / name
            if source.resolve() != target.resolve() and (name != "pdn_policy.json" or not target.exists()):
                shutil.copy2(source, target)
        atomic_json(root / "pdn_runtime.json", {"upstream_scanner": str(scanner)})
        cli = Path.home() / ".local/bin/llama-firewall"
        cli.parent.mkdir(parents=True, exist_ok=True)
        cli.write_text("#!" + base_python + " -I\nimport runpy\nrunpy.run_path(" + repr(str(root / "pdn_scan.py")) + ", run_name='__main__')\n")
        cli.chmod(0o700)
        scanner = cli.resolve()
    if args.check_prompts:
        updated = merge(updated, command + " --event UserPromptSubmit", args.mode, "UserPromptSubmit")
    atomic_json(root / "firewall.json", {"mode": args.mode, "scanner": str(scanner)})
    if settings_path.exists():
        backup = settings_path.with_name(settings_path.name + ".backup-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
        shutil.copy2(settings_path, backup)
        backup.chmod(0o600)
    atomic_json(settings_path, updated)
    print("Configured:", settings_path, "mode:", args.mode)
    print("Restart Claude Code, inspect /hooks, then test a real tool call.")
    print("No automatic tool approvals, no API credentials or provider settings were added.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["monitor", "enforce"], default="monitor")
    parser.add_argument("--local-pdn", action="store_true", help="Install local pilot PII rules and llama-firewall CLI")
    parser.add_argument("--check-prompts", action="store_true", help="Also check new user messages, not just tool arguments")
    config = Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude")))
    parser.add_argument("--settings", type=Path, default=config / "settings.json")
    parser.add_argument("--root", type=Path, default=Path("~/.local/share/claude-ollama-airgap"))
    parser.add_argument("--scanner", type=Path, default=Path("~/agent-controls/bin/agent-firewall-scan"))
    parser.add_argument("--claude", default="claude")
    try:
        configure(parser.parse_args())
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise SystemExit("Configuration failed: " + str(error))
