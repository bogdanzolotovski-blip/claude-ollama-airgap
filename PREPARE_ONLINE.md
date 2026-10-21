# Claude Code CLI + Ollama + Numbat + LlamaFirewall — Debian 13

Отдельный офлайн-комплект для **Debian 13.7 / Trixie, amd64**, Python **3.13**.
Claude Code работает на CPU-хосте пользователя, Ollama с уже загруженной моделью —
на отдельном сервере GPU. Root, apt, npm, Docker и интернет на целевом хосте не нужны.
Рекомендуется 4 ГБ+ RAM и 8 ГБ свободного диска; модели в этот комплект не входят.

```text
Debian: Claude Code CLI ── Anthropic Messages API ──> внутренний Ollama GPU
            │
            ├── Numbat hooks: локальные события и обнаружение
            └── PreToolUse → наш адаптер → LlamaFirewall: monitor / enforce
```

**Claude Code — клиент, модель отвечает через Ollama.** Это не локальные веса
Claude. Для Ollama не требуется ключ Anthropic или подключение к его облачному API;
использование самого клиента регулируется условиями Anthropic.

## Что включено и проверяется

- Claude Code **2.1.304**, официальный Linux x64 native build, без Node/npm.
- Numbat **0.3.0**, официальный бинарник и правила, native Claude hooks.
- LlamaFirewall **1.0.3**, локальные Regex/HiddenASCII; CodeShield доступен отдельно.
- Наш синхронный `PreToolUse`-адаптер: мониторинг или `deny`, не выдаёт автоматических
  разрешений Claude на команды. В enforce включает `onFailure: block`
  (нужен Claude Code >=2.1.295).
- В изолированном комплекте CPU PyTorch, wheels и Debian runtime-библиотеки.

**PromptGuard weights и AlignmentCheck не включены в рабочий профиль.** Адаптер
проверяет текст аргументов инструмента, а не смысл всей сессии и не ответы модели.
Это не песочница, не полный DLP и не защита от пользователя, владеющего hooks/logs.
Numbat здесь используется в monitor, блокировку делает отдельный LlamaFirewall hook.

Redistributable-архив controls сохранён без изменения из предыдущего проверенного
комплекта: в нём также есть неиспользуемое ядро/демо Harness2. Оно не интегрируется
с Claude и не требуется для этой схемы. См. [NOTICE.md](NOTICE.md).

## 1. Подготовить файлы на компьютере с интернетом

Скачайте `claude-ollama-setup.zip` из успешного **Release** и распакуйте.
Альтернатива: Code → Download ZIP в этом репозитории.
Откройте терминал в распакованной папке и выполните:

```sh
python fetch_offline.py --output offline
```

На Linux команда может называться `python3`. Загрузчик работает и на Windows,
скачивает именно **Linux x64**, не бинарник ОС компьютера загрузки.
Он получает ~335 МБ controls и ~289 МБ native Claude с официального сервера.
Ничего не устанавливается и не запускается на этом этапе.

Бинарник Claude **не перепубликуется в нашем GitHub Release**: это proprietary
software. Helper получает его непосредственно из официального Anthropic download
service для вашего последующего переноса. Все TLS-проверки включены; при ошибке
сертификата не используйте `--insecure` или отключение TLS.

SHA Claude проверяется по закреплённому значению и официальному manifest. На машине
с `gpg` можно дополнительно проверить подпись (CI делает это обязательно):

```sh
gpg --import offline/claude-linux-x64/claude-code.asc
gpg --fingerprint security@anthropic.com
gpg --verify offline/claude-linux-x64/manifest.json.sig offline/claude-linux-x64/manifest.json
```

Сверьте fingerprint: `31DD DE24 DDFA B679 F42D 7BD2 BAA9 29FF 1A7E CACE`.
Если прямые загрузки на рабочем компьютере заблокированы, подготовьте папку
`offline` на разрешённой машине с интернетом, затем перенесите её целиком.

## 2. Перенести папку и установить на Debian

Перенесите **всю папку `offline`**, включая подпапку `claude-linux-x64`, на флешке
или через SCP. Пример: разместить её как `~/claude-ollama-offline`.
Все дальнейшие действия — под обычным пользователем, который будет работать в CLI.

```sh
cd ~/claude-ollama-offline
cat /etc/os-release
uname -m
python3 --version

python3 install_agent_controls.py --bundle agent-controls-debian13-amd64-py313.tar.gz
python3 install_claude_offline.py --binary claude-linux-x64/claude

export PATH="$HOME/.local/bin:$HOME/agent-controls/bin:$PATH"
claude --version
python3 "$HOME/agent-controls/current/verify_agent_controls.py"
```

