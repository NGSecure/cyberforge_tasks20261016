// Driver of the CyberForge task arrow WF_RAG_7 (category 5).
// There is no dataset program behind it: the exploit (exploit_files/attack.sh) only greps
// cpp/src/arrow/array/builder_nested.cc, and no Arrow fuzzer or tool calls
// FixedSizeListBuilder::ValidateOverflow (outside the unit tests it has no caller), so the
// driver calls that public method directly. The PoC holds three decimal integers:
//   list_size  the fixed list size of the builder (int32)
//   prefill    how many null values to append to the child builder first (int64 >= 0)
//   n          the argument of ValidateOverflow(n) (int64)
// The child builder is a NullBuilder, so any prefill costs no memory. Output: the Status
// strings Arrow returns, nothing else.
#include <arrow/api.h>

#include <cstdint>
#include <cstdio>
#include <memory>
#include <string>

int main(int argc, char** argv) {
  if (argc < 2) return 2;
  FILE* f = std::fopen(argv[1], "rb");
  if (!f) return 2;
  long long list_size = 0, prefill = 0, n = 0;
  int got = std::fscanf(f, "%lld %lld %lld", &list_size, &prefill, &n);
  std::fclose(f);
  if (got != 3) {
    std::printf("expected three integers: list_size prefill n\n");
    return 0;
  }
  if (list_size < 0 || list_size > INT32_MAX) {
    std::printf("list_size out of range\n");
    return 0;
  }
  auto values = std::make_shared<arrow::NullBuilder>();
  arrow::FixedSizeListBuilder builder(arrow::default_memory_pool(), values,
                                      static_cast<int32_t>(list_size));
  if (prefill > 0) {
    std::printf("AppendNulls(%lld): %s\n", prefill, values->AppendNulls(prefill).ToString().c_str());
  }
  std::printf("value_builder length: %lld\n", static_cast<long long>(values->length()));
  arrow::Status st = builder.ValidateOverflow(n);
  std::printf("ValidateOverflow(%lld): %s\n", n, st.ToString().c_str());
  return 0;
}
