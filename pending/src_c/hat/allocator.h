#ifndef HAT_ALLOCATOR_H
#define HAT_ALLOCATOR_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif


typedef void *(*hat_allocator_alloc_t)(size_t size);
typedef void (*hat_allocator_free_t)(void *p);

typedef struct {
    hat_allocator_alloc_t alloc;
    hat_allocator_free_t free;
} hat_allocator_t;

extern hat_allocator_t hat_allocator_libc;


#ifdef __cplusplus
}
#endif

#endif
