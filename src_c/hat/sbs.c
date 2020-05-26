#include <string.h>
#include "sbs.h"


static inline size_t buf_free(hat_sbs_buf_t *buf) {
    return buf->cap - buf->len;
}


static inline void buf_move(hat_sbs_buf_t *buf, size_t size) {
    buf->data += size;
    buf->len -= size;
    buf->cap -= size;
}


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


static ssize_t decode_boolean(hat_sbs_buf_t *data, hat_sbs_buf_t *buf,
                              hat_sbs_boolean_t **value) {
    if (data->len < 1)
        return HAT_SBS_ERROR;
    size_t size = sizeof(hat_sbs_boolean_t);
    if (!buf || buf_free(buf) < size)
        return size;
    *value = (hat_sbs_boolean_t *)(buf->data + buf->len);
    buf->len += size;
    (*value)->base.type = HAT_SBS_TYPE_BOOLEAN;
    (*value)->value = data->data[0];
    buf_move(data, size);
    return HAT_SBS_SUCCESS;
}


static ssize_t encode_boolean(hat_sbs_boolean_t *value, hat_sbs_buf_t *data) {
    if (!data || buf_free(data) < 1)
        return 1;
    data->data[data->len] = value->value ? 0x01 : 0x00;
    data->len += 1;
    return HAT_SBS_SUCCESS;
}


static ssize_t decode_integer(hat_sbs_buf_t *data, hat_sbs_buf_t *buf,
                              hat_sbs_integer_t **value) {
    if (data->len < 1)
        return HAT_SBS_ERROR;
    int64_t v = data->data[0] & 0x40 ? -1 : 0;
    for (;;) {
        if (data->len < 1)
            return HAT_SBS_ERROR;
        v = (v << 7) | (data->data[0] & 0x7F);
        if (!(data->data[0] & 0x80))
            break;
        buf_move(data, 1);
    }
    size_t size = sizeof(hat_sbs_integer_t);
    if (!buf || buf_free(buf) < size)
        return size;
    *value = (hat_sbs_integer_t *)(buf->data + buf->len);
    buf->len += size;
    (*value)->base.type = HAT_SBS_TYPE_INTEGER;
    (*value)->value = v;
    return HAT_SBS_SUCCESS;
}


static ssize_t encode_integer(hat_sbs_integer_t *value, hat_sbs_buf_t *data) {
    size_t size = 1;
    int64_t v = value->value;
    while (v != 0 && v != -1) {
        v >>= 7;
        size += 1;
    }
    if (!data || buf_free(data) < size)
        return size;
    v = value->value;
    for (size_t i = 0; i < size; ++i) {
        data->data[data->len + i] = 0x80 | ((v >> ((size - i - 1) * 7)) & 0x7F);
    }
    data->len += size;
    return HAT_SBS_SUCCESS;
}


static ssize_t decode_float(hat_sbs_buf_t *data, hat_sbs_buf_t *buf,
                            hat_sbs_float_t **value) {
    if (data->len < 8)
        return HAT_SBS_ERROR;
    size_t size = sizeof(hat_sbs_float_t);
    if (!buf || buf_free(buf) < size)
        return size;
    *value = (hat_sbs_float_t *)(buf->data + buf->len);
    buf->len += size;
    (*value)->base.type = HAT_SBS_TYPE_FLOAT;
    memcpy(&((*value)->value), data->data, 8);
    if (is_little_endian())
        swap_endians((uint8_t *)&((*value)->value), 8);
    buf_move(data, 8);
    return HAT_SBS_SUCCESS;
}


static ssize_t encode_float(hat_sbs_float_t *value, hat_sbs_buf_t *data) {
    if (!data || buf_free(data) < 8)
        return 8;
    memcpy(data->data + data->len, &(value->value), 8);
    if (is_little_endian())
        swap_endians(data->data + data->len, 8);
    data->len += 8;
    return HAT_SBS_SUCCESS;
}


static ssize_t decode_string(hat_sbs_buf_t *data, hat_sbs_buf_t *buf,
                             hat_sbs_string_t **value) {
    uint8_t temp_buf_data[sizeof(hat_sbs_integer_t)];
    hat_sbs_buf_t temp_buf = {
        .data = temp_buf_data, .len = 0, .cap = sizeof(hat_sbs_integer_t)};
    hat_sbs_integer_t *temp_int;
    if (decode_integer(data, &temp_buf, &temp_int))
        return HAT_SBS_ERROR;
    size_t len = temp_int->value;
    if (data->len < len)
        return HAT_SBS_ERROR;
    size_t size = sizeof(hat_sbs_string_t) + len + 1;
    if (!buf || buf_free(buf) < size)
        return size;
    *value = (hat_sbs_string_t *)(buf->data + buf->len);
    buf->len += sizeof(hat_sbs_string_t);
    (*value)->base.type = HAT_SBS_TYPE_STRING;
    (*value)->value = buf->data + buf->len;
    buf->len += len + 1;
    memcpy((*value)->value, data->data, len);
    (*value)->value[len] = 0;
    buf_move(data, len);
    return HAT_SBS_SUCCESS;
}


