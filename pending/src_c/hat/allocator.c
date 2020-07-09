#include <stdlib.h>
#include "allocator.h"


hat_allocator_t hat_allocator_libc = {.alloc = malloc, .free = free};
