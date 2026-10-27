#!/usr/bin/env python3
"""
morph_tool.py - Automated Cosmetic Catalog & SkinChanger Tool for Dota 2 Morph.
Allows instant search and equipping of full sets, individual slot items,
and bugged ethereal gems (Trail of Burning Doom, Ethereal Flame, etc.)
without manual ID searching. Automates build and installation into Dota 2.
"""

import os
import sys
import json
import argparse
import subprocess
from typing import Dict, Any, Optional, List, Tuple

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CATALOG_PATH = os.path.join(BASE_DIR, "server", "cache", "catalog.json")
PRESET_PATH = os.path.join(BASE_DIR, "custom_user_preset.json")
CORE_EXE_PATH = os.path.join(BASE_DIR, "client", "build", "Release", "SkinChangerCore.exe")
OUTPUT_VPK_PATH = os.path.join(BASE_DIR, "server", "builds", "pak01_dir.vpk")
DEFAULT_DOTA_PATH = r"E:\Steam\steamapps\common\dota 2 beta"

sys.path.insert(0, os.path.join(BASE_DIR, "server"))
from vpk_builder import FastVpkBuilder, PRISMATIC_COLORS
import vpk

# Popular Bugged Ethereal Gems
ETHEREAL_GEMS = {
    "frostbloom": {
        "name": "Frostbloom (Silver / Cyan Winter Frost)",
        "path": "particles/econ/seasonal/seasonal_ambient_silver.vpcf",
        "desc": "Glacial silver swirling ethereal snowflakes and winter frostbloom."
    },
    "burning_doom": {
        "name": "Trail of Burning Doom (Lava / Flame)",
        "path": "particles/econ/courier/courier_trail_lava/courier_trail_lava.vpcf",
        "desc": "Burning pillars of fire and molten lava footsteps."
    },
    "ethereal_flame": {
        "name": "Ethereal Flame",
        "path": "particles/econ/courier/courier_trail_01/courier_trail_01.vpcf",
        "desc": "Rising intense spiritual energy flames."
    },
    "rubiline_sheen": {
        "name": "Rubiline Sheen",
        "path": "particles/econ/courier/courier_trail_ruby/courier_trail_ruby.vpcf",
        "desc": "Pink ruby crystals and ethereal particle trail."
    },
    "touch_of_midas": {
        "name": "Touch of Midas",
        "path": "particles/econ/courier/courier_golden_roshan/golden_roshan_ambient.vpcf",
        "desc": "Golden sparkling coins and celestial dust."
    },
    "touch_of_frost": {
        "name": "Touch of Frost",
        "path": "particles/econ/courier/courier_roshan_frost/courier_roshan_frost_ambient.vpcf",
        "desc": "Glacial ice crystals and freezing winter frost."
    },
    "bleak_hallucination": {
        "name": "Bleak Hallucination",
        "path": "particles/econ/courier/courier_trail_spirit/courier_trail_spirit.vpcf",
        "desc": "Ghostly spirit after-images when walking."
    },
    "lotus_blossom": {
        "name": "Trail of the Lotus Blossom",
        "path": "particles/econ/courier/courier_trail_blossoms/courier_trail_blossoms.vpcf",
        "desc": "Falling pink lotus petals."
    },
    "diretide_corruption": {
        "name": "Diretide Corruption",
        "path": "particles/econ/courier/courier_trail_hw_2012/courier_trail_hw_2012.vpcf",
        "desc": "Green ghostly cobwebs and eerie smoke."
    }
}

