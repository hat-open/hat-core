#ifndef HAT_DIE_H
#define HAT_DIE_H

#include <stdlib.h>
#include <stdio.h>

#define hat_die(msg, ...)                                                      \
    do {                                                                       \
        fprintf(stderr, "fatal error at %s(%d): ", __FILE__, __LINE__);        \
        fprintf(stderr, (msg), __VA_ARGS__);                                   \
        fprintf(stderr, "\n");                                                 \
    } while (false)

#endif
