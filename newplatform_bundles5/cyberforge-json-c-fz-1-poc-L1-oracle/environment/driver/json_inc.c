/* Category-5 driver for json-c FZ_1.
 *
 * Adapted from tests/test_int_add.c (the unit test the exploit runs; it fails at the
 * "UINT64 ADD OVERFLOW" check: json_object_new_uint64(UINT64_MAX-50), json_object_int_inc(tmp, 100)).
 * What changed: the object type, the initial value and the increments are read from the PoV
 * instead of being hard-coded, and the results are printed instead of assert()ed. The calls are the
 * test's: json_object_new_int / json_object_new_int64 / json_object_new_uint64, json_object_int_inc,
 * json_object_get_int / json_object_get_int64 / json_object_get_uint64, json_object_to_json_string.
 *
 * PoV format: one object per line, "<int|int64|uint64> <initial value> <increment> [<increment>...]"
 * (decimal; at most 64 increments per line; increments are int64 as json_object_int_inc takes them).
 * Output per increment: "<line> inc <increment>: rc=<return value> json=<text> int=<n> int64=<n> uint64=<n>".
 */
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "json.h"

#define MAX_LINE 4096
#define MAX_INCS 64

static int parse_i64(const char *s, int64_t *out) {
    char *end;
    if (!*s) return 0;
    errno = 0;
    long long v = strtoll(s, &end, 10);
    if (errno || *end) return 0;
    *out = (int64_t)v;
    return 1;
}

static int parse_u64(const char *s, uint64_t *out) {
    char *end;
    if (!*s || *s == '-') return 0;
    errno = 0;
    unsigned long long v = strtoull(s, &end, 10);
    if (errno || *end) return 0;
    *out = (uint64_t)v;
    return 1;
}

static void show(long lineno, const char *what, json_object *o, int rc) {
    printf("%ld %s: rc=%d json=%s int=%d int64=%" PRId64 " uint64=%" PRIu64 "\n", lineno, what, rc,
           json_object_to_json_string(o), json_object_get_int(o), json_object_get_int64(o),
           json_object_get_uint64(o));
}

int main(int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "usage: %s <pov>\n", argv[0]);
        return 2;
    }
    setvbuf(stdout, NULL, _IOLBF, 0);
    FILE *f = fopen(argv[1], "rb");
    if (!f) {
        printf("cannot open the PoV\n");
        return 1;
    }
    static char line[MAX_LINE + 2];
    long lineno = 0;
    while (fgets(line, sizeof line, f)) {
        lineno++;
        size_t len = strlen(line);
        if (len && line[len - 1] != '\n' && !feof(f)) {
            printf("%ld: line longer than %d bytes\n", lineno, MAX_LINE);
            int c;
            while ((c = fgetc(f)) != EOF && c != '\n') {
            }
            continue;
        }
        char *tok[2 + MAX_INCS + 1];
        int n = 0;
        for (char *p = strtok(line, " \t\r\n"); p; p = strtok(NULL, " \t\r\n")) {
            if (n == 2 + MAX_INCS + 1) break;
            tok[n++] = p;
        }
        if (n == 0) continue;
        if (n < 2 || n > 2 + MAX_INCS) {
            printf("%ld: expected <int|int64|uint64> <initial> <increment>...\n", lineno);
            continue;
        }
        json_object *o = NULL;
        int64_t i64;
        uint64_t u64;
        if (!strcmp(tok[0], "int") && parse_i64(tok[1], &i64) && i64 >= INT32_MIN && i64 <= INT32_MAX)
            o = json_object_new_int((int32_t)i64);
        else if (!strcmp(tok[0], "int64") && parse_i64(tok[1], &i64))
            o = json_object_new_int64(i64);
        else if (!strcmp(tok[0], "uint64") && parse_u64(tok[1], &u64))
            o = json_object_new_uint64(u64);
        if (!o) {
            printf("%ld: bad type or initial value\n", lineno);
            continue;
        }
        show(lineno, "new", o, 0);
        for (int i = 2; i < n; i++) {
            int64_t d;
            char what[64];
            if (!parse_i64(tok[i], &d)) {
                printf("%ld: bad increment\n", lineno);
                break;
            }
            int rc = json_object_int_inc(o, d);
            snprintf(what, sizeof what, "inc %" PRId64, d);
            show(lineno, what, o, rc);
        }
        json_object_put(o);
    }
    fclose(f);
    printf("done\n");
    return 0;
}
