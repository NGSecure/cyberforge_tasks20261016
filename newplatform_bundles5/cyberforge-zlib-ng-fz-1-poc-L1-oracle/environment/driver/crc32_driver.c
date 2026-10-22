/* Category-5 driver for this task.
 *
 * No dataset program fits as it is: the exploit runs the project's unit tests (the minigzip-*
 * ctests fail with "incorrect data check" on test/data/paper-100k.pdf, lcet10.txt, fireworks.jpg),
 * and the OSS-Fuzz harness fuzzer_minigzip reaches the changed code only when <project>'s run-time
 * CPU dispatch picks crc32_pclmulqdq (on a CPU with AVX-512 + VPCLMULQDQ it picks
 * crc32_vpclmulqdq_avx512, which does not use fold_12). This driver therefore computes the CRC-32 of
 * the PoV with crc32_pclmulqdq itself (arch/x86/crc32_pclmulqdq.c, the function the injected change
 * in arch/x86/crc32_pclmulqdq_tpl.h breaks; an internal symbol of the build's libz-ng.a, declared
 * here) and, for reference, with the public zng_crc32 (whatever implementation the dispatch picks).
 * It needs a CPU with PCLMULQDQ and SSE4.1 (every x86-64 CPU of the last decade).
 *
 * PoV: any file (at most 64 MiB); its CRC-32 is computed over the whole file in one call.
 * Output: "length=<n> crc32_pclmulqdq=<8 hex digits> zng_crc32=<8 hex digits>".
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#include "zlib-ng.h"

uint32_t crc32_pclmulqdq(uint32_t crc, const uint8_t *buf, size_t len);

#define MAX_INPUT (64u << 20)

int main(int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "usage: %s <pov>\n", argv[0]);
        return 2;
    }
    FILE *f = fopen(argv[1], "rb");
    if (!f) {
        printf("cannot open the PoV\n");
        return 1;
    }
    uint8_t *buf = malloc(MAX_INPUT + 1);
    size_t len = buf ? fread(buf, 1, MAX_INPUT + 1, f) : 0;
    fclose(f);
    if (!buf || len > MAX_INPUT) {
        printf("the PoV is larger than %u bytes\n", MAX_INPUT);
        free(buf);
        return 1;
    }
    uint32_t direct = crc32_pclmulqdq(0, buf, len);
    uint32_t api = zng_crc32(0, buf, (uint32_t)len);
    printf("length=%zu crc32_pclmulqdq=%08x zng_crc32=%08x\n", len, (unsigned)direct, (unsigned)api);
    free(buf);
    return 0;
}
