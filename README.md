# Dota 2 VPK SkinChanger

Архитектура профессионального скинченджера для **Dota 2 (Source 2)** на базе VPK-подмены без инъекций в память (`VAC-safe`).

## 📁 Структура проекта

```text
d:\morph\
├── client/                     # Нативный C++20 Core движок (клиент)
│   ├── CMakeLists.txt          # Конфигурация CMake
│   ├── include/                # nlohmann/json
│   └── src/
│       ├── SteamLocator.hpp    # Поиск Dota 2 через реестр Windows и libraryfolders.vdf
│       ├── GameInfoPatcher.hpp # Безопасный патч gameinfo_branchspecific.gi и dota.signatures (Zero VAC detection)
│       ├── ApiClient.hpp       # Нативный WinHTTP клиент (POST /api/build + GET download)
│       └── main.cpp            # Консольный лаунчер с CLI командами
├── server/                     # Бэкенд API и Fast VPK Builder (FastAPI + Python)
│   ├── cache/
│   │   └── catalog.json        # Полный кэш (127 героев, 10,851 скинов, 1,990 бандлов)
│   ├── builds/                 # Скомпилированные pak01_dir.vpk для юзеров
│   ├── items_catalog.py        # Парсер items_game.txt, русской локализации и бандлов
│   ├── vpk_builder.py          # Fast String Slicing билдер (сборка < 0.3 сек, 100% duplicate keys)
│   ├── main.py                 # REST API эндпоинты (Swagger docs)
│   └── requirements.txt        # Зависимости Python
├── custom_user_preset.json # Активный пресет пользователя
├── morph_tool.py           # CLI & Интерактивный инструмент управления каталогом и сборкой
├── test_preset.json            # Пример комбинированного пресета (скины + стиль + гем + необычный эффект)
├── run_server.py               # Точка запуска FastAPI сервера
├── RESEARCH_NOTES.md           # Детальное архитектурное исследование VFS Source 2 и ресерч Ardysa
└── README.md
```

---

## ⚡ Ключевые возможности бэкенда и ядра

1. **100% Безопасный монтаж через `gameinfo_branchspecific.gi` и `dota.signatures`:**
   * Базовый `gameinfo.gi` **никогда не модифицируется** (его SHA-1 остается оригинальным, что исключает краши и детекты координатора Valve).
   * Кастомный путь монтирования `Morph` прописывается в `gameinfo_branchspecific.gi`.
   * Контрольная сумма и CRC32 автоматически подписываются в хвосте `game/bin/win64/dota.signatures` после строки `DIGEST:`.
2. **Идеальная работа сложных Аркан и Персон (Terrorblade & Pudge):**
   * **Terrorblade**: полная связка Арканы (`hero_base` 5957) и рогов (`head` 37161) в `items_game.txt` без вредоносной подмены геометрии в VPK. Скелет, анимации стойки `abysm`, форма демона и другие слоты сета не ломаются.
   * **Pudge**: корректный инжект базовой геометрии милого Пуджа (`pudge_cute`) для личности "The Toy Butcher" (13786).
3. **Реальные Unusual и Prismatic ауры:**
   * Поддержка эфирных и призматических аур (Rubiline, Touch of Frost, Trail of Burning Doom, Midas, Ethereal Flame) через `particle_create` и валидное игровое качество `"item_quality" "unusual"`.
4. **Mix & Match кастомизация слотов:**
   * Любой слот героя (`weapon`, `head`, `back`, `armor`, `arms`, `shoulder`, `belt`) кастомизируется отдельно.
5. **Fast String Slicing Builder:**
   * Сборка кастомного VPK за **~0.25 - 0.48 секунды**.
   * Сохранение **100%** всех 9,200+ вложенных блоков `asset_modifier` (иконки, партиклы, анимации, звуки).
6. **C++ Клиент со встроенным WinHTTP:**
   * Одной командой `--apply <preset.json>` отправляет пресет на сервер, скачивает `pak01_dir.vpk` прямо в `Morph` и активирует виртуальную файловую систему.

---

## 🚀 Быстрый старт

### 1. Запуск сервера:
```powershell
python run_server.py
```

### 2. Сборка и деплой пресета через C++ клиент:
```powershell
.\client\build\Release\SkinChangerCore.exe --apply test_preset.json
```

### 3. Проверка статуса:
```powershell
.\client\build\Release\SkinChangerCore.exe --status
```

### 4. Автоматизированная утилита каталога `morph_tool.py`:
Полное управление героями, бандлами, слотами и сборкой без ручного поиска ID:
```powershell
# Интерактивное меню с выбором героя, сета и гемов
python morph_tool.py interactive

# Посмотреть текущий пресет
python morph_tool.py show

# Надеть полный сет в 1 клик (например, Doll of the Dead или The Eminence of Ristul)
python morph_tool.py equip-set pudge "Doll of the Dead"
python morph_tool.py equip-set queenofpain "The Eminence of Ristul"

# Повесить багнутый эфирный гем (Trail of Burning Doom, etc.) на оружие и спину
python morph_tool.py ethereal queenofpain burning_doom

# Скомпилировать VPK и установить в Dota 2 одной командой
python morph_tool.py build
```

### 5. Полное удаление модов и возврат к ванильной игре:
```powershell
.\client\build\Release\SkinChangerCore.exe --restore
```
