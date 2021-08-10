#ifndef HAT_SBS_H
#define HAT_SBS_H

#include <stdbool.h>
#include <stdint.h>
#include "buff.h"

#define HAT_SBS_SUCCESS 0
#define HAT_SBS_ERROR 1


#ifdef __cplusplus
extern "C" {
#endif

size_t hat_sbs_encode_boolean(hat_buff_t *buff, bool value);
size_t hat_sbs_encode_integer(hat_buff_t *buff, int64_t value);
size_t hat_sbs_encode_float(hat_buff_t *buff, double value);
size_t hat_sbs_encode_string(hat_buff_t *buff, uint8_t *value,
                             size_t value_len);
size_t hat_sbs_encode_bytes(hat_buff_t *buff, uint8_t *value, size_t value_len);
size_t hat_sbs_encode_array_header(hat_buff_t *buff, size_t len);
size_t hat_sbs_encode_union_header(hat_buff_t *buff, size_t id);

int hat_sbs_decode_boolean(hat_buff_t *buff, bool *value);
int hat_sbs_decode_integer(hat_buff_t *buff, int64_t *value);
int hat_sbs_decode_float(hat_buff_t *buff, double *value);
int hat_sbs_decode_string(hat_buff_t *buff, uint8_t **value, size_t *value_len);
int hat_sbs_decode_bytes(hat_buff_t *buff, uint8_t **value, size_t *value_len);
int hat_sbs_decode_array_header(hat_buff_t *buff, size_t *len);
int hat_sbs_decode_union_header(hat_buff_t *buff, size_t *id);

#ifdef __cplusplus
}
#endif

#endif
