#!/usr/bin/env python3
"""Install an already-downloaded official Claude binary without root/network."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile

from bundle_common import sha256


def install(binary, prefix):
    lock = json.loads((Path(__file__).resolve().parent / "versions.lock.json").read_text())
    if (platform.system() != "Linux" or platform.machine() not in ("x86_64", "amd64") or
            platform.freedesktop_os_release().get("ID") != "debian" or
            platform.freedesktop_os_release().get("VERSION_ID", "").split(".")[0] != "13"):
        raise ValueError("Supported target: Debian 13 amd64")
    if sha256(binary) != lock["claude_linux_x64_sha256"]:
        raise ValueError("Claude SHA-256 mismatch: installation cancelled")
    prefix = prefix.expanduser().resolve()
    versions = prefix / "share/claude/versions"
    versions.mkdir(parents=True, exist_ok=True)
    binary_target = versions / lock["claude"]
    bindir = prefix / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    link = bindir / "claude"
    if link.exists() and not link.is_symlink():
        raise ValueError("Existing claude is a regular file; preserve/move it first: " + str(link))
    with tempfile.NamedTemporaryFile(dir=versions, delete=False) as temporary:
        candidate = Path(temporary.name)
    try:
        shutil.copyfile(binary, candidate)
        candidate.chmod(0o755)
        environment = dict(os.environ, DISABLE_AUTOUPDATER="1", CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1")
        result = subprocess.run([str(candidate), "--version"], env=environment,
                                capture_output=True, text=True, timeout=30, check=True)
        if lock["claude"] not in result.stdout:
            raise ValueError("Downloaded executable reported an unexpected version")
        candidate.replace(binary_target)
        next_link = bindir / (".claude-next-" + str(os.getpid()))
        try:
            next_link.symlink_to(binary_target)
            os.replace(next_link, link)
        finally:
            next_link.unlink(missing_ok=True)
    finally:
        candidate.unlink(missing_ok=True)
    print("Installed:", link)
    print('Activate: export PATH="' + str(bindir) + ':$PATH"')
    print("Updates/telemetry are disabled by run-claude-ollama.sh, not for arbitrary direct CLI launches.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, default=Path("claude-linux-x64/claude"))
    parser.add_argument("--prefix", type=Path, default=Path("~/.local"))
    args = parser.parse_args()
    try:
        install(args.binary, args.prefix)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise SystemExit("Installation failed: " + str(error))
