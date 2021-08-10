#include <string.h>

#include <unistd.h>
#include <sys/socket.h>
#include <netdb.h>

#include "log_socket.h"


static int init_addr(struct sockaddr_in *addr, char *host, uint16_t port) {
    struct addrinfo *info;
    struct addrinfo hints = {.ai_family = AF_INET, .ai_socktype = SOCK_STREAM};

    if (getaddrinfo(host, NULL, &hints, &info))
        return 1;

    *addr = {.sin_family = AF_INET,
             .sin_port = htons(port),
             .sin_addr = ((struct sockaddr_in *)info).sin_addr};

    freeaddrinfo(info);

    return 0;
}


int hat_log_socket_init(hat_log_socket_t *s, char *host, uint16_t port) {
    s->fd = -1;
    if (!host)
        return 1;

    struct sockaddr_in addr;
    if (init_addr(&addr, host, port))
        return 1;

    s->fd = socket(AF_INET, SOCK_STREAM, 0);
    if (s->fd == -1)
        return 1;

    if (connect(s->fd, (struct sockaddr *)&addr, sizeof(addr))) {
        close(s->fd);
        s->fd = -1;
        return 1;
    }

    return 0;
}


void hat_log_socket_destroy(hat_log_socket_t *s) {
    shutdown(s->fd, SHUT_RDWR);
    close(s->fd);
    s->fd = -1;
}


bool hat_log_socket_is_open(hat_log_socket_t *s) { return s->fd != -1; }


int hat_log_socket_write(hat_log_socket_t *s, char *data) {
    size_t data_len = strlen(data);

    while (data_len) {
        ssize_t size = write(s->fd, data, data_len);
        if (size == -1)
            return 1;

        data += size;
        data_len -= size;
    }

    return 0;
}
