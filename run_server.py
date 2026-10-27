"""
run_server.py - Скрипт запуска FastAPI сервера Dota 2 SkinChanger
Запуск:
    python run_server.py
"""

import uvicorn

if __name__ == "__main__":
    print("Запуск FastAPI сервера Dota 2 SkinChanger на http://127.0.0.1:8000...")
    print("Документация Swagger UI будет доступна по адресу: http://127.0.0.1:8000/docs")
    uvicorn.run("server.main:app", host="127.0.0.1", port=8000, reload=False)
