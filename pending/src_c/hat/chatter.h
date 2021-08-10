#ifndef HAT_CHATTER_H
#define HAT_CHATTER_H

#include <stdbool.h>
#include <stdint.h>
#include "buff.h"
#include "allocator.h"

#define HAT_CHATTER_INITIAL_BUFFER_SIZE 4096
#define HAT_CHATTER_MAX_ACTIVE_TIMEOUTS 32
#define HAT_CHATTER_PING_PERIOD (30 * 1000)
#define HAT_CHATTER_PING_TIMEOUT (10 * 1000)

#define HAT_CHATTER_SUCCESS 0
#define HAT_CHATTER_ERROR 1

#ifdef __cplusplus
extern "C" {
#endif

typedef struct hat_chatter_conn_t hat_chatter_conn_t;

typedef struct {
    uint8_t *module;
    size_t module_len;
    uint8_t *type;
    size_t type_len;
    uint8_t *data;
    size_t data_len;
} hat_chatter_msg_data_t;

typedef struct {
    bool owner;
    int64_t first;
} hat_chatter_conv_t;

typedef struct {
    hat_chatter_msg_data_t data;
    hat_chatter_conv_t conv;
    bool first;
    bool last;
    bool token;
} hat_chatter_msg_t;

typedef void (*hat_chatter_msg_cb)(void *ctx, hat_chatter_msg_t *msg);
typedef void (*hat_chatter_write_cb)(void *ctx, uint8_t *data, size_t data_len);
typedef void (*hat_chatter_timeout_cb)(void *ctx, hat_chatter_conv_t *conv);


void hat_chatter_init(hat_chatter_conn_t *conn, void *ctx,
                      hat_allocator_t *alloc, uint64_t timestamp,
                      hat_chatter_msg_cb msg_cb, hat_chatter_write_cb write_cb,
                      hat_chatter_timeout_cb timeout_cb);
void hat_chatter_destroy(hat_chatter_conn_t *conn);
int hat_chatter_set_timestamp(hat_chatter_conn_t *conn, uint64_t timestamp);
int hat_chatter_feed(hat_chatter_conn_t *conn, hat_buff_t *data);
int hat_chatter_send(hat_chatter_conn_t *conn, hat_chatter_msg_data_t *msg_data,
                     hat_chatter_conv_t *conv, bool first, bool last,
                     bool token, uint64_t timeout);

#ifdef __cplusplus
}
#endif

#endif
