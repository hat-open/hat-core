#ifndef HAT_LOG_SOCKET_H
#define HAT_LOG_SOCKET_H

#include <stdint.h>
#include <stdbool.h>


#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    int fd;
} hat_log_socket_t;

int hat_log_socket_init(hat_log_socket_t *s, char *host, uint16_t port);
void hat_log_socket_destroy(hat_log_socket_t *s);
bool hat_log_socket_is_open(hat_log_socket_t *s);
int hat_log_socket_write(hat_log_socket_t *s, char *data);

#ifdef __cplusplus
}
#endif

#endif
