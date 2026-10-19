// Category-5 driver shared by double-conversion FZ_13, FZ_22, FZ_3 and FZ_6.
//
// Adapted from two dataset files:
//  - projects/double-conversion/setup/string_to_double_fuzzer.cc (the OSS-Fuzz harness): a
//    "strtod" line goes to StringToDoubleConverter::StringToDouble with exactly the harness's
//    flags and values;
//  - test/cctest/test-dtoa.cc (DoubleToAscii helper of the unit tests the exploits run): a "dtoa"
//    line goes to DoubleToStringConverter::DoubleToAscii, as the test does.
// What changed: the inputs are read from the PoV file, one call per line, instead of the
// harness's data or the test's hard-coded values, and each result is printed (the harness and
// the test print nothing). The project's code is called through its public API only.
//
// PoV format (lines separated by '\n'; empty lines are ignored):
//   strtod <text>                    <text> = the rest of the line, passed as it is
//   dtoa <MODE> <digits> <value>     MODE = SHORTEST | SHORTEST_SINGLE | FIXED | PRECISION;
//                                    <digits> = requested_digits (ignored by the SHORTEST modes,
//                                    0..100 for FIXED, 1..120 for PRECISION: the limits of
//                                    ToFixed / ToPrecision);
//                                    <value> = a decimal number (read with the C library's
//                                    strtod) or 0x followed by the 64-bit pattern of the double
//                                    (1 to 16 hex digits). SHORTEST_SINGLE uses (float)<value>,
//                                    as the test passes floats. NaN and infinities are refused
//                                    (DoubleToAscii does not accept them).
// Output: one line per call: "<line> strtod bits=<16 hex digits> value=<%.17g> processed=<n>"
// or "<line> dtoa <MODE> <digits> sign=<0|1> digits=<buffer> length=<n> point=<n>".
#include <cerrno>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#include "double-conversion/double-conversion.h"

using double_conversion::DoubleToStringConverter;
using double_conversion::StringToDoubleConverter;

static const size_t kMaxInput = 16u << 20;

static void do_strtod(long lineno, const char* text, size_t len) {
  // the converter string_to_double_fuzzer.cc builds
  StringToDoubleConverter converter(
      StringToDoubleConverter::ALLOW_HEX |
          StringToDoubleConverter::ALLOW_OCTALS |
          StringToDoubleConverter::ALLOW_TRAILING_JUNK |
          StringToDoubleConverter::ALLOW_LEADING_SPACES |
          StringToDoubleConverter::ALLOW_TRAILING_SPACES |
          StringToDoubleConverter::ALLOW_SPACES_AFTER_SIGN |
          StringToDoubleConverter::ALLOW_CASE_INSENSIBILITY |
          StringToDoubleConverter::ALLOW_HEX_FLOATS,
      /*empty_string_value=*/0.0,
      /*junk_string_value=*/0.0, "inf", "nan");
  int processed = 0;
  double d = converter.StringToDouble(text, static_cast<int>(len), &processed);
  uint64_t bits;
  memcpy(&bits, &d, sizeof bits);
  printf("%ld strtod bits=%016llx value=%.17g processed=%d\n", lineno,
         static_cast<unsigned long long>(bits), d, processed);
}

static bool parse_value(const std::string& tok, double* out) {
  if (tok.size() > 2 && tok[0] == '0' && (tok[1] == 'x' || tok[1] == 'X')) {
    if (tok.size() > 18) return false;
    uint64_t bits = 0;
    for (size_t i = 2; i < tok.size(); i++) {
      char c = tok[i];
      int v = (c >= '0' && c <= '9') ? c - '0' : (c >= 'a' && c <= 'f') ? c - 'a' + 10
            : (c >= 'A' && c <= 'F') ? c - 'A' + 10 : -1;
      if (v < 0) return false;
      bits = (bits << 4) | static_cast<uint64_t>(v);
    }
    memcpy(out, &bits, sizeof bits);
    return true;
  }
  if (tok.empty()) return false;
  char* end = nullptr;
  errno = 0;
  *out = strtod(tok.c_str(), &end);
  return end != nullptr && *end == '\0';
}

