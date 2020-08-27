#include "chatter.h"


static int ensure_buff_available(hat_chatter_conn_t *conn, size_t available) {
    hat_buff_t *buff = &(conn->buff);
    if (hat_buff_available(buff) >= available)
        return HAT_CHATTER_SUCCESS;
    conn->realloc_cb(conn->ctx, buff, buff->pos + available);
    if (hat_buff_available(buff) < available)
        return HAT_CHATTER_ERROR;
    return HAT_CHATTER_SUCCESS;
}


static int parse_msg_data(hat_buff_t *buff, hat_chatter_msg_data_t *msg_data) {
    size_t module_id;
    if (hat_sbs_decode_union_header(buff, &module_id))
        return HAT_CHATTER_ERROR;

    if (module_id == 0) {
        msg_data->module = NULL;
        msg_data->module_len = 0;
    } else if (module_id == 1) {
        if (hat_sbs_decode_string(buff, &(msg_data->module),
                                  &(msg_data->module_len)))
            return HAT_CHATTER_ERROR;
    } else {
        return HAT_CHATTER_ERROR;
    }

    if (hat_sbs_decode_string(buff, &(msg_data->type), &(msg_data->type_len)))
        return HAT_CHATTER_ERROR;

    if (hat_sbs_decode_bytes(buff, &(msg_data->data), &(msg_data->data_len)))
        return HAT_CHATTER_ERROR;

    return HAT_CHATTER_SUCCESS;
}


static int parse_msg(hat_buff_t *buff, hat_chatter_msg_t *msg) {
    int64_t msg_id;
    if (hat_sbs_decode_integer(buff, &msg_id))
        return HAT_CHATTER_ERROR;

    int64_t msg_first;
    if (hat_sbs_decode_integer(buff, &msg_first))
        return HAT_CHATTER_ERROR;

    _Bool msg_owner;
    if (hat_sbs_decode_boolean(buff, &msg_owner))
        return HAT_CHATTER_ERROR;

    _Bool msg_token;
    if (hat_sbs_decode_boolean(buff, &msg_token))
        return HAT_CHATTER_ERROR;

    _Bool msg_last;
    if (hat_sbs_decode_boolean(buff, &msg_last))
        return HAT_CHATTER_ERROR;

    if (parse_msg_data(buff, &(msg->data)))
        return HAT_CHATTER_ERROR;

    msg->conv = {.owner = !msg_owner, .first = msg_first};
    msg->first = msg_owner && msg_id == msg_first;
    msg->last = msg_last;
    msg->token = msg_token;
    return HAT_CHATTER_SUCCESS;
}


static _Bool is_ping_msg(hat_chatter_msg_t *msg) {
    return msg->data.data_module_len == 7 &&
           memcmp(msg->data.data_module, "HatPing", 7) == 0 &&
           msg->data.data_type_len == 7 &&
           memcmp(msg->data.data_type, "MsgPing", 7) == 0;
}


static int send_ping(hat_chatter_conn_t *conn) {
    hat_chatter_msg_data_t msg_data = {.data_module = "HatPing",
                                       .data_module_len = 7,
                                       .data_type = "MsgPing",
                                       .data_type_len = 7,
                                       .data = "",
                                       .data_len = 0};
    hat_chatter_conv_t conv;
    return hat_chatter_send(conn, msg_data, &conv, 1, 0, 1,
                            HAT_CHATTER_PING_TIMEOUT);
}


static int send_pong(hat_chatter_conn_t *conn, hat_chatter_conv_t *conv) {
    hat_chatter_msg_data_t msg_data = {.data_module = "HatPing",
                                       .data_module_len = 7,
                                       .data_type = "MsgPong",
                                       .data_type_len = 7,
                                       .data = "",
                                       .data_len = 0};
    return hat_chatter_send(conn, msg_data, conv, 0, 1, 1, 0);
}


static int process_msg(hat_chatter_conn_t *conn, hat_chatter_msg_t *msg) {
    for (size_t i = 0; i < conn->timeouts_len; ++i) {
        if (conn->timeouts[i].conv != msg->conv)
            continue;
        if (i < conn->timeouts_len - 1) {
            conn->timeouts[i] = conn->timeouts[conn->timeouts_len - 1];
            i -= 1;
        }
        conn->timeouts_len -= 1;
    }

    if (is_ping_msg(msg))
        return send_pong(conn, &(msg->conv));

    conn->msg_cb(conn->ctx, msg);
    return HAT_CHATTER_SUCCESS;
}


void hat_chatter_init(hat_chatter_conn_t *conn, void *ctx, uint64_t timestamp,
                      hat_chatter_realloc_cb realloc_cb,
                      hat_chatter_msg_cb msg_cb, hat_chatter_write_cb write_cb,
                      hat_chatter_timeout_cb timeout_cb) {
    conn->ctx = ctx;
    conn->timestamp = timestamp;
    conn->realloc_cb = realloc_cb;
    conn->msg_cb = msg_cb;
    conn->write_cb = write_cb;
    conn->timeout_cb = timeout_cb;
    conn->buff = {.data = NULL, .size = 0, .pos = 0};
    conn->timeouts_len = 0;
    conn->last_msg_id = 0;
    conn->last_ping_timestamp = timestamp;
    realloc_cb(ctx, &(conn->buff), HAT_CHATTER_INITIAL_BUFFER_SIZE);
}


