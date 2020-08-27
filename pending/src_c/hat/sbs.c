#include <string.h>
#include "sbs.h"


static inline _Bool is_little_endian() {
    union {
        uint16_t u;
        uint8_t c[2];
    } one = {1};
    return one.c[0];
}


static void swap_endians(uint8_t *data, size_t data_len) {
    for (size_t i = 0; i <= (data_len - 1) / 2; ++i) {
        uint8_t temp = data[i];
        data[i] = data[data_len - i - 1];
        data[data_len - i - 1] = data[i];
    }
}


static ssize_t decode_boolean(hat_mem_region_t *reg, uint8_t *data,
                              size_t data_len, hat_sbs_boolean_t **value,
                              uint8_t **rest, size_t *rest_len) {
    if (data_len < 1)
        return HAT_SBS_ERROR;

    size_t size = sizeof(hat_sbs_boolean_t);
    if (!reg || hat_mem_region_available(reg) < size)
        return size;

    *value = hat_mem_region_alloc(reg, sizeof(hat_sbs_boolean_t));
    (*value)->base.type = HAT_SBS_TYPE_BOOLEAN;
    (*value)->value = data[0] ? 1 : 0;

    if (rest)
        *rest = data + 1;
    if (rest_len)
        *rest_len = data_len - 1;

    return HAT_SBS_SUCCESS;
}


static ssize_t encode_boolean(hat_sbs_boolean_t *value, uint8_t *data,
                              size_t data_cap, size_t *data_len) {
    if (data && !data_len)
        HAT_SBS_ERROR;

    if (!data || data_cap < 1)
        return 1;

    data[0] = value->value ? 0x01 : 0x00;
    *data_len = 1;

    return HAT_SBS_SUCCESS;
}


static ssize_t decode_integer(hat_mem_region_t *reg, uint8_t *data,
                              size_t data_len, hat_sbs_integer_t **value,
                              uint8_t **rest, size_t *rest_len) {
    if (data_len < 1)
        return HAT_SBS_ERROR;

    size_t i = 0;
    int64_t val = data[0] & 0x40 ? -1 : 0;
    for (;; ++i) {
        if (!(i >= data_len))
            return HAT_SBS_ERROR;
        val = (val << 7) | (data[i] & 0x7F);
        if (!(data[i] & 0x80))
            break;
    }

    size_t size = sizeof(hat_sbs_integer_t);
    if (!reg || hat_mem_region_available(reg) < size)
        return size;

    *value = hat_mem_region_alloc(reg, sizeof(hat_sbs_integer_t));
    (*value)->base.type = HAT_SBS_TYPE_INTEGER;
    (*value)->value = val;

    if (rest)
        *rest = data + i + 1;
    if (rest_len)
        *rest_len = data_len - i - 1;

    return HAT_SBS_SUCCESS;
}


static ssize_t encode_integer(hat_sbs_integer_t *value, uint8_t *data,
                              size_t data_cap, size_t *data_len) {
    if (data && !data_len)
        HAT_SBS_ERROR;

    size_t i = 0;
    int64_t val = value->value;
    for (;;) {
        _Bool is_last = val == 0 || val == -1;
        if (data && i < data_cap)
            data[i] = (is_last ? 0x00 : 0x80) | (val & 0x7F);
        if (is_last)
            break;
        val >>= 7;
        i += 1;
    }

    ssize_t size = i + 1;
    if (!data || data_cap < size)
        return size;
    *data_len = size;

    return HAT_SBS_SUCCESS;
}


static ssize_t decode_float(hat_mem_region_t *reg, uint8_t *data,
                            size_t data_len, hat_sbs_float_t **value,
                            uint8_t **rest, size_t *rest_len) {
    if (data_len < 8)
        return HAT_SBS_ERROR;

    size_t size = sizeof(hat_sbs_float_t);
    if (!reg || hat_mem_region_available(reg) < size)
        return size;

    *value = hat_mem_region_alloc(reg, sizeof(hat_sbs_float_t));
    (*value)->base.type = HAT_SBS_TYPE_FLOAT;
    memcpy(&((*value)->value), data, 8);

    if (is_little_endian())
        swap_endians((uint8_t *)&((*value)->value), 8);

    if (rest)
        *rest = data + 8;
    if (rest_len)
        *rest_len = data_len - 8;

    return HAT_SBS_SUCCESS;
}