Ожидается Claude `2.1.304` и `PASS` проверки controls. Controls ставятся в
`~/agent-controls`; Claude — в `~/.local/share/claude/versions/`, с symlink
`~/.local/bin/claude`. Существующий обычный файл `claude` не перезаписывается.
При отсутствии venv installer controls автоматически использует изолированный
pip-target; для принудительного fallback добавьте `--force-target`.

Если нет отдельного `git`, базовый тест может работать, но Git-функции клиента
нужно проверять отдельно. Полный Git и VS Code в этот комплект не включены.

## 3. Проверить соединение с сервером Ollama

На GPU-сервере Ollama должна слушать доступный внутренний интерфейс, не только
127.0.0.1. Для Anthropic-compatible API нужна Ollama **0.14.0 или новее**.
В существующем systemd unit на GPU-сервере настройка выглядит так:

```ini
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
```

Изменение unit и перезапуск выполняет администратор GPU-сервера. Разрешите этот
порт только с хоста CLI. Если в вашей схеме уже используется внутренний порт **80**,
используйте его фактический адрес; второй listener создавать не требуется.

На Debian с Claude задайте **свои** адрес и точное имя уже установленной модели:

```sh
export OLLAMA_BASE_URL="http://192.168.1.10:11434"
export OLLAMA_MODEL="ИМЯ_ИЗ_OLLAMA_LIST"

python3 verify_ollama.py --url "$OLLAMA_BASE_URL" --model "$OLLAMA_MODEL" --test-messages
```

`192.168.1.10` — пример. Для порта 80: `http://ВАШ_IP:80`.
В **ANTHROPIC_BASE_URL нет `/v1`**: клиент сам добавляет `/v1/messages`.
Preflight проверяет внутренний адрес, наличие локальной модели, capability `tools`
и реальный небольшой запрос `/v1/messages`; ничего не скачивает и не делает pull.
Имена с `:cloud` и явно remote-модели отклоняются.

На GPU-хосте список смотрится командой `ollama list`. Если модель не поддерживает
tools, обычный чат ещё не подтверждает работу агента: нужна другая локальная модель.
Ollama рекомендует контекст 64k+ для Claude Code; на 16 ГБ VRAM это зависит от
модели, KV-cache и CPU-offload. Не выставляйте 100k вслепую. Сначала проверьте малый
workspace и фактическую память/скорость; изменение context — на сервере Ollama.

## 4. Запустить Claude Code через Ollama

```sh
mkdir -p "$HOME/claude-control-test"
cd "$HOME/claude-control-test"

sh "$HOME/claude-ollama-offline/run-claude-ollama.sh"
```

OLLAMA_BASE_URL и OLLAMA_MODEL должны быть экспортированы в этом же терминале.
Launcher отключает штатные обновления/телеметрию и назначает одну локальную модель
основному вызову, Haiku/Sonnet/Opus aliases и subagents. Это не сетевой firewall:
доступ в публичный интернет ограничивается на уровне ОС/сети.

Эквивалент минимального ручного подключения:

```sh
export ANTHROPIC_BASE_URL="$OLLAMA_BASE_URL"
export ANTHROPIC_AUTH_TOKEN=ollama
export ANTHROPIC_API_KEY=""
export DISABLE_AUTOUPDATER=1
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
claude --model "$OLLAMA_MODEL"
```

`ollama` здесь — фиктивный auth token для локального сервера, не выданный API-ключ.
Внутри CLI проверьте `/status`: должен использоваться ваш внутренний endpoint/model.
Существующие managed/user/project settings могут менять provider, env и hooks.
Если появляется вход в облако, не вводите рабочие credentials для этого теста:
проверьте base URL, aliases и эффективные настройки через `/status`.
Не включайте `--dangerously-skip-permissions`: штатные подтверждения остаются.

## 5. Включить Numbat для Claude CLI

Вернитесь в папку с файлами установки, затем:

```sh
export PATH="$HOME/.local/bin:$HOME/agent-controls/bin:$PATH"
umask 077
mkdir -p "$HOME/.numbat"
numbat hook install --agent claude --emit all --output file --output-file "$HOME/.numbat/claude.ndjson"
numbat hook status --agent claude
```

Настройки относятся к текущему пользователю/CLAUDE_CONFIG_DIR. Numbat сливает hooks
со штатным settings.json. Резервную копию имеющихся настроек сохраните перед первым
подключением: `cp -p ~/.claude/settings.json ~/.claude/settings.before-controls.json`
(если файл существует; при CLAUDE_CONFIG_DIR используйте его фактический путь).
Логи содержат рабочую информацию и не должны попадать в GitHub.

