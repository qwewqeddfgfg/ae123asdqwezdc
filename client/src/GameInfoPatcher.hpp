#pragma once
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include <iostream>
#include <iomanip>
#include <algorithm>
#include <windows.h>
#include <wincrypt.h>

#pragma comment(lib, "advapi32.lib")

namespace fs = std::filesystem;

class GameInfoPatcher {
public:
    explicit GameInfoPatcher(const fs::path& dotaRoot) 
        : m_dotaRoot(dotaRoot),
          m_modsDir(dotaRoot / "game" / "Morph"),
          m_branchGiPath(dotaRoot / "game" / "dota" / "gameinfo_branchspecific.gi"),
          m_signaturesPath(dotaRoot / "game" / "bin" / "win64" / "dota.signatures") {
        
        m_vanillaGiTargets.push_back(dotaRoot / "game" / "dota" / "gameinfo.gi");
        m_vanillaGiTargets.push_back(dotaRoot / "game" / "dota_russian" / "gameinfo.gi");
        m_vanillaGiTargets.push_back(dotaRoot / "game" / "dota_schinese" / "gameinfo.gi");
    }

    // Восстанавливает ванильные gameinfo.gi, чтобы Valve античит и координатор не выдавали предупреждений
    void RestoreVanillaGameInfos() {
        for (const auto& path : m_vanillaGiTargets) {
            fs::path backupPath = path;
            backupPath += ".bak";
            if (fs::exists(backupPath)) {
                try {
                    fs::copy_file(backupPath, path, fs::copy_options::overwrite_existing);
                } catch (...) {}
            } else if (fs::exists(path)) {
                // Если бэкапа нет, но файл содержит Morph, аккуратно убираем его
                std::ifstream in(path, std::ios::binary);
                std::string content((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
                in.close();

                size_t p = content.find("Game\t\t\t\tMorph\r\n\t\t\t");
                if (p != std::string::npos) content.erase(p, strlen("Game\t\t\t\tMorph\r\n\t\t\t"));
                p = content.find("Mod\t\t\t\t\tMorph\r\n\t\t\t");
                if (p != std::string::npos) content.erase(p, strlen("Mod\t\t\t\t\tMorph\r\n\t\t\t"));
                p = content.find("Game\t\t\t\tMorph\n\t\t\t");
                if (p != std::string::npos) content.erase(p, strlen("Game\t\t\t\tMorph\n\t\t\t"));
                p = content.find("Mod\t\t\t\t\tMorph\n\t\t\t");
                if (p != std::string::npos) content.erase(p, strlen("Mod\t\t\t\t\tMorph\n\t\t\t"));

                std::ofstream out(path, std::ios::binary | std::ios::trunc);
                out.write(content.data(), content.size());
                out.close();
            }
        }
    }

    bool PrepareEnvironment() {
        try {
            RestoreVanillaGameInfos();

            if (!fs::exists(m_modsDir)) {
                fs::create_directories(m_modsDir);
            }

            // Очищаем loose scripts если остались от старых версий
            fs::path looseScripts = m_modsDir / "scripts";
            if (fs::exists(looseScripts)) {
                fs::remove_all(looseScripts);
            }

            return PatchBranchGameInfoAndSignatures();
        } catch (const std::exception& e) {
            std::cerr << "[Error] PrepareEnvironment failed: " << e.what() << "\n";
            return false;
        }
    }

    bool PatchBranchGameInfoAndSignatures() {
        if (!fs::exists(m_branchGiPath) || !fs::exists(m_signaturesPath)) {
            std::cerr << "[Error] Не найдены критические файлы Dota 2: gameinfo_branchspecific.gi или dota.signatures\n";
            return false;
        }

        // Бэкапим branch gameinfo при первом патче
        fs::path branchBak = m_branchGiPath;
        branchBak += ".bak";
        if (!fs::exists(branchBak)) {
            fs::copy_file(m_branchGiPath, branchBak);
        }

        // Бэкапим signatures при первом патче
        fs::path sigBak = m_signaturesPath;
        sigBak += ".bak";
        if (!fs::exists(sigBak)) {
            fs::copy_file(m_signaturesPath, sigBak);
        }

        // Формируем контент gameinfo_branchspecific.gi с SearchPaths для Morph
        std::string branchContent = 
            "\"GameInfo\"\r\n"
            "{\r\n"
            "\t//\r\n"
            "\t// Branch-varying info, such as the game/title and app IDs, is in gameinfo_branchspecific.gi.\r\n"
            "\t// gameinfo.gi is the non-branch-varying content and can be integrated between branches.\r\n"
            "\t//\r\n"
            "\r\n"
            "\tgame \t\t\"Dota 2\"\r\n"
            "\ttitle \t\t\"Dota 2\"\r\n"
            "\r\n"
            "\tFileSystem\r\n"
            "\t{\r\n"
            "\t\tSteamAppId\t\t\t\t570\r\n"
            "\t\tBreakpadAppId\t\t\t373300\r\n"
            "\t\tBreakpadAppId_Tools\t\t375360\r\n"
            "\r\n"
            "\t\tSearchPaths\r\n"
            "\t\t{\r\n"
            "\t\t\tGame\t\t\t\tMorph\r\n"
            "\t\t\tGame\t\t\t\tdota\r\n"
            "\t\t\tGame\t\t\t\tcore\r\n"
            "\t\t\tMod\t\t\t\t\tMorph\r\n"
            "\t\t\tMod\t\t\t\t\tdota\r\n"
            "\t\t\tMod\t\t\t\t\tcore\r\n"
            "\t\t}\r\n"
            "\t}\r\n"
            "}\r\n";

        std::ofstream branchOut(m_branchGiPath, std::ios::binary | std::ios::trunc);
        branchOut.write(branchContent.data(), branchContent.size());
        branchOut.close();

        // Вычисляем SHA1 и CRC32 от получившегося gameinfo_branchspecific.gi
        std::string sha1 = CalculateSHA1(reinterpret_cast<const uint8_t*>(branchContent.data()), branchContent.size());
        uint32_t crcVal = CalculateCRC32(reinterpret_cast<const uint8_t*>(branchContent.data()), branchContent.size());
        std::string crcStr = FormatCrcForValve(crcVal);

        std::string targetSigLine = "...\\..\\..\\dota\\gameinfo_branchspecific.gi~SHA1:" + sha1 + ";CRC:" + crcStr;

        // Патчим dota.signatures: оставляем все до DIGEST:... и добавляем targetSigLine после него
        std::ifstream sigIn(m_signaturesPath, std::ios::binary);
        std::string sigContent((std::istreambuf_iterator<char>(sigIn)), std::istreambuf_iterator<char>());
        sigIn.close();

        size_t digestPos = sigContent.rfind("DIGEST:");
        if (digestPos == std::string::npos) {
            std::cerr << "[Error] Не удалось найти DIGEST в dota.signatures!\n";
            return false;
        }

        // Находим конец строки DIGEST:...
        size_t endOfDigestLine = sigContent.find('\n', digestPos);
        if (endOfDigestLine == std::string::npos) {
            endOfDigestLine = sigContent.size();
        } else {
            endOfDigestLine++; // включаем символ перевода строки
        }

        // Обрезаем все модификации после DIGEST и дописываем нашу сигнатуру
        std::string newSigContent = sigContent.substr(0, endOfDigestLine);
        if (!newSigContent.empty() && newSigContent.back() != '\n') {
            newSigContent += "\r\n";
        }
        newSigContent += targetSigLine + "\r\n";

        std::ofstream sigOut(m_signaturesPath, std::ios::binary | std::ios::trunc);
        sigOut.write(newSigContent.data(), newSigContent.size());
        sigOut.close();

        std::cout << "[Core] gameinfo_branchspecific.gi успешно настроен на Morph.\n";
        std::cout << "[Core] dota.signatures подписан (SHA1: " << sha1 << ", CRC: " << crcStr << ").\n";
        std::cout << "[Core] Чистый gameinfo.gi сохранен (100% VAC-safe).\n";
        return true;
    }

    bool InstallVpk(const fs::path& sourceVpk) {
        if (!fs::exists(sourceVpk)) {
            std::cerr << "[Error] Файл VPK не найден: " << sourceVpk.string() << "\n";
            return false;
        }

        if (!PrepareEnvironment()) {
            return false;
        }

        try {
            fs::copy_file(sourceVpk, GetTargetVpkPath(), fs::copy_options::overwrite_existing);
            return true;
        } catch (const std::exception& e) {
            std::cerr << "[Error] Не удалось скопировать VPK: " << e.what() << "\n";
            return false;
        }
    }

    bool RemoveMods() {
        bool success = true;

        RestoreVanillaGameInfos();

        // 1. Восстанавливаем оригинальный gameinfo_branchspecific.gi
        fs::path branchBak = m_branchGiPath;
        branchBak += ".bak";
        if (fs::exists(branchBak)) {
            try {
                fs::copy_file(branchBak, m_branchGiPath, fs::copy_options::overwrite_existing);
                std::cout << "[Core] gameinfo_branchspecific.gi восстановлен из оригинала.\n";
            } catch (...) { success = false; }
        }

        // 2. Восстанавливаем чистый dota.signatures (убираем строки после DIGEST)
        if (fs::exists(m_signaturesPath)) {
            try {
                std::ifstream sigIn(m_signaturesPath, std::ios::binary);
                std::string sigContent((std::istreambuf_iterator<char>(sigIn)), std::istreambuf_iterator<char>());
                sigIn.close();

                size_t digestPos = sigContent.rfind("DIGEST:");
                if (digestPos != std::string::npos) {
                    size_t endOfDigestLine = sigContent.find('\n', digestPos);
                    if (endOfDigestLine != std::string::npos) {
                        sigContent = sigContent.substr(0, endOfDigestLine + 1);
                        std::ofstream sigOut(m_signaturesPath, std::ios::binary | std::ios::trunc);
                        sigOut.write(sigContent.data(), sigContent.size());
                        sigOut.close();
                        std::cout << "[Core] dota.signatures очищен от модификаций.\n";
                    }
                }
            } catch (...) { success = false; }
        }

        // 3. Удаляем VPK и папку Morph
        try {
            if (fs::exists(GetTargetVpkPath())) {
                fs::remove(GetTargetVpkPath());
            }
            if (fs::exists(m_modsDir)) {
                fs::remove_all(m_modsDir);
            }
            std::cout << "[Core] Папка Morph удалена.\n";
        } catch (const std::exception& e) {
            std::cerr << "[Warning] Не удалось удалить папку Morph (возможно, файл занят): " << e.what() << "\n";
            success = false;
        }

        return success;
    }

    bool IsPatched() const {
        if (!fs::exists(m_branchGiPath) || !fs::exists(m_signaturesPath)) return false;

        std::ifstream bFile(m_branchGiPath, std::ios::binary);
        std::string bContent((std::istreambuf_iterator<char>(bFile)), std::istreambuf_iterator<char>());
        bFile.close();

        if (bContent.find("Morph") == std::string::npos) return false;

        std::ifstream sFile(m_signaturesPath, std::ios::binary);
        std::string sContent((std::istreambuf_iterator<char>(sFile)), std::istreambuf_iterator<char>());
        sFile.close();

        size_t dPos = sContent.rfind("DIGEST:");
        if (dPos == std::string::npos) return false;
        std::string afterDigest = sContent.substr(dPos);
        return afterDigest.find("gameinfo_branchspecific.gi") != std::string::npos;
    }

    bool HasVpkInstalled() const {
        return fs::exists(GetTargetVpkPath());
    }

    fs::path GetTargetVpkPath() const {
        return m_modsDir / "pak01_dir.vpk";
    }

    fs::path GetModsDir() const {
        return m_modsDir;
    }

private:
    fs::path m_dotaRoot;
    fs::path m_modsDir;
    fs::path m_branchGiPath;
    fs::path m_signaturesPath;
    std::vector<fs::path> m_vanillaGiTargets;

    static uint32_t CalculateCRC32(const uint8_t* data, size_t length) {
        uint32_t crc = 0xFFFFFFFF;
        for (size_t i = 0; i < length; ++i) {
            crc ^= data[i];
            for (int j = 0; j < 8; ++j) {
                crc = (crc >> 1) ^ (0xEDB88320 & (-(int)(crc & 1)));
            }
        }
        return ~crc;
    }

    static std::string FormatCrcForValve(uint32_t crc) {
        uint8_t bytes[4];
        bytes[0] = static_cast<uint8_t>(crc & 0xFF);
        bytes[1] = static_cast<uint8_t>((crc >> 8) & 0xFF);
        bytes[2] = static_cast<uint8_t>((crc >> 16) & 0xFF);
        bytes[3] = static_cast<uint8_t>((crc >> 24) & 0xFF);

        std::stringstream ss;
        ss << std::hex << std::uppercase << std::setfill('0');
        for (int i = 0; i < 4; ++i) {
            ss << std::setw(2) << static_cast<int>(bytes[i]);
        }
        return ss.str();
    }

    static std::string CalculateSHA1(const uint8_t* data, size_t length) {
        HCRYPTPROV hProv = 0;
        HCRYPTHASH hHash = 0;
        std::string result = "";

        if (CryptAcquireContext(&hProv, NULL, NULL, PROV_RSA_FULL, CRYPT_VERIFYCONTEXT)) {
            if (CryptCreateHash(hProv, CALG_SHA1, 0, 0, &hHash)) {
                if (CryptHashData(hHash, data, static_cast<DWORD>(length), 0)) {
                    DWORD hashLen = 20;
                    uint8_t hashBuf[20];
                    if (CryptGetHashParam(hHash, HP_HASHVAL, hashBuf, &hashLen, 0)) {
                        std::stringstream ss;
                        ss << std::hex << std::uppercase << std::setfill('0');
                        for (int i = 0; i < 20; ++i) {
                            ss << std::setw(2) << static_cast<int>(hashBuf[i]);
                        }
                        result = ss.str();
                    }
                }
                CryptDestroyHash(hHash);
            }
            CryptReleaseContext(hProv, 0);
        }
        return result;
    }
};
