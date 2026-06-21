#ifndef CJSON_H
#define CJSON_H
typedef struct cJSON cJSON;
cJSON *cJSON_CreateObject(void);
cJSON *cJSON_AddStringToObject(cJSON *object, const char *name, const char *value);
cJSON *cJSON_AddNumberToObject(cJSON *object, const char *name, double value);
char *cJSON_PrintUnformatted(const cJSON *item);
void cJSON_Delete(cJSON *item);
#endif
