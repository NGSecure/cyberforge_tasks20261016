/* Driver of this task (category 5).
 *
 * Adapted from the dataset exploit's own program, exploit_files/driver.c, which calls
 * unescape_crlf() on a 4-byte heap buffer holding "test" with a 16-byte output buffer.
 * Changes:
 *   - the input bytes are read from the PoC file (argv[1]) into a heap buffer of exactly
 *     the PoC's size (as the exploit's malloc(4)); an empty PoC gives len 0;
 *   - the output buffer is max(16, size) bytes, so the fixed build cannot overflow it.
 * The exploit compiled a copy of unescape_crlf cut out of src/core/strutils.c with sed; the
 * judge links this driver with the build's own /src/<project>/src/libkamilio.a instead (the
 * archive build.sh makes for the fuzzers) and falls back to the exploit's sed extraction
 * from the build's strutils.c only if that link fails.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    char *s;
    int len;
} str;

int unescape_crlf(str *sin, str *sout);

#define MAX_INPUT (1 << 20)

int main(int argc, char **argv) {
    if (argc < 2) return 2;
    FILE *f = fopen(argv[1], "rb");
    if (!f) return 2;
    char *tmp = malloc(MAX_INPUT);
    if (!tmp) return 2;
    size_t n = fread(tmp, 1, MAX_INPUT, f);
    fclose(f);

    // Allocate exactly the input's size, as the exploit's malloc(4) for "test"
    char *input_buf = malloc(n ? n : 1);
    if (!input_buf) return 2;
    memcpy(input_buf, tmp, n);
    free(tmp);

    str sin = { .s = input_buf, .len = (int)n };
    size_t out_len = n > 16 ? n : 16;
    char *output_buf = malloc(out_len);
    if (!output_buf) return 2;
    str sout = { .s = output_buf, .len = (int)out_len };

    printf("Calling unescape_crlf...\n");
    int rc = unescape_crlf(&sin, &sout);
    printf("unescape_crlf returned %d\n", rc);

    free(output_buf);
    free(input_buf);
    return 0;
}