static ssize_t encode_string(hat_sbs_string_t *value, hat_sbs_buf_t *data) {
    size_t len = strlen(value->value);
    hat_sbs_integer_t temp_int = {.base = {.type = HAT_SBS_TYPE_INTEGER},
                                  .value = len};
    size_t size = encode_integer(&temp_int, NULL) + len;
    if (!data || buf_free(data) < size)
        return size;
    encode_integer(&temp_int, data);
    memcpy(data->data + data->len, value->value, len);
    data->len += len;
    return HAT_SBS_SUCCESS;
}


static ssize_t decode_bytes(hat_sbs_buf_t *data, hat_sbs_buf_t *buf,
                            hat_sbs_bytes_t **value) {
    uint8_t temp_buf_data[sizeof(hat_sbs_integer_t)];
    hat_sbs_buf_t temp_buf = {
        .data = temp_buf_data, .len = 0, .cap = sizeof(hat_sbs_integer_t)};
    hat_sbs_integer_t *temp_int;
    if (decode_integer(data, &temp_buf, &temp_int))
        return HAT_SBS_ERROR;
    size_t len = temp_int->value;
    if (data->len < len)
        return HAT_SBS_ERROR;
    size_t size = sizeof(hat_sbs_bytes_t) + len;
    if (!buf || buf_free(buf) < size)
        return size;
    *value = (hat_sbs_bytes_t *)(buf->data + buf->len);
    buf->len += sizeof(hat_sbs_bytes_t);
    (*value)->base.type = HAT_SBS_TYPE_BYTES;
    (*value)->value = buf->data + buf->len;
    buf->len += len;
    memcpy((*value)->value, data->data, len);
    buf_move(data, len);
    return HAT_SBS_SUCCESS;
}


static ssize_t encode_bytes(hat_sbs_bytes_t *value, hat_sbs_buf_t *data) {
    hat_sbs_integer_t temp_int = {.base = {.type = HAT_SBS_TYPE_INTEGER},
                                  .value = value->len};
    size_t size = encode_integer(&temp_int, NULL) + value->len;
    if (!data || buf_free(data) < size)
        return size;
    encode_integer(&temp_int, data);
    memcpy(data->data + data->len, value->value, value->len);
    data->len += value->len;
    return HAT_SBS_SUCCESS;
}


static ssize_t decode_array(hat_sbs_def_t *def, hat_sbs_buf_t *data,
                            hat_sbs_buf_t *buf, hat_sbs_array_t **value) {
    uint8_t temp_buf_data[sizeof(hat_sbs_integer_t)];
    hat_sbs_buf_t temp_buf = {
        .data = temp_buf_data, .len = 0, .cap = sizeof(hat_sbs_integer_t)};
    hat_sbs_integer_t *temp_int;
    if (decode_integer(data, &temp_buf, &temp_int))
        return HAT_SBS_ERROR;
    size_t len = temp_int->value;
    size_t size = sizeof(hat_sbs_array_t) + sizeof(hat_sbs_t *) * len;
    _Bool size_ok = buf && (buf_free(buf) < size);
    if (size_ok) {
        *value = (hat_sbs_array_t *)(buf->data + buf->len);
        buf->len += sizeof(hat_sbs_array_t);
        (*value)->base.type = HAT_SBS_TYPE_ARRAY;
        (*value)->values = (hat_sbs_t **)(buf->data + buf->len);
        buf->len += sizeof(hat_sbs_t *) * len;
        (*value)->len = len;
    }
    for (size_t i = 0; i < len; ++i) {
        hat_sbs_buf_t *temp_buf = size_ok ? buf : NULL;
        hat_sbs_t **temp_value = size_ok ? (*value)->values + i : NULL;
        size_t old_buf_len = buf ? buf->len : 0;
        ssize_t err = hat_sbs_decode(def->builtin.array_d.def, data, temp_buf,
                                     temp_value);
        if (err < 0)
            return err;
        if (err) {
            size += err;
            size_ok = 0;
        } else if (buf) {
            size += buf->len - old_buf_len;
        }
    }
    if (!size_ok)
        return size;
    return HAT_SBS_SUCCESS;
}