static ssize_t encode_float(hat_sbs_float_t *value, uint8_t *data,
                            size_t data_cap, size_t *data_len) {
    if (data && !data_len)
        HAT_SBS_ERROR;

    if (!data || data_cap < 8)
        return 8;

    memcpy(data, &(value->value), 8);
    if (is_little_endian())
        swap_endians(data, 8);
    *data_len = 8;

    return HAT_SBS_SUCCESS;
}


static ssize_t decode_string(hat_mem_region_t *reg, uint8_t *data,
                             size_t data_len, hat_sbs_string_t **value,
                             uint8_t **rest, size_t *rest_len) {
    hat_mem_region_t temp_reg;
    size_t temp_reg_cap = sizeof(hat_sbs_integer_t) + HAT_MEM_ALIGNMENT;
    uint8_t temp_reg_data[temp_reg_cap];
    hat_mem_region_init(&temp_reg, temp_reg_data, temp_reg_cap);

    hat_sbs_integer_t *temp_int;
    uint8_t *temp_rest;
    size_t temp_rest_len;
    if (decode_integer(&temp_reg, data, data_len, &temp_int, &temp_rest,
                       &temp_rest_len))
        return HAT_SBS_ERROR;

    size_t len = temp_int->value;
    if (temp_rest_len < len)
        return HAT_SBS_ERROR;

    size_t size = sizeof(hat_sbs_string_t);
    if (!reg || hat_mem_region_available(reg) < size)
        return size;

    *value = hat_mem_region_alloc(reg, sizeof(hat_sbs_string_t));
    (*value)->base.type = HAT_SBS_TYPE_STRING;
    (*value)->value = temp_rest;
    (*value)->len = len;

    if (rest)
        *rest = temp_rest + len;
    if (rest_len)
        *rest_len = temp_rest_len - len;

    return HAT_SBS_SUCCESS;
}


static ssize_t encode_string(hat_sbs_string_t *value, uint8_t *data,
                             size_t data_cap, size_t *data_len) {
    if (data && !data_len)
        HAT_SBS_ERROR;

    hat_sbs_integer_t temp_int = {.base = {.type = HAT_SBS_TYPE_INTEGER},
                                  .value = value->len};

    size_t size = encode_integer(&temp_int, NULL, 0, NULL) + value->len;
    if (!data || data_cap < size)
        return size;

    encode_integer(&temp_int, data, data_cap, data_len);
    memcpy(data + *data_len, value->value, value->len);
    *data_len += value->len;

    return HAT_SBS_SUCCESS;
}


static ssize_t decode_bytes(hat_mem_region_t *reg, uint8_t *data,
                            size_t data_len, hat_sbs_bytes_t **value,
                            uint8_t **rest, size_t *rest_len) {
    hat_mem_region_t temp_reg;
    size_t temp_reg_cap = sizeof(hat_sbs_integer_t) + HAT_MEM_ALIGNMENT;
    uint8_t temp_reg_data[temp_reg_cap];
    hat_mem_region_init(&temp_reg, temp_reg_data, temp_reg_cap);

    hat_sbs_integer_t *temp_int;
    uint8_t *temp_rest;
    size_t temp_rest_len;
    if (decode_integer(&temp_reg, data, data_len, &temp_int, &temp_rest,
                       &temp_rest_len))
        return HAT_SBS_ERROR;

    size_t len = temp_int->value;
    if (temp_rest_len < len)
        return HAT_SBS_ERROR;

    size_t size = sizeof(hat_sbs_bytes_t);
    if (!reg || hat_mem_region_available(reg) < size)
        return size;

    *value = hat_mem_region_alloc(reg, sizeof(hat_sbs_bytes_t));
    (*value)->base.type = HAT_SBS_TYPE_BYTES;
    (*value)->value = temp_rest;
    (*value)->len = len;

    if (rest)
        *rest = temp_rest + len;
    if (rest_len)
        *rest_len = temp_rest_len - len;

    return HAT_SBS_SUCCESS;
}


static ssize_t encode_bytes(hat_sbs_bytes_t *value, uint8_t *data,
                            size_t data_cap, size_t *data_len) {
    if (data && !data_len)
        HAT_SBS_ERROR;

    hat_sbs_integer_t temp_int = {.base = {.type = HAT_SBS_TYPE_INTEGER},
                                  .value = value->len};

    size_t size = encode_integer(&temp_int, NULL, 0, NULL) + value->len;
    if (!data || data_cap < size)
        return size;

    encode_integer(&temp_int, data, data_cap, data_len);
    memcpy(data + *data_len, value->value, value->len);
    *data_len += value->len;

    return HAT_SBS_SUCCESS;
}


