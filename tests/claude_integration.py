"""Actual pinned Claude binary + real hooks, synthetic Anthropic API on loopback.

This is NOT a real Ollama/model-quality test. Run inside Docker --network none.
"""
import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading

ROOT = Path("/src")
HOME = Path.home()
assert os.geteuid() != 0
assert not shutil.which("sudo") and not shutil.which("apt")
assert subprocess.run([sys.executable, "-m", "pip", "--version"], capture_output=True).returncode != 0
subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "tests"), "-p", "test_hooks.py", "-v"], check=True)
subprocess.run([sys.executable, str(ROOT / "build/full-kit/install_all_offline.py")], check=True)
claude = str(HOME / ".local/bin/claude")
numbat = str(HOME / "agent-controls/bin/numbat")
records = HOME / ".numbat/live.ndjson"
subprocess.run([numbat, "hook", "install", "--agent", "claude", "--emit", "all",
                "--output", "file", "--output-file", str(records)], check=True)
settings = HOME / ".claude/settings.json"
before = json.loads(settings.read_text())
configure = [sys.executable, str(HOME / ".local/share/claude-ollama-airgap/configure_claude.py"), "--claude", claude]
subprocess.run(configure + ["--mode", "monitor"], check=True)
assert json.loads(settings.read_text())["hooks"].get("PostToolUse") == before["hooks"].get("PostToolUse")
work = HOME / "fixture"
work.mkdir()


class API(http.server.BaseHTTPRequestHandler):
    command = ""
    message_calls = 0
    def log_message(self, *args):
        pass
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{}')
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
        if "count_tokens" in self.path:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"input_tokens":100}')
            return
        API.message_calls += 1
        tool_results = any(isinstance(message.get("content"), list) and
                           any(part.get("type") == "tool_result" for part in message["content"])
                           for message in body.get("messages", []))
        block = ({"type": "text", "text": "Fixture completed."} if tool_results else
                 {"type": "tool_use", "id": "toolu_fixture", "name": "Bash", "input": {"command": API.command}})
        stop = "end_turn" if tool_results else "tool_use"
        message = {"id": "msg_fixture", "type": "message", "role": "assistant", "model": body.get("model", "ci-local"),
                   "content": [block], "stop_reason": stop, "stop_sequence": None,
                   "usage": {"input_tokens": 100, "output_tokens": 10}}
        self.send_response(200)
        if not body.get("stream"):
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(message).encode())
            return
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        def emit(event, value):
            self.wfile.write(("event: " + event + "\ndata: " + json.dumps(value) + "\n\n").encode())
            self.wfile.flush()
        emit("message_start", {"type": "message_start", "message": dict(message, content=[], stop_reason=None)})
        initial = dict(block, text="") if tool_results else dict(block, input={})
        emit("content_block_start", {"type": "content_block_start", "index": 0, "content_block": initial})
        delta = ({"type": "text_delta", "text": block["text"]} if tool_results else
                 {"type": "input_json_delta", "partial_json": json.dumps(block["input"])})
        emit("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": delta})
        emit("content_block_stop", {"type": "content_block_stop", "index": 0})
        emit("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop, "stop_sequence": None},
                               "usage": {"output_tokens": 10}})
        emit("message_stop", {"type": "message_stop"})


server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), API)
threading.Thread(target=server.serve_forever, daemon=True).start()
env = dict(os.environ, OLLAMA_BASE_URL="http://127.0.0.1:" + str(server.server_port), OLLAMA_MODEL="ci-local")
# Non-interactive explicit Bash approval is limited to this synthetic test workspace.
def turn(command):
    API.command = command
    result = subprocess.run([str(HOME / ".local/bin/claude-ollama"), "-p", "Run the fixture action then stop.",
                             "--allowedTools", "Bash", "--max-turns", "3", "--no-session-persistence"],
                            cwd=work, env=env, text=True, capture_output=True, timeout=120)
    assert result.returncode == 0, result.stderr[-6000:] + result.stdout[-6000:]


