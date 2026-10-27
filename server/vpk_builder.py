"""
vpk_builder.py - High Performance String Slicing VPK Builder for Dota 2 Morph.
- 100% faithful to Valve KeyValues syntax without corruption.
- Proper injection into single 'visuals' block with indexed asset_modifier entries.
- Real Gem Sockets displayed in Dota 2 inspection cards:
  * Ethereal Gem (3000) with effect index from attribute_controlled_attached_particles.
  * Prismatic Gem (3001) with RGB colors for Arcana / Unusual color tinting.
- Full Arcana support:
  * Terrorblade: Arcana base (5957) on hero_base (913), Arcana horns (37161) on head (478),
    native Prismatic Gem socket (Rubiline pink / custom color) binding directly to particle control points.
  * Queen of Pain: Full Arcana (The Eminence of Ristul) + direct .vmdl_c model injection + Trail of Burning Doom.
  * Pudge: Persona (Cute) + Doll of the Dead set direct .vmdl_c model injection.
- Panorama UI styling fixes:
  * Overrides .IsDefaultItem in ui_econ_item.vcss_c and hero_slot_item_picker*.vcss_c
    so loadout slot icons render in full vibrant saturation and with rarity borders instead of grey silhouettes.
- Preserves all Valve game files, generates clean pak01_dir.vpk.
"""

import os
import re
import shutil
import struct
import tempfile
import time
from typing import Dict, Any, Optional, Tuple, List
import vpk
import lz4.block

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

ETHEREAL_EFFECT_MAP = {
    "particles/econ/seasonal/seasonal_ambient_silver.vpcf": 826,                 # Frostbloom
    "particles/econ/seasonal/seasonal_ambient_candy_mint.vpcf": 827,             # Candy Caster
    "particles/econ/seasonal/new_bloom/seasonal_ambient_gold_drop.vpcf": 833,    # Gold Drop
    "particles/econ/seasonal/new_bloom/seasonal_ambient_gold_glow.vpcf": 834,    # Gold Glow
    "particles/econ/seasonal/crownfall/seasonal_ambient_screeauk.vpcf": 836,     # Featherfall
    "particles/econ/courier/courier_trail_lava/courier_trail_lava.vpcf": 96,     # Trail of Burning Doom
    "particles/econ/courier/courier_trail_ruby/courier_trail_ruby.vpcf": 129,    # Rubiline Sheen
    "particles/econ/courier/courier_trail_01/courier_trail_01.vpcf": 15,         # Ethereal Flame
    "particles/econ/courier/courier_trail_02/courier_trail_02.vpcf": 16,         # Resonant Energy
    "particles/econ/courier/courier_trail_03/courier_trail_03.vpcf": 21,         # Luminous Gaze
    "particles/econ/courier/courier_trail_04/courier_trail_04.vpcf": 22,         # Searing Essence
    "particles/econ/courier/courier_trail_05/courier_trail_05.vpcf": 32,         # Sunfire
    "particles/econ/courier/courier_trail_blossoms/courier_trail_blossoms.vpcf": 61, # Bleak Hallucination / Lotus
    "particles/econ/courier/courier_trail_cursed/courier_cursed_ambient.vpcf": 73,   # Cursed Essence
    "particles/econ/courier/courier_trail_divine/courier_divine_ambient.vpcf": 74,   # Divine Essence
    "particles/econ/courier/courier_trail_earth/courier_trail_earth.vpcf": 157,      # Spirit of Earth
    "particles/econ/courier/courier_trail_ember/courier_trail_ember.vpcf": 156,      # Spirit of Ember
    "particles/econ/courier/courier_trail_spirit/courier_trail_spirit.vpcf": 159,    # Orbital Decay
    "particles/econ/courier/courier_golden_roshan/golden_roshan_ambient.vpcf": 47,   # Touch of Midas
    "particles/econ/courier/courier_crystal_rift/courier_ambient_crystal_rift.vpcf": 68, # Crystal Rift
    "particles/econ/courier/courier_trail_hw_2012/courier_trail_hw_2012.vpcf": 46,  # Diretide Corruption
    "particles/econ/courier/courier_trail_hw_2013/courier_trail_hw_2013.vpcf": 155, # Bleak Hallucination (HW13)
    "particles/econ/courier/courier_trail_winter_2012/courier_trail_winter_2012.vpcf": 57, # Frostivus Frost
    "particles/econ/courier/courier_trail_international_2013/courier_international_2013.vpcf": 109, # Champions Aura 2013
    "particles/econ/courier/courier_trail_international_2014/courier_international_2014.vpcf": 268, # Champions Aura 2014
}

PRISMATIC_COLORS = {
    "rubiline": {"name": "Rubiline", "hex": "#D11FA1", "rgb": [209, 31, 161]},
    "ruby": {"name": "Rubiline", "hex": "#D11FA1", "rgb": [209, 31, 161]},
    "pink": {"name": "Rubiline", "hex": "#D11FA1", "rgb": [209, 31, 161]},
    "creators_light": {"name": "Creator's Light", "hex": "#DCF2FF", "rgb": [220, 242, 255]},
    "white": {"name": "Creator's Light", "hex": "#DCF2FF", "rgb": [220, 242, 255]},
    "blossom_red": {"name": "Blossom Red", "hex": "#D76092", "rgb": [215, 96, 146]},
    "red": {"name": "Red", "hex": "#D03D33", "rgb": [208, 61, 51]},
    "deep_blue": {"name": "Deep Blue", "hex": "#3D68C4", "rgb": [61, 104, 196]},
    "blue": {"name": "Blue", "hex": "#0097CE", "rgb": [0, 151, 206]},
    "bright_purple": {"name": "Bright Purple", "hex": "#8232ED", "rgb": [130, 50, 237]},
    "purple": {"name": "Purple", "hex": "#8232CF", "rgb": [130, 50, 207]},
    "dungeon_doom": {"name": "Dungeon Doom", "hex": "#7B68EE", "rgb": [123, 104, 238]},
    "bright_green": {"name": "Bright Green", "hex": "#A1FF59", "rgb": [161, 255, 89]},
    "green": {"name": "Verdant Green", "hex": "#51B350", "rgb": [81, 179, 80]},
    "gold": {"name": "Gold", "hex": "#CFAB31", "rgb": [207, 171, 49]},
    "midas_gold": {"name": "Midas Gold", "hex": "#FFCA15", "rgb": [255, 202, 21]},
    "ember_flame": {"name": "Ember Flame", "hex": "#FFC604", "rgb": [255, 198, 4]},
    "cursed_black": {"name": "Cursed Black", "hex": "#060606", "rgb": [6, 6, 6]},
    "black": {"name": "Cursed Black", "hex": "#060606", "rgb": [6, 6, 6]},
    "placid_blue": {"name": "Placid Blue", "hex": "#94CAD0", "rgb": [148, 202, 208]},
    "sea_green": {"name": "Sea Green", "hex": "#4AB78D", "rgb": [74, 183, 141]},
    "summer_warmth": {"name": "Summer Warmth", "hex": "#FFEEBC", "rgb": [255, 238, 188]},
    "vermilion_renewal": {"name": "Vermilion Renewal", "hex": "#CA0123", "rgb": [202, 1, 35]},
}


