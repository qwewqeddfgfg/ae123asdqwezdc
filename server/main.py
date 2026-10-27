"""
main.py - FastAPI Backend API & Fast VPK Builder Server для Dota 2 SkinChanger Morph.
- Каталог всех героев, слотов, косметических скинов и бандлов
- 820+ необычных эффектов (Unusual / Ethereal / Emblems)
- Палитра призматических гемов (TB, Techies)
- Нативная выдача PNG иконок из .vtex_c без внешних зависимостей (/api/icon)
- Сверхбыстрая сборка кастомных VPK архивов (< 0.3 сек)
"""

import os
import uuid
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import vpk

from .items_catalog import ItemsCatalog, DEFAULT_DOTA_PATH
from .vpk_builder import FastVpkBuilder

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(BASE_DIR, "cache", "catalog.json")
ICONS_CACHE_DIR = os.path.join(BASE_DIR, "cache", "icons")
BUILDS_DIR = os.path.join(BASE_DIR, "builds")

app = FastAPI(
    title="Morph Dota 2 SkinChanger API",
    version="2.1.0",
    description="Бэкенд кастомизации и сборщик модов Morph для Dota 2"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

catalog_instance = ItemsCatalog()
builder_instance: Optional[FastVpkBuilder] = None
dota_vpk_archive: Optional[vpk.VPK] = None


class PresetRequest(BaseModel):
    skins: Dict[str, Dict[str, Any]] = {}
    prismatic: Optional[Dict[str, Any]] = {}
    unusual: Optional[Dict[str, str]] = {}
    kinetic: Optional[Dict[str, str]] = {}
    global_items: Optional[Dict[str, str]] = {}


@app.on_event("startup")
async def startup_event():
    global builder_instance, dota_vpk_archive
    print("[Server] Инициализация бэкенда Morph SkinChanger...")

    if not catalog_instance.load_cache(CACHE_PATH):
        print("[Server] Генерация каталога из VPK игры...")
        if catalog_instance.load_from_vpk():
            catalog_instance.build_catalog()
            catalog_instance.save_cache(CACHE_PATH)

    vpk_path = os.path.join(DEFAULT_DOTA_PATH, "game", "dota", "pak01_dir.vpk")
    if os.path.exists(vpk_path):
        dota_vpk_archive = vpk.open(vpk_path)
        raw_text = dota_vpk_archive.get_file("scripts/items/items_game.txt").read().decode("utf-8", errors="ignore")
        builder_instance = FastVpkBuilder(raw_text, catalog_instance.catalog)

    os.makedirs(BUILDS_DIR, exist_ok=True)
    os.makedirs(ICONS_CACHE_DIR, exist_ok=True)
    print(f"[Server] Сервер готов! Героев: {len(catalog_instance.catalog.get('heroes', {}))}")


@app.get("/api/status")
def get_status():
    return {
        "status": "online",
        "app_name": "Morph",
        "heroes_count": len(catalog_instance.catalog.get("heroes", {})),
        "total_cosmetics": catalog_instance.catalog.get("stats", {}).get("total_cosmetics", 0),
        "total_bundles": catalog_instance.catalog.get("stats", {}).get("total_bundles", 0),
        "total_unusual_effects": len(catalog_instance.catalog.get("unusual_effects", [])),
        "builder_ready": builder_instance is not None
    }


@app.get("/api/heroes")
def get_heroes():
    heroes = catalog_instance.catalog.get("heroes", {})
    simplified = []
    for hero_id, data in sorted(heroes.items(), key=lambda x: x[1].get("display_name", "")):
        simplified.append({
            "hero_name": hero_id,
            "display_name": data.get("display_name"),
            "slots": list(data.get("default_items", {}).keys()),
            "bundles_count": len(data.get("bundles", [])),
            "available_skins_count": sum(len(items) for items in data.get("available_skins", {}).values())
        })
    return {"heroes": simplified}


@app.get("/api/heroes/{hero_name}")
def get_hero_details(hero_name: str):
    heroes = catalog_instance.catalog.get("heroes", {})
    if hero_name not in heroes:
        raise HTTPException(status_code=404, detail="Герой не найден")
    return heroes[hero_name]


@app.get("/api/globals")
def get_global_items():
    return catalog_instance.catalog.get("global_items", {})


@app.get("/api/prismatic")
def get_prismatic_colors():
    return catalog_instance.catalog.get("prismatic_colors", {})


@app.get("/api/unusual_effects")
def get_unusual_effects():
    """Возвращает все 820+ необычных эффектов (Ethereal Flame, Emblems, etc.)."""
    return {"unusual_effects": catalog_instance.catalog.get("unusual_effects", [])}


@app.get("/api/icon")
def get_item_icon(path: str):
    """
    Извлекает чистый PNG из скомпилированного .vtex_c внутри pak01_dir.vpk.
    Кэширует результат на диск.
    Пример path: econ/items/pudge/pudge_skeleton_hook_body
    """
    if not dota_vpk_archive:
        raise HTTPException(status_code=500, detail="VPK архив игры не открыт")

    clean_path = path.strip("/\\")
    safe_filename = clean_path.replace("/", "_").replace("\\", "_") + ".png"
    cached_file = os.path.join(ICONS_CACHE_DIR, safe_filename)

    if os.path.exists(cached_file):
        with open(cached_file, "rb") as f:
            return Response(content=f.read(), media_type="image/png")

    candidates = [
        f"panorama/images/{clean_path}_png.vtex_c",
        f"panorama/images/{clean_path}.vtex_c"
    ]

    png_bytes = None
    for cand in candidates:
        if cand in dota_vpk_archive:
            raw_vtex = dota_vpk_archive.get_file(cand).read()
            png_idx = raw_vtex.find(b"\x89PNG\r\n\x1a\n")
            if png_idx != -1:
                png_bytes = raw_vtex[png_idx:]
                break

    if not png_bytes:
        raise HTTPException(status_code=404, detail="Иконка не найдена в VPK")

    # Сохраняем в кэш
    with open(cached_file, "wb") as f:
        f.write(png_bytes)

    return Response(content=png_bytes, media_type="image/png")


@app.post("/api/build")
def build_vpk(preset: PresetRequest):
    if not builder_instance:
        raise HTTPException(status_code=500, detail="Билдер не инициализирован")

    build_id = str(uuid.uuid4())
    build_folder = os.path.join(BUILDS_DIR, build_id)
    target_vpk_path = os.path.join(build_folder, "pak01_dir.vpk")

    success = builder_instance.build_custom_vpk(preset.dict(), target_vpk_path)
    if not success or not os.path.exists(target_vpk_path):
        raise HTTPException(status_code=500, detail="Ошибка сборки VPK")

    return {
        "status": "ready",
        "build_id": build_id,
        "download_url": f"/api/download/{build_id}",
        "file_size": os.path.getsize(target_vpk_path)
    }


@app.get("/api/download/{build_id}")
def download_vpk(build_id: str):
    vpk_path = os.path.join(BUILDS_DIR, build_id, "pak01_dir.vpk")
    if not os.path.exists(vpk_path):
        raise HTTPException(status_code=404, detail="Сборка VPK не найдена")

    return FileResponse(
        path=vpk_path,
        media_type="application/octet-stream",
        filename="pak01_dir.vpk"
    )
