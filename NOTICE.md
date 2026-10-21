# Third-party components and provenance

Authored integration files are MIT licensed (see LICENSE).
`bundle_common.py` and `install_agent_controls.py` derive from the MIT project
https://github.com/bogdanzolotovski-blip/opencode-security-airgap at f53a8e5.

The redistributable controls archive is reused byte-for-byte from its verified
public Release; its licenses, exact sources and per-file manifest are retained.
It includes Numbat, LlamaFirewall/CodeShield/Semgrep, CPU PyTorch dependencies,
Debian runtime libraries, and an unused Harness2 core/demo inherited from that
archive. Harness2 is not installed into or integrated with Claude by this repo.
The optional core remains in the separate agent-controls installation.

Claude Code is proprietary Anthropic software, not covered by our MIT license.
This repository and its Releases do NOT redistribute its binary. The online
fetch helper obtains a pinned binary directly from the official Anthropic
download service for your own subsequent offline installation. Review the
upstream terms before use: https://github.com/anthropics/claude-code/blob/main/LICENSE.md

No weights, accounts, tokens, user logs or corporate source are distributed.
