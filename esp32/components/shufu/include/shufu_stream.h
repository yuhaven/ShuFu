#ifndef SHUFU_STREAM_H
#define SHUFU_STREAM_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#ifndef SHUFU_STREAM_LINE_CAPACITY
#define SHUFU_STREAM_LINE_CAPACITY 1024
#endif

typedef void (*shufu_stream_event_fn)(const char *json_line, size_t length, void *user_ctx);

typedef struct {
    char line[SHUFU_STREAM_LINE_CAPACITY];
    size_t length;
    shufu_stream_event_fn on_event;
    void *user_ctx;
} shufu_stream_parser_t;

/* The parser is allocation-free. It frames NDJSON but deliberately leaves JSON
 * interpretation to the host firmware, which may use cJSON or a smaller parser. */
void shufu_stream_parser_init(
    shufu_stream_parser_t *parser,
    shufu_stream_event_fn on_event,
    void *user_ctx
);

/* Returns 0 on success and -1 when a peer sends a line exceeding the hard cap. */
int shufu_stream_parser_feed(
    shufu_stream_parser_t *parser,
    const char *data,
    size_t length
);

#ifdef __cplusplus
}
#endif

#endif
