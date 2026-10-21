#!/usr/bin/env python3
"""Verify a completely prepared transfer folder, using only local files."""
import argparse
import json
from pathlib import Path, PurePosixPath

from bundle_common import sha256


def verify(root):
    root = Path(root).resolve()
    manifest = json.loads((root / "KIT-MANIFEST.json").read_text())
    if manifest.get("kind") != "claude-ollama-complete-offline":
        raise ValueError("This is not a complete offline kit")
    expected = manifest["files"]
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*")
              if p.is_file() and "__pycache__" not in p.parts and not p.name.endswith(".pyc")}
    if actual != set(expected) | {"KIT-MANIFEST.json"}:
        raise ValueError("Kit inventory differs from manifest; copy the complete prepared folder")
    for name, digest in expected.items():
        posix = PurePosixPath(name)
        path = root / name
        if (posix.is_absolute() or ".." in posix.parts or "\\" in name or ":" in name or
                path.is_symlink() or not path.resolve().is_relative_to(root)):
            raise ValueError("Unsafe kit path: " + name)
        if sha256(path) != digest:
            raise ValueError("Kit SHA-256 mismatch: " + name)
    lock = json.loads((root / "versions.lock.json").read_text())
    if sha256(root / lock["controls_archive"]) != lock["controls_sha256"]:
        raise ValueError("Pinned controls SHA mismatch")
    if sha256(root / "claude-linux-x64/claude") != lock["claude_linux_x64_sha256"]:
        raise ValueError("Pinned Claude native SHA mismatch")
    print("PASS: complete offline kit; all files and pinned binaries verified")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, nargs="?", default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    try:
        verify(args.directory)
    except (OSError, ValueError, KeyError) as error:
        raise SystemExit("Kit verification failed: " + str(error))
