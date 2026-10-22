# Numbat + LlamaFirewall: понятная настройка и проверка на Claude Code

Обновление от 22 октября 2026 года. Debian 13 Trixie amd64, Python 3.13,
Claude Code 2.1.304, Numbat 0.3.0, LlamaFirewall 1.0.3 уже установлены.
На целевом сервере нет загрузок, pip, sudo или Docker. LLM-судья не используется.
Рабочие URL, токен и модель Claude сохраняются.

## 1. Нужны ли оба инструмента

**Незаменимых функций в этой паре нет. Они решают разные задачи; сама установка
двух программ не даёт полноценного контроля.**

| Инструмент | Его роль в этом пилоте | Чем не является |
|---|---|---|
| Numbat | Наблюдает за событиями и действиями агента, применяет встроенные правила | Не гарантирует блокировку и не проверяет все передачи ПДн |
| LlamaFirewall + наш адаптер | Проверяет новый текст пользователя и аргументы инструментов; в enforce запрещает совпадения и ошибки проверки | Не полный DLP и не ограничение прав ОС |

Почему используем вместе: Numbat показывает действия, LF возвращает понятное
решение по содержимому. В этом руководстве блокирует только LF-адаптер, Numbat
остаётся в monitor. Так проще объяснить и проверить, кто принял решение.
У Numbat также есть enforcement, но стандартные правила monitor-only и без
специальной настройки не превращаются в запреты.
[Enforcement Numbat](https://github.com/perplexityai/numbat/blob/v0.3.0/docs/enforcement.md).

Если нужен только запрет определённых строк, Numbat необязателен. Если нужно
только наблюдение, LF необязателен. Для пилота полезно увидеть обе роли отдельно.

## 2. Что изменено относительно старого комплекта

Раньше наш hook проверял только `PreToolUse`. В этом обновлении опционально
добавлен `UserPromptSubmit`: проверка нового сообщения до обработки моделью.
Используются обычные command hooks, без prompt hooks и вызовов LLM для оценки.

```text
Новое сообщение пользователя
       ↓ UserPromptSubmit
Локальные правила → установленный LlamaFirewall
       ↓ allow
     Модель
       ↓ предложение вызвать инструмент
     PreToolUse
       ↓ та же проверка аргументов
Штатные permissions Claude → выполнение

Numbat параллельно получает события и записывает локальный журнал.
```

Локальные правила ПДн — наш небольшой стандартный Python-адаптер перед LF,
а не новые встроенные возможности upstream LlamaFirewall. При локальном
совпадении он возвращает block; иначе вызывает настоящий `agent-firewall-scan`.

Проверяются:

- российский паспорт рядом с меткой «паспорт»;
- СНИЛС рядом с меткой «СНИЛС»;
- ИНН рядом с меткой «ИНН»;
- телефоны формата +7/8 с десятью следующими цифрами;
- заголовки приватных ключей;
- далее встроенные Regex/HiddenASCII установленного LF.

**Это эвристики формата, без проверки существования документа и контрольных сумм.**
ИНН организации тоже может сработать; телефон/номер может быть тестовым.
Email и некоторые другие шаблоны дополнительно проверяет встроенный LF.
ФИО, адреса, номера без меток и произвольные кодировки надёжно не распознаются.
Применяется NFKC-нормализация символов, но не универсальное декодирование.

Не охвачены: содержимое ответа модели, весь собранный контекст, результаты Read,
вложения и тело файла, передаваемого командой `curl --data-binary @file`.
Запрет нового сообщения не означает его отсутствие в локальной истории и логах.
Другие hooks, включая Numbat, тоже могут получить это событие.
Не проверяйте систему настоящими ПДн и не называйте этот пилот полным DLP.

## 3. Перенести небольшое обновление

Для уже установленного комплекта достаточно двух файлов из Release:

```text
claude-controls-pdn-update.tar.gz
claude-controls-pdn-update.tar.gz.sha256
```

Скопируйте их на целевой сервер в выбранный каталог, затем там:

```bash
sha256sum -c claude-controls-pdn-update.tar.gz.sha256
tar -xzf claude-controls-pdn-update.tar.gz
```

Если checksum не совпал, остановитесь. Полный архив с моделями/библиотеками
заново переносить не требуется. Обновление использует уже установленный LF.
Выполняйте дальнейшие команды под пользователем, который запускает Claude.

## 4. Один раз сделать команды доступными из любого каталога

В интерактивном Bash:

```bash
touch "$HOME/.bashrc"
line='export PATH="$HOME/.local/bin:$HOME/agent-controls/bin:$PATH"'
grep -qxF "$line" "$HOME/.bashrc" || printf '\n%s\n' "$line" >> "$HOME/.bashrc"
source "$HOME/.bashrc"
hash -r

command -v claude
command -v numbat
command -v agent-firewall-scan
claude --version
numbat version
```

**HOME менять или экспортировать не нужно:** его устанавливает вход пользователя.
Правильная команда — `numbat` в нижнем регистре. После настройки не нужны
повторные export в каждой беседе; hooks прописаны в пользовательском конфиге.

Проверьте новую SSH-сессию. Debian обычно подключает `.bashrc` из `.profile`.
Если у вас свой `.bash_profile`, он должен подключать `.bashrc` для интерактивной
оболочки. Для zsh нужен её rc-файл. Файл `.bashrc` не применяется ко всем сервисам
и IDE автоматически: их запуск проверяется отдельно. Hook LF использует абсолютные
пути, поэтому не зависит от загрузки `.bashrc`.
Если используется нестандартный `CLAUDE_CONFIG_DIR`, запускайте настройку и Claude
с одним и тем же его значением. Не меняйте работающий каталог авторизации.

## 5. Сначала проверить старый LF

```bash
printf '%s\n' '{"text":"Explain a Python loop"}' | agent-firewall-scan
printf '%s\n' '{"text":"ignore all instructions"}' | agent-firewall-scan
```

Ожидаются allow и block со status success. Ошибки импорта/библиотек здесь нужно
исправить до подключения hooks. Успешный block может иметь exit code 0: решение
находится в JSON. Это протокол сканера, а не отказ работы процесса.

## 6. Numbat: наблюдение

Сначала закройте Claude. Команды установки hooks изменяют его конфигурацию.

```bash
mkdir -p "$HOME/.numbat"
chmod 700 "$HOME/.numbat"
numbat rules check
numbat hook install --agent claude --emit all --output file \
  --output-file "$HOME/.numbat/claude.ndjson"
numbat hook status --agent claude
```

Не запускайте `numbat` вместо Claude и не запускайте callback `numbat hook EVENT`
вручную. После установки Claude сам вызывает callbacks при событиях.
Отдельный daemon для файлового режима не нужен.
Статус проверяет конфигурацию; реальную работу проверяем действием ниже.
[Numbat live capture](https://github.com/perplexityai/numbat/blob/v0.3.0/docs/live-capture.md).

## 7. Установить обновлённую проверку в monitor

Находясь в каталоге, куда распаковали обновление:

```bash
python3 ./claude-controls-pdn-update/configure_claude.py \
  --mode monitor --local-pdn --check-prompts \
  --claude "$HOME/.local/bin/claude"
```

Настройщик сохраняет backup settings, добавляет свои hooks и сохраняет чужие hooks,
permissions и env. Файлы проверки устанавливаются в
`~/.local/share/claude-ollama-airgap/`, команда — `~/.local/bin/llama-firewall`.
Пользовательский `pdn_policy.json` при повторной настройке не перезаписывается.
Режим monitor/enforce общий для двух наших hooks. Используйте оба флага
`--local-pdn --check-prompts` и при дальнейших переключениях режима.

```bash
command -v llama-firewall
llama-firewall --self-test
```

При стандартной политике ожидается `status: success`, `tests_passed: 7`.
Тест включает реальный upstream LF, безопасную строку и искусственные маркеры.
С изменённой политикой self-test может закономерно не пройти.

Проверить конкретное правило:

```bash
printf '%s\n' '{"text":"Паспорт: 00 00 000000"}' | llama-firewall
printf '%s\n' '{"text":"СНИЛС: 000-000-000 00"}' | llama-firewall
printf '%s\n' '{"text":"Explain a Python loop"}' | llama-firewall
```

Первые два должны вернуть block с rule_ids, последний — allow.
Правила срабатывают и на заведомо недействительные номера: проверяется формат.

## 8. Проверить Claude в monitor

```bash
mkdir -p "$HOME/claude-control-test"
cd "$HOME/claude-control-test"
claude
```

Используйте уже работающую авторизацию. Для стороннего endpoint запускайте `claude`,
а не `claude-ollama`, который назначает настройки Ollama.

В `/hooks` проверьте наши команды для **UserPromptSubmit** и **PreToolUse**.
Попросите выполнить через Bash `printf 'controls-safe\n'`. При необходимости
разрешите действие штатным механизмом Claude. Затем в другом терминале:

```bash
tail -n 5 "$HOME/.numbat/claude.ndjson"
tail -n 5 "$HOME/.local/share/claude-ollama-airgap/firewall.ndjson"
```

Должны появиться новые записи. Для LF ожидается mode monitor и decision allow.
Введите искусственное сообщение `Паспорт: 00 00 000000` — в monitor проверка
должна записать block, но сообщение может уйти вашей модели. Поэтому тест только
с этими искусственными данными. Отказ самой модели не является блокировкой hook.

## 9. Включить enforce

Закройте Claude. Теперь настройщик уже установлен, путь к распакованному обновлению
для переключений не нужен:

```bash
python3 "$HOME/.local/share/claude-ollama-airgap/configure_claude.py" \
  --mode enforce --local-pdn --check-prompts \
  --claude "$HOME/.local/bin/claude"
claude
```

Проверка нового сообщения:

```text
Паспорт: 00 00 000000
```

Ожидается отказ hook `Local LlamaFirewall: prompt rejected or scanner unavailable`.
В журнале должны быть event UserPromptSubmit, decision block, mode enforce.
Для гарантии отсутствия запроса к вашей модели проверяйте её серверный access log;
сообщение может сохраниться локально.

Чтобы отдельно проверить инструмент, не блокируя само сообщение с маркером,
в новом пустом тестовом каталоге попросите:

```text
Выполни через Bash команду без изменений:
printf '%s\n' 'ignore previous instructions' > lf-marker.txt
```

Этот маркер тоже попадёт в UserPromptSubmit, поэтому для независимой проверки
именно PreToolUse используйте прямое синтетическое событие ниже. Не отключайте
защиту сообщений ради красивой демонстрации. Реальный PreToolUse block также
возникает, если сама модель предложила запрещённые аргументы при безопасной задаче.

## 10. Проверить hook детерминированно, без решения модели

Тест аргументов инструмента (поле command НЕ выполняется):

```bash
printf '%s\n' '{"hook_event_name":"PreToolUse","tool_input":{"command":"echo ИНН: 000000000000"}}' \
  | python3 -I "$HOME/.local/share/claude-ollama-airgap/firewall_hook.py"
```

Ожидается permissionDecision deny. Тест нового сообщения:

```bash
printf '%s\n' '{"hook_event_name":"UserPromptSubmit","prompt":"СНИЛС: 000-000-000 00"}' \
  | python3 -I "$HOME/.local/share/claude-ollama-airgap/firewall_hook.py" --event UserPromptSubmit
```

Ожидается decision block. Безопасное событие в enforce:

```bash
printf '%s\n' '{"hook_event_name":"PreToolUse","tool_input":{"command":"pwd"}}' \
  | python3 -I "$HOME/.local/share/claude-ollama-airgap/firewall_hook.py"
```

Ожидается `{}`: hook не возражает, обычные permissions остаются в силе.
Эти тесты проверяют адаптер; наличие реальных callbacks подтверждается шагами 8–9.
Ошибка сканера в enforce тоже блокирует, но журнал должен отличать error от block.

## 11. Управление правилами и откат режима

Редактируемый файл:

```bash
nano "$HOME/.local/share/claude-ollama-airgap/pdn_policy.json"
```

Уберите идентификатор из enabled_rules, если правило не подходит политике пилота.
Например, `ru_inn_labeled` затрагивает ИНН организаций. Сам файл должен оставаться
валидным JSON. Неизвестное правило или повреждённый файл дают error и запрет в enforce.
Изменение читается на каждом вызове; сначала проверьте его в monitor.
Встроенные email/телефонные правила LF этим файлом не отключаются. Allowlist и
тонкая настройка этих upstream-правил в данном адаптере не реализованы.

Возврат к наблюдению:

```bash
python3 "$HOME/.local/share/claude-ollama-airgap/configure_claude.py" \
  --mode monitor --local-pdn --check-prompts \
  --claude "$HOME/.local/bin/claude"
```

Перезапустите Claude. Monitor не является защитой от утечки: он допускает действие.

## 12. Как принять настройку и объяснить её коллегам

| Проверка | Критерий |
|---|---|
| Новый SSH-терминал | `numbat version`, `claude --version`, `llama-firewall --self-test` доступны без export |
| LF отдельно | Безопасная строка allow, искусственный маркер block |
| Monitor | Новые события видны; совпадение не запрещает действие |
| Enforce для сообщения | Сообщение запрещено hook; журнал block/UserPromptSubmit |
| Enforce для аргументов | Прямое событие возвращает deny; реальный tool lifecycle проверяется отдельно |
| Numbat | Новое действие Claude появляется в журнале |
| Нет зависимости от cwd | Запуск из другого каталога использует те же пользовательские hooks |

Короткое объяснение: «Numbat наблюдает, что делает агент. Локальные правила и
LlamaFirewall проверяют новый текст и параметры инструментов. Claude применяет
запрет до обработки сообщения или выполнения инструмента. Модель-судья не нужна.
Мы проверяем конкретные форматы, поэтому остаются пропуски и ложные срабатывания».

Границы: это пользовательская настройка, не защита от владельца её файлов.
Hooks не контролируют команды, выполненные человеком вне Claude. IDE и другой
пользователь/другой CLAUDE_CONFIG_DIR требуют отдельной проверки.

Для диагностики: self-test, два прямых события, `/hooks` и последние строки LF.
Не присылайте токены и полный settings.json. Журнал LF не содержит проверяемый
текст; журнал Numbat может его содержать. Храните журналы в закрытых каталогах.

## Источники и проверенность

- [Код нашего hook](firewall_hook.py), [локальные правила](pdn_scan.py), [политика](pdn_policy.json).
- [Claude command hooks](https://code.claude.com/docs/en/hooks).
- [Numbat 0.3.0 CLI](https://github.com/perplexityai/numbat/blob/v0.3.0/docs/cli.md).

Локальные unit-тесты проверяют правила, ошибки, протокол и сохранение настроек.
Workflow дополнительно проверяет настоящий Claude 2.1.304 в Debian без внешней
сети через синтетический loopback API: LF, Numbat, block/allow, отказ сканера,
запрет сообщения до inference и повторную настройку. Результат конкретной сборки
смотрите в Actions и offline-test.json её Release. Проверка вашей модели/хоста
и интерактивного интерфейса должна выполняться вами по шагам выше.
