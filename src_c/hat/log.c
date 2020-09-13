#include <stdint.h>
#include <threads.h>
#include <string.h>
#include <time.h>
#include <stdatomic.h>
#include <stdlib.h>

#include <unistd.h>
#include <sys/socket.h>
#include <netdb.h>

#include "log.h"
#include "die.h"
#include "log_socket.h"


volatile struct {
    atomic_bool running;
    hat_log_facility_t facility;
    hat_log_level_t level;
    char hostname[HAT_LOG_MAX_HOSTNAME_LEN + 1];
    char appname[HAT_LOG_MAX_APPNAME_LEN + 1];
    pid_t procid;
    char buffs[HAT_LOG_BUFF_COUNT][HAT_LOG_BUFF_SIZE];
    char *empty_buffs[HAT_LOG_BUFF_COUNT];
    size_t empty_buffs_len;
    char *full_buffs[HAT_LOG_BUFF_COUNT];
    size_t full_buffs_len;
    uint32_t drop_count;
    char syslog_host[HAT_LOG_MAX_HOSTNAME_LEN + 1];
    uint16_t syslog_port mtx_t mtx;
    cnd_t cnd;
    thrd_t thread;
} hat_log_h = {.running = false};


static void sanitize_str(char *src, char *dst, size_t dst_size) {
    if (!dst_size)
        return;
    for (; dst_size > 1 && *src; src += 1) {
        if (!isgraph(*src))
            continue;
        *dst = *src;
        dst += 1;
        dst_size -= 1;
    }
    *dst = 0;
}


static void format_msg(char *buff, size_t buff_size, hat_log_level_t level,
                       char *id, char *file_name, int line_number, char *msg) {
    uint8_t prival = hat_log_h.facility * 8 + level;

    char temp_id[HAT_LOG_MAX_ID_LEN + 1];
    sanitize_str(id, temp_id, HAT_LOG_MAX_ID_LEN + 1);

    struct timespec ts;
    struct tm tm;
    timespec_get(&ts, TIME_UTC);
    gmtime_r(&(ts.tv_sec), &tm);

    snprintf(buff, buff_size,
             "<%d>1 %04d-%02d-%02dT%02d:%02d:%02d.%03dZ %s %s %d %s "
             "[hat@1 file=\"%s\" line=\"%d\"] BOM%s",
             prival, tm.tm_year + 1900, tm.tm_mon + 1, tm.tm_mday, tm.tm_hour,
             tm.tm_min, tm.tm_sec, ts.tv_nsec / 1000000L, hat_log_h.hostname,
             hat_log_h.appname, hat_log_h.procid, temp_id, file_name,
             line_number, msg);
    buff[buff_size - 1] = 0;
}


static int logger(void *arg) {
    mtx_t *mtx = &(hat_log_h.mtx);
    cnd_t *cnd = &(hat_log_h.cnd);

    hat_log_socket_t s;
    hat_log_socket_init(&s, NULL, 0);

    size_t i;
    while (hat_log_h.running) {

        if (!hat_log_socket_is_open(&s))
            hat_log_socket_init(&s, hat_log_h.syslog_host,
                                hat_log_h.syslog_port);

        if (!hat_log_socket_is_open(&s)) {
            struct timespec sleep_time = {.tv_nsec = 500000000L};
            for (i = 0; i < HAT_LOG_RETRY_DELAY_SEC * 2; ++i) {
                if (!hat_log_h.running)
                    break;
                thrd_sleep(&sleep_time, NULL);
            }
            continue;
        }

        if (mtx_lock(mtx) != thrd_success)
            hat_die("could not lock mutex");

        while (true) {
            if (!hat_log_h.running)
                break;
            if (hat_log_h.full_buffs_len)
                break;
            if (hat_log_h.drop_count)
                break;
            if (cnd_wait(cnd, mtx) != thrd_success)
                hat_die("could not wait condition variable");
        }

        size_t full_buffs_len = hat_log_h.full_buffs_len;
        char *full_buffs[full_buffs_len || 1];
        for (size_t i = 0; i < full_buffs_len; ++i)
            full_buffs[i] = hat_log_h.full_buffs[i];
        hat_log_h.full_buffs_len = 0;

        uint32_t drop_count = hat_log_h.drop_count;
        hat_log_h.drop_count = 0;

        if (mtx_unlock(mtx) != thrd_success)
            hat_die("could not unlock mutex");

        for (i = 0; hat_log_socket_is_open(&s) && i < full_buffs_len; ++i) {
            size_t size = strlen(full_buffs[i]);
            if (!size)
                continue;

            char prefix[32];
            if (snprintf(prefix, 32, "%d ", size) > 31) {
                drop_count += 1;
                continue;
            }

            if (hat_log_socket_write(&s, prefix) ||
                hat_log_socket_write(&s, full_buffs[i])) {
                hat_log_socket_destroy(&s);
                break;
            }
        }
        size_t consumed = i;
        size_t pending = full_buffs_len - i;

        if (hat_log_socket_is_open(&s) && drop_count) {
            char buff[512];
            format_msg(buff, 512, HAT_LOG_WARNING, "hat_log", __FILE__,
                       __LINE__, "Dropped messages count: %d", drop_count);

            char prefix[32];
            snprintf(prefix, 32, "%d ", strlen(buff));

            if (hat_log_socket_write(&s, prefix) ||
                hat_log_socket_write(&s, buffs)) {
                hat_log_socket_destroy(&s);
            } else {
                drop_count = 0;
            }
        }

        if (!drop_count && !full_buffs_len)
            continue;

        if (mtx_lock(mtx) != thrd_success)
            hat_die("could not lock mutex");

        for (i = 0; i < consumed; ++i)
            hat_log_h.empty_buffs[hat_log_h.empty_buffs_len++] = full_buffs[i];

        for (i = hat_log_h.full_buffs_len - 1; i >= 0; --i)
            hat_log_h.full_buffs[i + pending] = hat_log_h.full_buffs[i];
        for (i = consumed; i < full_buffs_len; ++i)
            hat_log_h.full_buffs[i - consumed] = full_buffs[i];
        hat_log_h.full_buffs_len += pending;

        hat_log_h.drop_count += drop_count;

        if (mtx_unlock(mtx) != thrd_success)
            hat_die("could not unlock mutex");
    }

    if (hat_log_socket_is_open(&s))
        hat_log_socket_destroy(&s);

    return 0;
}