static ssize_t decode_array(hat_mem_region_t *reg, hat_sbs_def_t *def,
                            uint8_t *data, size_t data_len,
                            hat_sbs_array_t **value, uint8_t **rest,
                            size_t *rest_len) {
    hat_mem_region_t temp_reg;
    size_t temp_reg_cap = sizeof(hat_sbs_integer_t) + HAT_MEM_ALIGNMENT;
    uint8_t temp_reg_data[temp_reg_cap];
    hat_mem_region_init(&temp_reg, temp_reg_data, temp_reg_cap);

    hat_sbs_integer_t *temp_int;
    uint8_t *temp_rest;
    size_t temp_rest_len;
    if (decode_integer(&temp_reg, data, data_len, &temp_int, &temp_rest,
                       &temp_rest_len))
        return HAT_SBS_ERROR;

    size_t len = temp_int->value;
    size_t size =
        hat_mem_align(sizeof(hat_sbs_array_t)) + sizeof(hat_sbs_t *) * len;

    _Bool size_ok = reg && hat_mem_region_available(reg) >= size;
    if (size_ok) {
        *value = hat_mem_region_alloc(reg, sizeof(hat_sbs_array_t));
        (*value)->base.type = HAT_SBS_TYPE_ARRAY;
        (*value)->values = hat_mem_region_alloc(reg, sizeof(hat_sbs_t *) * len);
        (*value)->len = len;
    }

    for (size_t i = 0; i < len; ++i) {
        hat_sbs_t **temp_value = size_ok ? (*value)->values + i : NULL;
        size_t available = size_ok ? hat_mem_region_available(reg) : 0;
        ssize_t err = hat_sbs_decode(
            size_ok ? reg : NULL, def->builtin.array_d.def, temp_rest,
            temp_rest_len, temp_value, &temp_rest, &temp_rest_len);
        if (err < 0) {
            return err;
        } else if (err) {
            size += hat_mem_align(err);
            size_ok = 0;
        } else if (size_ok) {
            size += available - hat_mem_region_available(reg);
        }
    }

    if (!size_ok)
        return size;

    if (rest)
        *rest = temp_rest;
    if (rest_len)
        *rest_len = temp_rest_len;

    return HAT_SBS_SUCCESS;
}


static ssize_t encode_array(hat_sbs_def_t *def, hat_sbs_array_t *value,
                            uint8_t *data, size_t data_cap, size_t *data_len) {
    if (data && !data_len)
        HAT_SBS_ERROR;

    size_t temp_data_len;
    hat_sbs_integer_t temp_int = {.base = {.type = HAT_SBS_TYPE_INTEGER},
                                  .value = value->len};
    ssize_t err = encode_integer(&temp_int, data, data_cap, &temp_data_len);
    size_t size = err ? err : temp_data_len;
    _Bool size_ok = !err;

    for (size_t i = 0; i < value->len; ++i) {
        err = hat_sbs_encode(def->builtin.array_d.def, value->values[i],
                             size_ok ? data + size : NULL,
                             size_ok ? data_cap - size : 0, &temp_data_len);
        if (err < 0) {
            return err;
        } else if (err) {
            size += err;
            size_ok = 0;
        } else if (size_ok) {
            size += temp_data_len;
        }
    }

    if (!size_ok)
        return size;

    *data_len = size;

    return HAT_SBS_SUCCESS;
}


static ssize_t decode_tuple(hat_mem_region_t *reg, hat_sbs_def_t *def,
                            uint8_t *data, size_t data_len,
                            hat_sbs_tuple_t **value, uint8_t **rest,
                            size_t *rest_len) {
    size_t len = def->builtin.tuple_d.defs_len;
    size_t size =
        hat_mem_align(sizeof(hat_sbs_tuple_t)) + sizeof(hat_sbs_t *) * len;

    _Bool size_ok = reg && hat_mem_region_available(reg) >= size;
    if (size_ok) {
        *value = hat_mem_region_alloc(reg, sizeof(hat_sbs_tuple_t));
        (*value)->base.type = HAT_SBS_TYPE_TUPLE;
        (*value)->values = hat_mem_region_alloc(reg, sizeof(hat_sbs_t *) * len);
        (*value)->len = len;
    }

    uint8_t *temp_rest = data;
    size_t temp_rest_len = data_len;
    for (size_t i = 0; i < len; ++i) {
        hat_sbs_t **temp_value = size_ok ? (*value)->values + i : NULL;
        size_t available = size_ok ? hat_mem_region_available(reg) : 0;
        ssize_t err = hat_sbs_decode(
            size_ok ? reg : NULL, def->builtin.tuple_d.defs[i], temp_rest,
            temp_rest_len, temp_value, &temp_rest, &temp_rest_len);
        if (err < 0) {
            return err;
        } else if (err) {
            size += hat_mem_align(err);
            size_ok = 0;
        } else if (size_ok) {
            size += available - hat_mem_region_available(reg);
        }
    }

    if (!size_ok)
        return size;

    if (rest)
        *rest = temp_rest;
    if (rest_len)
        *rest_len = temp_rest_len;

    return HAT_SBS_SUCCESS;
}


