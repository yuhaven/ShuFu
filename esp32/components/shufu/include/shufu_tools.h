#ifndef SHUFU_TOOLS_H
#define SHUFU_TOOLS_H

#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SHUFU_TOOL_MAX_COUNT 16
#define SHUFU_TOOL_NAME_CAPACITY 32

typedef int (*shufu_tool_handler_fn)(
    const char *arguments_json,
    char *result_json,
    size_t result_capacity,
    void *handler_ctx
);

typedef struct {
    char name[SHUFU_TOOL_NAME_CAPACITY];
    bool has_side_effect;
    shufu_tool_handler_fn handler;
    void *handler_ctx;
} shufu_tool_t;

typedef struct {
    shufu_tool_t tools[SHUFU_TOOL_MAX_COUNT];
    size_t count;
} shufu_tool_registry_t;

enum {
    SHUFU_TOOL_OK = 0,
    SHUFU_TOOL_NOT_FOUND = -1,
    SHUFU_TOOL_PERMISSION_DENIED = -2,
    SHUFU_TOOL_INVALID_ARGUMENT = -3,
    SHUFU_TOOL_REGISTRY_FULL = -4
};

void shufu_tool_registry_init(shufu_tool_registry_t *registry);

/* Only firmware function pointers can be registered. There is no evaluator,
 * dlopen path, shell bridge, or model-provided executable payload. */
int shufu_tool_register(
    shufu_tool_registry_t *registry,
    const char *name,
    bool has_side_effect,
    shufu_tool_handler_fn handler,
    void *handler_ctx
);

/* ``allow_side_effect`` must be true for every GPIO/write invocation. Approval
 * is per execution and is intentionally not cached in the registry. */
int shufu_tool_execute(
    const shufu_tool_registry_t *registry,
    const char *name,
    const char *arguments_json,
    bool allow_side_effect,
    char *result_json,
    size_t result_capacity
);

#ifdef __cplusplus
}
#endif

#endif