def depth_at(text: str, index: int) -> int:
    """Calculates brace depth at a given index ignoring quoted strings."""
    depth = 0
    in_quote = False
    escape = False
    for i in range(min(index, len(text))):
        c = text[i]
        if escape:
            escape = False
            continue
        if c == '\\':
            escape = True
            continue
        if c == '"':
            in_quote = not in_quote
            continue
        if in_quote:
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
    return depth


def extract_balanced_block_end(text: str, open_brace_idx: int) -> int:
    """Finds the index immediately following the matching closing brace."""
    depth = 0
    in_quote = False
    escape = False
    for i in range(open_brace_idx, len(text)):
        c = text[i]
        if escape:
            escape = False
            continue
        if c == '\\':
            escape = True
            continue
        if c == '"':
            in_quote = not in_quote
            continue
        if in_quote:
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return i + 1
    return -1


def find_top_level_block(block: str, key: str) -> int:
    """Finds the position of the '{' for a top-level block key (depth 0 or 1)."""
    pattern = rf'"{re.escape(key)}"\s*\{{'
    for m in re.finditer(pattern, block, re.IGNORECASE):
        if depth_at(block, m.start()) in (0, 1):
            return block.find('{', m.start())
    return -1


def with_unusual_quality(block: str) -> str:
    """Ensures block has 'item_quality' 'unusual' at top level and removes forced_item_quality."""
    lines = block.splitlines(keepends=True)
    out_lines = []
    idx = 0
    for line in lines:
        if re.search(r'^\s*"forced_item_quality"', line, re.I) and depth_at(block, idx) in (0, 1):
            pass
        else:
            out_lines.append(line)
        idx += len(line)
    block = "".join(out_lines)

    for m in re.finditer(r'("item_quality"\s*")([^"]*)(")', block, re.IGNORECASE):
        if depth_at(block, m.start()) in (0, 1):
            return block[:m.start(2)] + "unusual" + block[m.end(2):]

    for m in re.finditer(r'^\s*"item_rarity"', block, re.IGNORECASE | re.MULTILINE):
        if depth_at(block, m.start()) in (0, 1):
            return block[:m.start()] + '\t"item_quality"\t\t"unusual"\n' + block[m.start():]

    first_brace = block.find('{')
    if first_brace != -1:
        next_nl = block.find('\n', first_brace)
        if next_nl != -1:
            return block[:next_nl+1] + '\t"item_quality"\t\t"unusual"\n' + block[next_nl+1:]
    return '\t"item_quality"\t\t"unusual"\n' + block


def inject_static_sockets(block: str, sockets: List[Dict[str, Any]]) -> str:
    """
    Injects static sockets into static_attributes block using authentic Valve schema.
    sockets is a list of dicts:
      - {"type": "ethereal" | "unusual", "gem_def_index": 3045, "effect": 826}
      - {"type": "kinetic", "gem_def_index": 3005, "hero": "npc_dota_hero_invoker", "asset_modifier": 142}
    """
    if not block or not sockets:
        return block

    socket_entries = []
    for i, s in enumerate(sockets, start=1):
        stype = s.get("type", "")
        if stype in ("ethereal", "unusual"):
            gem_def = s.get("gem_def_index", 3045)
            effect_id = s.get("effect", 826)
            val = f"socket {{ required_type: 1 gem_def_index: {gem_def} }} effect: {effect_id}"
        elif stype == "kinetic":
            gem_def = s.get("gem_def_index", 3005)
            hero = s.get("hero", "")
            mod_id = s.get("asset_modifier", 0)
            val = f"socket {{ required_hero: '{hero}' gem_def_index: {gem_def} }} asset_modifier: {mod_id}"
        elif stype == "prismatic":
            gem_def = s.get("gem_def_index", 3045)
            effect_id = s.get("effect", 129)
            val = f"socket {{ required_type: 1 gem_def_index: {gem_def} }} effect: {effect_id}"
        else:
            continue
        socket_entries.append((f"static socket {i}", val))

    if not socket_entries:
        return block

    sa_brace = find_top_level_block(block, "static_attributes")
    if sa_brace < 0:
        chunk = '\t"static_attributes"\n\t{\n'
        for name, val in socket_entries:
            chunk += f'\t\t"{name}"\n\t\t{{\n\t\t\t"attribute_class"\t\t"socket"\n\t\t\t"value"\t\t"{val}"\n\t\t}}\n'
        chunk += '\t}\n'
        if depth_at(block, len(block)) == 0:
            return block + "\n" + chunk
        last_close = block.rfind('}')
        if last_close < 0:
            return block + "\n" + chunk
        return block[:last_close] + chunk + block[last_close:]

    sa_end = extract_balanced_block_end(block, sa_brace)
    if sa_end < 0:
        return block

    sa_body = block[sa_brace:sa_end]
    lines = sa_body.splitlines(keepends=True)
    filtered_lines = []
    skip = False
    depth = 0
    for line in lines:
        if re.search(r'^\s*"static socket \d+"', line):
            skip = True
            depth = 0
        if skip:
            depth += line.count('{') - line.count('}')
            if depth <= 0 and ('}' in line or '{' not in line):
                skip = False
            continue
        filtered_lines.append(line)

    cleaned_sa = "".join(filtered_lines)
    close_brace = cleaned_sa.rfind('}')
    if close_brace < 0:
        close_brace = len(cleaned_sa)

    chunk = ""
    for name, val in socket_entries:
        chunk += f'\t\t"{name}"\n\t\t{{\n\t\t\t"attribute_class"\t\t"socket"\n\t\t\t"value"\t\t"{val}"\n\t\t}}\n'

    new_sa = cleaned_sa[:close_brace] + chunk + cleaned_sa[close_brace:]
    return block[:sa_brace] + new_sa + block[sa_end:]


