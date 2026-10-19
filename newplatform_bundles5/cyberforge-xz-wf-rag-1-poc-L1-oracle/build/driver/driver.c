/* Driver of the CyberForge task xz WF_RAG_1 (category 5).
 *
 * No dataset program is behind this driver. The exploit (exploit_files/exploit.sh) preloads a
 * library whose malloc() always returns NULL into /out/fuzz_decode_alone, which cannot work:
 * the harness links the sanitizer runtime statically (an LD_PRELOADed malloc is never used),
 * and a malloc that always fails would also break the harness itself in both builds. Its
 * exploit_description.md instead describes "a custom harness that wraps the target
 * functionality and explicitly provides an allocator that returns NULL"; this is that harness.
 * It does what fuzz_decode_alone.c does (lzma_alone_decoder(&strm, MEM_LIMIT), then decode the
 * input), with these changes:
 *   - the stream gets liblzma's own custom-allocator hook (lzma_allocator); the PoC chooses from
 *     which allocation on it fails: the PoC's first line is a decimal number N (0: none fails;
 *     N >= 1: allocations N, N+1, ... return NULL; allocations are numbered from 1 in the
 *     order liblzma makes them);
 *   - the rest of the PoC (after the first newline) is decoded as .lzma data, like the harness
 *     input;
 *   - lzma_alone_decoder() failing is printed and the driver exits 0 (the harness abort()s).
 * Built against the build's own liblzma (src/liblzma/.libs/liblzma.a) with AddressSanitizer.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "lzma.h"

#define MAX_INPUT (1 << 20)
#define MEM_LIMIT (300 << 20) /* as tests/ossfuzz/fuzz_common.h */

static unsigned long fail_from; /* 0: no allocation fails */
static unsigned long count;

static void *failing_alloc(void *opaque, size_t nmemb, size_t size)
{
	(void)opaque;
	count++;
	if (fail_from != 0 && count >= fail_from)
		return NULL;
	if (nmemb != 0 && size > SIZE_MAX / nmemb)
		return NULL;
	return malloc(nmemb * size);
}

static void plain_free(void *opaque, void *ptr)
{
	(void)opaque;
	free(ptr);
}

int main(int argc, char **argv)
{
	if (argc < 2)
		return 2;
	FILE *f = fopen(argv[1], "rb");
	if (!f)
		return 2;
	uint8_t *data = malloc(MAX_INPUT);
	if (!data)
		return 2;
	size_t n = fread(data, 1, MAX_INPUT, f);
	fclose(f);

	size_t i = 0;
	unsigned long v = 0;
	int digits = 0;
	while (i < n && data[i] >= '0' && data[i] <= '9') {
		if (v > 100000000UL) {
			printf("N is at most 100000000\n");
			free(data);
			return 0;
		}
		v = v * 10 + (unsigned long)(data[i] - '0');
		digits++;
		i++;
	}
	if (!digits) {
		printf("expected: N (the first allocation that fails; 0 for none), a newline, then .lzma data\n");
		free(data);
		return 0;
	}
	fail_from = v;
	while (i < n && data[i] != '\n')
		i++;
	if (i < n)
		i++; /* the input starts after the first newline */

	lzma_allocator allocator = { failing_alloc, plain_free, NULL };
	lzma_stream strm = LZMA_STREAM_INIT;
	strm.allocator = &allocator;
	lzma_ret ret = lzma_alone_decoder(&strm, MEM_LIMIT);
	printf("lzma_alone_decoder returned %d after %lu allocation(s)\n", (int)ret, count);
	if (ret != LZMA_OK) {
		lzma_end(&strm);
		free(data);
		return 0;
	}

	uint8_t out[4096];
	strm.next_in = data + i;
	strm.avail_in = n - i;
	do {
		strm.next_out = out;
		strm.avail_out = sizeof(out);
		ret = lzma_code(&strm, LZMA_FINISH);
	} while (ret == LZMA_OK);
	printf("lzma_code returned %d\n", (int)ret);

	lzma_end(&strm);
	free(data);
	return 0;
}
