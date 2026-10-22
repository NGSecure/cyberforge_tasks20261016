/* Category-5 driver for this task.
 *
 * Adapted from src/apps/fuzzers/fuzzerPolygonToCellsExperimental.c (the OSS-Fuzz harness built by
 * build.sh), which reads the same input layout and makes the same calls but
 * frees the result unseen. What changed: the input is read from the PoV file; the loops are copied
 * into memory the driver owns (the harness points into its input buffer); a negative vertex count
 * is refused; and every call's result is printed: the error codes, the number of cells, an FNV-1a
 * hash of the sorted cells and the first 8 of them. polygonToCellsExperimental is the public API
 * the failing test (src/apps/testapps/testPolyfillInternal.c) exercises through the internal
 * polygon iterator.
 *
 * PoV layout (little-endian, as the harness's inputArgs): int32 res (taken % 16), int32 numHoles
 * (taken % 100; negative: nothing is run), then from offset 8: int32 numVerts, numVerts x
 * {double lat, double lng} (radians), then the same for each hole. The file must be at least
 * 1032 bytes (sizeof(inputArgs)). As the harness does, each of the flags 0..3 is run with the
 * holes and without them.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "h3api.h"

#define MAX_RES 15
#define MAX_SZ 4000000
#define MAX_HOLES 100
#define INPUT_ARGS_SIZE (2 * sizeof(int) + 1024) /* sizeof(inputArgs) in the harness */
#define MAX_INPUT (16 << 20)

static int read_loop(GeoLoop *g, const uint8_t *data, size_t *offset, size_t size) {
    int numVerts;
    if (size < *offset + sizeof(int)) return 1;
    memcpy(&numVerts, data + *offset, sizeof(int));
    *offset += sizeof(int);
    if (numVerts < 0) return 2;
    if ((size - *offset) / sizeof(LatLng) < (size_t)numVerts) return 1;
    g->numVerts = numVerts;
    g->verts = calloc(numVerts ? (size_t)numVerts : 1, sizeof(LatLng));
    if (!g->verts) return 3;
    memcpy(g->verts, data + *offset, sizeof(LatLng) * (size_t)numVerts);
    *offset += sizeof(LatLng) * (size_t)numVerts;
    return 0;
}

static void free_poly(GeoPolygon *poly, int numHoles) {
    free(poly->geoloop.verts);
    for (int i = 0; i < numHoles; i++) free(poly->holes[i].verts);
    free(poly->holes);
}

static int cmp_cell(const void *a, const void *b) {
    H3Index x = *(const H3Index *)a, y = *(const H3Index *)b;
    return x < y ? -1 : x > y;
}

static void run(const GeoPolygon *poly, uint32_t flags, int res, const char *holes) {
    int64_t sz = 0;
    H3Error err = maxPolygonToCellsSizeExperimental(poly, res, flags, &sz);
    printf("flags=%u holes=%s maxSize: error=%u size=%lld", (unsigned)flags, holes, (unsigned)err,
           (long long)(err ? 0 : sz));
    if (err || sz >= MAX_SZ || sz < 0) {
        printf("%s\n", (!err && sz >= MAX_SZ) ? " (not run: size limit)" : "");
        return;
    }
    H3Index *out = calloc(sz ? (size_t)sz : 1, sizeof(H3Index));
    if (!out) {
        printf(" (not run: out of memory)\n");
        return;
    }
    err = polygonToCellsExperimental(poly, res, flags, sz, out);
    int64_t n = 0;
    for (int64_t i = 0; i < sz; i++)
        if (out[i]) out[n++] = out[i];
    qsort(out, (size_t)n, sizeof(H3Index), cmp_cell);
    uint64_t h = 1469598103934665603ULL;
    for (int64_t i = 0; i < n; i++)
        for (int b = 0; b < 8; b++) {
            h ^= (out[i] >> (8 * b)) & 0xff;
            h *= 1099511628211ULL;
        }
    printf(" fill: error=%u cells=%lld hash=%016llx first:", (unsigned)err, (long long)n,
           (unsigned long long)h);
    for (int64_t i = 0; i < n && i < 8; i++) printf(" %llx", (unsigned long long)out[i]);
    printf("\n");
    free(out);
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
    uint8_t *data = malloc(MAX_INPUT + 1);
    size_t size = data ? fread(data, 1, MAX_INPUT + 1, f) : 0;
    fclose(f);
    if (!data || size > MAX_INPUT) {
        printf("the PoV is larger than %d bytes\n", MAX_INPUT);
        free(data);
        return 1;
    }
    if (size < INPUT_ARGS_SIZE) {
        printf("the PoV is shorter than %zu bytes: nothing is run\n", (size_t)INPUT_ARGS_SIZE);
        free(data);
        return 0;
    }
    int rawRes, rawHoles;
    memcpy(&rawRes, data, sizeof(int));
    memcpy(&rawHoles, data + sizeof(int), sizeof(int));
    int res = rawRes % (MAX_RES + 1);
    int numHoles = rawHoles % MAX_HOLES;
    printf("res=%d holes=%d\n", res, numHoles);
    if (numHoles < 0) {
        printf("negative hole count: nothing is run\n");
        free(data);
        return 0;
    }
    GeoPolygon poly;
    memset(&poly, 0, sizeof poly);
    poly.holes = calloc(numHoles ? (size_t)numHoles : 1, sizeof(GeoLoop));
    size_t offset = 2 * sizeof(int);
    int bad = read_loop(&poly.geoloop, data, &offset, size);
    for (int i = 0; !bad && i < numHoles; i++) bad = read_loop(&poly.holes[i], data, &offset, size);
    free(data);
    if (bad) {
        printf("%s: nothing is run\n", bad == 2 ? "negative vertex count" : "the loops do not fit");
        free_poly(&poly, numHoles);
        return 0;
    }
    printf("outer loop: %d vertices\n", poly.geoloop.numVerts);
    for (uint32_t flags = 0; flags < CONTAINMENT_INVALID; flags++) {
        poly.numHoles = numHoles;
        run(&poly, flags, res, "yes");
        poly.numHoles = 0;
        run(&poly, flags, res, "no");
    }
    free_poly(&poly, numHoles);
    printf("done\n");
    return 0;
}
