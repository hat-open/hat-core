#include <string.h>
#include "sbs.h"

static inline bool is_little_endian() {
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
        data[data_len - i - 1] = temp;
    }
}


size_t hat_sbs_encode_boolean(hat_buff_t *buff, bool value) {
    if (!hat_buff_available(buff))
        return 1;
    buff->data[buff->pos] = value ? 0x01 : 0x00;
    buff->pos += 1;
    return HAT_SBS_SUCCESS;
}


size_t hat_sbs_encode_integer(hat_buff_t *buff, int64_t value) {
    size_t available = hat_buff_available(buff);
    size_t size = 1;
    for (;;) {
        if (size <= available)
            buff->data[buff->pos + size - 1] =
                (size == 1 ? 0x80 : 0x00) | (value & 0x7F);
        bool sign = value & 0x40;
        value >>= 7;
        if ((value == 0 && !sign) || (value == -1 && sign))
            break;
        size += 1;
    }
    if (size > available)
        return size;
    swap_endians(buff->data + buff->pos, size);
    buff->pos += size;
    return HAT_SBS_SUCCESS;
}


size_t hat_sbs_encode_float(hat_buff_t *buff, double value) {
    if (hat_buff_available(buff) < 8)
        return 8;
    memcpy(buff->data + buff->pos, &value, 8);
    if (is_little_endian())
        swap_endians(buff->data + buff->pos, 8);
    buff->pos += 8;
    return HAT_SBS_SUCCESS;
}


size_t hat_sbs_encode_string(hat_buff_t *buff, uint8_t *value,
                             size_t value_len) {
    size_t size = hat_sbs_encode_integer(NULL, value_len) + value_len;
    if (hat_buff_available(buff) < size)
        return size;
    hat_sbs_encode_integer(buff, value_len);
    return hat_buff_write(buff, value, value_len);
}


size_t hat_sbs_encode_bytes(hat_buff_t *buff, uint8_t *value,
                            size_t value_len) {
    return hat_sbs_encode_string(buff, value, value_len);
}


size_t hat_sbs_encode_array_header(hat_buff_t *buff, size_t len) {
    return hat_sbs_encode_integer(buff, len);
}


size_t hat_sbs_encode_union_header(hat_buff_t *buff, size_t id) {
    return hat_sbs_encode_integer(buff, id);
}


int hat_sbs_decode_boolean(hat_buff_t *buff, bool *value) {
    if (!hat_buff_available(buff))
        return HAT_SBS_ERROR;
    *value = buff->data[buff->pos];
    buff->pos += 1;
    return HAT_SBS_SUCCESS;
}


int hat_sbs_decode_integer(hat_buff_t *buff, int64_t *value) {
    size_t available = hat_buff_available(buff);
    size_t size = 1;
    *value = ((available && (buff->data[buff->pos] & 0x40)) ? -1 : 0);
    for (;;) {
        if (size > available)
            return HAT_SBS_ERROR;
        *value = (*value << 7) | (buff->data[buff->pos + size - 1] & 0x7F);
        if (buff->data[buff->pos + size - 1] & 0x80)
            break;
        size += 1;
    }
    buff->pos += size;
    return HAT_SBS_SUCCESS;
}


int hat_sbs_decode_float(hat_buff_t *buff, double *value) {
    if (hat_buff_available(buff) < 8)
        return HAT_SBS_ERROR;
    memcpy(value, buff->data + buff->pos, 8);
    if (is_little_endian())
        swap_endians((uint8_t *)value, 8);
    buff->pos += 8;
    return HAT_SBS_SUCCESS;
}


int hat_sbs_decode_string(hat_buff_t *buff, uint8_t **value,
                          size_t *value_len) {
    size_t pos = buff->pos;
    int64_t size;
    if (hat_sbs_decode_integer(buff, &size))
        return HAT_SBS_ERROR;
    if (hat_buff_available(buff) < size) {
        buff->pos = pos;
        return HAT_SBS_ERROR;
    }
    *value = hat_buff_read(buff, size);
    *value_len = size;
    return HAT_SBS_SUCCESS;
}


int hat_sbs_decode_bytes(hat_buff_t *buff, uint8_t **value, size_t *value_len) {
    return hat_sbs_decode_string(buff, value, value_len);
}


int hat_sbs_decode_array_header(hat_buff_t *buff, size_t *len) {
    int64_t temp_len;
    if (hat_sbs_decode_integer(buff, &temp_len))
        return HAT_SBS_ERROR;
    *len = temp_len;
    return HAT_SBS_SUCCESS;
}


int hat_sbs_decode_union_header(hat_buff_t *buff, size_t *id) {
    int64_t temp_id;
    if (hat_sbs_decode_integer(buff, &temp_id))
        return HAT_SBS_ERROR;
    *id = temp_id;
    return HAT_SBS_SUCCESS;
}
