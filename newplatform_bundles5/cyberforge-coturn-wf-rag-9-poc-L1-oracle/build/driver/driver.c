/* Driver of the CyberForge task coturn WF_RAG_9 (category 5).
 * Adapted from the dataset exploit's exploit_files/prog.c, which includes proxy_string_field()
 * cut out of src/apps/relay/ns_ioalib_engine_impl.c (exploit_files/attack.sh does the cutting)
 * and calls proxy_string_field(field, 16, buf, 0, 40) on 40 x 'A', detecting the overflow with a
 * canary byte placed after field[16] in a struct. Changes: the buffer and its length come from
 * the PoC file; field is a plain 16-byte stack array, so AddressSanitizer reports the write past
 * its end (it cannot see an overflow into the next member of the same struct). The build command
 * cuts the function out of the build's own ns_ioalib_engine_impl.c into proxy_string_field.inc,
 * as attack.sh does; it is static there, and its only caller, socket_parse_proxy_v1(), parses
 * PROXY-protocol headers on TCP connections to a running server. */
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "proxy_string_field.inc"

static uint8_t buf[65536]; /* the first 64 KiB of the PoC */

int main(int argc, char **argv) {
  if (argc < 2) return 2;
  FILE *f = fopen(argv[1], "rb");
  if (!f) return 2;
  size_t len = fread(buf, 1, sizeof buf, f);
  fclose(f);

  char field[16];
  size_t next = proxy_string_field(field, sizeof(field), buf, 0, len);
  if (next)
    printf("proxy_string_field: field \"%.*s\", next index %zu\n", (int)strnlen(field, sizeof(field)), field, next);
  else
    printf("proxy_string_field: no field (0)\n");
  return 0;
}
