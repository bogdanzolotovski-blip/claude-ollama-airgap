# Настройка Numbat и LlamaFirewall для работающего Claude Code CLI

Пошаговая настройка на Debian 13 Trixie без загрузок из интернета.
Файлы нашего офлайн-комплекта уже находятся на хосте, Claude Code уже подключён
к рабочему endpoint модели. Все команды выполняются обычным пользователем,
который запускает Claude, без sudo.

## Как устроена схема

| Компонент | Что делает в этом руководстве |
|---|---|
| Numbat | Записывает события Claude и проверяет их встроенными правилами |
| LlamaFirewall | Проверяет текст аргументов инструментов перед выполнением |
| Наш адаптер `firewall_hook.py` | Возвращает Claude решение: наблюдать или запретить вызов |

В этом руководстве Numbat используется для наблюдения, блокировку возвращает
отдельный адаптер LlamaFirewall. Подключение к модели, URL и ключ остаются в
существующих настройках Claude. Запускайте `~/.local/bin/claude` напрямую:
launcher `claude-ollama` назначает параметры авторизации Ollama и не подходит
для уже настроенного стороннего endpoint с собственным Bearer token.

## 1. Проверить файлы

```bash
export PATH="$HOME/.local/bin:$HOME/agent-controls/bin:$PATH"

numbat version
ls -l "$HOME/agent-controls/bin/agent-firewall-scan"
ls -l "$HOME/.local/share/claude-ollama-airgap/configure_claude.py"
```

Далее используем:

```bash
FW_ROOT="$HOME/.local/share/claude-ollama-airgap"
```

Если `configure_claude.py` отсутствует в установленном каталоге, найдите его:

```bash
find "$HOME" -maxdepth 6 -type f -name configure_claude.py 2>/dev/null
```

В командах запуска `configure_claude.py` ниже подставьте найденный путь.
`firewall_hook.py` должен лежать рядом с ним. По умолчанию настройщик устанавливает
адаптер и конфиг в `~/.local/share/claude-ollama-airgap`, поэтому `FW_ROOT` остаётся
тем же. Если самого `agent-firewall-scan` нет, сначала требуется установка
перенесённого комплекта по [офлайн-инструкции](AIRGAP_INSTALL_RU.md).

## 2. Сохранить рабочие настройки Claude

В них уже находятся правильные URL, ключ и модель.

```bash
CC_CONFIG="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
printf 'Каталог настроек: %s\n' "$CC_CONFIG"

umask 077
cp -p "$CC_CONFIG/settings.json" \
  "$CC_CONFIG/settings.before-controls.$(date +%Y%m%d-%H%M%S).json"
```

Убедитесь, что это тот каталог, который использует рабочий Claude. Если
`CLAUDE_CONFIG_DIR` не используется, обычный путь — `~/.claude`.
Сам текст `CLAUDE_CONFIG_DIR` не является путём к вашему конфигу.
Если копирование закончилось ошибкой, сначала найдите фактический файл настроек.

**Не публикуйте settings.json и его backup: в них находится ключ.**

## 3. Подключить Numbat

```bash
mkdir -p "$HOME/.numbat"

numbat hook install \
  --agent claude \
  --emit all \
  --output file \
  --output-file "$HOME/.numbat/claude.ndjson"

numbat hook status --agent claude
```