static ssize_t encode_array(hat_sbs_def_t *def, hat_sbs_array_t *value,
                            hat_sbs_buf_t *data) {
    hat_sbs_integer_t temp_int = {.base = {.type = HAT_SBS_TYPE_INTEGER},
                                  .value = value->len};
    size_t old_data_len = data ? data->len : 0;
    size_t err = encode_integer(&temp_int, data);
    size_t size = err ? err : data->len - old_data_len;
    _Bool size_ok = !err;
    for (size_t i = 0; i < value->len; ++i) {
        hat_sbs_buf_t *temp_data = size_ok ? data : NULL;
        old_data_len = data ? data->len : 0;
        err = hat_sbs_encode(def->builtin.array_d.def, value->values[i],
                             temp_data);
        if (err < 0)
            return err;
        if (err) {
            size += err;
            size_ok = 0;
        } else if (data) {
            size += data->len - old_data_len;
        }
    }
    if (!size_ok)
        return size;
    return HAT_SBS_SUCCESS;
}


static ssize_t decode_tuple(hat_sbs_def_t *def, hat_sbs_buf_t *data,
                            hat_sbs_buf_t *buf, hat_sbs_tuple_t **value) {
    size_t len = def->builtin.tuple_d.defs_len;
    size_t size = sizeof(hat_sbs_tuple_t) + sizeof(hat_sbs_t *) * len;
    _Bool size_ok = buf && (buf_free(buf) < size);
    if (size_ok) {
        *value = (hat_sbs_tuple_t *)(buf->data + buf->len);
        buf->len += sizeof(hat_sbs_tuple_t);
        (*value)->base.type = HAT_SBS_TYPE_TUPLE;
        (*value)->values = (hat_sbs_t **)(buf->data + buf->len);
        buf->len += sizeof(hat_sbs_t *) * len;
        (*value)->len = len;
    }
    for (size_t i = 0; i < len; ++i) {
        hat_sbs_buf_t *temp_buf = size_ok ? buf : NULL;
        hat_sbs_t **temp_value = size_ok ? (*value)->values + i : NULL;
        size_t old_buf_len = buf ? buf->len : 0;
        ssize_t err = hat_sbs_decode(def->builtin.tuple_d.defs[i], data,
                                     temp_buf, temp_value);
        if (err < 0)
            return err;
        if (err) {
            size += err;
            size_ok = 0;
        } else if (buf) {
            size += buf->len - old_buf_len;
        }
    }
    if (!size_ok)
        return size;
    return HAT_SBS_SUCCESS;
}


static ssize_t encode_tuple(hat_sbs_def_t *def, hat_sbs_tuple_t *value,
                            hat_sbs_buf_t *data) {
    if (def->builtin.tuple_d.defs_len != value->len)
        return HAT_SBS_ERROR;
    size_t size = 0;
    _Bool size_ok = data ? 1 : 0;
    for (size_t i = 0; i < value->len; ++i) {
        hat_sbs_buf_t *temp_data = size_ok ? data : NULL;
        size_t old_data_len = data ? data->len : 0;
        ssize_t err = hat_sbs_encode(def->builtin.tuple_d.defs[i],
                                     value->values[i], temp_data);
        if (err < 0)
            return err;
        if (err) {
            size += err;
            size_ok = 0;
        } else if (data) {
            size += data->len - old_data_len;
        }
    }
    if (!size_ok)
        return size;
    return HAT_SBS_SUCCESS;
}


static ssize_t decode_union(hat_sbs_def_t *def, hat_sbs_buf_t *data,
                            hat_sbs_buf_t *buf, hat_sbs_union_t **value) {
    size_t size = sizeof(hat_sbs_union_t);
    if (!def->builtin.union_d.defs_len) {
        if (!buf || buf_free(buf) < size)
            return size;
        *value = (hat_sbs_union_t *)(buf->data + buf->len);
        buf->len += size;
        (*value)->base.type = HAT_SBS_TYPE_UNION;
        (*value)->value = NULL;
        (*value)->id = 0;
        return HAT_SBS_SUCCESS;
    }
    uint8_t temp_buf_data[sizeof(hat_sbs_integer_t)];
    hat_sbs_buf_t temp_buf = {
        .data = temp_buf_data, .len = 0, .cap = sizeof(hat_sbs_integer_t)};
    hat_sbs_integer_t *temp_int;
    if (decode_integer(data, &temp_buf, &temp_int))
        return HAT_SBS_ERROR;
    size_t id = temp_int->value;
    if (id >= def->builtin.union_d.defs_len)
        return HAT_SBS_ERROR;
    _Bool size_ok = buf && (buf_free(buf) < size);
    if (size_ok) {
        *value = (hat_sbs_union_t *)(buf->data + buf->len);
        buf->len += size;
        (*value)->base.type = HAT_SBS_TYPE_UNION;
        (*value)->id = id;
    }
    hat_sbs_t **temp_value = size_ok ? &((*value)->value) : NULL;
    ssize_t err = hat_sbs_decode(def->builtin.union_d.defs[id], data,
                                 (size_ok ? buf : NULL), temp_value);
    if (err < 0)
        return err;
    if (err || !size_ok)
        return size + err;
    return HAT_SBS_SUCCESS;
}


