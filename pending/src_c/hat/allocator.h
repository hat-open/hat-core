#ifndef HAT_ALLOCATOR_H
#define HAT_ALLOCATOR_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif


typedef struct hat_allocator_t hat_allocator_t;

typedef void *(*hat_allocator_alloc_t)(hat_allocator_t *a, size_t size,
                                       void *old);

struct hat_allocator_t {
    void *ctx;
    hat_allocator_alloc_t alloc;
}


extern hat_allocator_t hat_allocator_libc;


static inline void *hat_allocator_alloc(hat_allocator_t *a, size_t size,
                                        void *old) {
    return a->alloc(a, size, old);
}


static inline void *hat_allocator_free(hat_allocator_t *a, void *old) {
    return a->alloc(a, 0, old);
}


#ifdef __cplusplus
}
#endif

#endif
