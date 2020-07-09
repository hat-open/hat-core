#ifndef HAT_LOG_H
#define HAT_LOG_H

#include <stdint.h>
#include <uv.h>

#define HAT_LOG_MAX_ENTRIES 20
#define HAT_LOG_CONNECT_TIMEOUT_MS 5000
#define HAT_LOG_MAX_MSG_SIZE 1024
#define HAT_LOG_MAX_ID_SIZE 32

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    EMERGENCY = 0,
    ALERT = 1,
    CRITICAL = 2,
    ERROR = 3,
    WARNING = 4,
    NOTICE = 5,
    INFORMATIONAL = 6,
    DEBUG = 7
} hat_log_level_t;

typedef struct hat_log_t hat_log_t;

hat_log_t *hat_log_create(struct sockaddr *addr);
void hat_log_close(hat_log_t *log);
void hat_log_log(hat_log_t *log, hat_log_level_t level, char *id, char *msg,
                 ...);

#ifdef __cplusplus
}
#endif

#endif