static ssize_t encode_tuple(hat_sbs_def_t *def, hat_sbs_tuple_t *value,
                            uint8_t *data, size_t data_cap, size_t *data_len) {
    if (data && !data_len)
        HAT_SBS_ERROR;

    if (def->builtin.tuple_d.defs_len != value->len)
        return HAT_SBS_ERROR;

    size_t temp_data_len;
    size_t size = 0;
    _Bool size_ok = data ? 1 : 0;
    for (size_t i = 0; i < value->len; ++i) {
        ssize_t err =
            hat_sbs_encode(def->builtin.tuple_d.defs[i], value->values[i],
                           size_ok ? data + size : NULL,
                           size_ok ? data_cap - size : 0, &temp_data_len);
        if (err < 0) {
            return err;
        } else if (err) {
            size += err;
            size_ok = 0;
        } else if (size_ok) {
            size += temp_data_len;
        }
    }

    if (!size_ok)
        return size;

    *data_len = size;

    return HAT_SBS_SUCCESS;
}


static ssize_t decode_union(hat_mem_region_t *reg, hat_sbs_def_t *def,
                            uint8_t *data, size_t data_len,
                            hat_sbs_union_t **value, uint8_t **rest,
                            size_t *rest_len) {
    size_t size = hat_mem_align(sizeof(hat_sbs_union_t));
    if (!def->builtin.union_d.defs_len) {
        if (!reg || hat_mem_region_available(reg) < size)
            return size;

        *value = hat_mem_region_alloc(reg, sizeof(hat_sbs_tuple_t));
        (*value)->base.type = HAT_SBS_TYPE_UNION;
        (*value)->value = NULL;
        (*value)->id = 0;
        return HAT_SBS_SUCCESS;
    }

    hat_mem_region_t temp_reg;
    size_t temp_reg_cap = sizeof(hat_sbs_integer_t) + HAT_MEM_ALIGNMENT;
    uint8_t temp_reg_data[temp_reg_cap];
    hat_mem_region_init(&temp_reg, temp_reg_data, temp_reg_cap);

    hat_sbs_integer_t *temp_int;
    uint8_t *temp_rest;
    size_t temp_rest_len;
    if (decode_integer(&temp_reg, data, data_len, &temp_int, &temp_rest,
                       &temp_rest_len))
        return HAT_SBS_ERROR;

    size_t id = temp_int->value;
    if (id >= def->builtin.union_d.defs_len)
        return HAT_SBS_ERROR;

    _Bool size_ok = reg && hat_mem_region_available(reg) >= size;
    if (size_ok) {
        *value = hat_mem_region_alloc(reg, sizeof(hat_sbs_array_t));
        (*value)->base.type = HAT_SBS_TYPE_UNION;
        (*value)->id = id;
    }

    hat_sbs_t **temp_value = size_ok ? &((*value)->value) : NULL;
    ssize_t err = hat_sbs_decode(
        size_ok ? reg : NULL, def->builtin.union_d.defs[id], temp_rest,
        temp_rest_len, temp_value, &temp_rest, &temp_rest_len);

    if (err < 0)
        return err;

    if (err || !size_ok)
        return size + err;

    if (rest)
        *rest = temp_rest;
    if (rest_len)
        *rest_len = temp_rest_len;

    return HAT_SBS_SUCCESS;
}


