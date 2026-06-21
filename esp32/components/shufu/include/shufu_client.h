#ifndef SHUFU_CLIENT_H
#define SHUFU_CLIENT_H

#include "esp_err.h"
#include "shufu_stream.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    const char *node_url;
    const char *bearer_token;
    int timeout_ms;
    size_t stream_chunk_size;
} shufu_client_config_t;

/* Calls a ShuFu Node over HTTP. This SDK contains no model weights and exposes
 * no local inference entry point by design. Wi-Fi setup remains the app's job. */
esp_err_t shufu_invoke_stream(
    const shufu_client_config_t *config,
    const char *model,
    const char *session_id,
    const char *input,
    shufu_stream_event_fn on_event,
    void *user_ctx
);

#ifdef __cplusplus
}
#endif

#endif
