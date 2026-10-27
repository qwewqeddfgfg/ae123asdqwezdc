cmake_minimum_required(VERSION 3.20)
project(DotaSkinChangerClient VERSION 0.2.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(SkinChangerCore
    src/main.cpp
    src/SteamLocator.hpp
    src/GameInfoPatcher.hpp
    src/ApiClient.hpp
)

target_include_directories(SkinChangerCore PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/src
)

target_link_libraries(SkinChangerCore PRIVATE winhttp)
