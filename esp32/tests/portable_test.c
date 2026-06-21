#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>

#include "shufu_stream.h"
#include "shufu_tools.h"

static int event_count;
static int side_effect_count;

static void count_event(const char *line, size_t length, void *context) {
    (void)context;
    assert(length > 0);
    assert(line[0] == '{');
    event_count++;
}

static int set_gpio(
    const char *arguments,
    char *result,
    size_t result_capacity,
    void *context
) {
    (void)arguments;
    (void)context;
    side_effect_count++;
    return snprintf(result, result_capacity, "{\"ok\":true}") < (int)result_capacity
               ? SHUFU_TOOL_OK
               : SHUFU_TOOL_INVALID_ARGUMENT;
}

int main(void) {
    shufu_stream_parser_t parser;
    shufu_tool_registry_t registry;
    char result[32];

    shufu_stream_parser_init(&parser, count_event, NULL);
    {
        static const char first[] = "{\"type\":\"sta";
        static const char second[] = "rt\"}\n{\"type\":\"done\"}\n";
        assert(shufu_stream_parser_feed(&parser, first, sizeof(first) - 1) == 0);
        assert(shufu_stream_parser_feed(&parser, second, sizeof(second) - 1) == 0);
    }
    assert(event_count == 2);

    shufu_tool_registry_init(&registry);
    assert(shufu_tool_register(&registry, "gpio.set", true, set_gpio, NULL) == SHUFU_TOOL_OK);
    assert(shufu_tool_execute(
               &registry, "gpio.set", "{}", false, result, sizeof(result)
           ) == SHUFU_TOOL_PERMISSION_DENIED);
    assert(side_effect_count == 0);
    assert(shufu_tool_execute(
               &registry, "gpio.set", "{}", true, result, sizeof(result)
           ) == SHUFU_TOOL_OK);
    assert(side_effect_count == 1);
    return 0;
}