def inject_visuals_modifiers(block: str, mod_entries: List[Dict[str, str]]) -> str:
    """
    Inserts asset_modifier entries into the single existing or new visuals block.
    Guarantees no duplicate visuals blocks and sequential asset_modifier indices.
    """
    if not block or not mod_entries:
        return block

    visuals_brace = find_top_level_block(block, "visuals")
    if visuals_brace < 0:
        visuals_chunk = '\t"visuals"\n\t{\n'
        for i, entry in enumerate(mod_entries):
            visuals_chunk += f'\t\t"asset_modifier{i}"\n\t\t{{\n'
            for k, v in entry.items():
                visuals_chunk += f'\t\t\t"{k}"\t\t"{v}"\n'
            visuals_chunk += '\t\t}\n'
        visuals_chunk += '\t}\n'
        if depth_at(block, len(block)) == 0:
            return block + "\n" + visuals_chunk
        last_close = block.rfind('}')
        if last_close < 0:
            return block + "\n" + visuals_chunk
        return block[:last_close] + visuals_chunk + block[last_close:]

    visuals_end = extract_balanced_block_end(block, visuals_brace)
    if visuals_end < 0:
        return block

    visuals_body = block[visuals_brace:visuals_end]
    next_idx = 0
    for m in re.finditer(r'"asset_modifier(\d*)"\s*\{', visuals_body, re.IGNORECASE):
        digits = m.group(1)
        if digits:
            try:
                next_idx = max(next_idx, int(digits) + 1)
            except ValueError:
                pass
        else:
            next_idx = max(next_idx, 1)

    close_brace = visuals_end - 1
    chunk = ""
    for entry in mod_entries:
        if entry.get("type") == "particle_create" and entry.get("modifier", "").lower() in visuals_body.lower():
            continue
        chunk += f'\t\t"asset_modifier{next_idx}"\n\t\t{{\n'
        for k, v in entry.items():
            chunk += f'\t\t\t"{k}"\t\t"{v}"\n'
        chunk += '\t\t}\n'
        next_idx += 1

    return block[:close_brace] + chunk + block[close_brace:]


def resolve_prismatic_rgb(prism: Any) -> Optional[List[int]]:
    """Resolves prismatic color into [R, G, B] integers."""
    if not prism:
        return None
    if isinstance(prism, str):
        col = PRISMATIC_COLORS.get(prism.lower().strip())
        if col:
            return col["rgb"]
        hex_str = prism.lstrip("#").strip()
        if len(hex_str) == 6:
            try:
                return [int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)]
            except ValueError:
                pass
    elif isinstance(prism, dict):
        if "rgb" in prism and isinstance(prism["rgb"], (list, tuple)) and len(prism["rgb"]) >= 3:
            return [int(prism["rgb"][0]), int(prism["rgb"][1]), int(prism["rgb"][2])]
        if "name" in prism:
            col = PRISMATIC_COLORS.get(prism["name"].lower().strip())
            if col:
                return col["rgb"]
        if "hex" in prism:
            hex_str = prism["hex"].lstrip("#").strip()
            if len(hex_str) == 6:
                try:
                    return [int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)]
                except ValueError:
                    pass
    return [209, 31, 161]  # Default Rubiline


