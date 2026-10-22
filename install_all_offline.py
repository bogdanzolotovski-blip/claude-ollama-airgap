#!/usr/bin/env python3
"""Install a complete transferred kit. No downloads or third-party bootstrap."""
import argparse
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys

from verify_kit import verify


def install(force_target=False):
    root = Path(__file__).resolve().parent
    lock = json.loads((root / "versions.lock.json").read_text())
    if (sys.platform != "linux" or platform.machine() not in ("x86_64", "amd64") or
            platform.python_implementation() != "CPython" or sys.version_info[:2] != (3, 13)):
        raise ValueError("Requires Debian 13 amd64 and standard CPython 3.13")
    os_release = platform.freedesktop_os_release()
    if os_release.get("ID") != "debian" or os_release.get("VERSION_ID", "").split(".")[0] != "13":
        raise ValueError("Requires Debian 13 Trixie")
    verify(root)
    base = str(Path(getattr(sys, "_base_executable", sys.executable)).resolve())
    env = dict(os.environ, PIP_NO_INDEX="1", DISABLE_AUTOUPDATER="1",
               CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1", HF_HUB_OFFLINE="1",
               TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1")
    controls = [base, str(root / "install_agent_controls.py"), "--bundle", str(root / lock["controls_archive"])]
    if force_target:
        controls.append("--force-target")
    subprocess.run(controls, check=True, env=env)
    subprocess.run([base, str(root / "install_claude_offline.py"), "--binary",
                    str(root / "claude-linux-x64/claude")], check=True, env=env)
    support = Path.home() / ".local/share/claude-ollama-airgap"
    support.mkdir(parents=True, exist_ok=True)
    for name in ("configure_claude.py", "firewall_hook.py", "pdn_scan.py", "pdn_policy.json", "verify_ollama.py", "run-claude-ollama.sh"):
        if name == "pdn_policy.json" and (support / name).exists():
            continue
        shutil.copy2(root / name, support / name)
    binpath = Path.home() / ".local/bin/claude-ollama"
    # Preserve an unrelated launcher; never silently overwrite arbitrary user files.
    if binpath.exists() and "# claude-ollama-airgap launcher" not in binpath.read_text():
        raise ValueError("Unrelated launcher exists: " + str(binpath))
    binpath.write_text("#!/bin/sh\n# claude-ollama-airgap launcher\nexec sh " +
                       shlex.quote(str(support / "run-claude-ollama.sh")) + ' "$@"\n')
    binpath.chmod(0o755)
    print("PASS: all components installed from transferred local files; no download step")
    print('export PATH="$HOME/.local/bin:$HOME/agent-controls/bin:$PATH"')
    print('Set OLLAMA_BASE_URL and OLLAMA_MODEL, then run: claude-ollama')
    print("Existing Claude provider settings and hooks have not been changed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force-target", action="store_true")
    args = parser.parse_args()
    try:
        install(args.force_target)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise SystemExit("Offline installation failed: " + str(error))
