#pragma once
#include <windows.h>
#include <winhttp.h>
#include <string>
#include <vector>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <nlohmann/json.hpp>

#pragma comment(lib, "winhttp.lib")

namespace fs = std::filesystem;

class ApiClient {
public:
    static bool SendBuildRequest(
        const std::wstring& serverHost,
        INTERNET_PORT serverPort,
        const std::string& jsonPayload,
        std::string& outBuildId
    ) {
        HINTERNET hSession = WinHttpOpen(
            L"DotaSkinChangerNativeClient/2.0",
            WINHTTP_ACCESS_TYPE_DEFAULT_PROXY,
            WINHTTP_NO_PROXY_NAME,
            WINHTTP_NO_PROXY_BYPASS,
            0
        );
        if (!hSession) {
            std::cerr << "[Network] WinHttpOpen failed: " << GetLastError() << "\n";
            return false;
        }

        HINTERNET hConnect = WinHttpConnect(hSession, serverHost.c_str(), serverPort, 0);
        if (!hConnect) {
            std::cerr << "[Network] WinHttpConnect failed: " << GetLastError() << "\n";
            WinHttpCloseHandle(hSession);
            return false;
        }

        HINTERNET hRequest = WinHttpOpenRequest(
            hConnect,
            L"POST",
            L"/api/build",
            nullptr,
            WINHTTP_NO_REFERER,
            WINHTTP_DEFAULT_ACCEPT_TYPES,
            0
        );
        if (!hRequest) {
            std::cerr << "[Network] WinHttpOpenRequest failed: " << GetLastError() << "\n";
            WinHttpCloseHandle(hConnect);
            WinHttpCloseHandle(hSession);
            return false;
        }

        std::wstring headers = L"Content-Type: application/json\r\n";
        BOOL bResults = WinHttpSendRequest(
            hRequest,
            headers.c_str(),
            static_cast<DWORD>(headers.length()),
            (LPVOID)jsonPayload.c_str(),
            static_cast<DWORD>(jsonPayload.length()),
            static_cast<DWORD>(jsonPayload.length()),
            0
        );

        if (bResults) {
            bResults = WinHttpReceiveResponse(hRequest, nullptr);
        }

        if (!bResults) {
            std::cerr << "[Network] SendRequest/ReceiveResponse failed: " << GetLastError() << "\n";
            WinHttpCloseHandle(hRequest);
            WinHttpCloseHandle(hConnect);
            WinHttpCloseHandle(hSession);
            return false;
        }

        // Читаем тело ответа
        std::string responseBody;
        DWORD dwSize = 0;
        DWORD dwDownloaded = 0;
        do {
            dwSize = 0;
            if (!WinHttpQueryDataAvailable(hRequest, &dwSize)) {
                break;
            }
            if (dwSize == 0) break;

            std::vector<char> buffer(dwSize + 1, 0);
            if (WinHttpReadData(hRequest, buffer.data(), dwSize, &dwDownloaded)) {
                responseBody.append(buffer.data(), dwDownloaded);
            }
        } while (dwSize > 0);

        WinHttpCloseHandle(hRequest);
        WinHttpCloseHandle(hConnect);
        WinHttpCloseHandle(hSession);

        try {
            auto resJson = nlohmann::json::parse(responseBody);
            if (resJson.contains("build_id")) {
                outBuildId = resJson["build_id"].get<std::string>();
                return true;
            } else {
                std::cerr << "[Network] Ответ сервера не содержит build_id: " << responseBody << "\n";
                return false;
            }
        } catch (const std::exception& e) {
            std::cerr << "[Network] Ошибка парсинга JSON ответа: " << e.what() << "\n";
            return false;
        }
    }

    static bool DownloadVpk(
        const std::wstring& serverHost,
        INTERNET_PORT serverPort,
        const std::string& buildId,
        const fs::path& destinationPath
    ) {
        HINTERNET hSession = WinHttpOpen(
            L"DotaSkinChangerNativeClient/2.0",
            WINHTTP_ACCESS_TYPE_DEFAULT_PROXY,
            WINHTTP_NO_PROXY_NAME,
            WINHTTP_NO_PROXY_BYPASS,
            0
        );
        if (!hSession) return false;

        HINTERNET hConnect = WinHttpConnect(hSession, serverHost.c_str(), serverPort, 0);
        if (!hConnect) {
            WinHttpCloseHandle(hSession);
            return false;
        }

        std::wstring downloadUrl = L"/api/download/" + std::wstring(buildId.begin(), buildId.end());
        HINTERNET hRequest = WinHttpOpenRequest(
            hConnect,
            L"GET",
            downloadUrl.c_str(),
            nullptr,
            WINHTTP_NO_REFERER,
            WINHTTP_DEFAULT_ACCEPT_TYPES,
            0
        );
        if (!hRequest) {
            WinHttpCloseHandle(hConnect);
            WinHttpCloseHandle(hSession);
            return false;
        }

        BOOL bResults = WinHttpSendRequest(hRequest, WINHTTP_NO_ADDITIONAL_HEADERS, 0, WINHTTP_NO_REQUEST_DATA, 0, 0, 0);
        if (bResults) {
            bResults = WinHttpReceiveResponse(hRequest, nullptr);
        }

        if (!bResults) {
            WinHttpCloseHandle(hRequest);
            WinHttpCloseHandle(hConnect);
            WinHttpCloseHandle(hSession);
            return false;
        }

        // Создаем целевую директорию, если нужно
        fs::create_directories(destinationPath.parent_path());

        std::ofstream outFile(destinationPath, std::ios::binary | std::ios::trunc);
        if (!outFile.is_open()) {
            std::cerr << "[Network] Не удалось открыть файл для записи: " << destinationPath.string() << "\n";
            WinHttpCloseHandle(hRequest);
            WinHttpCloseHandle(hConnect);
            WinHttpCloseHandle(hSession);
            return false;
        }

        DWORD dwSize = 0;
        DWORD dwDownloaded = 0;
        size_t totalBytes = 0;
        std::vector<char> buffer(64 * 1024); // 64 KB чанки

        do {
            dwSize = 0;
            if (!WinHttpQueryDataAvailable(hRequest, &dwSize)) {
                break;
            }
            if (dwSize == 0) break;

            DWORD bytesToRead = (std::min)(dwSize, static_cast<DWORD>(buffer.size()));
            if (WinHttpReadData(hRequest, buffer.data(), bytesToRead, &dwDownloaded)) {
                outFile.write(buffer.data(), dwDownloaded);
                totalBytes += dwDownloaded;
            }
        } while (dwSize > 0);

        outFile.close();
        WinHttpCloseHandle(hRequest);
        WinHttpCloseHandle(hConnect);
        WinHttpCloseHandle(hSession);

        std::cout << "[Network] VPK успешно скачан: " << totalBytes / 1024 / 1024 << " МБ -> " << destinationPath.string() << "\n";
        return true;
    }
};
