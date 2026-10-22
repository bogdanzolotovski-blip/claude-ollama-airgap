#!/usr/bin/env python3
"""Small source-only update for an already installed offline controls bundle."""
import hashlib
from pathlib import Path
import tarfile

root = Path(__file__).resolve().parents[1]
output = root / "dist/claude-controls-pdn-update.tar.gz"
output.parent.mkdir(exist_ok=True)
names = ["configure_claude.py", "firewall_hook.py", "pdn_scan.py", "pdn_policy.json", "NUMBAT_LLAMA_PILOT_RU.md"]
with tarfile.open(output, "w:gz") as archive:
    for name in names:
        archive.add(root / name, arcname="claude-controls-pdn-update/" + name)
digest = hashlib.sha256(output.read_bytes()).hexdigest()
Path(str(output) + ".sha256").write_text(digest + "  " + output.name + "\n", encoding="ascii")
print(output.name, digest)
