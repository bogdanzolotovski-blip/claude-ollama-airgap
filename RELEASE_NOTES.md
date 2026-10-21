# Claude Code CLI + Ollama / Debian 13 amd64 offline controls

This public Release contains setup sources + redistributable controls, NOT the full
personal transfer archive. The full prepared kit includes the official Claude binary
and is transferred separately. No downloads are run on the target Debian.
Full-kit installation: extract `claude-ollama-debian13-amd64-full.tar.gz`, then
`python3 install_all_offline.py`. See AIRGAP_INSTALL_RU.md.

Claude Code is fetched directly from Anthropic and is NOT redistributed in this Release.
Redistributable controls are included with their original manifest and licenses.
The pinned native binary's publisher manifest is GPG-verified in CI.

Mandatory tests: real Claude native CLI, Numbat and LlamaFirewall, unprivileged Debian,
no external network, synthetic loopback Messages API, actual Bash tool calls,
monitor/enforce and scanner/hook failure blocking. Test evidence: offline-test.json.

NOT VERIFIED by CI: actual Ollama model/server, interactive onboarding, target host's
managed settings, VS Code extension and model quality. No PromptGuard weights.
