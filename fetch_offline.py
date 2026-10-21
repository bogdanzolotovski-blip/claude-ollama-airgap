#!/usr/bin/env python3
"""Run ONLY on an internet-connected computer. stdlib, works on Windows/Linux."""
import argparse
import json
from pathlib import Path
import shutil
import urllib.request

from bundle_common import sha256

ROOT = Path(__file__).resolve().parent


def fetch(url, destination, expected=None):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and expected and sha256(destination) == expected:
        print("Already verified:", destination.name)
        return
    temporary = destination.with_name(destination.name + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "claude-ollama-airgap/1"})
    try:
        with urllib.request.urlopen(request, timeout=300) as source, open(temporary, "wb") as output:
            shutil.copyfileobj(source, output, 1024 * 1024)
        if expected and sha256(temporary) != expected:
            raise ValueError("SHA-256 mismatch: " + destination.name)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    print("Downloaded:", destination.name)


def prepare(output, controls_only=False, claude_only=False):
    lock = json.loads((ROOT / "versions.lock.json").read_text())
    output.mkdir(parents=True, exist_ok=True)
    if not claude_only:
        archive = output / lock["controls_archive"]
        fetch(lock["controls_release"] + "/" + archive.name, archive, lock["controls_sha256"])
        (output / (archive.name + ".sha256")).write_text(lock["controls_sha256"] + "  " + archive.name + "\n")
    if not controls_only:
        folder = output / "claude-linux-x64"
        base = lock["claude_download_root"] + "/" + lock["claude"]
        fetch(base + "/manifest.json", folder / "manifest.json")
        manifest = json.loads((folder / "manifest.json").read_text())
        expected = lock["claude_linux_x64_sha256"]
        if (manifest.get("version") != lock["claude"] or
                manifest["platforms"]["linux-x64"]["checksum"] != expected):
            raise ValueError("Official manifest differs from pinned version/checksum")
        fetch(base + "/manifest.json.sig", folder / "manifest.json.sig")
        fetch("https://downloads.claude.ai/keys/claude-code.asc", folder / "claude-code.asc")
        fetch(base + "/linux-x64/claude", folder / "claude", expected)
        (folder / "claude").chmod(0o755)
        (folder / "claude.sha256").write_text(expected + "  claude\n")
    for name in ("bundle_common.py", "install_agent_controls.py", "install_claude_offline.py",
                 "configure_claude.py", "firewall_hook.py", "run-claude-ollama.sh",
                 "verify_ollama.py", "versions.lock.json", "README.md", "NOTICE.md", "LICENSE"):
        if (ROOT / name).resolve() != (output / name).resolve():
            shutil.copy2(ROOT / name, output / name)
    print("Prepared:", output.resolve())
    print("Claude checksum is verified against a pinned value + publisher manifest.")
    print("GPG signature verification is mandatory in CI; optional local steps are in README.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("offline"))
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--controls-only", action="store_true")
    modes.add_argument("--claude-only", action="store_true")
    args = parser.parse_args()
    prepare(args.output, args.controls_only, args.claude_only)