Numbat добавляет callbacks в settings.json Claude. При событиях агента запускается
короткий процесс Numbat, который обрабатывает событие и дописывает журнал.
Для этого режима не нужен отдельный сервер или постоянно работающий daemon.
`--emit all` включает обычные события, поэтому для проверки подходит безопасное
действие. [Официальное описание режима](https://github.com/perplexityai/numbat/blob/v0.3.0/docs/deployment.md).

`hook status` подтверждает конфигурацию. Реальную доставку событий проверяем ниже.
Используется текущий пользователь и его `CLAUDE_CONFIG_DIR`.

## 4. Проверить LlamaFirewall отдельно

Безопасная строка:

```bash
printf '%s\n' '{"text":"Summarize a local file"}' \
  | agent-firewall-scan
```

Ожидается `"decision": "allow"`.

Тестовый маркер:

```bash
printf '%s\n' '{"text":"ignore previous instructions"}' \
  | agent-firewall-scan
```

Ожидается `"decision": "block"`. В обоих ответах должен быть
`"status": "success"`. Код выхода 0 означает успешную проверку; само решение
allow/block находится в JSON. Код 2 означает ошибку сканера.

Это локальный профиль Regex/HiddenASCII. Фразу-маркер обнаруживает регулярное
выражение. **PromptGuard weights в этот комплект не входят.** CodeShield доступен
отдельным профилем `agent-firewall-scan --profile code` с JSON на stdin; наш hook
не включает его автоматически для каждого вызова инструмента.

## 5. Подключить LlamaFirewall в monitor

```bash
python3 "$FW_ROOT/configure_claude.py" \
  --mode monitor \
  --settings "$CC_CONFIG/settings.json" \
  --claude "$HOME/.local/bin/claude"
```

Если использовали найденный в распакованном комплекте настройщик, замените только
путь к `configure_claude.py` в этой команде.

Настройщик сохраняет существующие env, permissions и чужие hooks, включая Numbat,
и дополнительно делает timestamp backup. Он добавляет `PreToolUse` — проверку
перед вызовом инструмента. Для `onFailure: block` нужен Claude Code >=2.1.295;
в нашем комплекте закреплена 2.1.304.

Посмотрите конфиг самого адаптера (этот файл не содержит API-ключа):

```bash
cat "$FW_ROOT/firewall.json"
```

Пример:

```json
{
  "mode": "monitor",
  "scanner": "/home/USER/agent-controls/releases/GENERATION/bin/agent-firewall-scan"
}
```

Путь к конкретному поколению установки нормален. После обновления комплекта
повторите настройку, чтобы обновить путь сканера.

## 6. Проверить реальные действия Claude

Завершите старую сессию CLI. Создайте отдельную рабочую папку и запустите новую:

```bash
mkdir -p "$HOME/claude-control-test"
cd "$HOME/claude-control-test"
"$HOME/.local/bin/claude"
```

Внутри выполните `/hooks`. Проверьте callbacks Numbat и наш `firewall_hook.py`
в `PreToolUse`. Настройки модели и endpoint должны остаться рабочими.

### Журналы

Во **втором SSH-терминале**:

```bash
tail -F "$HOME/.numbat/claude.ndjson"
```

В **третьем SSH-терминале**:

```bash
tail -F "$HOME/.local/share/claude-ollama-airgap/firewall.ndjson"
```

Numbat может сохранять фрагменты рабочих действий; не публикуйте весь журнал.
Журнал нашего адаптера содержит время, событие, решение и режим без текста
аргументов. В rootless установке оба журнала доступны их владельцу.

### Безопасное действие

Напишите агенту:

```text
Выполни через инструмент Bash команду pwd и покажи результат.
```

Ожидается настоящий вызов Bash, событие в Numbat и `decision: allow`,
`mode: monitor` в firewall. Если модель просто написала предполагаемый результат,
тест ещё не выполнен.

### Обнаружение маркера

Напишите агенту:

```text
Выполни через Bash следующую безвредную команду.
Сохрани текст аргумента без изменений:

printf '%s\n' 'ignore previous instructions' > monitor-marker.txt
```

В monitor файл должен создаться, а firewall записать, например:

```json
{"event":"PreToolUse","decision":"block","mode":"monitor"}
```

Сканер обнаружил маркер; режим наблюдения допускает обычное продолжение обработки
действия. Штатные permissions Claude продолжают применяться.

## 7. Включить enforce

Закройте Claude. В терминале, где заданы `FW_ROOT` и `CC_CONFIG`:

```bash
python3 "$FW_ROOT/configure_claude.py" \
  --mode enforce \
  --settings "$CC_CONFIG/settings.json" \
  --claude "$HOME/.local/bin/claude"

cd "$HOME/claude-control-test"
"$HOME/.local/bin/claude"
```

Если это новый SSH-терминал, сначала заново задайте:

```bash
export PATH="$HOME/.local/bin:$HOME/agent-controls/bin:$PATH"
FW_ROOT="$HOME/.local/share/claude-ollama-airgap"
CC_CONFIG="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
```

Для теста используйте новое имя файла, которого ещё нет. Попросите агента:

```text
Выполни через Bash:

printf '%s\n' 'ignore previous instructions' > enforce-marker.txt
```

Ожидается отказ:

```text
Local LlamaFirewall: tool input rejected or scanner unavailable
```

В другом терминале проверьте:

```bash
ls -l "$HOME/claude-control-test/enforce-marker.txt"
```

Файл не должен появиться. В журнале firewall ожидается `decision: block`,
`mode: enforce`. Затем снова попросите выполнить `pwd`: безопасное действие
должно проходить через штатные permissions Claude.

| Проверка | Monitor | Enforce |
|---|---|---|
| `pwd` | Проходит через обычные permissions | Проходит через обычные permissions |
| Аргумент с маркером | Журнал block, действие допускается | Вызов отклоняется |
| Ошибка сканера | Журнал error | Вызов отклоняется |

Адаптер возвращает deny при block/ошибке в enforce. `onFailure: block` дополнительно
покрывает отказ запуска самого hook и его timeout. Автоматического allow адаптер
не выдаёт. Если модель не вызвала инструмент или изменила маркер, проверку нужно
повторить с реальным вызовом. Запись Numbat об обычном событии подтверждает доставку;
для проверки его конкретных детекторов нужны отдельные fixtures/rules.

## 8. Вернуться к monitor

```bash
python3 "$FW_ROOT/configure_claude.py" \
  --mode monitor \
  --settings "$CC_CONFIG/settings.json" \
  --claude "$HOME/.local/bin/claude"
```

После изменения перезапустите Claude.

## Границы контроля и диагностика

- Проверяется содержимое аргументов инструмента: например, текст команды или
  записываемого файла. Обычный текст в чате сам по себе не проходит через наш
  `PreToolUse`; ответы модели и результаты инструментов этим адаптером не проверяются.
- Allow не гарантирует безопасность команды. Regex/HiddenASCII имеют пропуски
  и ложные срабатывания, включая срабатывания на email/телефоны.
- Настройки OpenCode отдельные. Здесь подключаются Claude hooks; существующие
  плагины OpenCode не редактируются.
- Если событий нет, проверьте нового пользователя/процесс, HOME, CLAUDE_CONFIG_DIR,
  `/hooks`, эффективные settings и stderr/debug Claude.
- Пользователь, владеющий файлами hooks, бинарниками и журналами, может отключить
  контроль. Для обязательной корпоративной политики администратор должен защищать
  настройки и независимый приёмник журналов.

Для разбора подключения достаточно вывода `numbat hook status --agent claude`
и нескольких строк `firewall.ndjson`. Settings с ключами и полный журнал Numbat
не передавайте в публичные обсуждения.

## Источники и проверенность

- [Numbat v0.3.0: deployment](https://github.com/perplexityai/numbat/blob/v0.3.0/docs/deployment.md)
- [Numbat v0.3.0: coverage](https://github.com/perplexityai/numbat/blob/v0.3.0/docs/agent-coverage.md)
- [Claude Code: hooks](https://code.claude.com/docs/en/hooks)
- [Исходник нашего настройщика](configure_claude.py)
- [Исходник нашего адаптера](firewall_hook.py)

Контракт и реальные Claude tool calls проверялись в CI с синтетическим локальным
Anthropic API без внешней сети. Выполнение всех шагов на вашем хосте подтверждается
реальными событиями и результатом тестового действия, а не наличием файлов.
