cmake_minimum_required(VERSION 3.22.1)
project(shufu_android LANGUAGES C CXX)

include(FetchContent)

# Keep the embedded runtime focused on inference: server, examples, tests, CURL,
# and OpenMP would enlarge the AAR or make the first ARM64 build less portable.
set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_COMMON OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_SERVER OFF CACHE BOOL "" FORCE)
set(LLAMA_CURL OFF CACHE BOOL "" FORCE)
set(GGML_OPENMP OFF CACHE BOOL "" FORCE)
set(GGML_NATIVE OFF CACHE BOOL "" FORCE)

# CI and offline contributors can provide the exact verified archive locally.
# Otherwise FetchContent downloads the pinned tag and rejects a hash mismatch.
set(SHUFU_LLAMA_ARCHIVE "" CACHE FILEPATH "Optional verified local llama.cpp b9722 archive")
if(SHUFU_LLAMA_ARCHIVE AND EXISTS "${SHUFU_LLAMA_ARCHIVE}")
    set(SHUFU_LLAMA_SOURCE "${SHUFU_LLAMA_ARCHIVE}")
else()
    set(SHUFU_LLAMA_SOURCE "https://github.com/ggml-org/llama.cpp/archive/refs/tags/b9722.zip")
endif()

FetchContent_Declare(
    llama_cpp
    URL ${SHUFU_LLAMA_SOURCE}
    URL_HASH SHA256=7144212cca13b6014dac1a7f284f2b551de91f9c8f80c5ecbf9cfde4cb549540
)
FetchContent_MakeAvailable(llama_cpp)

add_library(shufu_jni SHARED shufu_jni.cpp)
# C++17 is the common denominator for NDK r27c and the pinned llama.cpp source.
target_compile_features(shufu_jni PRIVATE cxx_std_17)
target_compile_definitions(shufu_jni PRIVATE SHUFU_LLAMA_VERSION="b9722")
target_link_libraries(shufu_jni PRIVATE llama android log)
if(NOT CMAKE_BUILD_TYPE STREQUAL "Debug")
    # Debug symbols remain available locally; distributable variants are smaller.
    target_link_options(shufu_jni PRIVATE "-Wl,--strip-all")
endif()
