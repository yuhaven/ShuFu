idf_component_register(
    SRCS
        "src/shufu_client.c"
        "src/shufu_stream.c"
        "src/shufu_tools.c"
    INCLUDE_DIRS "include"
    REQUIRES esp_http_client json
)
