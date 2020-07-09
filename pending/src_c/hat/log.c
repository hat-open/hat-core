#include "log.h"


#define BUFFERS_COUNT (HAT_LOG_MAX_ENTRIES + 1)
#define SINGLE_BUFFER_SIZE (??? + HAT_LOG_MAX_ID_SIZE + HAT_LOG_MAX_MSG_SIZE + 1)
#define READ_BUFFER_SIZE 1024

typedef enum { DISCONNECTED, CONNECTING, CONNECTED, DISCONNECTING } log_state_t;


typedef struct {
    uv_timeval64_t t;
    hat_log_level_t level;
    char id[HAT_LOG_MAX_ID_SIZE + 1];
    char msg[HAT_LOG_MAX_MSG_SIZE + 1];
} log_entry_t;


struct hat_log_t {
    uv_thread_t thread;
    uv_loop_t loop;
    uv_tcp_t tcp;
    uv_timer_t timer;
    uv_async_t async_log;
    uv_async_t async_close;
    uv_connect_t connect_req;
    uv_write_t write_req;

    struct sockaddr addr;
    log_state_t state;

    log_entry_t entries[HAT_LOG_MAX_ENTRIES + 1];
    atomic size_t entries_head;
    atomic size_t entries_tail;
    atomic size_t drop_count;
    uv_mutex_t drop_mutex;

    uv_buf_t buffers[BUFFERS_COUNT];
    size_t buffers_len;
    char *buffer_data[BUFFERS_COUNT * SINGLE_BUFFER_SIZE];

    char *read_buffer_data[READ_BUFFER_SIZE];
};


static inline size_t entries_len(hat_log_t *log) {}

static inline _Bool entries_is_empty(hat_log_t *log) {}

static inline _Bool entries_is_full(hat_log_t *log) {}

static inline log_entry_t *entries_first(hat_log_t *log) {}

static inline log_entry_t *entries_last(hat_log_t *log) {}

static inline void entries_move_first(hat_log_t *log) {}

static inline void entries_move_last(hat_log_t *log) {}

static void write_entry(log_entry_t *entry, uv_buf_t *buff) {}

static void write_drop_count(size_t drop_count, uv_buf_t *buff) {}


static voif alloc_cb(uv_handle_t *handle, size_t suggested_size,
                     uv_buf_t *buf) {
    hat_log_t *log = (hat_log_t *)handle->data;
    bug->base = log->read_buffer_data;
    buf->len = READ_BUFFER_SIZE;
}


static void tcp_close_cb(uv_handle_t *handle) {
    hat_log_t *log = (hat_log_t *)handle->data;
    log->state = DISCONNECTED;
}


static void read_cb(uv_stream_t *stream, ssize_t nread, const uv_buf_t *buf) {
    hat_log_t *log = (hat_log_t *)stream->data;
    if (nread != UV_EOF)
        return;
    log->state = DISCONNECTING;
    uv_close(&(log->tcp), tcp_close_cb);
}


static void connect_cb(uv_connect_t *req, int status) {
    hat_log_t *log = (hat_log_t *)req->data;
    if (status) {
        log->state = DISCONNECTED;
        return;
    }
    log->state = CONNECTED;
    uv_read_start(&(log->tcp), alloc_cb, read_cb);
    uv_async_send(&(log->async_log));
}


static void timer_cb(uv_timer_t *handle) {
    hat_log_t *log = (hat_log_t *)handle->data;
    if (log->state != DISCONNECTED)
        return;
    log->state = CONNECTING;
    uv_tcp_connect(&(log->connect_req), &(log->tcp), &(log->addr), connect_cb);
}


static void write_cb(uv_write_t *req, int status) {
    hat_log_t *log = (hat_log_t *)req->data;
    log->buffers_len = 0;
    uv_async_send(&(log->async_log));
}


static void async_log_cb(uv_async_t *handle) {
    hat_log_t *log = (hat_log_t *)handle->data;
    if (log->buffers_len)
        return;
    log->buffers_len = entries_len(log);
    size_t drop_count = log->drop_count;
    if (drop_count) {
        uv_mutex_lock(&(log->drop_mutex));
        drop_count = log->drop_count log->drop_count = 0;
        uv_mutex_unlock(&(log->drop_mutex));
    }
    if (!log->buffers_len && !drop_count)
        return;
    for (size_t i = 0; i < log->buffers_len; ++i) {
        entries_move_first(log);
        log_entry_t *entry = entries_first(log);
        write_entry(entry, log->buffers[i]);
    }
    if (drop_count) {
        write_drop_count(drop_count, log->buffers[log->buffers_len]);
        log->buffers_len += 1;
    }
    uv_write(&(log->write_req), &(log->tcp), log->buffers, log->buffers_len,
             write_cb);
}

static void async_close_cb(uv_async_t *handle) {
    hat_log_t *log = (hat_log_t *)handle->data;
    // TODO
    uv_stop(&(log->loop));
}


static void thread_cb(void *arg) {
    hat_log_t *log = (hat_log_t *)arg;
    uv_timer_start(&(log->timer), timer_cb, 0, HAT_LOG_CONNECT_TIMEOUT_MS);
    uv_run(&(log->loop), UV_RUN_DEFAULT);
    uv_loop_close(&(log->loop));
}


hat_log_t *hat_log_create(uv_loop_t *loop, const struct sockaddr *addr) {
    hat_log_t *log = malloc(sizeof(hat_log_t));

    log->loop.data = log;
    log->tcp.data = log;
    log->timer.data = log;
    log->async_log.data = log;
    log->async_close.data = log;
    log->connect_req.data = log;
    log->write_req.data = log;

    log->addr = *addr;
    log->state = DISCONNECTED;

    log->entries_head = 0;
    log->entries_tail = 1;

    for (size_t i = 0; i < BUFFERS_COUNT; ++i)
        log->buffers[i] = {.base = log->buffer_data + (i * SINGLE_BUFFER_SIZE),
                           .len = 0};
    log->buffers_len = 0;

    uv_loop_init(&(log->loop));
    uv_tcp_init(&(log->loop), &(log->tcp));
    uv_timer_init(&(log->loop), &(log->timer));
    uv_async_init(&(log->loop), &(log->async_log), async_log_cb);
    uv_async_init(&(log->loop), &(log->async_close), async_close_cb);
    uv_mutex_init(&(log->drop_mutex));

    uv_thread_create(&(log->thread), thread_cb, log);
    return log;
}


void hat_log_close(hat_log_t *log, hat_log_close_cb close_cb) {
    uv_async_send(&(log->async_close));
    uv_thread_join(&(log->thread));
    free(log);
}


void hat_log_log(hat_log_t *log, hat_log_level_t level, char *id, char *msg,
                 ...) {
    if (entries_is_full(log)) {
        uv_mutex_lock(&(log->drop_mutex));
        log->drop_count += 1;
        uv_mutex_unlock(&(log->drop_mutex));
        return;
    }
    va_list args;
    log_entry_t *entry = entries_last(log);
    uv_gettimeofday(&(entry->t));
    entry->level = level;
    strncpy(entry->id, id, HAT_LOG_MAX_ID_SIZE);
    entry->id[HAT_LOG_MAX_ID_SIZE] = 0;
    va_start(args, msg);
    vsnprintf(entry->msg, HAT_LOG_MAX_MSG_SIZE, msg, args);
    va_end(args);
    entry->msg[HAT_LOG_MAX_MSG_SIZE] = 0;
    entries_move_last(log);
    uv_async_send(&(log->async_log));
}