static void do_dtoa(long lineno, const std::string& rest) {
  std::vector<std::string> tok;
  size_t i = 0;
  while (i < rest.size()) {
    while (i < rest.size() && (rest[i] == ' ' || rest[i] == '\t' || rest[i] == '\r')) i++;
    size_t j = i;
    while (j < rest.size() && rest[j] != ' ' && rest[j] != '\t' && rest[j] != '\r') j++;
    if (j > i) tok.push_back(rest.substr(i, j - i));
    i = j;
  }
  if (tok.size() != 3) {
    printf("%ld dtoa: expected <MODE> <digits> <value>\n", lineno);
    return;
  }
  DoubleToStringConverter::DtoaMode mode;
  if (tok[0] == "SHORTEST") mode = DoubleToStringConverter::SHORTEST;
  else if (tok[0] == "SHORTEST_SINGLE") mode = DoubleToStringConverter::SHORTEST_SINGLE;
  else if (tok[0] == "FIXED") mode = DoubleToStringConverter::FIXED;
  else if (tok[0] == "PRECISION") mode = DoubleToStringConverter::PRECISION;
  else {
    printf("%ld dtoa: unknown mode\n", lineno);
    return;
  }
  char* end = nullptr;
  long digits = strtol(tok[1].c_str(), &end, 10);
  if (end == nullptr || *end != '\0' || tok[1].empty()) {
    printf("%ld dtoa: bad digits\n", lineno);
    return;
  }
  if (mode == DoubleToStringConverter::SHORTEST || mode == DoubleToStringConverter::SHORTEST_SINGLE) {
    digits = 0;
  } else if ((mode == DoubleToStringConverter::FIXED && (digits < 0 || digits > 100)) ||
             (mode == DoubleToStringConverter::PRECISION && (digits < 1 || digits > 120))) {
    printf("%ld dtoa: digits out of range\n", lineno);
    return;
  }
  double v;
  if (!parse_value(tok[2], &v)) {
    printf("%ld dtoa: bad value\n", lineno);
    return;
  }
  if (mode == DoubleToStringConverter::SHORTEST_SINGLE) v = static_cast<float>(v);
  if (!std::isfinite(v)) {
    printf("%ld dtoa: value is not finite\n", lineno);
    return;
  }
  char buffer[2048];
  memset(buffer, 0, sizeof buffer);
  bool sign = false;
  int length = 0, point = 0;
  DoubleToStringConverter::DoubleToAscii(v, mode, static_cast<int>(digits), buffer,
                                         static_cast<int>(sizeof buffer), &sign, &length, &point);
  buffer[sizeof buffer - 1] = '\0';
  printf("%ld dtoa %s %ld sign=%d digits=%s length=%d point=%d\n", lineno, tok[0].c_str(), digits,
         sign ? 1 : 0, buffer, length, point);
}

int main(int argc, char** argv) {
  if (argc != 2) {
    fprintf(stderr, "usage: %s <pov>\n", argv[0]);
    return 2;
  }
  setvbuf(stdout, nullptr, _IOLBF, 0);  // every result is out before a later line can abort
  FILE* f = fopen(argv[1], "rb");
  if (!f) {
    printf("cannot open the PoV\n");
    return 1;
  }
  std::string data;
  char chunk[65536];
  size_t n;
  while ((n = fread(chunk, 1, sizeof chunk, f)) > 0) {
    data.append(chunk, n);
    if (data.size() > kMaxInput) {
      printf("the PoV is larger than %zu bytes\n", kMaxInput);
      fclose(f);
      return 1;
    }
  }
  fclose(f);
  long lineno = 0;
  size_t pos = 0;
  while (pos < data.size()) {
    size_t nl = data.find('\n', pos);
    if (nl == std::string::npos) nl = data.size();
    std::string line = data.substr(pos, nl - pos);
    pos = nl + 1;
    lineno++;
    if (line.empty()) continue;
    if (line.compare(0, 7, "strtod ") == 0) {
      do_strtod(lineno, line.data() + 7, line.size() - 7);
    } else if (line.compare(0, 5, "dtoa ") == 0) {
      do_dtoa(lineno, line.substr(5));
    } else {
      printf("%ld: unknown line (expected strtod or dtoa)\n", lineno);
    }
  }
  printf("done\n");
  return 0;
}
