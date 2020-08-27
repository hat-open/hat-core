#ifndef HAT_SBS_H
#define HAT_SBS_H

#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include "mem.h"

#define HAT_SBS_SUCCESS 0
#define HAT_SBS_ERROR -1


#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    HAT_SBS_TYPE_BOOLEAN,
    HAT_SBS_TYPE_INTEGER,
    HAT_SBS_TYPE_FLOAT,
    HAT_SBS_TYPE_STRING,
    HAT_SBS_TYPE_BYTES,
    HAT_SBS_TYPE_ARRAY,
    HAT_SBS_TYPE_TUPLE,
    HAT_SBS_TYPE_UNION
} hat_sbs_type_t;

typedef enum {
    HAT_SBS_DEF_TYPE_BUILTIN,
    HAT_SBS_DEF_TYPE_USER
} hat_sbs_def_type_t;

typedef struct hat_sbs_def_t {
    hat_sbs_def_type_t type;
    union {
        struct {
            hat_sbs_type_t type;
            union {
                struct {
                    void *dummy;
                } simple_d;
                struct {
                    struct hat_sbs_def_t *def;
                } array_d;
                struct {
                    struct hat_sbs_def_t **defs;
                    size_t defs_len;
                } tuple_d;
                struct {
                    struct hat_sbs_def_t **defs;
                    size_t defs_len;
                } union_d;
            };
        } builtin;
        struct {
            struct hat_sbs_def_t *def;
        } user;
    };
} hat_sbs_def_t;

typedef struct {
    hat_sbs_type_t type;
} hat_sbs_t;

typedef struct {
    hat_sbs_t base;
    _Bool value;
} hat_sbs_boolean_t;

typedef struct {
    hat_sbs_t base;
    int64_t value;
} hat_sbs_integer_t;

typedef struct {
    hat_sbs_t base;
    double value;
} hat_sbs_float_t;

typedef struct {
    hat_sbs_t base;
    uint8_t *value;
    size_t len;
} hat_sbs_string_t;

typedef struct {
    hat_sbs_t base;
    uint8_t *value;
    size_t len;
} hat_sbs_bytes_t;

typedef struct {
    hat_sbs_t base;
    hat_sbs_t **values;
    size_t len;
} hat_sbs_array_t;

typedef struct {
    hat_sbs_t base;
    hat_sbs_t **values;
    size_t len;
} hat_sbs_tuple_t;

typedef struct {
    hat_sbs_t base;
    hat_sbs_t *value;
    size_t id;
} hat_sbs_union_t;


ssize_t hat_sbs_decode(hat_mem_region_t *reg, hat_sbs_def_t *def, uint8_t *data,
                       size_t data_len, hat_sbs_t **value, uint8_t **rest,
                       size_t *rest_len);
ssize_t hat_sbs_encode(hat_sbs_def_t *def, hat_sbs_t *value, uint8_t *data,
                       size_t data_cap, size_t *data_len);

#ifdef __cplusplus
}
#endif

#endif