class MorphCatalogTool:
    def __init__(self):
        if not os.path.exists(CATALOG_PATH):
            raise FileNotFoundError(f"Catalog cache not found at {CATALOG_PATH}. Run server first.")
        with open(CATALOG_PATH, "r", encoding="utf-8") as f:
            self.catalog = json.load(f)
        self.heroes = self.catalog.get("heroes", {})
        self.preset = self.load_preset()

    def load_preset(self) -> Dict[str, Any]:
        if os.path.exists(PRESET_PATH):
            try:
                with open(PRESET_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"skins": {}, "prismatic": {}, "unusual": {}, "kinetic": {}, "global_items": {}}

    def save_preset(self):
        with open(PRESET_PATH, "w", encoding="utf-8") as f:
            json.dump(self.preset, f, indent=2, ensure_ascii=False)

    def find_hero(self, query: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        query = query.lower().strip()
        if not query:
            return None, None

        if query in self.heroes:
            return query, self.heroes[query]

        clean_q = query.replace("npc_dota_hero_", "").replace(" ", "_")
        for hname, hdata in self.heroes.items():
            h_clean = hname.replace("npc_dota_hero_", "")
            disp = hdata.get("display_name", "").lower()
            if clean_q == h_clean or clean_q in h_clean or query in disp:
                return hname, hdata
        return None, None

    def list_heroes(self, filter_query: Optional[str] = None):
        print("=" * 60)
        print("          DOTA 2 HERO CATALOG - MORPH SKINCHANGER")
        print("=" * 60)
        count = 0
        for hname, hdata in sorted(self.heroes.items(), key=lambda x: x[1].get("display_name", "")):
            disp = hdata.get("display_name", hname)
            clean_id = hname.replace("npc_dota_hero_", "")
            if filter_query and filter_query.lower() not in clean_id.lower() and filter_query.lower() not in disp.lower():
                continue
            bundles = len(hdata.get("bundles", []))
            slots = len(hdata.get("available_skins", {}))
            print(f" - {disp:<25} ({clean_id:<22}) | Sets: {bundles:<2} | Slots: {slots}")
            count += 1
        print("-" * 60)
        print(f"Total heroes listed: {count}")

    def show_hero(self, query: str):
        hname, hdata = self.find_hero(query)
        if not hname:
            print(f"[Error] Hero '{query}' not found in catalog.")
            return

        disp = hdata.get("display_name", hname)
        print("=" * 70)
        print(f" Hero: {disp} [{hname}]")
        print("=" * 70)

        # Bundles / Sets
        bundles = hdata.get("bundles", [])
        print(f"\n[AVAILABLE SETS / BUNDLES] ({len(bundles)} total):")
        for b in sorted(bundles, key=lambda x: x.get("rarity", "")):
            name = b.get("name", "Unknown").replace("", "").strip()
            bid = b.get("id")
            rarity = b.get("rarity", "common").upper()
            items_count = len(b.get("items", []))
            print(f"  [{bid:>5}] {name:<35} | {rarity:<10} | {items_count} items")

        # Slots
        avail_skins = hdata.get("available_skins", {})
        print(f"\n[SLOTS & COSMETICS] ({len(avail_skins)} slots):")
        for slot, items in avail_skins.items():
            print(f"  Slot '{slot}': {len(items)} items available")
            for it in items[:6]:
                it_id = it.get("id")
                it_name = it.get("name", "").replace("", "").strip()
                rarity = it.get("rarity", "").capitalize()
                print(f"    - [{it_id:>5}] {it_name:<35} ({rarity})")
            if len(items) > 6:
                print(f"    ... and {len(items) - 6} more")

    def show_current_preset(self):
        print("=" * 70)
        print("                 CURRENT ACTIVE PRESET")
        print("=" * 70)
        skins = self.preset.get("skins", {})
        unusual = self.preset.get("unusual", {})
        prismatic = self.preset.get("prismatic", {})

        if not skins:
            print("Preset is currently empty.")
            return

        for hname, slots in skins.items():
            h_info = self.heroes.get(hname, {})
            disp = h_info.get("display_name", hname)
            print(f"\nHero: {disp} ({hname})")
            for slot, val in slots.items():
                item_id = val.get("id") if isinstance(val, dict) else val
                style = val.get("style") if isinstance(val, dict) else None
                # resolve item name
                item_name = item_id
                for s_items in h_info.get("available_skins", {}).values():
                    for it in s_items:
                        if str(it.get("id")) == str(item_id):
                            item_name = it.get("name", "").replace("", "").strip()
                            break
                style_str = f" [Style {style}]" if style is not None else ""
                print(f"  - Slot {slot:<22}: [{item_id}] {item_name}{style_str}")

            if hname in unusual:
                eff = unusual[hname]
                eff_name = eff
                for k, info in ETHEREAL_GEMS.items():
                    if info["path"] == eff:
                        eff_name = f"{info['name']} ({k})"
                        break
                print(f"  * Bugged Ethereal Gem : {eff_name}")

            if hname in prismatic:
                prism = prismatic[hname]
                print(f"  * Prismatic Gem Color : {prism}")
        print("=" * 70)

    def equip_set(self, hero_query: str, set_query: str):
        hname, hdata = self.find_hero(hero_query)
        if not hname:
            print(f"[Error] Hero '{hero_query}' not found.")
            return

        bundles = hdata.get("bundles", [])
        chosen_bundle = None
        for b in bundles:
            if str(b.get("id")) == set_query or set_query.lower() in b.get("name", "").lower():
                chosen_bundle = b
                break

        if not chosen_bundle:
            print(f"[Error] Set '{set_query}' not found for hero {hdata.get('display_name')}.")
            print("Available sets:")
            for b in bundles:
                print(f"  - [{b.get('id')}] {b.get('name')}")
            return

        b_name = chosen_bundle.get("name", "").replace("", "").strip()
        b_items = chosen_bundle.get("items", [])
        if "skins" not in self.preset:
            self.preset["skins"] = {}
        if hname not in self.preset["skins"]:
            self.preset["skins"][hname] = {}

        # Reset existing slots for this hero
        self.preset["skins"][hname] = {}

        for it in b_items:
            slot = it.get("slot")
            it_id = str(it.get("id"))
            if slot:
                self.preset["skins"][hname][slot] = it_id

        # Special handling for Arcanas that map to hero_base
        if "arcana" in chosen_bundle.get("rarity", "").lower() or "Arcana" in b_name:
            if hname == "npc_dota_hero_terrorblade":
                self.preset["skins"][hname]["hero_base"] = "5957"
                self.preset["skins"][hname]["head"] = "37161"
            elif hname == "npc_dota_hero_queenofpain":
                self.preset["skins"][hname]["back"] = "12930"
                self.preset["skins"][hname]["weapon"] = "13770"
                self.preset["skins"][hname]["head"] = "13769"
                self.preset["skins"][hname]["shoulder"] = "13768"

        self.save_preset()
        print(f"[Success] Equipped full set '{b_name}' ({len(b_items)} items) on {hdata.get('display_name')}!")

    def equip_slot_item(self, hero_query: str, slot: str, item_query: str):
        hname, hdata = self.find_hero(hero_query)
        if not hname:
            print(f"[Error] Hero '{hero_query}' not found.")
            return

        avail = hdata.get("available_skins", {}).get(slot, [])
        chosen_item = None
        for it in avail:
            if str(it.get("id")) == item_query or item_query.lower() in it.get("name", "").lower():
                chosen_item = it
                break

        if not chosen_item and item_query.isdigit():
            chosen_item = {"id": item_query, "name": f"Item {item_query}"}

        if not chosen_item:
            print(f"[Error] Item '{item_query}' not found for slot '{slot}'.")
            return

        it_id = str(chosen_item["id"])
        it_name = chosen_item.get("name", it_id).replace("", "").strip()

        if "skins" not in self.preset:
            self.preset["skins"] = {}
        if hname not in self.preset["skins"]:
            self.preset["skins"][hname] = {}

        self.preset["skins"][hname][slot] = it_id
        self.save_preset()
        print(f"[Success] Set {slot} = [{it_id}] {it_name} on {hdata.get('display_name')}!")

    def set_ethereal(self, hero_query: str, effect_key: str):
        hname, hdata = self.find_hero(hero_query)
        if not hname:
            print(f"[Error] Hero '{hero_query}' not found.")
            return

        effect_path = None
        effect_name = None
        key = effect_key.lower().strip()
        if key in ETHEREAL_GEMS:
            effect_path = ETHEREAL_GEMS[key]["path"]
            effect_name = ETHEREAL_GEMS[key]["name"]
        else:
            for k, info in ETHEREAL_GEMS.items():
                if key in k or key in info["name"].lower():
                    effect_path = info["path"]
                    effect_name = info["name"]
                    break

        if not effect_path:
            print(f"[Error] Ethereal effect '{effect_key}' not recognized.")
            print("Available effects:")
            for k, info in ETHEREAL_GEMS.items():
                print(f" - {k:<20}: {info['name']}")
            return

        if "unusual" not in self.preset:
            self.preset["unusual"] = {}
        self.preset["unusual"][hname] = effect_path
        self.save_preset()
        print(f"[Success] Added Bugged Ethereal Gem '{effect_name}' to {hdata.get('display_name')}!")

    def clear_ethereal(self, hero_query: str):
        hname, hdata = self.find_hero(hero_query)
        if not hname:
            return
        if "unusual" in self.preset and hname in self.preset["unusual"]:
            del self.preset["unusual"][hname]
            self.save_preset()
            print(f"[Success] Removed Ethereal Gem from {hdata.get('display_name')}.")

    def set_prismatic(self, hero_query: str, color_query: str):
        hname, hdata = self.find_hero(hero_query)
        if not hname:
            print(f"[Error] Hero '{hero_query}' not found.")
            return

        cq = color_query.lower().strip()
        color_entry = None
        if cq in PRISMATIC_COLORS:
            color_entry = PRISMATIC_COLORS[cq]
        else:
            for k, info in PRISMATIC_COLORS.items():
                if cq in k or cq in info["name"].lower():
                    color_entry = info
                    break

        if not color_entry:
            hex_str = cq.lstrip("#")
            if len(hex_str) == 6:
                try:
                    r, g, b = int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)
                    color_entry = {"name": f"Custom (#{hex_str.upper()})", "hex": f"#{hex_str.upper()}", "rgb": [r, g, b]}
                except ValueError:
                    pass

        if not color_entry:
            print(f"[Error] Prismatic color '{color_query}' not recognized.")
            print("Available colors:")
            for k, info in PRISMATIC_COLORS.items():
                print(f" - {k:<20}: {info['name']} ({info['hex']})")
            return

        if "prismatic" not in self.preset:
            self.preset["prismatic"] = {}
        self.preset["prismatic"][hname] = color_entry
        self.save_preset()
        print(f"[Success] Set Prismatic Gem '{color_entry['name']}' ({color_entry['hex']}) on {hdata.get('display_name')}!")

    def clear_prismatic(self, hero_query: str):
        hname, hdata = self.find_hero(hero_query)
        if not hname:
            return
        if "prismatic" in self.preset and hname in self.preset["prismatic"]:
            del self.preset["prismatic"][hname]
            self.save_preset()
            print(f"[Success] Removed Prismatic Gem from {hdata.get('display_name')}.")

    def build_and_install(self):
        print("=" * 60)
        print("          BUILDING & INSTALLING MORPH VPK")
        print("=" * 60)
        dota_vpk_path = os.path.join(DEFAULT_DOTA_PATH, "game", "dota", "pak01_dir.vpk")
        if not os.path.exists(dota_vpk_path):
            print(f"[Error] Dota VPK not found at: {dota_vpk_path}")
            return False

        print("[1/3] Reading Valve items_game.txt...")
        dota_archive = vpk.open(dota_vpk_path)
        raw_text = dota_archive["scripts/items/items_game.txt"].read().decode('utf-8', errors='ignore')

        print("[2/3] Compiling custom VPK archive with FastVpkBuilder...")
        builder = FastVpkBuilder(raw_text, self.catalog)
        os.makedirs(os.path.dirname(OUTPUT_VPK_PATH), exist_ok=True)
        success = builder.build_custom_vpk(self.preset, OUTPUT_VPK_PATH)
        if not success or not os.path.exists(OUTPUT_VPK_PATH):
            print("[Error] VPK build failed.")
            return False

        vpk_size = os.path.getsize(OUTPUT_VPK_PATH) / (1024 * 1024)
        print(f"[Success] VPK created: {OUTPUT_VPK_PATH} ({vpk_size:.2f} MB)")

        print("[3/3] Installing into game with SkinChangerCore...")
        if not os.path.exists(CORE_EXE_PATH):
            print(f"[Error] SkinChangerCore.exe not found at {CORE_EXE_PATH}")
            return False

        cmd = [CORE_EXE_PATH, "--install", OUTPUT_VPK_PATH]
        res = subprocess.run(cmd, capture_output=True, text=True)
        print(res.stdout)
        if res.returncode == 0:
            print("[SUCCESS] All cosmetics and bugged gems successfully installed!")
            print("Launch Dota 2 and enjoy!")
            return True
        else:
            print(f"[Error] SkinChangerCore exited with code {res.returncode}: {res.stderr}")
            return False


