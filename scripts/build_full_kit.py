#!/usr/bin/env python3
"""Pack already fetched local files into ONE transfer archive. Does not download."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bundle_common import sha256
from verify_kit import verify


def build(folder, output, prepare_only=False):
    folder = folder.resolve()
    output = output.resolve()
    lock = json.loads((ROOT / "versions.lock.json").read_text())
    required = [lock["controls_archive"], lock["controls_archive"] + ".sha256",
                "claude-linux-x64/claude", "claude-linux-x64/manifest.json",
                "claude-linux-x64/manifest.json.sig", "claude-linux-x64/claude-code.asc"]
    for name in required:
        if not (folder / name).is_file():
            raise ValueError("Complete local input missing: " + name)
    for name in ("install_all_offline.py", "verify_kit.py", "bundle_common.py", "install_agent_controls.py",
                 "install_claude_offline.py", "configure_claude.py", "firewall_hook.py", "verify_ollama.py",
                 "run-claude-ollama.sh", "versions.lock.json", "README.md", "AIRGAP_INSTALL_RU.md",
                 "LICENSE", "NOTICE.md"):
        shutil.copy2(ROOT / name, folder / name)
    files = {}
    for path in sorted(folder.rglob("*")):
        if path.is_symlink():
            raise ValueError("Links not allowed in transfer kit")
        if path.is_file() and path.name != "KIT-MANIFEST.json" and "__pycache__" not in path.parts and not path.name.endswith(".pyc"):
            files[path.relative_to(folder).as_posix()] = sha256(path)
    (folder / "KIT-MANIFEST.json").write_text(json.dumps({
        "kind": "claude-ollama-complete-offline", "created_utc": datetime.now(timezone.utc).isoformat(),
        "versions": lock, "files": files,
        "distribution": "Prepared for this user's offline transfer; includes proprietary official Claude binary"
    }, indent=2) + "\n")
    verify(folder)
    if prepare_only:
        print("Prepared complete local kit:", folder)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".part")
    try:
        with tarfile.open(temporary, "w:gz", compresslevel=1) as archive:
            for name in sorted(files.keys() | {"KIT-MANIFEST.json"}):
                path = folder / name
                def normalize(info):
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    info.mode = 0o755 if name.endswith(".sh") or name == "claude-linux-x64/claude" else 0o644
                    return info
                archive.add(path, arcname="claude-ollama-offline/" + name, filter=normalize)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    digest = sha256(output)
    Path(str(output) + ".sha256").write_text(digest + "  " + output.name + "\n")
    print(json.dumps({"archive": str(output), "size_bytes": output.stat().st_size, "sha256": digest}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "offline")
    parser.add_argument("--output", type=Path, default=ROOT / "dist-local/claude-ollama-debian13-amd64-full.tar.gz")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    build(args.input, args.output, args.prepare_only)
