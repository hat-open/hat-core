#ifndef HAT_MEM_H
#define HAT_MEM_H

#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <limits.h>


#if (UINT_MAX == 0xffffffffffffffffULL)
#define HAT_MEM_ALIGNMENT 8
#elif (UINT_MAX == 0xffffffffULL)
#define HAT_MEM_ALIGNMENT 4
#else
#define HAT_MEM_ALIGNMENT 1
#endif

#define HAT_MEM_MALLOC malloc
#define HAT_MEM_FREE free


#ifdef __cplusplus
extern "C" {
#endif


typedef struct {
    uint8_t *data;
    size_t len;
    size_t cap;
} hat_mem_region_t;


inline static size_t hat_mem_align(size_t x) {
    return x % HAT_MEM_ALIGNMENT == 0 ? x : x / HAT_MEM_ALIGNMENT + 1;
}


inline static void hat_mem_region_init(hat_mem_region_t *reg, uint8_t *data,
                                       size_t cap) {
    reg->data = data;
    reg->len = hat_mem_align((size_t)data) - (size_t)data;
    reg->cap = cap;
}


inline static hat_mem_region_t *hat_mem_region_create(size_t cap) {
    size_t reg_size = hat_mem_align(sizeof(hat_mem_region_t));
    hat_mem_region_t *reg = HAT_MEM_MALLOC(reg_size + cap);
    if (!reg)
        return NULL;
    hat_mem_region_init(reg, (uint8_t *)reg + reg_size, cap);
    return reg;
}


inline static void hat_mem_region_free(hat_mem_region_t *reg) {
    HAT_MEM_FREE(reg);
}


inline static size_t hat_mem_region_available(hat_mem_region_t *reg) {
    if (reg->len >= reg->cap)
        return 0;
    return reg->cap - reg->len;
}


inline static void *hat_mem_region_alloc(hat_mem_region_t *reg, size_t size) {
    if (size > hat_mem_region_available(reg))
        return NULL;
    size_t len = reg->len;
    reg->len += hat_mem_align(size);
    return reg->data + len;
}


#ifdef __cplusplus
}
#endif

#endif
