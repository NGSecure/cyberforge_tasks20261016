/* Part of the judge of these tasks (category 5); not
 * from the dataset. Stand-ins for the <project> functions that src/apps/relay/http_server.c calls
 * outside the code under test: the ioa_* socket helpers used only by write_http_echo() (the
 * HTTP echo reply on a TURN socket, which needs the whole server) and the logger. With them the
 * judge compiles the build's own http_server.c into a small program. None of them is reached
 * from parse_http_request(), get_http_header_value(), free_http_request() or the str_buffer_*
 * functions (the logger only when calloc fails). */
#include <stdarg.h>
#include <stdio.h>

#include "ns_turn_ioalib.h"
#include "ns_turn_utils.h"

ioa_network_buffer_handle ioa_network_buffer_allocate(ioa_engine_handle e) {
  (void)e;
  return NULL;
}

uint8_t *ioa_network_buffer_data(ioa_network_buffer_handle nbh) {
  (void)nbh;
  return NULL;
}

size_t ioa_network_buffer_get_capacity(ioa_network_buffer_handle nbh) {
  (void)nbh;
  return 0;
}

void ioa_network_buffer_set_size(ioa_network_buffer_handle nbh, size_t len) {
  (void)nbh;
  (void)len;
}

SOCKET_APP_TYPE get_ioa_socket_app_type(ioa_socket_handle s) {
  (void)s;
  return UNKNOWN_APP_SOCKET;
}

int send_data_from_ioa_socket_nbh(ioa_socket_handle s, ioa_addr *dest_addr, ioa_network_buffer_handle nbh, int ttl,
                                  int tos, int *skip) {
  (void)s;
  (void)dest_addr;
  (void)nbh;
  (void)ttl;
  (void)tos;
  (void)skip;
  return -1;
}

int ioa_socket_tobeclosed(ioa_socket_handle s) {
  (void)s;
  return 1;
}

void turn_log_func_default(const char *file, int line, TURN_LOG_LEVEL level, const char *format, ...) {
  (void)file;
  (void)line;
  (void)level;
  va_list ap;
  va_start(ap, format);
  vfprintf(stderr, format, ap);
  va_end(ap);
}
