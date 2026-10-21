# Claude Code CLI + Ollama / Debian 13 amd64 offline controls

Download `claude-ollama-setup.zip`, extract and run on an internet-connected computer:
`python fetch_offline.py --output offline`. Transfer the entire `offline` folder to Debian.
See README.md for rootless native installation, Ollama connection and opt-in hooks.

Claude Code is fetched directly from Anthropic and is NOT redistributed in this Release.
Redistributable controls are included with their original manifest and licenses.
The pinned native binary's publisher manifest is GPG-verified in CI.

Mandatory tests: real Claude native CLI, Numbat and LlamaFirewall, unprivileged Debian,
no external network, synthetic loopback Messages API, actual Bash tool calls,
monitor/enforce and scanner/hook failure blocking. Test evidence: offline-test.json.

NOT VERIFIED by CI: actual Ollama model/server, interactive onboarding, target host's
managed settings, VS Code extension and model quality. No PromptGuard weights.