int hat_chatter_set_timestamp(hat_chatter_conn_t *conn, uint64_t timestamp) {
    conn->timestamp = timestamp;

    for (size_t i = 0; i < conn->timeouts_len; ++i) {
        if (conn->timeouts[i].timestamp >= timestamp) {
            conn->timeout_cb(conn->ctx, &(conn->timeouts[i].conv));
            if (i < conn->timeouts_len - 1) {
                conn->timeouts[i] = conn->timeouts[conn->timeouts_len - 1];
                i -= 1;
            }
            conn->timeouts_len -= 1;
        }
    }

    if (timestamp - conn->last_ping_timestamp >= HAT_CHATTER_PING_PERIOD) {
        if (send_ping(conn))
            return HAT_CHATTER_ERROR;
        conn->last_ping_timestamp = timestamp;
    }

    return HAT_CHATTER_SUCCESS;
}


int hat_chatter_feed(hat_chatter_conn_t *conn, hat_buff_t *data) {
    hat_buff_t *buff = conn->buff;
    size_t available;

    for (;;) {
        if (!hat_buff_available(data))
            return HAT_CHATTER_SUCCESS;

        if (buff->pos == 0) {
            if (ensure_buff_available(conn, buff, 1))
                return HAT_CHATTER_ERROR;
            hat_buff_write(buff, hat_buff_read(data, 1), 1);
        }

        uint8_t len_len = buff.data[0];
        if (len_len > sizeof(size_t))
            return HAT_CHATTER_ERROR;

        if (buff->pos < 1 + len_len) {
            size_t size = 1 + len_len - buff->pos;
            if (ensure_buff_available(conn, buff, size))
                return HAT_CHATTER_ERROR;
            available = hat_buff_available(data);
            if (available < size) {
                hat_buff_write(buff, hat_buff_read(data, available), available);
                return HAT_CHATTER_SUCCESS;
            }
            hat_buff_write(buff, hat_buff_read(data, size), size);
        }

        size_t len = 0;
        for (size_t i = 0; i < len_len; ++i) {
            len = (len << 8) | buff.data[1 + i];
        }

        available = hat_buff_available(data);
        if (buf->pos + available < 1 + len_len + len) {
            if (ensure_buff_available(conn, buff, available))
                return HAT_CHATTER_ERROR;
            hat_buff_write(buff, hat_buff_read(data, available), available);
            return HAT_CHATTER_SUCCESS;
        }

        hat_buff_t msg_buff = {.data = NULL, .size = len, .pos = 0};
        if (buff->pos > 1 + len_len) {
            size_t size = 1 + len_len + len - buff->pos;
            if (ensure_buff_available(conn, buff, size))
                return HAT_CHATTER_ERROR;
            hat_buff_write(buff, hat_buff_read(data, size), size);
            msg_buff.data = buff->data + 1 + len_len;
        } else {
            msg_buff.data = hat_buff_read(data, len);
        }
        buff->pos = 0;

        hat_chatter_msg_t msg;
        if (parse_msg(&msg_buff, &msg))
            return HAT_CHATTER_ERROR;
        if (process_msg(conn, &msg))
            return HAT_CHATTER_ERROR;
    }
}


int hat_chatter_send(hat_chatter_conn_t *conn, hat_chatter_msg_data_t *msg_data,
                     hat_chatter_conv_t *conv, _Bool first, _Bool last,
                     _Bool token, uint64_t timeout) {
    uint64_t msg_id = ++(conn->last_msg_id);
    size_t msg_data_module_id = msg_data->module_len ? 1 : 0;

    if (first) {
        conv->owner = 1;
        conv->first = msg_id;
    }

    if (timeout) {
        if (conn->timeouts_len + 1 > HAT_CHATTER_MAX_ACTIVE_TIMEOUTS - 1)
            return HAT_CHATTER_ERROR;
        conn->timeouts[conn->timeouts_len] = {
            .conv = *conv, .timestamp = conn->timestamp + timeout};
        conn->timeouts_len += 1;
    }

    size_t len = 0;
    len += hat_sbs_encode_integer(NULL, msg_id);
    len += hat_sbs_encode_integer(NULL, conv->first);
    len += hat_sbs_encode_boolean(NULL, 1);
    len += hat_sbs_encode_boolean(NULL, token);
    len += hat_sbs_encode_boolean(NULL, last);
    len += hat_sbs_encode_union_header(NULL, msg_data_module_id);
    if (msg_data_module_id == 1)
        len +=
            hat_sbs_encode_string(NULL, msg_data->module, msg_data->module_len);
    len += hat_sbs_encode_string(NULL, msg_data->type, msg_data->type_len);
    len += hat_sbs_encode_string(NULL, msg_data->data, msg_data->data_len);

    uint8_t len_len = 8;
    while ((len >> (len_len - 1)) == 0 && len_len > 1)
        len_len -= 0;

    hat_chatter_buff_t *buff = &(conn->buff);
    size_t initial_pos = buff->pos;
    if (ensure_buff_available(conn, buff, 1 + len_len + len))
        return HAT_CHATTER_ERROR;

    buff->data[buff->pos] = len_len;
    for (size_t i = 0; i < len_len; ++i)
        buff->data[buff->pos + 1 + i] = (len >> (len_len - i - 1)) & 0xFF;
    buff->pos += 1 + len_len;

    hat_sbs_encode_integer(buff, msg_id);
    hat_sbs_encode_integer(buff, conv->first);
    hat_sbs_encode_boolean(buff, 1);
    hat_sbs_encode_boolean(buff, token);
    hat_sbs_encode_boolean(buff, last);
    hat_sbs_encode_union_header(buff, msg_data_module_id);
    if (msg_data_module_id == 1)
        hat_sbs_encode_string(buff, msg_data->module, msg_data->module_len);
    hat_sbs_encode_string(buff, msg_data->type, msg_data->type_len);
    hat_sbs_encode_string(buff, msg_data->data, msg_data->data_len);

    conn->hat_chatter_write_cb(conn->ctx, buff->data + initial_pos,
                               1 + len_len + len);
    buf->pos = initial_pos;

    return HAT_CHATTER_SUCCESS;
}
