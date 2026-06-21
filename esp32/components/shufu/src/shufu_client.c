#include "shufu_client.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "cJSON.h"
#include "esp_http_client.h"

typedef struct {
    shufu_stream_parser_t parser;
    esp_err_t parser_result;
} shufu_http_context_t;

static esp_err_t shufu_http_event(esp_http_client_event_t *event) {
    shufu_http_context_t *context = (shufu_http_context_t *)event->user_data;
    if (event->event_id == HTTP_EVENT_ON_DATA && event->data_len > 0) {
        if (shufu_stream_parser_feed(&context->parser, event->data, (size_t)event->data_len) != 0) {
            context->parser_result = ESP_ERR_INVALID_SIZE;
            return ESP_FAIL;
        }
    }
    return ESP_OK;
}

esp_err_t shufu_invoke_stream(
    const shufu_client_config_t *config,
    const char *model,
    const char *session_id,
    const char *input,
    shufu_stream_event_fn on_event,
    void *user_ctx
) {
    char endpoint[256];
    cJSON *payload = NULL;
    char *body = NULL;
    esp_http_client_handle_t client = NULL;
    esp_err_t result = ESP_FAIL;
    shufu_http_context_t context;
    esp_http_client_config_t http_config = {0};

    if (config == NULL || config->node_url == NULL || session_id == NULL ||
        input == NULL || on_event == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    if (snprintf(endpoint, sizeof(endpoint), "%s/shufu/v3/invoke/stream", config->node_url) >=
        (int)sizeof(endpoint)) {
        return ESP_ERR_INVALID_SIZE;
    }
    payload = cJSON_CreateObject();
    if (payload == NULL) {
        return ESP_ERR_NO_MEM;
    }
    cJSON_AddStringToObject(payload, "model", model != NULL ? model : "assistant");
    cJSON_AddStringToObject(payload, "session_id", session_id);
    cJSON_AddStringToObject(payload, "input", input);
    cJSON_AddNumberToObject(
        payload,
        "stream_chunk_size",
        config->stream_chunk_size != 0 ? (double)config->stream_chunk_size : 64.0
    );
    body = cJSON_PrintUnformatted(payload);
    cJSON_Delete(payload);
    if (body == NULL) {
        return ESP_ERR_NO_MEM;
    }

    shufu_stream_parser_init(&context.parser, on_event, user_ctx);
    context.parser_result = ESP_OK;
    http_config.url = endpoint;
    http_config.method = HTTP_METHOD_POST;
    http_config.timeout_ms = config->timeout_ms > 0 ? config->timeout_ms : 120000;
    http_config.event_handler = shufu_http_event;
    http_config.user_data = &context;
    client = esp_http_client_init(&http_config);
    if (client == NULL) {
        free(body);
        return ESP_ERR_NO_MEM;
    }
    esp_http_client_set_header(client, "Content-Type", "application/json");
    esp_http_client_set_header(client, "Accept", "application/x-ndjson");
    if (config->bearer_token != NULL && config->bearer_token[0] != '\0') {
        char authorization[192];
        if (snprintf(authorization, sizeof(authorization), "Bearer %s", config->bearer_token) >=
            (int)sizeof(authorization)) {
            result = ESP_ERR_INVALID_SIZE;
            goto cleanup;
        }
        esp_http_client_set_header(client, "Authorization", authorization);
    }
    esp_http_client_set_post_field(client, body, (int)strlen(body));
    result = esp_http_client_perform(client);
    if (result == ESP_OK) {
        const int status = esp_http_client_get_status_code(client);
        if (status < 200 || status >= 300) {
            result = ESP_FAIL;
        } else if (context.parser_result != ESP_OK) {
            result = context.parser_result;
        }
    }

cleanup:
    esp_http_client_cleanup(client);
    free(body);
    return result;
}
