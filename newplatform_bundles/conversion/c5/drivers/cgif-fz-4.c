/* Driver of the CyberForge task cgif FZ_4 (category 5).
 *
 * Adapted from the dataset exploit's own program, exploit_files/driver.c, which includes
 * src/cgif_raw.c and calls its static function lzw_crawl_tree() on a hand-built
 * LZWGenState (initDictLen 256, parentIndex 256, 10 zero pixels). Changes:
 *   - the values are read from the PoC file (argv[1]) instead of being hard-coded:
 *     text "initDictLen parentIndex numPixel p0 p1 ... p(numPixel-1)" (missing pixel
 *     values are 0, as in the exploit's zero-initialised array);
 *   - the LZW tables are allocated on the heap with the sizes LZW_GenerateStream() in
 *     cgif_raw.c uses for that initDictLen (the exploit used fixed stack arrays sized for
 *     initDictLen 256), so no input can overflow memory the driver itself owns;
 *   - it prints lzw_crawl_tree()'s return value instead of TRIGGERED / NO_TRIGGER and
 *     always exits 0 (the judge looks for a sanitizer report).
 * Built like the exploit builds it: clang -fsanitize=address -g -I/src/cgif/inc -I/src/cgif/src.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "cgif_raw.h"

#define STATIC
#include "cgif_raw.c"

#define MAX_INPUT (1 << 20)
#define MAX_PIXELS 65536

int main(int argc, char **argv) {
    if (argc < 2) return 2;
    FILE *f = fopen(argv[1], "rb");
    if (!f) return 2;
    char *text = calloc(MAX_INPUT + 1, 1);
    if (!text) return 2;
    size_t len = fread(text, 1, MAX_INPUT, f);
    fclose(f);
    text[len] = '\0';

    char *p = text, *end;
    unsigned long v[3];
    for (int i = 0; i < 3; i++) {
        v[i] = strtoul(p, &end, 10);
        if (end == p) {
            printf("expected: initDictLen parentIndex numPixel pixel...\n");
            return 0;
        }
        p = end;
    }
    unsigned long initDictLenL = v[0], parentIndexL = v[1], numPixelL = v[2];
    if (initDictLenL < 1 || initDictLenL > 256 || parentIndexL > 65535 || numPixelL < 1 || numPixelL > MAX_PIXELS) {
        printf("out of range: 1 <= initDictLen <= 256, parentIndex <= 65535, 1 <= numPixel <= %d\n", MAX_PIXELS);
        return 0;
    }
    uint16_t initDictLen = (uint16_t)initDictLenL;
    uint16_t parentIndex = (uint16_t)parentIndexL;
    uint32_t numPixel = (uint32_t)numPixelL;

    uint8_t *pImageData = calloc(numPixel, 1);
    for (uint32_t i = 0; pImageData && i < numPixel; i++) {
        unsigned long px = strtoul(p, &end, 10);
        if (end == p) break; /* the rest stays 0 */
        if (px > 255) {
            printf("pixel values are bytes (0..255)\n");
            return 0;
        }
        pImageData[i] = (uint8_t)px;
        p = end;
    }

    /* table sizes as in LZW_GenerateStream() */
    uint32_t entriesPerCycle = MAX_DICT_LEN - initDictLen - 2;
    uint32_t maxResets = numPixel / entriesPerCycle;
    uint16_t *pTreeInit = calloc((size_t)initDictLen * initDictLen, sizeof(uint16_t));
    uint16_t *pTreeList = calloc((size_t)(2 + 1) * MAX_DICT_LEN, sizeof(uint16_t));
    uint16_t *pTreeMap = calloc((size_t)(MAX_DICT_LEN / 2 + 1) * initDictLen, sizeof(uint16_t));
    uint16_t *pLZWData = calloc((size_t)numPixel + 2 + maxResets, sizeof(uint16_t));
    if (!pImageData || !pTreeInit || !pTreeList || !pTreeMap || !pLZWData) return 2;

    LZWGenState ctx;
    memset(&ctx, 0, sizeof(ctx));
    ctx.pTreeInit = pTreeInit;
    ctx.pTreeList = pTreeList;
    ctx.pTreeMap = pTreeMap;
    ctx.pLZWData = pLZWData;
    ctx.pImageData = pImageData;
    ctx.numPixel = numPixel;
    ctx.LZWPos = 0;
    ctx.dictPos = 0;
    ctx.mapPos = 0;

    uint32_t strPos = 0;
    int res = lzw_crawl_tree(&ctx, &strPos, parentIndex, initDictLen);
    printf("lzw_crawl_tree returned %d\n", res);

    free(pImageData);
    free(pTreeInit);
    free(pTreeList);
    free(pTreeMap);
    free(pLZWData);
    free(text);
    return 0;
}
