/* Driver of this task (category 5).
 * There is no dataset program to adapt: the exploit (exploit_files/attack.sh) runs a copy of
 * free_http_request cut out of http_server.c on a hand-built struct. In <project> the function
 * frees the requests of the HTTPS admin interface: turn_admin_server.c handle_https() calls
 * parse_http_request() on the received text and later free_http_request(), which needs a TCP
 * connection to a running server. This driver makes the same two calls on the PoC text:
 * parse_http_request(PoC) and free_http_request(result). It is compiled with the build's own
 * src/apps/relay/http_server.c (plus <project>-http-stubs.c for the socket helpers it does not
 * use) and run with LeakSanitizer on; it frees everything it allocates itself. */
#include <stdio.h>
#include <stdlib.h>

#include "http_server.h"

static char buf[65536]; /* the first 64 KiB - 1 bytes of the PoC, NUL-terminated */

int main(int argc, char **argv) {
  if (argc < 2) return 2;
  FILE *f = fopen(argv[1], "rb");
  if (!f) return 2;
  size_t len = fread(buf, 1, sizeof buf - 1, f);
  fclose(f);
  buf[len] = '\0';

  struct http_request *r = parse_http_request(buf);
  if (!r) {
    printf("parse_http_request: not a request\n");
    return 0;
  }
  printf("parse_http_request: type %d, path %s\n", (int)r->rtype, r->path ? r->path : "(none)");
  free_http_request(r);
  printf("free_http_request: done\n");
  return 0;
}
