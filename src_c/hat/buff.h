#ifndef HAT_BUF_H
#define HAT_BUF_H

#include <stdint.h>
#include <string.h>

#define HAT_BUF_SUCCESS 0
#define HAT_BUF_ERROR 1


#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    uint8_t *data;
    size_t size;
    size_t pos;
} hat_buff_t;


static inline size_t hat_buff_available(hat_buff_t *buff) {
    return (buff && buff->size > buff->pos) ? buff->size - buff->pos : 0;
}


static inline int hat_buff_write(hat_buff_t *buff, uint8_t *data,
                                 size_t data_len) {
    if (hat_buff_available(buff) < data_len)
        return HAT_BUF_ERROR;
    memcpy(buff->data + buff->pos, data, data_len);
    buff->pos += data_len;
    return HAT_BUF_SUCCESS;
}


static inline uint8_t *hat_buff_read(hat_buff_t *buff, size_t size) {
    if (hat_buff_available(buff) < size)
        return NULL;
    uint8_t *data = buff->data + buff->pos;
    buff->pos += size;
    return data;
}

#ifdef __cplusplus
}
#endif

#endif
