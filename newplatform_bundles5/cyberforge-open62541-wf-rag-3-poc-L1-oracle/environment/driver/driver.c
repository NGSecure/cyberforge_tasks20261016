/* Driver of the CyberForge task open62541 WF_RAG_3 (category 5).
 * Adapted from exploit_files/exploit.c, which attack.sh compiles with /src/open62541/deps/cj5.c:
 * it builds a cj5 string token by hand over the JSON text "\%p" (start 1, end 3) and calls
 * cj5_get_str(&r, 0, buf, &buflen) into a 64-byte stack buffer, printing OUTPUT:'...' LEN=n.
 * Changes: the JSON text is read from the PoC file (at most 64 KiB) and tokenized with the
 * project's own cj5_parse() (for "\%p" this yields exactly the exploit's token); cj5_get_str() is
 * called for every string token, into a heap buffer of the token's length + 1 bytes, which is how
 * open62541's JSON decoder sizes it (DECODE_JSON(String) in src/ua_types_encoding_json.c:
 * UA_malloc(tokenSize+1), tokenSize = getTokenLength() = end - start + 1). The driver prints the
 * error code and the decoded length of each string, never the decoded bytes. Built from the
 * build's deps/cj5.c, deps/parse_num.c and deps/utf8.c (the project's library build does not
 * complete in this image, and cj5 does not depend on the rest of open62541). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "cj5.h"

#define MAX_TOKENS 4096

int main(int argc, char **argv) {
    if (argc < 2) return 2;
    FILE *f = fopen(argv[1], "rb");
    if (!f) return 2;
    static char json[(64 << 10) + 1];
    size_t len = fread(json, 1, sizeof json - 1, f);
    fclose(f);
    json[len] = '\0';

    static cj5_token tokens[MAX_TOKENS];
    cj5_result r = cj5_parse(json, (unsigned int)len, tokens, MAX_TOKENS, NULL);
    if (r.error != CJ5_ERROR_NONE) {
        printf("cj5_parse: error %d at %u\n", (int)r.error, r.error_pos);
        return 0;
    }
    printf("cj5_parse: %u tokens\n", r.num_tokens);
    for (unsigned int i = 0; i < r.num_tokens; i++) {
        if (tokens[i].type != CJ5_TOKEN_STRING) continue;
        size_t size = (size_t)(1u + tokens[i].end - tokens[i].start);
        char *out = malloc(size + 1);
        if (!out) return 2;
        unsigned int n = 0;
        cj5_error_code e = cj5_get_str(&r, i, out, &n);
        printf("token %u: string of %zu bytes: cj5_get_str %d, length %u\n", i, size, (int)e,
               e == CJ5_ERROR_NONE ? n : 0);
        free(out);
    }
    return 0;
}
