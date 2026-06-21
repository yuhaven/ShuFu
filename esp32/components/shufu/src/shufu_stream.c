#include "shufu_stream.h"

void shufu_stream_parser_init(
    shufu_stream_parser_t *parser,
    shufu_stream_event_fn on_event,
    void *user_ctx
) {
    if (parser == NULL) {
        return;
    }
    parser->length = 0;
    parser->on_event = on_event;
    parser->user_ctx = user_ctx;
}

int shufu_stream_parser_feed(
    shufu_stream_parser_t *parser,
    const char *data,
    size_t length
) {
    size_t index;
    if (parser == NULL || (data == NULL && length != 0)) {
        return -1;
    }
    for (index = 0; index < length; ++index) {
        const char value = data[index];
        if (value == '\n') {
            if (parser->length != 0 && parser->on_event != NULL) {
                parser->line[parser->length] = '\0';
                parser->on_event(parser->line, parser->length, parser->user_ctx);
            }
            parser->length = 0;
            continue;
        }
        if (value == '\r') {
            continue;
        }
        if (parser->length >= SHUFU_STREAM_LINE_CAPACITY - 1) {
            parser->length = 0;
            return -1;
        }
        parser->line[parser->length++] = value;
    }
    return 0;
}
