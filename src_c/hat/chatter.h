#ifndef HAT_CHATTER_H
#define HAT_CHATTER_H

#include <stdint.h>
#include "buff.h"

#define HAT_CHATTER_INITIAL_BUFFER_SIZE 4096
#define HAT_CHATTER_MAX_ACTIVE_TIMEOUTS 32
#define HAT_CHATTER_PING_PERIOD (30 * 1000)
#define HAT_CHATTER_PING_TIMEOUT (10 * 1000)

#define HAT_CHATTER_SUCCESS 0
#define HAT_CHATTER_ERROR 1

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    uint8_t *module;
    size_t module_len;
    uint8_t *type;
    size_t type_len;
    uint8_t *data;
    size_t data_len;
} hat_chatter_msg_data_t;

typedef struct {
    _Bool owner;
    int64_t first;
} hat_chatter_conv_t;

typedef struct {
    hat_chatter_msg_data_t data;
    hat_chatter_conv_t conv;
    _Bool first;
    _Bool last;
    _Bool token;
} hat_chatter_msg_t;

typedef void (*hat_chatter_realloc_cb)(void *ctx, hat_buff_t *buff,
                                       size_t size);
typedef void (*hat_chatter_msg_cb)(void *ctx, hat_chatter_msg_t *msg);
typedef void (*hat_chatter_write_cb)(void *ctx, uint8_t *data, size_t data_len);
typedef void (*hat_chatter_timeout_cb)(void *ctx, hat_chatter_conv_t *conv);

typedef struct {
    void *ctx;
    uint64_t timestamp;
    hat_chatter_realloc_cb realloc_cb;
    hat_chatter_msg_cb msg_cb;
    hat_chatter_write_cb write_cb;
    hat_chatter_timeout_cb timeout_cb;
    hat_buff_t buff;
    struct {
        hat_chatter_conv_t conv;
        uint64_t timestamp;
    } timeouts[HAT_CHATTER_MAX_ACTIVE_TIMEOUTS];
    size_t timeouts_len;
    uint64_t last_msg_id;
    uint64_t last_ping_timestamp;
} hat_chatter_conn_t;


void hat_chatter_init(hat_chatter_conn_t *conn, void *ctx, uint64_t timestamp,
                      hat_chatter_realloc_cb realloc_cb,
                      hat_chatter_msg_cb msg_cb, hat_chatter_write_cb write_cb,
                      hat_chatter_timeout_cb timeout_cb);
int hat_chatter_set_timestamp(hat_chatter_conn_t *conn, uint64_t timestamp);
int hat_chatter_feed(hat_chatter_conn_t *conn, hat_buff_t *data);
int hat_chatter_send(hat_chatter_conn_t *conn, hat_chatter_msg_data_t *msg_data,
                     hat_chatter_conv_t *conv, _Bool first, _Bool last,
                     _Bool token, uint64_t timeout);

#ifdef __cplusplus
}
#endif

#endif
