#ifndef HAT_LOG_H
#define HAT_LOG_H

#include <stdbool.h>
#include <stdio.h>

#define HAT_LOG_RETRY_DELAY_SEC 5

#define HAT_LOG_BUFF_COUNT 32
#define HAT_LOG_BUFF_SIZE 4096

#define HAT_LOG_MAX_HOSTNAME_LEN 32
#define HAT_LOG_MAX_APPNAME_LEN 64
#define HAT_LOG_MAX_ID_LEN 64
#define HAT_LOG_MAX_FILENAME_LEN 128
#define HAT_LOG_MAX_MSG_LEN (HAT_LOG_BUFF_SIZE - 32)

#define hat_log(level, id, msg, ...)                                           \
    do {                                                                       \
        hat_log_level_t temp_level = (level);                                  \
        if (temp_level > hat_log_get_level())                                  \
            break;                                                             \
        char temp_msg[HAT_LOG_MAX_MSG_LEN + 1];                                \
        snprintf(temp_msg, HAT_LOG_MAX_MSG_LEN + 1, (msg), __VA_ARGS__);       \
        temp_msg[HAT_LOG_MAX_MSG_LEN] = 0;                                     \
        hat_log_log(temp_level, (id), __FILE__, __LINE__, temp_msg);           \
    } while (false)


#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    HAT_LOG_KERNEL = 0,
    HAT_LOG_USER = 1,
    HAT_LOG_MAIL = 2,
    HAT_LOG_SYSTEM = 3,
    HAT_LOG_AUTHORIZATION1 = 4,
    HAT_LOG_INTERNAL = 5,
    HAT_LOG_PRINTER = 6,
    HAT_LOG_NETWORK = 7,
    HAT_LOG_UUCP = 8,
    HAT_LOG_CLOCK1 = 9,
    HAT_LOG_AUTHORIZATION2 = 10,
    HAT_LOG_FTP = 11,
    HAT_LOG_NTP = 12,
    HAT_LOG_AUDIT = 13,
    HAT_LOG_ALERT = 14,
    HAT_LOG_CLOCK2 = 15,
    HAT_LOG_LOCAL0 = 16,
    HAT_LOG_LOCAL1 = 17,
    HAT_LOG_LOCAL2 = 18,
    HAT_LOG_LOCAL3 = 19,
    HAT_LOG_LOCAL4 = 20,
    HAT_LOG_LOCAL5 = 21,
    HAT_LOG_LOCAL6 = 22,
    HAT_LOG_LOCAL7 = 23
} hat_log_facility_t;

typedef enum {
    HAT_LOG_EMERGENCY = 0,
    HAT_LOG_ALERT = 1,
    HAT_LOG_CRITICAL = 2,
    HAT_LOG_ERROR = 3,
    HAT_LOG_WARNING = 4,
    HAT_LOG_NOTICE = 5,
    HAT_LOG_INFORMATIONAL = 6,
    HAT_LOG_DEBUG = 7
} hat_log_level_t;

void hat_log_init(hat_log_facility_t facility, hat_log_level_t level,
                  char *appname, char *syslog_host, uint16_t syslog_port) ;
void hat_log_destroy();
hat_log_level_t hat_log_get_level();
int hat_log_log(hat_log_level_t level, char *id, char *file_name,
                int line_number, char *msg);

#ifdef __cplusplus
}
#endif

#endif