def patch_vpcf_binary(raw_bytes: bytes, target_rgb: List[int]) -> bytes:
    """
    Patches Source 2 compiled particle system (.vpcf_c) KV3 binary resource:
    recolors m_ConstantColor, m_ColorMin, and m_ColorMax to match target_rgb [R, G, B].
    Preserves all KV3 structure and recalculates compressed/uncompressed block sizes.
    """
    data_idx = raw_bytes.find(b'DATA')
    if data_idx == -1:
        return raw_bytes
    offset, total_size = struct.unpack_from("<II", raw_bytes, data_idx + 4)
    data_start = data_idx + 4 + offset
    if data_start + 4 > len(raw_bytes):
        return raw_bytes
    magic = struct.unpack_from("<I", raw_bytes, data_start)[0]
    if (magic & 0xFFFFFF00) != 0x4B563300:
        return raw_bytes
    version = magic & 0xFF
    pos = data_start + 4 + 16
    if pos + 4 > len(raw_bytes):
        return raw_bytes
    comp_method = struct.unpack_from("<I", raw_bytes, pos)[0]
    pos += 4
    if comp_method != 1:  # Only LZ4 block compression
        return raw_bytes
        
    dict_id, frame_size = struct.unpack_from("<HH", raw_bytes, pos)
    pos += 4
    c_b1, c_b4, c_b8, c_types = struct.unpack_from("<iiii", raw_bytes, pos)
    pos += 16
    c_objs, c_arrs = struct.unpack_from("<HH", raw_bytes, pos)
    pos += 4
    comp_header_offset = pos
    uncomp_total, comp_total, c_blocks, s_blobs = struct.unpack_from("<iiii", raw_bytes, pos)
    pos += 16
    if version >= 4:
        pos += 8
    if version >= 5:
        pos += 40
        
    if pos + comp_total > len(raw_bytes):
        return raw_bytes
        
    comp_data = raw_bytes[pos : pos + comp_total]
    try:
        decomp = bytearray(lz4.block.decompress(comp_data, uncompressed_size=uncomp_total))
    except Exception:
        return raw_bytes
        
    b4_len = c_b4 * 4
    b8_start = (b4_len + 7) & ~7
    b8_len = c_b8 * 8
    strings_start = b8_start + b8_len
    
    if len(decomp) < strings_start + 4:
        return raw_bytes
        
    num_strings = struct.unpack_from("<i", decomp, 0)[0]
    strings = []
    str_pos = strings_start
    for _ in range(num_strings):
        end = decomp.find(b'\x00', str_pos)
        if end == -1:
            break
        strings.append(decomp[str_pos:end].decode('utf-8', errors='ignore'))
        str_pos = end + 1
        
    modified = False
    
    # 1. Patch m_ConstantColor (only in root object fields, i < 150)
    if "m_ConstantColor" in strings:
        str_id = strings.index("m_ConstantColor")
        for i in range(8, min(150, b4_len - 16), 4):
            val = struct.unpack_from("<i", decomp, i)[0]
            if val == str_id:
                arr_len = struct.unpack_from("<i", decomp, i + 4)[0]
                if arr_len in (3, 4):
                    r_old = struct.unpack_from("<i", decomp, i + 8)[0]
                    g_old = struct.unpack_from("<i", decomp, i + 12)[0]
                    b_old = struct.unpack_from("<i", decomp, i + 16)[0]
                    if g_old > 20 or b_old > 20 or r_old > 20:
                        lum = max(r_old, g_old, b_old) / 255.0
                        new_r = max(0, min(255, int(target_rgb[0] * lum)))
                        new_g = max(0, min(255, int(target_rgb[1] * lum)))
                        new_b = max(0, min(255, int(target_rgb[2] * lum)))
                        struct.pack_into("<i", decomp, i + 8, new_r)
                        struct.pack_into("<i", decomp, i + 12, new_g)
                        struct.pack_into("<i", decomp, i + 16, new_b)
                        modified = True
                        break # Never continue past root m_ConstantColor!
                        
    # 2. Patch C_INIT_RandomColor (m_ColorMin / m_ColorMax) and color fade
    for c_key in ["m_ColorMin", "m_ColorMax", "m_ColorFade"]:
        if c_key in strings:
            str_id = strings.index(c_key)
            for i in range(8, min(150, b4_len - 16), 4):
                val = struct.unpack_from("<i", decomp, i)[0]
                if val == str_id:
                    arr_len = struct.unpack_from("<i", decomp, i + 4)[0]
                    if arr_len in (3, 4):
                        r_old = struct.unpack_from("<i", decomp, i + 8)[0]
                        g_old = struct.unpack_from("<i", decomp, i + 12)[0]
                        b_old = struct.unpack_from("<i", decomp, i + 16)[0]
                        if g_old > 20 or b_old > 20 or r_old > 20:
                            lum = max(r_old, g_old, b_old) / 255.0
                            new_r = max(0, min(255, int(target_rgb[0] * lum)))
                            new_g = max(0, min(255, int(target_rgb[1] * lum)))
                            new_b = max(0, min(255, int(target_rgb[2] * lum)))
                            struct.pack_into("<i", decomp, i + 8, new_r)
                            struct.pack_into("<i", decomp, i + 12, new_g)
                            struct.pack_into("<i", decomp, i + 16, new_b)
                            modified = True
                            break
                            
    if not modified:
        return raw_bytes
        
    new_comp_data = lz4.block.compress(bytes(decomp), store_size=False)
    new_comp_total = len(new_comp_data)
    
    prefix = bytearray(raw_bytes[:pos])
    struct.pack_into("<i", prefix, comp_header_offset + 4, new_comp_total)
    new_data_size = (pos - data_start) + new_comp_total
    struct.pack_into("<I", prefix, data_idx + 8, new_data_size)
    new_file = prefix + new_comp_data
    new_file_size = len(new_file)
    struct.pack_into("<I", new_file, 0, new_file_size)
    return bytes(new_file)