static ssize_t encode_union(hat_sbs_def_t *def, hat_sbs_union_t *value,
                            uint8_t *data, size_t data_cap, size_t *data_len) {
    if (data && !data_len)
        HAT_SBS_ERROR;

    if (!def->builtin.union_d.defs_len && !value->value) {
        if (data_len)
            *data_len = 0;
        return HAT_SBS_SUCCESS;
    }

    if (!def->builtin.union_d.defs_len || !value->value ||
        value->id >= def->builtin.union_d.defs_len)
        return HAT_SBS_ERROR;

    size_t temp_data_len;
    hat_sbs_integer_t temp_int = {.base = {.type = HAT_SBS_TYPE_INTEGER},
                                  .value = value->id};
    ssize_t err = encode_integer(&temp_int, data, data_cap, &temp_data_len);
    size_t size = err ? err : temp_data_len;
    _Bool size_ok = !err;

    err = hat_sbs_encode(def->builtin.union_d.defs[value->id], value->value,
                         size_ok ? data + size : NULL,
                         size_ok ? data_cap - size : 0, &temp_data_len);

    if (err < 0)
        return err;

    if (err || !size_ok)
        return size + err;

    *data_len = size + temp_data_len;

    return HAT_SBS_SUCCESS;
}


ssize_t hat_sbs_decode(hat_mem_region_t *reg, hat_sbs_def_t *def, uint8_t *data,
                       size_t data_len, hat_sbs_t **value, uint8_t **rest,
                       size_t *rest_len) {
    while (def->type == HAT_SBS_DEF_TYPE_USER)
        def = def->user.def;

    if (def->builtin.type == HAT_SBS_TYPE_BOOLEAN) {
        return decode_boolean(reg, data, data_len, (hat_sbs_boolean_t **)value,
                              rest, rest_len);
    } else if (def->builtin.type == HAT_SBS_TYPE_INTEGER) {
        return decode_integer(reg, data, data_len, (hat_sbs_integer_t **)value,
                              rest, rest_len);
    } else if (def->builtin.type == HAT_SBS_TYPE_FLOAT) {
        return decode_float(reg, data, data_len, (hat_sbs_float_t **)value,
                            rest, rest_len);
    } else if (def->builtin.type == HAT_SBS_TYPE_STRING) {
        return decode_string(reg, data, data_len, (hat_sbs_string_t **)value,
                             rest, rest_len);
    } else if (def->builtin.type == HAT_SBS_TYPE_BYTES) {
        return decode_bytes(reg, data, data_len, (hat_sbs_bytes_t **)value,
                            rest, rest_len);
    } else if (def->builtin.type == HAT_SBS_TYPE_ARRAY) {
        return decode_array(reg, def, data, data_len, (hat_sbs_array_t **)value,
                            rest, rest_len);
    } else if (def->builtin.type == HAT_SBS_TYPE_TUPLE) {
        return decode_tuple(reg, def, data, data_len, (hat_sbs_tuple_t **)value,
                            rest, rest_len);
    } else if (def->builtin.type == HAT_SBS_TYPE_UNION) {
        return decode_union(reg, def, data, data_len, (hat_sbs_union_t **)value,
                            rest, rest_len);
    }
    return HAT_SBS_ERROR;
}


ssize_t hat_sbs_encode(hat_sbs_def_t *def, hat_sbs_t *value, uint8_t *data,
                       size_t data_cap, size_t *data_len) {
    while (def->type == HAT_SBS_DEF_TYPE_USER)
        def = def->user.def;

    if (def->builtin.type != value->type)
        return HAT_SBS_ERROR;

    if (def->builtin.type == HAT_SBS_TYPE_BOOLEAN) {
        return encode_boolean((hat_sbs_boolean_t *)value, data, data_cap,
                              data_len);
    } else if (def->builtin.type == HAT_SBS_TYPE_INTEGER) {
        return encode_integer((hat_sbs_integer_t *)value, data, data_cap,
                              data_len);
    } else if (def->builtin.type == HAT_SBS_TYPE_FLOAT) {
        return encode_float((hat_sbs_float_t *)value, data, data_cap, data_len);
    } else if (def->builtin.type == HAT_SBS_TYPE_STRING) {
        return encode_string((hat_sbs_string_t *)value, data, data_cap,
                             data_len);
    } else if (def->builtin.type == HAT_SBS_TYPE_BYTES) {
        return encode_bytes((hat_sbs_bytes_t *)value, data, data_cap, data_len);
    } else if (def->builtin.type == HAT_SBS_TYPE_ARRAY) {
        return encode_array(def, (hat_sbs_array_t *)value, data, data_cap,
                            data_len);
    } else if (def->builtin.type == HAT_SBS_TYPE_TUPLE) {
        return encode_tuple(def, (hat_sbs_tuple_t *)value, data, data_cap,
                            data_len);
    } else if (def->builtin.type == HAT_SBS_TYPE_UNION) {
        return encode_union(def, (hat_sbs_union_t *)value, data, data_cap,
                            data_len);
    }
    return HAT_SBS_ERROR;
}
