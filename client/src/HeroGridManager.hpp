#pragma once
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>
#include <optional>
#include <iostream>
#include <nlohmann/json.hpp>

namespace fs = std::filesystem;

class HeroGridManager {
public:
    static std::vector<fs::path> FindAllHeroGridConfigs(const fs::path& steamRoot) {
        std::vector<fs::path> result;
        fs::path userdata = steamRoot / "userdata";
        if (!fs::exists(userdata)) return result;

        try {
            for (const auto& entry : fs::directory_iterator(userdata)) {
                if (entry.is_directory()) {
                    fs::path configPath = entry.path() / "570" / "remote" / "cfg" / "hero_grid_config.json";
                    if (fs::exists(configPath)) {
                        result.push_back(configPath);
                    }
                }
            }
        } catch (const std::exception& e) {
            std::cerr << "[HeroGrid] Ошибка поиска сеток: " << e.what() << "\n";
        }
        return result;
    }

    static bool SaveCustomGrid(const fs::path& gridConfigPath, const std::string& jsonContent) {
        try {
            // Резервная копия
            fs::path backup = gridConfigPath;
            backup += ".bak";
            if (!fs::exists(backup)) {
                fs::copy_file(gridConfigPath, backup);
            }

            std::ofstream out(gridConfigPath, std::ios::trunc);
            out << jsonContent;
            out.close();
            return true;
        } catch (const std::exception& e) {
            std::cerr << "[HeroGrid] Ошибка записи сетки: " << e.what() << "\n";
            return false;
        }
    }
};
