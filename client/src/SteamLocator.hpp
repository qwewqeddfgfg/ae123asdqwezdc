#pragma once
#include <windows.h>
#include <filesystem>
#include <fstream>
#include <string>
#include <regex>
#include <optional>

namespace fs = std::filesystem;

class SteamLocator {
public:
    static std::optional<fs::path> FindDotaPath() {
        auto steamPath = GetSteamPathFromRegistry();
        if (!steamPath) return std::nullopt;

        // 1. Сначала проверяем стандартную библиотеку внутри самого каталога Steam
        fs::path defaultDota = *steamPath / "steamapps" / "common" / "dota 2 beta";
        if (fs::exists(defaultDota / "game" / "dota" / "gameinfo.gi")) {
            return defaultDota;
        }

        // 2. Ищем во всех подключенных библиотеках Steam через libraryfolders.vdf
        fs::path vdfPath = *steamPath / "steamapps" / "libraryfolders.vdf";
        if (!fs::exists(vdfPath)) return std::nullopt;

        std::ifstream file(vdfPath);
        std::string content((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());

        // Ищем все пути библиотек Steam в libraryfolders.vdf: "path" "..."
        std::regex pathRegex("\"path\"\\s+\"([^\"]+)\"");
        auto words_begin = std::sregex_iterator(content.begin(), content.end(), pathRegex);
        auto words_end = std::sregex_iterator();

        for (std::sregex_iterator i = words_begin; i != words_end; ++i) {
            std::string rawPath = (*i)[1].str();
            // Заменяем двойные слэши из VDF на обычные
            rawPath = std::regex_replace(rawPath, std::regex(R"(\\\\)"), R"(\)");
            
            fs::path dotaCandidate = fs::path(rawPath) / "steamapps" / "common" / "dota 2 beta";
            if (fs::exists(dotaCandidate / "game" / "dota" / "gameinfo.gi")) {
                return dotaCandidate;
            }
        }
        return std::nullopt;
    }

private:
    static std::optional<fs::path> GetSteamPathFromRegistry() {
        HKEY hKey;
        if (RegOpenKeyExW(HKEY_CURRENT_USER, L"Software\\Valve\\Steam", 0, KEY_READ, &hKey) != ERROR_SUCCESS) {
            return std::nullopt;
        }

        wchar_t buffer[MAX_PATH];
        DWORD bufferSize = sizeof(buffer);
        if (RegQueryValueExW(hKey, L"SteamPath", nullptr, nullptr, reinterpret_cast<LPBYTE>(buffer), &bufferSize) == ERROR_SUCCESS) {
            RegCloseKey(hKey);
            return fs::path(buffer);
        }

        RegCloseKey(hKey);
        return std::nullopt;
    }
};