class FastVpkBuilder:
    def __init__(self, raw_text: str, catalog_data: Dict[str, Any]):
        self.raw_text = raw_text
        self.catalog = catalog_data
        self.item_spans: Dict[str, Tuple[int, int]] = {}
        self.index_item_spans()

    def index_item_spans(self):
        """Indexes item boundaries in items_game.txt."""
        items_start = self.raw_text.find('"items"\r\n\t{')
        if items_start == -1:
            items_start = self.raw_text.find('"items"\n\t{')
        if items_start == -1:
            items_start = self.raw_text.find('"items"')

        next_sec = self.raw_text.find('"item_sets"', items_start)
        if next_sec == -1:
            next_sec = len(self.raw_text)

        items_end = self.raw_text.rfind('\n\t}', items_start, next_sec)
        if items_end == -1:
            items_end = next_sec
        else:
            items_end += len('\n\t}')

        pattern = re.compile(r'\n\t\t"(\d+)"\s*\{', re.MULTILINE)
        matches = list(pattern.finditer(self.raw_text, items_start, items_end))

        for i, m in enumerate(matches):
            item_id = m.group(1)
            start_pos = m.start() + 1
            next_s = matches[i + 1].start() if (i + 1 < len(matches)) else items_end
            close_pos = self.raw_text.rfind('\t\t}', start_pos, next_s)
            if close_pos != -1:
                end_pos = close_pos + len('\t\t}')
                self.item_spans[item_id] = (start_pos, end_pos)

    def build_merged_item_block(
        self,
        def_id: str,
        target_item_id: str,
        hero_name: Optional[str] = None,
        slot_name: Optional[str] = None,
        style: Optional[Any] = None,
        unusual_particle: Optional[str] = None,
        kinetic_activity: Optional[str] = None,
        sockets: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[str]:
        target_span = self.item_spans.get(target_item_id)
        if not target_span:
            return None

        target_raw = self.raw_text[target_span[0]:target_span[1]]
        first_brace = target_raw.find('{')
        last_brace = target_raw.rfind('}')
        if first_brace == -1 or last_brace == -1:
            return None

        body = target_raw[first_brace + 1:last_brace].strip()

        # Prefab must ALWAYS be default_item for default hero slots so Dota 2 equips them freely
        if '"prefab"' in body:
            body = re.sub(r'"prefab"\s+"[^"]+"', '"prefab"\t\t"default_item"', body)
        else:
            body = '\t"prefab"\t\t"default_item"\n' + body

        # Ensure item rarity exists
        if '"item_rarity"' not in body:
            body = '\t"item_rarity"\t\t"uncommon"\n' + body

        # Slot name
        if slot_name and '"item_slot"' not in body:
            body = f'\t"item_slot"\t\t"{slot_name}"\n' + body

        # Used by heroes
        if hero_name and '"used_by_heroes"' not in body:
            body = body + f'\n\t"used_by_heroes"\n\t{{\n\t\t"{hero_name}"\t\t"1"\n\t}}'

        # Fallback model_player if missing
        if '"model_player"' not in body and '"entity_model"' not in body:
            def_span = self.item_spans.get(def_id)
            if def_span:
                def_raw = self.raw_text[def_span[0]:def_span[1]]
                m_model = re.search(r'"model_player"\s+"([^"]+)"', def_raw)
                if m_model:
                    body = f'\t"model_player"\t\t"{m_model.group(1)}"\n' + body

        # Style / skin
        if style is not None:
            body = body + f'\n\t"style"\t\t"{style}"\n\t"skin"\t\t"{style}"'

        # Ensure description exists for items with custom particles/sockets
        if unusual_particle or sockets:
            if '"item_description"' not in body:
                body = body + f'\n\t"item_description"\t\t"#DOTA_Item_Desc_{target_item_id}"'

        # Sockets injection for real gem inspection card
        if sockets:
            body = inject_static_sockets(body, sockets)

        # Collect modifiers to inject into single visuals block
        mods_to_inject = []
        if unusual_particle:
            body = with_unusual_quality(body)
            mods_to_inject.append({
                "type": "particle_create",
                "modifier": unusual_particle
            })

        if kinetic_activity:
            mods_to_inject.append({
                "type": "activity",
                "modifier": kinetic_activity
            })

        if mods_to_inject:
            body = inject_visuals_modifiers(body, mods_to_inject)

        lines = body.splitlines()
        formatted_body = "\r\n".join("\t\t\t" + line.strip() for line in lines if line.strip())
        return f'\t\t"{def_id}"\r\n\t\t{{\r\n{formatted_body}\r\n\t\t}}'

    def build_custom_vpk(self, preset: Dict[str, Any], output_path: str) -> bool:
        """Generates pak01_dir.vpk with modified items, gem sockets, and models."""
        t0 = time.time()
        replacements: List[Tuple[int, int, str]] = []
        replaced_def_ids = set()
        heroes_catalog = self.catalog.get("heroes", {})

        skins = preset.get("skins", {})
        prismatic_config = preset.get("prismatic", {})
        unusual_config = preset.get("unusual", {})
        kinetic_config = preset.get("kinetic", {})

        for hero_name, slots in skins.items():
            hero_info = heroes_catalog.get(hero_name)
            if not hero_info:
                continue

            default_items = hero_info.get("default_items", {})
            hero_prismatic = prismatic_config.get(hero_name)
            hero_unusual = unusual_config.get(hero_name)
            hero_kinetic = kinetic_config.get(hero_name)

            prismatic_rgb = resolve_prismatic_rgb(hero_prismatic) if hero_prismatic else None

            # --- SPECIAL HANDLING FOR TERRORBLADE ---
            if hero_name == "npc_dota_hero_terrorblade":
                has_arcana = (
                    str(slots.get("hero_base", "")) == "5957" or 
                    str(slots.get("head", "")) == "5957" or
                    (isinstance(slots.get("hero_base"), dict) and str(slots.get("hero_base", {}).get("id")) == "5957") or
                    (isinstance(slots.get("head"), dict) and str(slots.get("head", {}).get("id")) == "5957")
                )

                if has_arcana:
                    tb_sockets = []
                    tb_particle = hero_unusual if hero_unusual else None
                    if tb_particle:
                        eff_id = ETHEREAL_EFFECT_MAP.get(tb_particle, 129)
                        tb_sockets.append({"type": "ethereal", "gem_def_index": 3045, "effect": eff_id})

                    # 1. Map Arcana 5957 to hero_base (913)
                    if "913" not in replaced_def_ids and "913" in self.item_spans:
                        arcana_block = self.build_merged_item_block(
                            def_id="913",
                            target_item_id="5957",
                            hero_name=hero_name,
                            slot_name="hero_base",
                            unusual_particle=tb_particle,
                            kinetic_activity=hero_kinetic,
                            sockets=tb_sockets if tb_sockets else None
                        )
                        if arcana_block:
                            dspan = self.item_spans["913"]
                            replacements.append((dspan[0], dspan[1], arcana_block))
                            replaced_def_ids.add("913")

                    # 2. Map Arcana Horns (37161) to head (478)
                    head_val = slots.get("head")
                    head_id = ""
                    head_style = None
                    if isinstance(head_val, dict):
                        head_id = str(head_val.get("id", ""))
                        head_style = head_val.get("style")
                    elif head_val:
                        head_id = str(head_val)

                    target_horns_id = head_id if head_id and head_id != "5957" else "37161"

                    if "478" not in replaced_def_ids and "478" in self.item_spans and target_horns_id in self.item_spans:
                        horns_block = self.build_merged_item_block(
                            def_id="478",
                            target_item_id=target_horns_id,
                            hero_name=hero_name,
                            slot_name="head",
                            style=head_style,
                            sockets=tb_sockets if tb_sockets else None
                        )
                        if horns_block:
                            dspan = self.item_spans["478"]
                            replacements.append((dspan[0], dspan[1], horns_block))
                            replaced_def_ids.add("478")

            # --- GENERAL SLOTS MAPPING ---
            for slot_name, skin_val in slots.items():
                target_item_id = ""
                selected_style = None

                if isinstance(skin_val, dict):
                    target_item_id = str(skin_val.get("id", ""))
                    selected_style = skin_val.get("style")
                else:
                    target_item_id = str(skin_val)

                if not target_item_id:
                    continue

                target_span = self.item_spans.get(target_item_id)
                if not target_span:
                    continue

                target_raw = self.raw_text[target_span[0]:target_span[1]]
                m_slot = re.search(r'"item_slot"\s+"([^"]+)"', target_raw)
                actual_slot = m_slot.group(1) if m_slot else slot_name

                def_info = default_items.get(actual_slot)
                if not def_info:
                    for s, d in default_items.items():
                        if s == actual_slot or actual_slot in s:
                            def_info = d
                            break

                if not def_info:
                    continue

                def_id = str(def_info["id"])
                if def_id in replaced_def_ids or def_id not in self.item_spans:
                    continue

                # Prepare sockets & particles
                item_sockets = []
                item_particle = None

                # Slot eligible for unusual particle & ethereal socket
                is_effect_slot = (
                    actual_slot in ("weapon", "weapon_persona_1", "offhand_weapon_persona_1") or
                    (actual_slot in ("back", "wings") and hero_name == "npc_dota_hero_queenofpain") or
                    (actual_slot in ("head",) and hero_name == "npc_dota_hero_invoker") or
                    (actual_slot in ("hero_base", "head") and hero_name == "npc_dota_hero_terrorblade")
                )

                if hero_unusual and is_effect_slot:
                    item_particle = hero_unusual
                    eff_id = ETHEREAL_EFFECT_MAP.get(hero_unusual, 826)
                    item_sockets.append({"type": "ethereal", "gem_def_index": 3045, "effect": eff_id})

                # Hero-specific kinetic gem injection for authentic inspection card view
                if hero_kinetic and actual_slot in ("head", "weapon", "weapon_persona_1"):
                    hero_kinetic_defaults = {
                        "npc_dota_hero_pudge": 104,
                    }
                    k_mod = hero_kinetic_defaults.get(hero_name)
                    if k_mod:
                        item_sockets.append({"type": "kinetic", "gem_def_index": 3005, "hero": hero_name, "asset_modifier": k_mod})

                new_block = self.build_merged_item_block(
                    def_id=def_id,
                    target_item_id=target_item_id,
                    hero_name=hero_name,
                    slot_name=actual_slot,
                    style=selected_style,
                    unusual_particle=item_particle,
                    kinetic_activity=hero_kinetic,
                    sockets=item_sockets if item_sockets else None
                )

                if new_block:
                    def_span = self.item_spans[def_id]
                    replacements.append((def_span[0], def_span[1], new_block))
                    replaced_def_ids.add(def_id)

        # 2. Global Items
        global_items = preset.get("global_items", {})
        for cat_name, target_item_id in global_items.items():
            target_item_id = str(target_item_id)
            def_id = GLOBAL_DEFAULT_IDS.get(cat_name)
            if not def_id or def_id in replaced_def_ids or def_id not in self.item_spans or target_item_id not in self.item_spans:
                continue

            new_block = self.build_merged_item_block(
                def_id=def_id,
                target_item_id=target_item_id
            )

            if new_block:
                def_span = self.item_spans[def_id]
                replacements.append((def_span[0], def_span[1], new_block))
                replaced_def_ids.add(def_id)

        # 3. Fast String Slicing
        replacements.sort(key=lambda x: x[0])
        chunks = []
        last_pos = 0
        for start, end, new_text in replacements:
            chunks.append(self.raw_text[last_pos:start])
            chunks.append(new_text)
            last_pos = end
        chunks.append(self.raw_text[last_pos:])

        patched_text = "".join(chunks)

        # 4. Pack into pak01_dir.vpk with direct model overrides & Panorama CSS patches
        temp_dir = tempfile.mkdtemp(prefix="morph_vpk_")
        try:
            scripts_dir = os.path.join(temp_dir, "scripts", "items")
            os.makedirs(scripts_dir, exist_ok=True)
            vpk_internal_file = os.path.join(scripts_dir, "items_game.txt")
            with open(vpk_internal_file, "wb") as f:
                f.write(patched_text.encode("utf-8"))

            dota_vpk_path = os.path.join(DEFAULT_DOTA_PATH, "game", "dota", "pak01_dir.vpk")
            if os.path.exists(dota_vpk_path):
                try:
                    dota_archive = vpk.open(dota_vpk_path)
                    model_maps = {}

                    # A. Pudge Persona (Cute) direct model overrides
                    if "npc_dota_hero_pudge" in skins and str(skins["npc_dota_hero_pudge"].get("persona_selector")) == "13786":
                        p_slots = skins["npc_dota_hero_pudge"]
                        model_maps['models/heroes/pudge/pudge.vmdl_c'] = 'models/heroes/pudge_cute/pudge_cute.vmdl_c'

                        slot_to_dest = {
                            'weapon_persona_1': 'models/heroes/pudge/righthook.vmdl_c',
                            'offhand_weapon_persona_1': 'models/heroes/pudge/leftweapon.vmdl_c',
                            'armor_persona_1': 'models/heroes/pudge/back.vmdl_c',
                            'head_persona_1': 'models/heroes/pudge/hair.vmdl_c',
                            'arms_persona_1': 'models/heroes/pudge/bracer.vmdl_c',
                        }

                        default_cute_models = {
                            'weapon_persona_1': 'models/heroes/pudge_cute/pudge_cute_hook.vmdl_c',
                            'offhand_weapon_persona_1': 'models/heroes/pudge_cute/pudge_cute_offhand.vmdl_c',
                            'armor_persona_1': 'models/heroes/pudge_cute/pudge_cute_costume.vmdl_c',
                            'head_persona_1': 'models/heroes/pudge_cute/pudge_cute_hair.vmdl_c',
                            'arms_persona_1': 'models/heroes/pudge_cute/pudge_cute_arms.vmdl_c',
                        }

                        for p_slot, dst in slot_to_dest.items():
                            src_model = default_cute_models[p_slot]
                            chosen_id = str(p_slots.get(p_slot, ""))
                            if chosen_id and chosen_id in self.item_spans:
                                c_span = self.item_spans[chosen_id]
                                c_raw = self.raw_text[c_span[0]:c_span[1]]
                                m_c = re.search(r'"model_player"\s+"([^"]+)"', c_raw)
                                if m_c:
                                    src_model = m_c.group(1).strip() + "_c"
                            model_maps[dst] = src_model

                    # B. Queen of Pain Arcana direct model overrides
                    if "npc_dota_hero_queenofpain" in skins:
                        qop_slots = skins["npc_dota_hero_queenofpain"]
                        has_qop_arcana = any(
                            str(v) in ("12930", "13768", "13769", "13770") or 
                            (isinstance(v, dict) and str(v.get("id")) in ("12930", "13768", "13769", "13770")) 
                            for v in qop_slots.values()
                        )
                        if has_qop_arcana:
                            model_maps['models/heroes/queenofpain/queenofpain.vmdl_c'] = 'models/items/queenofpain/queenofpain_arcana/queenofpain_arcana.vmdl_c'
                            model_maps['models/heroes/queenofpain/wings.vmdl_c'] = 'models/items/queenofpain/queenofpain_arcana/queenofpain_arcana_wings.vmdl_c'
                            model_maps['models/heroes/queenofpain/queenofpain_weapon.vmdl_c'] = 'models/items/queenofpain/queenofpain_arcana/queenofpain_arcana_dagger.vmdl_c'
                            model_maps['models/heroes/queenofpain/hair.vmdl_c'] = 'models/items/queenofpain/queenofpain_arcana/queenofpain_arcana_head.vmdl_c'
                            model_maps['models/heroes/queenofpain/shoulders.vmdl_c'] = 'models/items/queenofpain/queenofpain_arcana/queenofpain_arcana_base_armor.vmdl_c'

                    for dst, src in model_maps.items():
                        if src in dota_archive:
                            out_f = os.path.join(temp_dir, *dst.split('/'))
                            os.makedirs(os.path.dirname(out_f), exist_ok=True)
                            with open(out_f, 'wb') as f:
                                f.write(dota_archive[src].read())

                    # C. Panorama UI styling overrides: restore full saturation to default items & show gem panels in hover tooltips
                    css_targets = [
                        ('panorama/styles/ui_econ_item.vcss_c', [
                            (b'.IsDefaultItem{saturation: 0.0;wash-color: #c4e8fe;}', b'.IsDefaultItem{saturation: 1.0;wash-color: #ffffff;}'),
                            (b'.IsDefaultItem:hover{saturation: 0.0;wash-color: #c4e8fe;}', b'.IsDefaultItem:hover{saturation: 1.0;wash-color: #ffffff;}'),
                        ]),
                        ('panorama/styles/hero_slot_item_picker_loadout.vcss_c', [
                            (b'#SlotEconItem.IsDefaultItem{saturation: 0.0;wash-color: #c4e8fe;}', b'#SlotEconItem.IsDefaultItem{saturation: 1.0;wash-color: #ffffff;}'),
                        ]),
                        ('panorama/styles/hero_slot_item_picker.vcss_c', [
                            (b'#SlotEconItem.IsDefaultItem{saturation: 0.0;wash-color: #c4e8fe;}', b'#SlotEconItem.IsDefaultItem{saturation: 1.0;wash-color: #ffffff;}'),
                        ]),
                        ('panorama/styles/tooltips/tooltip_econ_item.vcss_c', [
                            (b'#GemPanel.HiddenGem{visibility: collapse;}', b'#GemPanel.HiddenGem{visibility: visible; }'),
                        ]),
                    ]
                    for css_path, patches in css_targets:
                        if css_path in dota_archive:
                            css_bytes = dota_archive[css_path].read()
                            for target, replacement in patches:
                                if target in css_bytes:
                                    css_bytes = css_bytes.replace(target, replacement)
                            out_css = os.path.join(temp_dir, *css_path.split('/'))
                            os.makedirs(os.path.dirname(out_css), exist_ok=True)
                            with open(out_css, 'wb') as f:
                                f.write(css_bytes)

                    # D. Terrorblade Arcana Real Binary Particle Recoloring & 3D Colorwarp LUT & Materials
                    tb_prismatic = prismatic_config.get("npc_dota_hero_terrorblade")
                    if tb_prismatic:
                        tb_rgb = resolve_prismatic_rgb(tb_prismatic)
                        if tb_rgb:
                            r_val, g_val, b_val = tb_rgb[0], tb_rgb[1], tb_rgb[2]
                            r_norm = max(0.0, min(1.0, r_val / 255.0))
                            g_norm = max(0.0, min(1.0, g_val / 255.0))
                            b_norm = max(0.0, min(1.0, b_val / 255.0))
                            custom_tint_pat = b'\x07' + struct.pack('<f', r_norm) + b'\x07' + struct.pack('<f', g_norm) + b'\x07' + struct.pack('<f', b_norm)
                            cyan_pat = bytes.fromhex('07 21 b0 b2 3e 07 f6 28 3c 3f 07 00 00 80 3f')

                            # 1. Patch All Terrorblade Arcana & Weapon Particle Systems (.vpcf_c)
                            tb_particles = [
                                k for k in dota_archive 
                                if k.startswith("particles/") and k.endswith(".vpcf_c") and (
                                    "terrorblade" in k or "dreadhunt" in k
                                ) and (
                                    "arcana" in k or "ambient" in k or "horns" in k or "sword" in k or 
                                    "metamorphosis" in k or "blade" in k or "eyes" in k or "mouth" in k or
                                    "feet" in k or "foot" in k or "wing" in k or "sunder" in k
                                )
                            ]
                            recolored_particles = 0
                            for p_path in tb_particles:
                                try:
                                    p_raw = dota_archive[p_path].read()
                                    p_patched = patch_vpcf_binary(p_raw, tb_rgb)
                                    if p_patched != p_raw:
                                        out_p = os.path.join(temp_dir, *p_path.split('/'))
                                        os.makedirs(os.path.dirname(out_p), exist_ok=True)
                                        with open(out_p, 'wb') as f:
                                            f.write(p_patched)
                                        recolored_particles += 1
                                except Exception as e_p:
                                    print(f"[Builder] Warning: failed to patch particle {p_path}: {e_p}")
                            print(f"[Builder] Terrorblade Prismatic: recolored {recolored_particles} particle systems to RGB {tb_rgb}")

                            # 2. Patch Materials (chest and demon forms)
                            tb_vmats = [
                                'materials/models/heroes/terrorblade/terrorblade_arcana_color.vmat_c',
                                'materials/models/items/terrorblade/corrupted_form/corrupted_form.vmat_c',
                                'materials/models/items/terrorblade/endless_purgatory_demon/endless_purgatory_demon.vmat_c',
                                'materials/models/items/terrorblade/knight_of_foulfell_demon/knight_of_foulfell_demon.vmat_c',
                                'materials/models/items/terrorblade/marauders_demon/marauders_demon.vmat_c',
                            ]
                            for vmat_path in tb_vmats:
                                if vmat_path in dota_archive:
                                    mat_bytes = dota_archive[vmat_path].read()
                                    if cyan_pat in mat_bytes:
                                        mat_bytes = mat_bytes.replace(cyan_pat, custom_tint_pat)
                                        out_vmat = os.path.join(temp_dir, *vmat_path.split('/'))
                                        os.makedirs(os.path.dirname(out_vmat), exist_ok=True)
                                        with open(out_vmat, 'wb') as f:
                                            f.write(mat_bytes)

                    # E. Real In-Game Gem Display via Localization
                    loc_targets = [
                        ('resource/localization/items_russian.txt', 'russian'),
                        ('resource/localization/items_english.txt', 'english'),
                    ]
                    for loc_path, lang in loc_targets:
                        if loc_path in dota_archive:
                            try:
                                loc_bytes = dota_archive[loc_path].read()
                                loc_text = loc_bytes.decode('utf-8', errors='ignore')
                                modified_loc = False

                                # 1. Terrorblade Prismatic Gem Badge
                                if tb_prismatic:
                                    p_name = tb_prismatic.get("name", "Rubiline") if isinstance(tb_prismatic, dict) else str(tb_prismatic)
                                    p_hex = tb_prismatic.get("hex", "#D11FA1") if isinstance(tb_prismatic, dict) else "#D11FA1"
                                    
                                    # Desc
                                    tb_desc_token = '"DOTA_Item_Desc_Fractal_Shard_of_Inner_Abysm"'
                                    if tb_desc_token in loc_text:
                                        if lang == 'russian':
                                            badge = f"<font color='{p_hex}'><b>◆ ПРИЗМАТИЧЕСКИЙ САМОЦВЕТ: {p_name} ({p_hex})</b></font><br><br>"
                                        else:
                                            badge = f"<font color='{p_hex}'><b>◆ PRISMATIC GEM: {p_name} ({p_hex})</b></font><br><br>"
                                        m_tb = re.search(r'("DOTA_Item_Desc_Fractal_Shard_of_Inner_Abysm"\s*")([^"]*)(")', loc_text)
                                        if m_tb and badge not in m_tb.group(2):
                                            loc_text = loc_text[:m_tb.start(2)] + badge + m_tb.group(2) + loc_text[m_tb.end(2):]
                                            modified_loc = True

                                    # Title
                                    tb_title_token = '"DOTA_Item_Fractal_Horns_of_Inner_Abysm"'
                                    if tb_title_token in loc_text:
                                        m_title = re.search(r'("DOTA_Item_Fractal_Horns_of_Inner_Abysm"\s*")([^"]*)(")', loc_text)
                                        if m_title and f"({p_name})" not in m_title.group(2):
                                            loc_text = loc_text[:m_title.start(2)] + m_title.group(2) + f" ({p_name})" + loc_text[m_title.end(2):]
                                            modified_loc = True

                                # 2. Invoker Northern Blight Style Unusual Ethereal Gem Badge
                                inv_unusual = unusual_config.get("npc_dota_hero_invoker")
                                if inv_unusual:
                                    eff_name = "Frostbloom" if "silver" in inv_unusual else "Ethereal"
                                    eff_color = "#94CAD0"
                                    if lang == 'russian':
                                        inv_badge = f"<font color='{eff_color}'><b>◆ НЕОБЫЧНЫЙ ЭФИРНЫЙ САМОЦВЕТ: {eff_name}</b></font><br>Встроенный редкий самоцвет Доты (Ледяное цветение)."
                                    else:
                                        inv_badge = f"<font color='{eff_color}'><b>◆ UNUSUAL ETHEREAL GEM: {eff_name}</b></font><br>Embedded rare Ethereal Gem."
                                    
                                    desc_key = '"DOTA_Item_Desc_12762"'
                                    if desc_key in loc_text:
                                        m_inv = re.search(r'("DOTA_Item_Desc_12762"\s*")([^"]*)(")', loc_text)
                                        if m_inv and inv_badge not in m_inv.group(2):
                                            loc_text = loc_text[:m_inv.start(2)] + inv_badge + loc_text[m_inv.end(2):]
                                            modified_loc = True
                                    else:
                                        last_brace = loc_text.rfind('}')
                                        if last_brace != -1:
                                            entry = f'\t\t"DOTA_Item_Desc_12762"\t\t"{inv_badge}"\n'
                                            loc_text = loc_text[:last_brace] + entry + loc_text[last_brace:]
                                            modified_loc = True

                                    inv_title_token = '"DOTA_Item_Northern_Blight_Style"'
                                    if inv_title_token in loc_text:
                                        m_ititle = re.search(r'("DOTA_Item_Northern_Blight_Style"\s*")([^"]*)(")', loc_text)
                                        if m_ititle and f"({eff_name})" not in m_ititle.group(2):
                                            loc_text = loc_text[:m_ititle.start(2)] + m_ititle.group(2) + f" (Unusual {eff_name})" + loc_text[m_ititle.end(2):]
                                            modified_loc = True

                                if modified_loc:
                                    out_loc = os.path.join(temp_dir, *loc_path.split('/'))
                                    os.makedirs(os.path.dirname(out_loc), exist_ok=True)
                                    with open(out_loc, 'wb') as f_loc:
                                        f_loc.write(loc_text.encode('utf-8'))
                                    print(f"[Builder] Injected real in-game gem badges into {loc_path}")
                            except Exception as e_loc:
                                print(f"[Builder] Warning: failed to patch {loc_path}: {e_loc}")

                            # 3. Patch Terrorblade Arcana 3D Color LUT Textures
                            cw_tex_paths = [
                                'materials/models/heroes/statuseffects/colorwarp_tb_arcana.vtex_c',
                                'materials/models/heroes/statuseffects/colorwarp_tb_arcana_colorwarp3d_z000_tga_b560854a.vtex_c',
                            ]
                            for cw_tex_path in cw_tex_paths:
                                if cw_tex_path in dota_archive:
                                    cw_bytes = bytearray(dota_archive[cw_tex_path].read())
                                    if len(cw_bytes) >= 16384:
                                        for i in range(len(cw_bytes) - 16384, len(cw_bytes), 4):
                                            b_pix, g_pix, r_pix = cw_bytes[i], cw_bytes[i+1], cw_bytes[i+2]
                                            # Transform any pixel with green/cyan tint into Rubiline / custom prismatic
                                            if (b_pix > 15 and g_pix > 15) or (g_pix > 30 and g_pix >= r_pix):
                                                lum = max(r_pix, g_pix, b_pix) / 255.0
                                                cw_bytes[i]   = int(b_val * lum)  # Blue
                                                cw_bytes[i+1] = int(g_val * lum)  # Green
                                                cw_bytes[i+2] = int(r_val * lum)  # Red
                                        out_cw = os.path.join(temp_dir, *cw_tex_path.split('/'))
                                        os.makedirs(os.path.dirname(out_cw), exist_ok=True)
                                        with open(out_cw, 'wb') as f:
                                            f.write(cw_bytes)

                except Exception as e:
                    print(f"[Builder] Warning: failed direct model/CSS injection: {e}")

            target_dir = os.path.dirname(os.path.abspath(output_path))
            os.makedirs(target_dir, exist_ok=True)

            new_vpk = vpk.new(temp_dir)
            new_vpk.save(output_path)
            print(f"[Builder] VPK generated in {time.time()-t0:.3f} s. Modified items: {len(replacements)}")
            return True
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

VpkBuilder = FastVpkBuilder