static ssize_t encode_union(hat_sbs_def_t *def, hat_sbs_union_t *value,
                            hat_sbs_buf_t *data) {
    if (!def->builtin.union_d.defs_len && !value->value)
        return HAT_SBS_SUCCESS;
    if (!def->builtin.union_d.defs_len || !value->value ||
        value->id >= def->builtin.union_d.defs_len)
        return HAT_SBS_ERROR;
    hat_sbs_integer_t temp_int = {.base = {.type = HAT_SBS_TYPE_INTEGER},
                                  .value = value->id};
    size_t old_data_len = data ? data->len : 0;
    size_t err = encode_integer(&temp_int, data);
    size_t size = err ? err : data->len - old_data_len;
    _Bool size_ok = !err;
    hat_sbs_buf_t *temp_data = size_ok ? data : NULL;
    err = hat_sbs_encode(def->builtin.union_d.defs[value->id], value->value,
                         temp_data);
    if (err < 0)
        return err;
    if (err || !size_ok)
        return size + err;
    return HAT_SBS_SUCCESS;
}


ssize_t hat_sbs_decode(hat_sbs_def_t *def, hat_sbs_buf_t *data,
                       hat_sbs_buf_t *buf, hat_sbs_t **value) {
    while (def->type == HAT_SBS_DEF_TYPE_USER)
        def = def->user.def;
    if (def->builtin.type == HAT_SBS_TYPE_BOOLEAN) {
        return decode_boolean(data, buf, (hat_sbs_boolean_t **)value);
    } else if (def->builtin.type == HAT_SBS_TYPE_INTEGER) {
        return decode_integer(data, buf, (hat_sbs_integer_t **)value);
    } else if (def->builtin.type == HAT_SBS_TYPE_FLOAT) {
        return decode_float(data, buf, (hat_sbs_float_t **)value);
    } else if (def->builtin.type == HAT_SBS_TYPE_STRING) {
        return decode_string(data, buf, (hat_sbs_string_t **)value);
    } else if (def->builtin.type == HAT_SBS_TYPE_BYTES) {
        return decode_bytes(data, buf, (hat_sbs_bytes_t **)value);
    } else if (def->builtin.type == HAT_SBS_TYPE_ARRAY) {
        return decode_array(def, data, buf, (hat_sbs_array_t **)value);
    } else if (def->builtin.type == HAT_SBS_TYPE_TUPLE) {
        return decode_tuple(def, data, buf, (hat_sbs_tuple_t **)value);
    } else if (def->builtin.type == HAT_SBS_TYPE_UNION) {
        return decode_union(def, data, buf, (hat_sbs_union_t **)value);
    }
    return HAT_SBS_ERROR;
}


ssize_t hat_sbs_encode(hat_sbs_def_t *def, hat_sbs_t *value,
                       hat_sbs_buf_t *data) {
    while (def->type == HAT_SBS_DEF_TYPE_USER)
        def = def->user.def;
    if (def->builtin.type != value->type)
        return HAT_SBS_ERROR;
    if (def->builtin.type == HAT_SBS_TYPE_BOOLEAN) {
        return encode_boolean((hat_sbs_boolean_t *)value, data);
    } else if (def->builtin.type == HAT_SBS_TYPE_INTEGER) {
        return encode_integer((hat_sbs_integer_t *)value, data);
    } else if (def->builtin.type == HAT_SBS_TYPE_FLOAT) {
        return encode_float((hat_sbs_float_t *)value, data);
    } else if (def->builtin.type == HAT_SBS_TYPE_STRING) {
        return encode_string((hat_sbs_string_t *)value, data);
    } else if (def->builtin.type == HAT_SBS_TYPE_BYTES) {
        return encode_bytes((hat_sbs_bytes_t *)value, data);
    } else if (def->builtin.type == HAT_SBS_TYPE_ARRAY) {
        return encode_array(def, (hat_sbs_array_t *)value, data);
    } else if (def->builtin.type == HAT_SBS_TYPE_TUPLE) {
        return encode_tuple(def, (hat_sbs_tuple_t *)value, data);
    } else if (def->builtin.type == HAT_SBS_TYPE_UNION) {
        return encode_union(def, (hat_sbs_union_t *)value, data);
    }
    return HAT_SBS_ERROR;
}