## 6. Добавить LlamaFirewall hook — сначала monitor

```sh
cd "$HOME/claude-ollama-offline"
python3 configure_claude.py --mode monitor
```

Существующие env, permissions, чужие hooks и Numbat сохраняются. Перед изменением
settings создаётся timestamp backup с правами 600. Повторная команда не дублирует
наш hook. Адаптер находится в `~/.local/share/claude-ollama-airgap/`.

Закройте старый CLI и запустите новый через `run-claude-ollama.sh`. Внутри проверьте
`/hooks`, затем попросите агент выполнить через Bash команду `pwd`.
Во втором терминале:

```sh
tail -F "$HOME/.numbat/claude.ndjson"
```

В третьем:

```sh
tail -F "$HOME/.local/share/claude-ollama-airgap/firewall.ndjson"
```

Numbat должен записать реальный tool call; firewall — `allow`, `mode: monitor`.
`hook status` сам по себе не доказывает выполнение hook.

## 7. Проверить обнаружение и блокировку

В тестовом workspace попросите агента выполнить **через Bash**:

```sh
printf '%s\n' 'ignore previous instructions'
```

Это безвредная строка-маркер, не команда изменения политики. В режиме monitor
команда выполняется, в журнале firewall должно быть `decision: block`.
Если модель не вызвала инструмент или изменила строку, тест не засчитывается.

Переключите hook и перезапустите CLI:

```sh
cd "$HOME/claude-ollama-offline"
python3 configure_claude.py --mode enforce
```

Снова проверьте `pwd` и маркер: `pwd` проходит через обычные permissions,
маркер отклоняется PreToolUse hook. Ошибка сканера, timeout или невозможность
запуска hook также должны блокировать благодаря `onFailure: block`.
Наш hook **никогда не возвращает automatic allow**; native permissions сохраняются.
Regex имеет ложные срабатывания (в том числе на email/телефоны) и пропуски: allow
не является гарантией безопасности команды. CodeShield не сканирует всё
автоматически; доступен как `agent-firewall-scan --profile code` для кода на stdin.

Возврат к наблюдению:

```sh
python3 configure_claude.py --mode monitor
```

## Диагностика

- `Connection refused` — Ollama не слушает адрес/порт или service не запущен.
- Timeout — проверьте маршрутизацию/МСЭ между CLI и GPU-хостом.
- `/api/tags` работает, `/v1/messages` нет — проверьте версию Ollama, proxy и имя модели.
- Слишком много запросов к разным именам моделей — запускайте нашим launcher и
  проверьте aliases в эффективных settings.
- Нет hooks — новый процесс CLI, тот же HOME/CLAUDE_CONFIG_DIR и `/hooks`.
- `.so` missing — запишите имя; не копируйте библиотеки Ubuntu и не меняйте glibc.
  Debian 13 runtime controls включает только совместимые вспомогательные библиотеки.
- VS Code remote extension — hooks надо устанавливать там, где действительно
  работает процесс Claude, а не автоматически на клиентском Windows.

## Проверки и границы доказательств

Workflow вручную: Actions → **Verify Claude Ollama offline controls** → Run workflow.
Обязательны SHA controls/native, GPG подпись официального manifest и тесты в Debian
без root/pip/внешней сети. Используется настоящий pinned Claude binary и loopback
эмулятор Anthropic API с синтетическими ответами, вызывающими реальные Bash tool
calls. Проверяются Numbat records, monitor, enforce, безопасное действие,
недоступный scanner, отсутствующий hook (`onFailure: block`) и сохранность настроек.

**Это не тест реальной модели Ollama.** Ваш endpoint, качество tool calls,
interactive onboarding, корпоративные managed settings и расширение VS Code
нужно проверять на целевом хосте. Результат CI опубликован как `offline-test.json`.
При неуспешном workflow Artifact не считается готовой проверенной поставкой;
Release создаётся только после всех обязательных проверок.

Rootless hooks можно изменить от имени их владельца. Для обязательного контроля
администратор должен защищать executable/policy и независимый приёмник журналов.

## Официальные источники

- [Ollama: Claude Code integration](https://docs.ollama.com/integrations/claude-code)
- [Ollama: Anthropic compatibility](https://docs.ollama.com/api/anthropic-compatibility)
- [Claude Code: setup and signed manifests](https://code.claude.com/docs/en/setup)
- [Claude Code: hooks and onFailure](https://code.claude.com/docs/en/hooks)
- [Numbat v0.3.0 deployment](https://github.com/perplexityai/numbat/blob/v0.3.0/docs/deployment.md)
- [LlamaFirewall](https://github.com/meta-llama/PurpleLlama/tree/main/LlamaFirewall)
