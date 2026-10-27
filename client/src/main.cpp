#include <iostream>
#include <windows.h>
#include <fstream>
#include "SteamLocator.hpp"
#include "GameInfoPatcher.hpp"
#include "ApiClient.hpp"

void PrintUsage(const char* exeName) {
    std::cout << "Использование:\n"
              << "  " << exeName << "                 - Проверить пути и подготовить окружение (gameinfo.gi)\n"
              << "  " << exeName << " --status        - Показать текущий статус клиента\n"
              << "  " << exeName << " --apply <json>  - Отправить пресет на бэкенд, собрать VPK и применить в игру\n"
              << "  " << exeName << " --install <vpk> - Установить локальный VPK файл в game/Morph\n"
              << "  " << exeName << " --restore       - Восстановить чистый gameinfo.gi и удалить моды\n";
}

int main(int argc, char* argv[]) {
    SetConsoleOutputCP(CP_UTF8);
    std::cout << "========================================" << std::endl;
    std::cout << "   Dota 2 VPK SkinChanger Client Core   " << std::endl;
    std::cout << "========================================" << std::endl;

    auto dotaPath = SteamLocator::FindDotaPath();
    if (!dotaPath) {
        std::cerr << "[Error] Dota 2 не найдена! Проверьте установку Steam.\n";
        return 1;
    }

    GameInfoPatcher patcher(*dotaPath);

    if (argc > 1) {
        std::string cmd = argv[1];

        if (cmd == "--help" || cmd == "-h") {
            PrintUsage(argv[0]);
            return 0;
        }

        if (cmd == "--status") {
            std::cout << "[Status] Путь к Dota 2:     " << dotaPath->string() << "\n";
            std::cout << "[Status] gameinfo.gi статус: " << (patcher.IsPatched() ? "ПРОПАТЧЕН (Morph активен)" : "ОРИГИНАЛЬНЫЙ") << "\n";
            std::cout << "[Status] Установлен VPK:     " << (patcher.HasVpkInstalled() ? "ДА (активен)" : "НЕТ") << "\n";
            if (patcher.HasVpkInstalled()) {
                std::cout << "[Status] Размер VPK:         " << fs::file_size(patcher.GetTargetVpkPath()) / 1024 / 1024 << " MB\n";
            }
            return 0;
        }

        if (cmd == "--restore" || cmd == "--uninstall") {
            std::cout << "[Core] Восстановление оригинального состояния игры...\n";
            if (patcher.RemoveMods()) {
                std::cout << "[Core] Успешно! Моды удалены, gameinfo.gi восстановлен из резервной копии.\n";
            } else {
                std::cerr << "[Error] Ошибка при восстановлении оригинальных файлов.\n";
                return 1;
            }
            return 0;
        }

        if (cmd == "--install") {
            if (argc < 3) {
                std::cerr << "[Error] Не указан путь к VPK файлу для установки.\n";
                PrintUsage(argv[0]);
                return 1;
            }
            fs::path srcVpk = argv[2];
            std::cout << "[Core] Установка VPK архива: " << srcVpk.string() << "...\n";
            if (patcher.InstallVpk(srcVpk)) {
                std::cout << "[Core] VPK успешно установлен в: " << patcher.GetTargetVpkPath().string() << "\n";
                std::cout << "[Core] Скинченджер активирован! Можно запускать Dota 2.\n";
            } else {
                std::cerr << "[Error] Не удалось установить VPK.\n";
                return 1;
            }
            return 0;
        }

        if (cmd == "--apply") {
            if (argc < 3) {
                std::cerr << "[Error] Не указан путь к preset.json файлу.\n";
                PrintUsage(argv[0]);
                return 1;
            }
            fs::path presetFile = argv[2];
            if (!fs::exists(presetFile)) {
                std::cerr << "[Error] Файл пресета не найден: " << presetFile.string() << "\n";
                return 1;
            }

            std::ifstream inFile(presetFile);
            std::string payload((std::istreambuf_iterator<char>(inFile)), std::istreambuf_iterator<char>());
            inFile.close();

            std::cout << "[Core] Загружен пресет из: " << presetFile.string() << "\n";
            std::cout << "[Core] Отправка запроса на сборку в бэкенд (http://127.0.0.1:8000/api/build)...\n";

            std::string buildId;
            if (!ApiClient::SendBuildRequest(L"127.0.0.1", 8000, payload, buildId)) {
                std::cerr << "[Error] Не удалось связаться с сервером сборки. Проверьте, запущен ли run_server.py!\n";
                return 1;
            }

            std::cout << "[Core] VPK успешно скомпилирован сервером! ID сборки: " << buildId << "\n";
            std::cout << "[Core] Скачивание VPK архива напрямую в директорию модов Доты...\n";

            if (!ApiClient::DownloadVpk(L"127.0.0.1", 8000, buildId, patcher.GetTargetVpkPath())) {
                std::cerr << "[Error] Ошибка при скачивании VPK с сервера.\n";
                return 1;
            }

            if (patcher.PrepareEnvironment()) {
                std::cout << "[Core] Окружение проверено: gameinfo.gi настроен на dota_mods.\n";
                std::cout << "[Core] ГОТОВО! Скинченджер успешно применен. Запускайте Dota 2!\n";
            } else {
                std::cerr << "[Error] Не удалось пропатчить gameinfo.gi.\n";
                return 1;
            }
            return 0;
        }
    }

    // По умолчанию: проверка и подготовка
    std::cout << "[Core] Dota 2 найдена: " << dotaPath->string() << std::endl;
    if (patcher.PrepareEnvironment()) {
        std::cout << "[Core] Окружение готово к установке модов!\n";
        std::cout << "[Core] Папка модов:  " << patcher.GetModsDir().string() << "\n";
        std::cout << "[Core] Путь для VPK: " << patcher.GetTargetVpkPath().string() << "\n";
        std::cout << "[Core] gameinfo.gi проверен и пропатчен.\n";
    } else {
        std::cerr << "[Error] Не удалось пропатчить gameinfo.gi.\n";
        return 1;
    }

    return 0;
}
