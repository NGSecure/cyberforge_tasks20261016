/* Driver of this task (category 5).
 *
 * Adapted from the dataset's exploit_files/wrapper.cc (which exploit.sh never ran): it
 * #includes Gandiva's cpp/src/gandiva/precompiled/time.cc and calls castTIMESTAMP_utf8() with
 * wrapper.cc's own stub of gdv_fn_time_with_zone(), which accepts only the zone "UTC".
 * Gandiva is not part of the OSS-Fuzz build (<project>_GANDIVA is off), so this driver compiles
 * time.cc itself, from each build's source tree. Changes against wrapper.cc:
 *  - the input is the PoC file (argv[1]) instead of the hard-coded
 *    "2000-09-23 9:45:30.920 UTC", and it is passed with its full length in a heap buffer of
 *    exactly that size, with no terminating NUL, the way <project> hands string values to Gandiva
 *    functions (wrapper.cc passed only the length up to the zone's first letter, on a
 *    NUL-terminated stack copy);
 *  - time.cc is included through the include path (-I/src/<project>/cpp/src) instead of by its
 *    absolute path; the two Gandiva context functions time.cc calls get no-op stubs, and four
 *    functions of other gandiva/precompiled files, used only by other functions of time.cc,
 *    get stubs so that the program links (wrapper.cc did not link);
 *  - an empty file is not passed on (Gandiva never calls the function on a zero-length value);
 *  - it prints the function's return value instead of EXPLOIT_TRIGGERED / NO_TRIGGER.
 * Note: time.cc's error path (set_error_for_date: an invalid date or time, or a zone the stub
 * rejects) prints the whole input with "%s", so on such an input both builds read past the
 * end of the buffer too. */
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

extern "C" {
int gdv_fn_time_with_zone(int* time_fields, const char* zone, int zone_len, int64_t* ret_time) {
  (void)time_fields;
  std::string z(zone, (size_t)zone_len);
  // trim
  while(!z.empty() && (z.back()==' '||z.back()=='\n'||z.back()=='\r'||z.back()=='\t')) z.pop_back();
  if (z == "UTC") { *ret_time = 0x11223344; return 0; }
  return 1;
}
}

// the build's own source file (the vulnerable or the fixed one)
#include "gandiva/precompiled/time.cc"

extern "C" {
void gdv_fn_context_set_error_msg(int64_t context_ptr, const char* err_msg) {
  (void)context_ptr;
  (void)err_msg;
}
uint8_t* gdv_fn_context_arena_malloc(int64_t context_ptr, int32_t data_len) {
  (void)context_ptr;
  (void)data_len;
  return nullptr;
}
// Only so that the other functions of time.cc link (they come from other files of
// gandiva/precompiled); castTIMESTAMP_utf8 does not call them.
bool is_substr_utf8_utf8(const char* data, gdv_int32 data_len, const char* substr,
                         gdv_int32 substr_len) {
  (void)data; (void)data_len; (void)substr; (void)substr_len;
  return false;
}
gdv_int64 date_add_int64_timestamp(gdv_int64 days, gdv_timestamp millis) {
  (void)days;
  return millis;
}
}
bool did_days_overflow(arrow_vendored::date::year_month_day ymd) {
  (void)ymd;
  return false;
}
int last_possible_day_in_month(int month, int year) {
  (void)month; (void)year;
  return 28;
}

int main(int argc, char** argv) {
  if (argc < 2) return 2;
  FILE* f = fopen(argv[1], "rb");
  if (!f) return 2;
  std::string data;
  char chunk[4096];
  size_t n;
  while ((n = fread(chunk, 1, sizeof chunk, f)) > 0 && data.size() < (1u << 20)) data.append(chunk, n);
  fclose(f);
  if (data.empty()) {  // castTIMESTAMP_utf8 is never called with a zero-length value
    printf("empty input\n");
    return 0;
  }
  if (data.size() > (1u << 20)) data.resize(1u << 20);
  char* buf = static_cast<char*>(malloc(data.size()));  // exactly the value's bytes, no NUL
  if (!buf) return 2;
  memcpy(buf, data.data(), data.size());
  int64_t r = castTIMESTAMP_utf8(0, buf, static_cast<int32_t>(data.size()));
  printf("castTIMESTAMP_utf8 returned %lld\n", static_cast<long long>(r));
  free(buf);
  return 0;
}