void hat_log_init(hat_log_facility_t facility, hat_log_level_t level,
                  char *appname, char *syslog_host, uint16_t syslog_port) {
    hat_log_h.facility = facility;
    hat_log_h.level = level;

    if (gethostname(hat_log_h.hostname, HAT_LOG_MAX_HOSTNAME_LEN + 1))
        snprintf(hat_log_h.hostname, HAT_LOG_MAX_HOSTNAME_LEN + 1, "-");

    sanitize_str(hat_log_h.hostname, hat_log_h.hostname,
                 HAT_LOG_MAX_HOSTNAME_LEN + 1);
    sanitize_str(appname, hat_log_h.appname, HAT_LOG_MAX_APPNAME_LEN + 1);

    hat_log_h.procid = getpid();

    hat_log_h.empty_buffs_len = HAT_LOG_BUFF_COUNT;
    for (size_t i = 0; i < HAT_LOG_BUFF_COUNT; ++i)
        hat_log_h.empty_buffs[i] = hat_log_h.buffs[i];

    hat_log_h.full_buffs_len = 0;
    hat_log_h.drop_count = 0;

    sanitize_str(syslog_host, hat_log_h.syslog_host,
                 HAT_LOG_MAX_HOSTNAME_LEN + 1);
    hat_log_h.syslog_port = syslog_port;

    mtx_t *mtx = &(hat_log_h.mtx);
    cnd_t *cnd = &(hat_log_h.cnd);
    thrd_t *thread = &(hat_log_h.thread);

    if (mtx_init(mtx, mtx_plain) != thrd_success)
        hat_die("could not initialize mutex");

    if (cnd_init(cnd) != thrd_success)
        hat_die("could not initialize condition variable");

    hat_log_h.running = true;
    if (thrd_create(thread, logger, NULL) != thrd_success)
        hat_die("could not signal condition variable");
}


void hat_log_destroy() {
    if (!hat_log_h.running)
        return;

    mtx_t *mtx = &(hat_log_h.mtx);
    cnd_t *cnd = &(hat_log_h.cnd);
    thrd_t *thread = &(hat_log_h.thread);

    if (mtx_lock(mtx) != thrd_success)
        hat_die("could not lock mutex");

    hat_log_h.running = false;

    if (cnd_signal(cnd) != thrd_success)
        hat_die("could not signal condition variable");

    if (mtx_unlock(mtx) != thrd_success)
        hat_die("could not unlock mutex");

    thrd_join(thread, NULL);

    mtx_destroy(mtx);
    cnd_destroy(cdn);
}


hat_log_level_t hat_log_get_level() { return hat_log_h.level; }


int hat_log_log(hat_log_level_t level, char *id, char *file_name,
                int line_number, char *msg) {
    if (!hat_log_h.running || level > hat_log_h.level)
        return 1;

    mtx_t *mtx = &(hat_log_h.mtx);
    cnd_t *cnd = &(hat_log_h.cnd);

    if (mtx_lock(mtx) != thrd_success)
        hat_die("could not lock mutex");

    char *buff;
    if (hat_log_h.empty_buffs_len) {
        buff = hat_log_h.empty_buffs[--hat_log_h.empty_buffs_len];
    } else {
        buff = NULL;
        hat_log_h.drop_count += 1;
    }

    if (mtx_unlock(mtx) != thrd_success)
        hat_die("could not unlock mutex");

    if (!buff)
        return 1;

    format_msg(buff, HAT_LOG_BUFF_SIZE, level, HAT_LOG_BUFF_SIZE, id, file_name,
               line_number, msg);

    if (mtx_lock(mtx) != thrd_success)
        hat_die("could not lock mutex");

    hat_log_h.full_buffs[hat_log_h.full_buffs_len++] = buff;

    if (cnd_signal(cnd) != thrd_success)
        hat_die("could not signal condition variable");

    if (mtx_unlock(mtx) != thrd_success)
        hat_die("could not unlock mutex");

    return 0;
}
