# Claude Code CLI + Ollama / Debian 13 amd64 offline controls

Download `claude-ollama-debian13-amd64-full.tar.gz` and its adjacent `.sha256`.
The full prepared archive includes the official pinned Claude Linux binary and
all controls dependencies. No downloads are run on the target Debian.
Full-kit installation: extract `claude-ollama-debian13-amd64-full.tar.gz`, then
`python3 install_all_offline.py`. See AIRGAP_INSTALL_RU.md.

Claude Code remains proprietary Anthropic software; our MIT license does not apply
to it. Controls retain their original manifest and licenses.
The pinned native binary's publisher manifest is GPG-verified in CI.

Mandatory tests: real Claude native CLI, Numbat and LlamaFirewall, unprivileged Debian,
no external network, synthetic loopback Messages API, actual Bash tool calls,
monitor/enforce and scanner/hook failure blocking. Test evidence: offline-test.json.

NOT VERIFIED by CI: actual Ollama model/server, interactive onboarding, target host's
managed settings, VS Code extension and model quality. No PromptGuard weights.
