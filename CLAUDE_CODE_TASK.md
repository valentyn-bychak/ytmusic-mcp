# Завдання для Claude Code: розгорнути ytmusic-mcp

Привіт, Claude Code. Користувач — Valentyn. Я (Claude в Cowork-mode) уже написав весь код проєкту і поклав сюди — `/Users/valentine/Code/ytmusic-mcp/`. Твоя задача — запустити його і перевірити що все працює.

## Контекст

Це **YouTube Music MCP-сервер** на Python — обгортка над `ytmusicapi`. Після розгортання він буде доступний з Claude Desktop через стандартний MCP-протокол.

Структура проєкту вже на диску:
```
~/Code/ytmusic-mcp/
├── pyproject.toml         (deps: mcp[cli], ytmusicapi==1.11.0, PyYAML)
├── setup.sh               (готовий bootstrap-скрипт)
├── README.md
├── LICENSE
├── .gitignore
├── examples/playlists_spec.yaml
└── src/ytmusic_mcp/
    ├── __init__.py
    ├── __main__.py
    ├── auth.py
    ├── cli.py
    └── server.py
```

Конфіг `~/Library/Application Support/Claude/claude_desktop_config.json` уже оновлений — `YouTube Music` MCP зареєстрований і вказує на `~/Code/ytmusic-mcp/venv/bin/python -m ytmusic_mcp`.

## Що зробити

### Крок 1. Запустити setup.sh
```bash
cd ~/Code/ytmusic-mcp && bash setup.sh
```

Скрипт повинен:
1. Перевірити/встановити Homebrew (запитає пароль адміна якщо ставитиме)
2. Перевірити/встановити Python 3.11 і gh CLI через brew
3. Залогінити користувача в `gh` (відкриє браузер) — якщо ще не залогінений
4. Створити venv і поставити пакет (`pip install -e .`)
5. Створити git-репо, зробити initial commit
6. Створити **публічний** GitHub-репо `ytmusic-mcp` через `gh repo create` і запушити
7. Оновити Claude Desktop config (я вже зробив, але повторне записування ідемпотентне)

Якщо щось падає — діагностуй, ремонтуй, пробуй ще раз. Найімовірніші проблеми:
- `gh auth login` хоче інтерактив → запропонуй користувачу `gh auth login --web` і чекай
- Конфлікт назви репо → подивись `gh repo view valentine/ytmusic-mcp` і запропонуй або підлинкувати існуюче, або змінити назву
- Старий Python 3.9 у системі → переконайся що `venv` створено з python3.11

### Крок 2. Авторизація на YouTube Music (потрібна допомога користувача)

Після setup.sh:

1. Скажи Valentyn: «Відкрий Chrome → https://music.youtube.com → переконайся що залогнений → `Cmd+Opt+I` → вкладка Network → онови сторінку якщо порожньо → клік на будь-який запит до music.youtube.com → правий клік → Copy → **Copy request headers**. Скажи "готово" коли скопіюєш.»

2. Як тільки Valentyn скаже що скопіював — використай `pbpaste` для читання з буфера обміну:
```bash
pbpaste > /tmp/yt-headers.txt
wc -l /tmp/yt-headers.txt   # повинно бути 20+ рядків
head -3 /tmp/yt-headers.txt # перевір що це справді headers, не випадковий текст
```

3. Запусти auth-команду з цим файлом:
```bash
cd ~/Code/ytmusic-mcp && source venv/bin/activate && ytmusic-mcp auth --headers-file /tmp/yt-headers.txt
```

4. Перевір що працює:
```bash
ytmusic-mcp status
```
Має повернути JSON з `"valid": true` і `"account_name"`. Якщо ні — покажи помилку Valentyn.

5. Прибери тимчасовий файл з cookies:
```bash
rm /tmp/yt-headers.txt
```

### Крок 3. Smoke-test MCP-сервера

Запусти сервер у режимі stdio і дай йому 2 секунди — повинен стартонути без помилок:
```bash
cd ~/Code/ytmusic-mcp && timeout 2 venv/bin/python -m ytmusic_mcp || echo "Exit code: $?"
```
Очікуваний вихід: exit code 124 (timeout) — означає що сервер стартонув і слухав stdio. Будь-який інший exit code з трейсбеком — є проблема, її треба знайти.

### Крок 4. Фінал

Скажи Valentyn:
- ✅ Що зроблено (список з посиланнями на GitHub-репо)
- ⚠️ Що `YouTube Music` MCP з'явиться в Claude Desktop **після повного перезапуску** (Cmd+Q → відкрити знову, не просто закрити вікно)
- 📝 Що в наступному чаті в Claude Desktop він може попросити: "Перевір що YT Music MCP працює" — і Claude (я) викличу `config(action='auth_status')`

## Важливо

- **Не редагуй файли проєкту без потреби.** Код уже написаний і протестований логічно. Якщо щось не працює — швидше за все проблема в середовищі (відсутній pip, python не той), а не в коді.
- **Auth-файл `~/.config/ytmusic-mcp/browser.json` містить cookies YouTube** — поводься з ним як з паролем. У `.gitignore` він уже виключений.
- **Не комітити cookies** ні в якому разі. Перевір що `git status` після setup.sh не показує `browser.json` чи подібне.
- Якщо `gh repo create` створив **private** замість public — переключи через `gh repo edit --visibility public --accept-visibility-change-consequences`.

## Якщо застрягнеш

Покажи Valentyn повну помилку і запропонуй варіанти. Він зрозуміє — у нього є dev-досвід (у нього в `~/` є `whisper.cpp`, `my-bot`, `.zshrc`, він користується VS Code).
