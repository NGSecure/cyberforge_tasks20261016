/* Driver of this task (category 5).
 *
 * Adapted from the dataset exploit's own harness.c (written by exploit_files/exploit.sh),
 * which includes /src/<project>/<project>.c, fills a printbuffer (buffer = malloc(100),
 * length 100, offset SIZE_MAX), calls the static function ensure(&p, 1) and writes one
 * byte through the pointer it returns. Changes:
 *   - length, offset and needed are read from the PoC file (argv[1]) instead of being
 *     hard-coded: text "length offset needed" (decimal); length is 1..1048576 and needed
 *     at most 1048576 (larger values are refused), so the fixed build never grows the
 *     buffer to gigabytes;
 *   - the printbuffer is zero-initialised and gets <project>'s default allocator hooks (the
 *     exploit left those fields uninitialised; they are used when ensure() grows the buffer);
 *   - the returned pointer is not printed (addresses differ between runs).
 * Built as exploit.sh builds it: $CC $CFLAGS -fsanitize=address harness.c.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "/src/cjson/cJSON.c"

int main(int argc, char **argv) {
    if (argc < 2) return 2;
    FILE *f = fopen(argv[1], "rb");
    if (!f) return 2;
    char text[256];
    size_t n = fread(text, 1, sizeof(text) - 1, f);
    fclose(f);
    text[n] = '\0';

    unsigned long long v[3];
    char *s = text, *end;
    for (int i = 0; i < 3; i++) {
        v[i] = strtoull(s, &end, 10);
        if (end == s) {
            printf("expected: length offset needed\n");
            return 0;
        }
        s = end;
    }
    if (v[0] < 1 || v[0] > (1u << 20) || v[2] > (1u << 20)) {
        printf("out of range: 1 <= length <= 1048576, needed <= 1048576\n");
        return 0;
    }

    printbuffer p;
    memset(&p, 0, sizeof(p));
    p.buffer = malloc((size_t)v[0]);
    if (!p.buffer) return 2;
    p.length = (size_t)v[0];
    p.offset = (size_t)v[1];
    p.hooks = global_hooks;

    printf("Calling ensure(length=%llu, offset=%llu, needed=%llu)...\n", v[0], v[1], v[2]);
    unsigned char *res = ensure(&p, (size_t)v[2]);

    if (res == NULL) {
        printf("ensure returned NULL\n");
        free(p.buffer);
        return 0;
    }

    printf("ensure returned a pointer\n");

    // Write to the returned pointer (as the exploit does)
    *res = 'A';

    p.hooks.deallocate(p.buffer);
    return 0;
}