def interactive_mode(tool: MorphCatalogTool):
    while True:
        print("\n" + "=" * 50)
        print("        MORPH DOTA 2 SKINCHANGER TOOL")
        print("=" * 50)
        print(" [1] Посмотреть текущий пресет")
        print(" [2] Надеть ПОЛНЫЙ СЕТ на героя (1 клик)")
        print(" [3] Настроить отдельный предмет по слоту")
        print(" [4] Добавить БАГНУТЫЙ ГЕМ (Trail of Burning Doom, etc.)")
        print(" [5] Убрать багнутый гем с героя")
        print(" [6] Установить ПРИЗМАТИЧЕСКИЙ ГЕМ (Rubiline, Blossom Red, etc.)")
        print(" [7] СОБРАТЬ И УСТАНОВИТЬ В ДОТУ")
        print(" [8] Найти героя / список сетов")
        print(" [0] Выход")
        print("-" * 50)
        choice = input("Выберите действие [0-8]: ").strip()

        if choice == "1":
            tool.show_current_preset()
        elif choice == "2":
            h = input("Введите имя героя (например, pudge, qop, terrorblade): ").strip()
            tool.show_hero(h)
            s = input("Введите ID сета или название: ").strip()
            tool.equip_set(h, s)
        elif choice == "3":
            h = input("Введите имя героя: ").strip()
            slot = input("Введите слот (weapon, head, back, shoulder, etc.): ").strip()
            item = input("Введите ID предмета или название: ").strip()
            tool.equip_slot_item(h, slot, item)
        elif choice == "4":
            h = input("Введите имя героя: ").strip()
            print("Доступные багнутые гемы:")
            for k, info in ETHEREAL_GEMS.items():
                print(f"  - {k:<20}: {info['name']}")
            eff = input("Выберите гем (например, burning_doom, rubiline_sheen): ").strip()
            tool.set_ethereal(h, eff)
        elif choice == "5":
            h = input("Введите имя героя: ").strip()
            tool.clear_ethereal(h)
        elif choice == "6":
            h = input("Введите имя героя: ").strip()
            print("Популярные призматические цвета:")
            for k in ["rubiline", "creators_light", "blossom_red", "ember_flame", "gold", "bright_purple", "cursed_black"]:
                info = PRISMATIC_COLORS.get(k, {})
                print(f"  - {k:<16}: {info.get('name')} ({info.get('hex')})")
            col = input("Введите цвет или HEX (#D11FA1): ").strip()
            tool.set_prismatic(h, col)
        elif choice == "7":
            tool.build_and_install()
        elif choice == "8":
            q = input("Поиск героя (или Enter для всех): ").strip()
            tool.list_heroes(q if q else None)
        elif choice == "0":
            break


