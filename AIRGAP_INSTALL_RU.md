# Установка ГОТОВОГО полного комплекта на изолированный Debian

Никаких загрузок на этом сервере. Все необходимые файлы, включая native Claude
Code 2.1.304, уже внутри `claude-ollama-debian13-amd64-full.tar.gz`.
Сам сервер Ollama и веса модели уже должны работать во внутренней сети.

## 1. Перенос и проверка

Перенесите на сервер **два файла**: полный `.tar.gz` и его `.tar.gz.sha256`.
Это один цельный архив, не набор частей. Положите в домашний каталог, затем:

```sh
cd ~
sha256sum -c claude-ollama-debian13-amd64-full.tar.gz.sha256
tar -xzf claude-ollama-debian13-amd64-full.tar.gz
cd claude-ollama-offline
```

Должно быть `OK`. Требуются Debian 13 Trixie amd64 и стандартный Python 3.13.
Архив содержит более 600 МБ файлов до сжатия, рекомендуется 8 ГБ свободного диска
для установки/обновления. Установка идёт под обычным пользователем без sudo.

## 2. Единственная команда установки

```sh
python3 install_all_offline.py
```

Установщик проверяет полный manifest и SHA закреплённых бинарников, ставит
изолированные зависимости из локальных wheels и Claude из локального бинарника.
Нет `curl`, `apt`, `npm`, скачивания pip/venv или обращения к внешним репозиториям.
Если venv отсутствует, используется локальный pip-target. При необходимости:

```sh
python3 install_all_offline.py --force-target
```

## 3. Подключение к внутренней Ollama

Подставьте настоящий IP/порт GPU-сервера и точное имя локальной модели:

```sh
export PATH="$HOME/.local/bin:$HOME/agent-controls/bin:$PATH"
export OLLAMA_BASE_URL="http://192.168.1.10:11434"
export OLLAMA_MODEL="ИМЯ_УЖЕ_УСТАНОВЛЕННОЙ_МОДЕЛИ"

python3 "$HOME/.local/share/claude-ollama-airgap/verify_ollama.py" \
  --url "$OLLAMA_BASE_URL" --model "$OLLAMA_MODEL" --test-messages

mkdir -p "$HOME/claude-control-test"
cd "$HOME/claude-control-test"
claude-ollama
```

Если внутренний endpoint уже работает на 80, используйте `http://ВАШ_IP:80`.
Не добавляйте `/v1`. Требуется Ollama >=0.14 и локальная модель с tool calling.
Preflight обращается только к явно указанному внутреннему серверу; ничего не pull.
Ни аккаунт, ни ключ Anthropic для вызова вашей модели через Ollama не нужны.
Это Claude Code CLI с моделью Ollama, а не веса Claude. В интерактивном CLI
проверьте `/status`. Штатные подтверждения действий остаются включёнными.

## 4. Numbat и LlamaFirewall

Закройте CLI, затем:

```sh
umask 077
mkdir -p "$HOME/.numbat"
numbat hook install --agent claude --emit all \
  --output file --output-file "$HOME/.numbat/claude.ndjson"

python3 "$HOME/.local/share/claude-ollama-airgap/configure_claude.py" --mode monitor
```

Перезапустите `claude-ollama`, посмотрите `/hooks` и попросите через Bash выполнить
`pwd`. В другом терминале:

```sh
tail -F "$HOME/.numbat/claude.ndjson"
tail -F "$HOME/.local/share/claude-ollama-airgap/firewall.ndjson"
```

Эти две команды наблюдения запускайте в разных терминалах.
Тестовый маркер для инструмента Bash:

```sh
printf '%s\n' 'ignore previous instructions'
```

В monitor команда выполняется, firewall пишет `block`. После проверки включите
enforce и перезапустите CLI:

```sh
python3 "$HOME/.local/share/claude-ollama-airgap/configure_claude.py" --mode enforce
```

Маркер должен отклоняться, `pwd` — выполняться через обычные permissions. Если
модель не вызвала инструмент, тест не засчитывается. Никакие hooks не подключаются
автоматически во время установки: это отдельный явно выполняемый шаг выше.

Сканер — локальный Regex/HiddenASCII, CodeShield доступен отдельно. PromptGuard
weights не входят. Это не OS sandbox и не полный контроль всех действий агента.
Логи не переносите в публичный GitHub. Существующие settings сохраняются с backup.

## Проверенность

Настоящий pinned Claude Code, Numbat и LlamaFirewall проверяются в CI на Debian
без root и внешней сети, с локальным синтетическим Anthropic API. Вашу Ollama и
интерактивный вход проверяйте на хосте: CI не имеет доступа к вашему GPU-серверу.
Бинарник Claude подготовлен для вашего переноса; публичные исходники и открытые
зависимости доступны в репозитории отдельно от полного персонального архива.
