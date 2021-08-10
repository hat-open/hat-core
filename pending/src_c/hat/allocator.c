#include <stdlib.h>
#include "allocator.h"


static void *libc_alloc(hat_allocator_t *a, size_t size, void *old) {
    return realloc(old, size);
}


hat_allocator_t hat_allocator_libc = {.ctx = NULL, .alloc = libc_alloc};