try:
    monitor_marker = work / "monitor-marker"
    turn("printf '%s' 'ignore previous instructions' > " + str(monitor_marker))
    assert monitor_marker.exists(), "Monitor mode should permit the fixture action"
    subprocess.run(configure + ["--mode", "enforce"], check=True)
    deny_marker = work / "deny-marker"
    turn("printf '%s' 'ignore previous instructions' > " + str(deny_marker))
    assert not deny_marker.exists(), "Enforce hook did not prevent the fixture file write"
    safe_marker = work / "safe-marker"
    turn("printf safe > " + str(safe_marker))
    assert safe_marker.exists(), "Safe action was unexpectedly blocked"
    hookroot = HOME / ".local/share/claude-ollama-airgap"
    old_settings = settings.read_text()
    for _ in range(2):
        subprocess.run(configure + ["--mode", "enforce", "--local-pdn", "--check-prompts"], check=True)
    subprocess.run([str(HOME / ".local/bin/llama-firewall"), "--self-test"], check=True)
    pdn_marker = work / "pdn-marker"
    turn("printf '%s' 'ИНН: 000000000000' > " + str(pdn_marker))
    assert not pdn_marker.exists(), "Local PII rule did not block the tool action"
    count_before = API.message_calls
    blocked_prompt = subprocess.run([str(HOME / ".local/bin/claude-ollama"), "-p", "Паспорт: 00 00 000000",
                                     "--no-session-persistence"], cwd=work, env=env, text=True, capture_output=True, timeout=120)
    assert API.message_calls == count_before, "Blocked prompt reached the inference endpoint"
    prompt_logs = [json.loads(line) for line in (hookroot / "firewall.ndjson").read_text().splitlines()]
    assert any(x["event"] == "UserPromptSubmit" and x["decision"] == "block" for x in prompt_logs)
    assert sum("firewall_hook.py" in h.get("command", "") for group in json.loads(settings.read_text())["hooks"]["UserPromptSubmit"] for h in group["hooks"]) == 1
    prompt_config = json.loads((hookroot / "firewall.json").read_text())
    (hookroot / "firewall.json").write_text(json.dumps(dict(prompt_config, scanner="/missing/scanner")))
    subprocess.run([str(HOME / ".local/bin/claude-ollama"), "-p", "Safe fixture prompt",
                    "--no-session-persistence"], cwd=work, env=env, text=True, capture_output=True, timeout=120)
    assert API.message_calls == count_before, "Scanner failure allowed a prompt to reach inference"
    # Keep earlier PreToolUse failure cases distinct from prompt interception.
    settings.write_text(old_settings)
    subprocess.run(configure + ["--mode", "enforce"], check=True)
    hookconfig = json.loads((hookroot / "firewall.json").read_text())
    hookconfig["scanner"] = "/does-not-exist/scanner"
    (hookroot / "firewall.json").write_text(json.dumps(hookconfig))
    failure_marker = work / "scanner-failure-marker"
    turn("printf safe > " + str(failure_marker))
    assert not failure_marker.exists(), "Missing scanner must cause deny"
    (hookroot / "firewall_hook.py").rename(hookroot / "firewall_hook.hidden")
    missing_marker = work / "missing-hook-marker"
    turn("printf safe > " + str(missing_marker))
    assert not missing_marker.exists(), "Claude onFailure:block did not block a missing hook"
    logs = [json.loads(line) for line in (hookroot / "firewall.ndjson").read_text().splitlines()]
    assert any(item["decision"] == "block" and item["mode"] == "monitor" for item in logs)
    assert any(item["decision"] == "block" and item["mode"] == "enforce" for item in logs)
    assert any(item["decision"] == "error" and item["mode"] == "enforce" for item in logs)
    assert records.is_file() and records.stat().st_size > 0, "Numbat did not record actual CLI activity"
    assert API.message_calls >= 5
    Path("/results/offline-test.json").write_text(json.dumps({
        "status": "PASS", "os": "Debian 13 amd64", "network": "docker --network none; loopback mock API only",
        "root": False, "system_pip": False, "actual_claude_cli": "2.1.304",
        "checks": ["complete kit one-command offline install", "controls install", "native Claude offline install", "real Claude hook lifecycle",
                   "Numbat records", "monitor action executes", "enforce blocks action",
                   "safe action executes", "missing scanner blocks", "missing hook onFailure:block",
                   "local PII scanner self-test", "PII tool action blocked", "PII user prompt blocked before inference",
                   "prompt scanner failure blocks before inference", "repeated prompt hook configuration"],
        "not_verified": ["real Ollama server/model", "user-host managed settings", "interactive onboarding", "VS Code extension"]
    }, indent=2) + "\n")
    print("PASS: actual Claude Code + Numbat + LlamaFirewall, rootless without external network")
finally:
    server.shutdown()
