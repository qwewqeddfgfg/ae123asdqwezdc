"""
items_catalog.py - Профессиональный парсер и генератор каталога Dota 2.
- Извлекает русские и английские токены локализации.
- Поддерживает полные бандлы (bundles) с распаковкой по слотам.
- Поддерживает закрытые и альтернативные стили предметов (styles).
- Индексирует базовые слоты героев и глобальные предметы (Roshan, Weather, Terrain, HUD, Towers, Creeps, Tormentor).
- Индексирует 820+ необычных эффектов (Unusual / Ethereal / Emblems) из attribute_controlled_attached_particles.
"""

import os
import json
import time
from typing import Dict, Any, List, Optional
import vdf
import vpk

DEFAULT_DOTA_PATH = r"E:\Steam\steamapps\common\dota 2 beta"

GLOBAL_DEFAULT_IDS = {
    "weather": "555",
    "terrain": "590",
    "roshan": "801",
    "hud": "587",
    "couriers": "595",
    "wards": "596",
    "music": "588",
    "announcer": "11173",
    "mega_kills": "586",
    "towers": "13781",
    "creeps": "13782"
}

class ItemsCatalog:
    def __init__(self, dota_root: Optional[str] = None):
        self.dota_root = dota_root or DEFAULT_DOTA_PATH
        self.raw_items_game: Dict[str, Any] = {}
        self.localization: Dict[str, str] = {}
        self.catalog: Dict[str, Any] = {
            "heroes": {},
            "global_items": {},
            "global_default_ids": GLOBAL_DEFAULT_IDS,
            "prismatic_colors": {},
            "unusual_effects": [],
            "stats": {}
        }

    def load_localization(self, archive: vpk.VPK) -> None:
        """Загружает токены локализации из pak01_dir.vpk."""
        tokens: Dict[str, str] = {}
        if "resource/localization/items_english.txt" in archive:
            try:
                en_data = archive.get_file("resource/localization/items_english.txt").read().decode("utf-8", errors="ignore")
                en_vdf = vdf.loads(en_data)
                tokens.update(en_vdf.get("lang", {}).get("Tokens", {}))
            except Exception as e:
                print(f"[Catalog] Ошибка items_english: {e}")

        if "resource/localization/items_russian.txt" in archive:
            try:
                ru_data = archive.get_file("resource/localization/items_russian.txt").read().decode("utf-8", errors="ignore")
                ru_vdf = vdf.loads(ru_data)
                tokens.update(ru_vdf.get("lang", {}).get("Tokens", {}))
            except Exception as e:
                print(f"[Catalog] Ошибка items_russian: {e}")

        self.localization = tokens

    def get_localized_name(self, token: Optional[str], default_name: str = "") -> str:
        if not token:
            return default_name
        key = token.lstrip("#")
        return self.localization.get(key, default_name or key)

    def load_from_vpk(self, vpk_path: Optional[str] = None) -> bool:
        if not vpk_path:
            vpk_path = os.path.join(self.dota_root, "game", "dota", "pak01_dir.vpk")

        if not os.path.exists(vpk_path):
            print(f"[Catalog] VPK файл не найден: {vpk_path}")
            return False

        archive = vpk.open(vpk_path)
        self.load_localization(archive)

        file_handle = archive.get_file("scripts/items/items_game.txt")
        raw_data = file_handle.read().decode("utf-8", errors="ignore")

        parsed = vdf.loads(raw_data, mapper=vdf.VDFDict, merge_duplicate_keys=False)
        self.raw_items_game = parsed.get("items_game", {})
        return True

    def build_catalog(self) -> Dict[str, Any]:
        items = self.raw_items_game.get("items", {})
        prefabs = self.raw_items_game.get("prefabs", {})

        heroes_dict: Dict[str, Dict[str, Any]] = {}
        global_dict: Dict[str, List[Dict[str, Any]]] = {
            "weather": [],
            "terrain": [],
            "wards": [],
            "couriers": [],
            "roshan": [],
            "hud": [],
            "music": [],
            "announcer": [],
            "towers": [],
            "creeps": []
        }

        items_by_internal_name: Dict[str, Dict[str, Any]] = {}

        # 1. Первый проход: собираем базовые предметы и индексируем по имени
        for item_id, item_data in items.items():
            internal_name = item_data.get("name", "")
            prefab = item_data.get("prefab", "")
            slot = item_data.get("item_slot") or prefabs.get(prefab, {}).get("item_slot", "misc")
            
            if internal_name:
                items_by_internal_name[internal_name] = {
                    "id": item_id,
                    "slot": slot,
                    "name": internal_name
                }

            used_by = item_data.get("used_by_heroes", {})
            if not isinstance(used_by, (dict, vdf.VDFDict)):
                continue

            for hero_name in used_by.keys():
                if not hero_name.startswith("npc_dota_hero_"):
                    continue

                if hero_name not in heroes_dict:
                    clean_name = hero_name.replace("npc_dota_hero_", "")
                    heroes_dict[hero_name] = {
                        "hero_name": hero_name,
                        "display_name": clean_name.replace("_", " ").title(),
                        "default_items": {},
                        "available_skins": {},
                        "bundles": []
                    }

                if prefab == "default_item":
                    def_slot = item_data.get("item_slot") or item_data.get("prefab_slot") or "weapon"
                    heroes_dict[hero_name]["default_items"][def_slot] = {
                        "id": item_id,
                        "name": internal_name,
                        "slot": def_slot,
                        "model_player": item_data.get("model_player", "")
                    }

        # 2. Второй проход: собираем носимые предметы, бандлы и стили
        total_cosmetics = 0
        total_bundles = 0

        for item_id, item_data in items.items():
            prefab = item_data.get("prefab", "")
            if prefab == "default_item":
                continue

            used_by = item_data.get("used_by_heroes", {})
            rarity = item_data.get("item_rarity", "common")
            internal_name = item_data.get("name", "")
            raw_item_name = item_data.get("item_name", internal_name)
            display_name = self.get_localized_name(raw_item_name, internal_name)
            model_player = item_data.get("model_player")
            image_inv = item_data.get("image_inventory", "")

            # Извлекаем стили
            styles_list = []
            styles_node = item_data.get("visuals", {}).get("styles") if isinstance(item_data.get("visuals"), (dict, vdf.VDFDict)) else None
            if not styles_node:
                styles_node = item_data.get("styles")

            if styles_node and isinstance(styles_node, (dict, vdf.VDFDict)):
                for style_idx, style_val in styles_node.items():
                    if isinstance(style_val, (dict, vdf.VDFDict)):
                        style_token = style_val.get("name", f"Style {style_idx}")
                        styles_list.append({
                            "index": style_idx,
                            "name": self.get_localized_name(style_token, f"Style {style_idx}"),
                            "skin": style_val.get("skin", style_idx)
                        })

            # Бандлы (Сеты)
            if prefab == "bundle":
                bundle_items_node = item_data.get("bundle", {})
                bundle_parts = []
                if isinstance(bundle_items_node, (dict, vdf.VDFDict)):
                    for part_name in bundle_items_node.keys():
                        part_info = items_by_internal_name.get(part_name)
                        if part_info:
                            part_item_data = items.get(part_info["id"], {})
                            bundle_parts.append({
                                "id": part_info["id"],
                                "name": self.get_localized_name(part_item_data.get("item_name"), part_name),
                                "slot": part_info["slot"],
                                "image": part_item_data.get("image_inventory", "")
                            })

                if isinstance(used_by, (dict, vdf.VDFDict)):
                    for hero_name in used_by.keys():
                        if hero_name in heroes_dict:
                            heroes_dict[hero_name]["bundles"].append({
                                "id": item_id,
                                "name": display_name,
                                "rarity": rarity,
                                "image": image_inv,
                                "items": bundle_parts
                            })
                            total_bundles += 1
                continue

            # Носимые скины
            if isinstance(used_by, (dict, vdf.VDFDict)) and used_by:
                for hero_name in used_by.keys():
                    if hero_name not in heroes_dict:
                        continue

                    slot = item_data.get("item_slot") or prefabs.get(prefab, {}).get("item_slot", "misc")
                    if slot not in heroes_dict[hero_name]["available_skins"]:
                        heroes_dict[hero_name]["available_skins"][slot] = []

                    heroes_dict[hero_name]["available_skins"][slot].append({
                        "id": item_id,
                        "name": display_name,
                        "internal_name": internal_name,
                        "slot": slot,
                        "rarity": rarity,
                        "image": image_inv,
                        "has_model": bool(model_player),
                        "has_visuals": "visuals" in item_data,
                        "styles": styles_list
                    })
                    total_cosmetics += 1

            # Глобальные предметы
            if prefab in ("courier", "ward", "roshan", "terrain", "hud_skin", "music_pack", "announcer", "weather"):
                cat_name = "couriers" if prefab == "courier" else \
                           "wards" if prefab == "ward" else \
                           "roshan" if prefab == "roshan" else \
                           "terrain" if prefab == "terrain" else \
                           "weather" if prefab == "weather" else \
                           "hud" if prefab == "hud_skin" else \
                           "music" if prefab == "music_pack" else \
                           "announcer" if prefab == "announcer" else "misc"
                if cat_name in global_dict:
                    global_dict[cat_name].append({
                        "id": item_id,
                        "name": display_name,
                        "internal_name": internal_name,
                        "rarity": rarity,
                        "image": image_inv,
                        "styles": styles_list
                    })

        # 3. Извлечение 820+ необычных эффектов (Unusual / Ethereal / Emblems)
        unusual_raw = self.raw_items_game.get("attribute_controlled_attached_particles", {})
        unusual_list = []
        for u_id, u_data in unusual_raw.items():
            system_path = u_data.get("system", "")
            if system_path:
                short_name = system_path.split("/")[-1].replace(".vpcf", "").replace("_", " ").title()
                unusual_list.append({
                    "id": u_id,
                    "name": short_name,
                    "system": system_path,
                    "attach_type": u_data.get("attach_type", "absorigin_follow")
                })

        # Призматические цвета
        prismatic_gems = {
            "Red": {"hex": "#D03D33", "rgb": [208, 61, 51]},
            "Rubiline": {"hex": "#D11FA5", "rgb": [209, 31, 165]},
            "Blossom Red": {"hex": "#D76092", "rgb": [215, 96, 146]},
            "Creators Light": {"hex": "#FBF5F0", "rgb": [251, 245, 240]},
            "Placid Blue": {"hex": "#94CAD0", "rgb": [148, 202, 208]},
            "Sea Green": {"hex": "#4AB78D", "rgb": [74, 183, 141]},
            "Champions Green": {"hex": "#539423", "rgb": [83, 148, 35]},
            "Midas Gold": {"hex": "#FFCA15", "rgb": [255, 202, 21]},
            "Dungeon Doom": {"hex": "#7B1FA2", "rgb": [123, 31, 162]},
            "Ember Flame": {"hex": "#FF8000", "rgb": [255, 128, 0]},
            "Cursed Black": {"hex": "#060606", "rgb": [6, 6, 6]},
            "Bright Purple": {"hex": "#8232ED", "rgb": [130, 50, 237]},
            "Deep Blue": {"hex": "#3D68C4", "rgb": [61, 104, 196]},
            "Crystalline Blue": {"hex": "#1A3D85", "rgb": [26, 61, 133]}
        }

        self.catalog = {
            "heroes": heroes_dict,
            "global_items": global_dict,
            "global_default_ids": GLOBAL_DEFAULT_IDS,
            "prismatic_colors": prismatic_gems,
            "unusual_effects": unusual_list,
            "stats": {
                "total_heroes": len(heroes_dict),
                "total_cosmetics": total_cosmetics,
                "total_bundles": total_bundles,
                "total_unusual_effects": len(unusual_list),
                "cached_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        }
        return self.catalog

    def save_cache(self, cache_path: str):
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(self.catalog, f, ensure_ascii=False, indent=2)

    def load_cache(self, cache_path: str) -> bool:
        if not os.path.exists(cache_path):
            return False
        with open(cache_path, "r", encoding="utf-8") as f:
            self.catalog = json.load(f)
        return True


if __name__ == "__main__":
    cat = ItemsCatalog()
    if cat.load_from_vpk():
        cat.build_catalog()
        cat.save_cache(os.path.join(os.path.dirname(__file__), "cache", "catalog.json"))
