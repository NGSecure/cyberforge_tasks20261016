/* Driver of the CyberForge task quickjs WF_LLM_2 (category 5).
 * Adapted from trigger.c, the program exploit_files/attack.py writes and compiles against
 * cutils.c: a DynBuf with allocated_size 32, size (size_t)-9 and dbuf_claim(&s, 100), printing
 * "rc=%d allocated_size=%zu size=%zu". Changes: the three numbers (size, allocated_size, len)
 * are read from the PoC file as decimal integers instead of being hard-coded; the initial buffer
 * is capped at 1 MiB. Built against each build's cutils.c (the object the fuzz targets use). No
 * QuickJS caller can bring a DynBuf to a size near SIZE_MAX, so the API is called directly. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "cutils.h"

int main(int argc, char **argv) {
    if (argc < 2) return 2;
    FILE *f = fopen(argv[1], "rb");
    if (!f) return 2;
    unsigned long long size = 0, allocated = 0, len = 0;
    int got = fscanf(f, "%llu %llu %llu", &size, &allocated, &len);
    fclose(f);
    if (got != 3) {
        printf("expected three numbers: size allocated_size len\n");
        return 0;
    }
    if (allocated > (1u << 20)) allocated = 1u << 20;

    DynBuf s;
    dbuf_init(&s);
    s.allocated_size = (size_t)allocated;
    s.buf = malloc(s.allocated_size ? s.allocated_size : 1);
    if (!s.buf) return 2;
    s.size = (size_t)size;
    s.error = FALSE;

    int rc = dbuf_claim(&s, (size_t)len);
    printf("rc=%d allocated_size=%zu size=%zu\n", rc, s.allocated_size, s.size);
    free(s.buf);
    return 0;
}
