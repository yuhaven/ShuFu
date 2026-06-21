#include "shufu_tools.h"

#include <string.h>

void shufu_tool_registry_init(shufu_tool_registry_t *registry) {
    if (registry != NULL) {
        memset(registry, 0, sizeof(*registry));
    }
}

int shufu_tool_register(
    shufu_tool_registry_t *registry,
    const char *name,
    bool has_side_effect,
    shufu_tool_handler_fn handler,
    void *handler_ctx
) {
    size_t name_length;
    shufu_tool_t *tool;
    if (registry == NULL || name == NULL || handler == NULL) {
        return SHUFU_TOOL_INVALID_ARGUMENT;
    }
    name_length = strlen(name);
    if (name_length == 0 || name_length >= SHUFU_TOOL_NAME_CAPACITY) {
        return SHUFU_TOOL_INVALID_ARGUMENT;
    }
    if (registry->count >= SHUFU_TOOL_MAX_COUNT) {
        return SHUFU_TOOL_REGISTRY_FULL;
    }
    tool = &registry->tools[registry->count++];
    memcpy(tool->name, name, name_length + 1);
    tool->has_side_effect = has_side_effect;
    tool->handler = handler;
    tool->handler_ctx = handler_ctx;
    return SHUFU_TOOL_OK;
}

int shufu_tool_execute(
    const shufu_tool_registry_t *registry,
    const char *name,
    const char *arguments_json,
    bool allow_side_effect,
    char *result_json,
    size_t result_capacity
) {
    size_t index;
    if (registry == NULL || name == NULL || arguments_json == NULL ||
        result_json == NULL || result_capacity == 0) {
        return SHUFU_TOOL_INVALID_ARGUMENT;
    }
    for (index = 0; index < registry->count; ++index) {
        const shufu_tool_t *tool = &registry->tools[index];
        if (strcmp(tool->name, name) != 0) {
            continue;
        }
        if (tool->has_side_effect && !allow_side_effect) {
            return SHUFU_TOOL_PERMISSION_DENIED;
        }
        return tool->handler(arguments_json, result_json, result_capacity, tool->handler_ctx);
    }
    return SHUFU_TOOL_NOT_FOUND;
}
