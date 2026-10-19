/* Driver of the CyberForge task quickjs WF_LLM_3 (category 5).
 *
 * Adapted from the dataset exploit's own program (exploit.c, written by
 * exploit_files/attack.py), which calls dbuf_put() from cutils.c with len 12 on a DynBuf
 * that claims allocated_size 8 and size 0, then checks a marker byte behind the 8-byte
 * buffer. Changes:
 *   - allocated_size, size and len are read from the PoC file (argv[1]): text
 *     "allocated_size size len" (decimal; allocated_size 1..1048576, size <= allocated_size,
 *     len <= 1048576); the bytes written are 0x41 as in the exploit;
 *   - the DynBuf is set up with dbuf_init() (cutils.c's default realloc) instead of
 *     realloc_func = NULL: with NULL the fixed build crashes calling a null pointer
 *     whenever dbuf_put() has to grow the buffer;
 *   - the buffer is its own malloc(allocated_size) instead of an array inside a struct, so
 *     AddressSanitizer sees a write past it (the exploit's marker byte check is dropped);
 *   - built with AddressSanitizer (the exploit used gcc -g -O0 without a sanitizer).
 */
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "cutils.h"

int main(int argc, char **argv) {
    if (argc < 2) return 2;
    FILE *f = fopen(argv[1], "rb");
    if (!f) return 2;
    char text[256];
    size_t n = fread(text, 1, sizeof(text) - 1, f);
    fclose(f);
    text[n] = '\0';

    unsigned long v[3];
    char *p = text, *end;
    for (int i = 0; i < 3; i++) {
        v[i] = strtoul(p, &end, 10);
        if (end == p) {
            printf("expected: allocated_size size len\n");
            return 0;
        }
        p = end;
    }
    if (v[0] < 1 || v[0] > (1ul << 20) || v[1] > v[0] || v[2] > (1ul << 20)) {
        printf("out of range: 1 <= allocated_size <= 1048576, size <= allocated_size, len <= 1048576\n");
        return 0;
    }

    DynBuf s;
    dbuf_init(&s);
    s.buf = malloc(v[0]);
    if (!s.buf) return 2;
    memset(s.buf, 0, v[0]);
    s.allocated_size = v[0];
    s.size = v[1];

    size_t len = v[2];
    uint8_t *data = malloc(len ? len : 1);
    if (!data) return 2;
    memset(data, 0x41, len);

    printf("dbuf_put(allocated=%lu, size=%lu, len=%zu)\n", v[0], v[1], len);
    int rc = dbuf_put(&s, data, len);
    printf("dbuf_put returned %d\n", rc);

    free(data);
    dbuf_free(&s);
    return 0;
}
