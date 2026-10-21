# Claude Code + Ollama: полностью офлайн-установка на Debian 13

**На изолированном сервере ничего не скачивается.** Передаётся один заранее
подготовленный архив `claude-ollama-debian13-amd64-full.tar.gz` и его `.sha256`.
В полном архиве уже находятся Claude Code 2.1.304 Linux amd64, Numbat 0.3.0,
LlamaFirewall 1.0.3, wheels/CPU runtime и все установщики.

**[Скачать полный архив и SHA-256 из последнего Release](https://github.com/bogdanzolotovski-blip/claude-ollama-airgap/releases/latest)**
Выбирайте `claude-ollama-debian13-amd64-full.tar.gz` и одноимённый `.sha256`.

## Команды на целевом Debian 13.7 / Trixie

Под обычным пользователем, без sudo, с Python 3.13:

```sh
sha256sum -c claude-ollama-debian13-amd64-full.tar.gz.sha256
tar -xzf claude-ollama-debian13-amd64-full.tar.gz
cd claude-ollama-offline
python3 install_all_offline.py
```

Затем укажите внутренний endpoint Ollama и точное имя уже установленной модели:

```sh
export PATH="$HOME/.local/bin:$HOME/agent-controls/bin:$PATH"
export OLLAMA_BASE_URL="http://192.168.1.10:11434"
export OLLAMA_MODEL="ИМЯ_ВАШЕЙ_ЛОКАЛЬНОЙ_МОДЕЛИ"
claude-ollama
```

Вместо 11434 можно использовать существующий внутренний порт 80. В адресе нет
`/v1`. Требуется Ollama >=0.14 и модель с поддержкой tools. Это клиент Claude Code
с моделью Ollama, а не локальные веса Claude. Публичный интернет для inference не
нужен; сама Ollama/веса уже должны быть установлены на GPU-сервере.

**[Полное руководство: перенос, проверки, Numbat, LlamaFirewall](AIRGAP_INSTALL_RU.md)**

**[Пошаговая настройка Numbat и LlamaFirewall для уже работающего Claude CLI](CLAUDE_NUMBAT_LLAMA_FIREWALL_RU.md)**

## Что находится в публичном GitHub

Полный архив для переноса, его checksum, исходники, установщики, инструкция и
CI evidence. `claude-ollama-setup.zip` предназначен для сборщика и содержит
исходники настройки. Для изолированного сервера скачивайте именно `full.tar.gz`.
Claude Code внутри полного комплекта остаётся proprietary software Anthropic;
MIT-лицензия нашего кода на него не распространяется. См. NOTICE.md.

## Контроль и проверки

- Numbat записывает Claude hooks в локальный журнал.
- Отдельный LlamaFirewall PreToolUse hook имеет режимы monitor/enforce; в enforce
  предусмотрен deny при отказе сканера и `onFailure: block` при отказе hook.
- Штатные permissions Claude сохраняются, автоматический allow не добавляется.
- Regex/HiddenASCII не являются полноценной семантической проверкой; PromptGuard
  weights не включены. CodeShield доступен отдельно. Это не OS sandbox.
- В controls унаследовано неиспользуемое ядро/демо Harness2; для Claude не нужно.

CI устанавливает полный комплект одной командой внутри Debian без root/pip и
внешней сети. Используются настоящий Claude native binary и loopback-эмулятор
Anthropic API: проверяются реальные tool calls, Numbat, allow/block, отказ scanner
и отсутствующий hook. Это **не тест вашей модели Ollama**; её проверяйте локально.
Интерактивное onboarding и корпоративные managed settings тоже требуют проверки
на хосте. Логи/credentials/корпоративные исходники в GitHub не публикуются.

## Только для сборщика, до переноса в изолированный контур

Эти команды НЕ выполняются на air-gapped Debian:

```sh
python fetch_offline.py --output offline
python scripts/build_full_kit.py --input offline
```

Они создают `dist-local/claude-ollama-debian13-amd64-full.tar.gz` и checksum.
`build_full_kit.py` сам не скачивает; он проверяет и пакует уже подготовленные
файлы. [Подробности подготовки и официальные источники](PREPARE_ONLINE.md).
Бинарник Claude проверяется по закреплённому SHA и официальному manifest;
GPG signature verification обязательна в CI. [Лицензии и происхождение](NOTICE.md).
