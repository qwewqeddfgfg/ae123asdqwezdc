# Архитектурное исследование Source 2 VFS, VPK-моддинга Dota 2 и ресерч ArdysaModsTools

Документ описывает технические принципы работы виртуальной файловой системы Source 2, механизмы валидации целостности Valve (`dota.signatures`), анатомию сложных предметов (`Terrorblade Arcana`, `Pudge Persona`, `Invoker`) и решение проблемы детектов и вылетов.

---

## 1. Механизм валидации файлов Valve и почему происходил вылет / детект

### 1.1. Ошибка модификации `gameinfo.gi`
В движке Source 2 (`engine2.dll` / `filesystem_stdio.dll`) в каталоге `game/bin/win64/dota.signatures` хранится таблица контрольных сумм всех критических системных файлов:
```text
...\..\..\dota\gameinfo.gi~SHA1:088FE9788E2342E7AF671A5AD136FB143A6B5A09;CRC:C18D898A
...\..\..\dota\gameinfo_branchspecific.gi~SHA1:224B6F879D00D419B6A10FE07B4DDB3D827FD31F;CRC:7B89F784
...
DIGEST:D17BC6730890...
```

* Строка `gameinfo.gi` жестко прописана **ДО** строки `DIGEST:`.
* Любая модификация `gameinfo.gi` приводит к несовпадению SHA-1/CRC. В результате:
  1. Либо Game Coordinator при проверке целостности выдает окно: *"Античит Valve не может подтвердить надёжность устройства"* (VAC Untrusted) или крашит игру.
  2. Либо движок Source 2 сбрасывает `SearchPaths` на дефолтные, и кастомный VPK перестает монтироваться — **в игре исчезают все кастомные скины и остаются только дефолтные модельки!**

### 1.2. Решение по архитектуре ArdysaModsTools
1. **`gameinfo.gi` никогда не модифицируется!** Он остается 100% ванильным.
2. Кастомный путь монтирования `Morph` прописывается в **`game/dota/gameinfo_branchspecific.gi`**:
   ```vdf
   "GameInfo"
   {
       game 		"Dota 2"
       title 		"Dota 2"

       FileSystem
       {
           SteamAppId				570
           BreakpadAppId			373300
           BreakpadAppId_Tools		375360

           SearchPaths
           {
               Game				Morph
               Mod					Morph
           }
       }
   }
   ```
3. Вычисляется SHA-1 и CRC32 от получившегося `gameinfo_branchspecific.gi`.
   * CRC вычисляется по стандарту IEEE 802.3 (полином 0xEDB88320) в формате little-endian hex: `(crc & 0xffffffff).to_bytes(4, 'little').hex().upper()`.
4. В конец файла `game/bin/win64/dota.signatures` **ПОСЛЕ** строки `DIGEST:` дописывается строка:
   ```text
   ...\..\..\dota\gameinfo_branchspecific.gi~SHA1:<SHA1>;CRC:<CRC>
   ```
   Движок Source 2 считывает сигнатуры сверху вниз и берет последнее вхождение файла. Сигнатура совпадает, проверка целостности проходит успешно, клиент 100% VAC-safe, моды монтируются без сбоев.

---

## 2. Анатомия косметических предметов и исправление Terrorblade

### 2.1. Почему Terrorblade получался «упоротым»
1. **Вредоносная перезапись файлов геометрии (`.vmdl_c`)**:
   Предыдущая версия сборщика физически заменяла внутри `pak01_dir.vpk`:
   * `models/heroes/terrorblade/terrorblade.vmdl_c` <- `terrorblade_arcana.vmdl_c`
   * `models/heroes/terrorblade/horns.vmdl_c` <- `horns_arcana.vmdl_c`
   
   В Source 2 предмет Арканы ТБ (`5957`) **УЖЕ** содержит `asset_modifier` типа `entity_model`:
   ```vdf
   "asset_modifier"
   {
       "type"        "entity_model"
       "asset"       "npc_dota_hero_terrorblade"
       "modifier"    "models/heroes/terrorblade/terrorblade_arcana.vmdl"
   }
   ```
   Движок САМ берет модель Арканы для героя. При физической замене файлов происходил двойной спавн меша, конфликт скелетов с другими слотами (крылья, броня, оружие), кости смещались, и персонаж деформировался.
   
2. **Невалидные `static_attributes`**:
   Инжект несуществующих классов атрибутов (`gem color`, `prismatic_color`) в `static_attributes` ломал внутренний парсер предметов Valve и приводил к сбоям рендера.

### 2.2. Правильная архитектура Terrorblade
* Слот `hero_base` (дефолтный ID `913`) заменяется на Аркану `5957` (несет `entity_model`, все звуки, иконки, частицы тела `terrorblade_ambient_body_arcana_horns.vpcf` и анимацию `abysm`).
* Слот `head` (дефолтный ID `478`):
  * Если пользователь не выбрал другие рога -> получает рога Арканы `37161` (`horns_arcana.vmdl`).
  * Если пользователь выбрал кастомные рога из сета -> получает выбранные рога.
* Прямая подмена файлов `terrorblade.vmdl_c` и `horns.vmdl_c` **полностью удалена**.
* Для Unusual / Prismatic эффектов используется проверенный метод: инжект ауры частиц через `visuals -> asset_modifier -> particle_create` с `"item_quality" "unusual"`.

---

## 3. Резюме исправлений

| Компонент | Было | Стало (по ресерчу Ardysa) |
| :--- | :--- | :--- |
| **Монтаж VFS** | Модификация `gameinfo.gi` (вылеты, детекты) | Модификация `gameinfo_branchspecific.gi` |
| **Сигнатуры** | Игнорировались (несовпадение SHA1 в `dota.signatures`) | Дописывание SHA1/CRC в хвост `dota.signatures` после `DIGEST:` |
| **Целостность `gameinfo.gi`** | Ломалась | 100% оригинальный ванильный файл |
| **Terrorblade модели** | Принудительная перезапись `.vmdl_c` (ломал скелет) | Чистый `entity_model` через `items_game.txt` без перезаписи меша |
| **Terrorblade гемы** | Фиктивный `static_attributes` (не работал) | Unusual / Prismatic ауры через `particle_create` |
| **Loose files** | Лежали распакованные `scripts/` рядом с VPK | Только чистый `pak01_dir.vpk` в `game/Morph/` |