def main():
    parser = argparse.ArgumentParser(description="Morph Dota 2 SkinChanger Automated Tool")
    subparsers = parser.add_subparsers(dest="command")

    # heroes
    p_heroes = subparsers.add_parser("heroes", help="List all heroes")
    p_heroes.add_argument("query", nargs="?", default=None, help="Optional hero name filter")

    # hero
    p_hero = subparsers.add_parser("hero", help="Show all sets and slots for a hero")
    p_hero.add_argument("query", help="Hero name or ID")

    # show
    subparsers.add_parser("show", help="Show current active preset")

    # equip-set
    p_set = subparsers.add_parser("equip-set", help="Equip full set on hero")
    p_set.add_argument("hero", help="Hero name")
    p_set.add_argument("set_name", help="Set name or ID")

    # equip-slot
    p_slot = subparsers.add_parser("equip-slot", help="Equip specific item on slot")
    p_slot.add_argument("hero", help="Hero name")
    p_slot.add_argument("slot", help="Slot name")
    p_slot.add_argument("item", help="Item name or ID")

    # ethereal
    p_eth = subparsers.add_parser("ethereal", help="Add bugged ethereal gem to hero")
    p_eth.add_argument("hero", help="Hero name")
    p_eth.add_argument("effect", help="Effect key (burning_doom, ethereal_flame, etc.)")

    # clear-ethereal
    p_cleareth = subparsers.add_parser("clear-ethereal", help="Remove ethereal gem from hero")
    p_cleareth.add_argument("hero", help="Hero name")

    # ethereals
    subparsers.add_parser("ethereals", help="List all available bugged ethereal gems")

    # prismatic
    p_prism = subparsers.add_parser("prismatic", help="Set prismatic gem color on hero")
    p_prism.add_argument("hero", help="Hero name")
    p_prism.add_argument("color", help="Color name (rubiline, blossom_red, etc.) or HEX (#D11FA1)")

    # clear-prismatic
    p_clearprism = subparsers.add_parser("clear-prismatic", help="Remove prismatic gem from hero")
    p_clearprism.add_argument("hero", help="Hero name")

    # prismatics
    subparsers.add_parser("prismatics", help="List all available prismatic gem colors")

    # build
    subparsers.add_parser("build", help="Compile and install VPK into Dota 2")

    # interactive
    subparsers.add_parser("interactive", help="Start interactive CLI wizard")

    args = parser.parse_args()
    tool = MorphCatalogTool()

    if not args.command:
        interactive_mode(tool)
        return

    if args.command == "heroes":
        tool.list_heroes(args.query)
    elif args.command == "hero":
        tool.show_hero(args.query)
    elif args.command == "show":
        tool.show_current_preset()
    elif args.command == "equip-set":
        tool.equip_set(args.hero, args.set_name)
    elif args.command == "equip-slot":
        tool.equip_slot_item(args.hero, args.slot, args.item)
    elif args.command == "ethereal":
        tool.set_ethereal(args.hero, args.effect)
    elif args.command == "clear-ethereal":
        tool.clear_ethereal(args.hero)
    elif args.command == "ethereals":
        print("=" * 60)
        print("          POPULAR BUGGED ETHEREAL GEMS")
        print("=" * 60)
        for k, info in ETHEREAL_GEMS.items():
            print(f"Key : {k}")
            print(f"Name: {info['name']}")
            print(f"Desc: {info['desc']}")
            print("-" * 60)
    elif args.command == "prismatic":
        tool.set_prismatic(args.hero, args.color)
    elif args.command == "clear-prismatic":
        tool.clear_prismatic(args.hero)
    elif args.command == "prismatics":
        print("=" * 60)
        print("          OFFICIAL PRISMATIC GEM COLORS")
        print("=" * 60)
        for k, info in PRISMATIC_COLORS.items():
            print(f" - {k:<20}: {info['name']:<24} {info['hex']} RGB{info['rgb']}")
        print("-" * 60)
    elif args.command == "build":
        tool.build_and_install()
    elif args.command == "interactive":
        interactive_mode(tool)


if __name__ == "__main__":
    main()
