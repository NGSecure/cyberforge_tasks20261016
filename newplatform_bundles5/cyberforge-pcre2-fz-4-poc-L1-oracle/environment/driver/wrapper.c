/* Driver of this task (category 5).
 *
 * No dataset program is behind it: the dataset's exploit.sh only greps the source for the
 * removed check (its exploit.c is never compiled). The injected change is in the machine code
 * that <project>_jit_compile.c generates, which AddressSanitizer does not instrument, and no
 * harness or CLI of the build runs JIT code on its own input: see below.
 *
 * The driver is the project's own fuzz target, src/<project>_fuzzsupport.c (the source of
 * /out/<project>_fuzzer), included unchanged and compiled with SUPPORT_DIFF_FUZZ: <project>'s own
 * differential mode (configure --enable-diff-fuzz-support, which the OSS-Fuzz build.sh does
 * not pass). In that mode each match the target makes is run by the interpreter and by the
 * JIT, and describe_failure() prints both results and calls abort() when they differ.
 *
 * One change: the target adds <project>_DISABLE_RECURSELOOP_CHECK to every match
 * (BASE_MATCH_OPTIONS), but <project>_match() uses the JIT only for options listed in
 * PUBLIC_JIT_MATCH_OPTIONS (<project>_match.c), which does not contain it; so its "JIT" match
 * silently ran the interpreter again. Here that option is defined as 0, so the target's JIT
 * match really runs the JIT code and its interpreter match runs the interpreter.
 *
 * Input format: the same as /out/<project>_fuzzer's. The first 8 bytes are option bits read as
 * one little-endian 64-bit number: compile options from its high 32 bits, match options from
 * its low 32 bits (masked by ALLOWED_COMPILE_OPTIONS / ALLOWED_MATCH_OPTIONS below); the rest
 * is the pattern, which is also the subject string. Built the way build.sh builds
 * <project>_fuzzer (libFuzzer, AddressSanitizer), against the build's 8-bit library
 * /src/<project>/.libs/lib<project>-8.a. */
#define SUPPORT_DIFF_FUZZ 1
#ifndef PCRE2_CODE_UNIT_WIDTH
#define PCRE2_CODE_UNIT_WIDTH 8
#endif
#include "pcre2_internal.h"
#undef PCRE2_DISABLE_RECURSELOOP_CHECK
#define PCRE2_DISABLE_RECURSELOOP_CHECK 0u
#include "pcre2_fuzzsupport.c"
