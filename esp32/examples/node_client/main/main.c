#include <stdio.h>
#include <stdint.h>
#include <string.h>

#include "driver/gpio.h"
#include "esp_log.h"
#include "shufu_client.h"
#include "shufu_tools.h"

static const char *TAG = "shufu-example";

static int set_led(
    const char *arguments_json,
    char *result_json,
    size_t result_capacity,
    void *handler_ctx
) {
    const gpio_num_t pin = (gpio_num_t)(intptr_t)handler_ctx;
    /* A production app should parse a strict boolean with cJSON. The example
     * keeps the handler short while still avoiding code or command evaluation. */
    const int level = strstr(arguments_json, "true") != NULL ? 1 : 0;
    gpio_set_level(pin, level);
    return snprintf(result_json, result_capacity, "{\"on\":%s}", level ? "true" : "false") <
                   (int)result_capacity
               ? SHUFU_TOOL_OK
               : SHUFU_TOOL_INVALID_ARGUMENT;
}

static void on_stream_event(const char *json_line, size_t length, void *user_ctx) {
    (void)user_ctx;
    ESP_LOGI(TAG, "event: %.*s", (int)length, json_line);
}

void app_main(void) {
    shufu_tool_registry_t tools;
    shufu_client_config_t client = {
        .node_url = "http://192.168.1.20:7878",
        .bearer_token = "replace-me",
        .timeout_ms = 120000,
        .stream_chunk_size = 64,
    };

    gpio_reset_pin(GPIO_NUM_2);
    gpio_set_direction(GPIO_NUM_2, GPIO_MODE_OUTPUT);
    shufu_tool_registry_init(&tools);
    shufu_tool_register(&tools, "gpio.set_led", true, set_led, (void *)(intptr_t)GPIO_NUM_2);

    /* Networking must already be connected by the host firmware. */
    ESP_ERROR_CHECK(shufu_invoke_stream(
        &client,
        "assistant",
        "esp32-demo",
        "请给设备一条简短状态提示",
        on_stream_event,
        NULL
    ));

    /* A model response never executes a tool by itself. The host must validate
     * the proposed call, request approval, and pass true for this one execution. */
}
