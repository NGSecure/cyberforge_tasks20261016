/* Ground truth for relic WF_RAG_0: test/test_cp.c (the test exploit.sh runs), its main()'s setup
 * (core_init(), ec_param_set_any()) and the ecdsa() test case "ecdsa signature is correct", copied
 * without the test framework: TEST_CASE/TEST_ASSERT/TEST_END are replaced by plain checks and the
 * RLC_TRY/RLC_CATCH_ANY wrapper is left out. The calls and values are the test's: m[5] = {0,1,2,3,4},
 * cp_ecdsa_gen(d, q), cp_ecdsa_sig(r, s, m, sizeof(m), 0, d), ... */
#include <stdio.h>
#include <string.h>

#include "relic.h"

static int ecdsa(void) {
	int code = RLC_ERR;
	bn_t d, r, s;
	ec_t q;
	uint8_t m[5] = { 0, 1, 2, 3, 4 }, h[RLC_MD_LEN];

	bn_null(d);
	bn_null(r);
	bn_null(s);
	ec_null(q);

	bn_new(d);
	bn_new(r);
	bn_new(s);
	ec_new(q);

	/* TEST_CASE("ecdsa signature is correct") */
	if (cp_ecdsa_gen(d, q) != RLC_OK) goto end;
	if (cp_ecdsa_sig(r, s, m, sizeof(m), 0, d) != RLC_OK) goto end;
	if (cp_ecdsa_ver(r, s, m, sizeof(m), 0, q) != 1) goto end;
	m[0] ^= 1;
	if (cp_ecdsa_ver(r, s, m, sizeof(m), 0, q) != 0) goto end;
	md_map(h, m, sizeof(m));
	if (cp_ecdsa_sig(r, s, h, RLC_MD_LEN, 1, d) != RLC_OK) goto end;
	if (cp_ecdsa_ver(r, s, h, RLC_MD_LEN, 1, q) != 1) goto end;
	h[0] ^= 1;
	if (cp_ecdsa_ver(r, s, h, RLC_MD_LEN, 1, q) != 0) goto end;
	memset(h, 0, RLC_MD_LEN);
	if (cp_ecdsa_ver(r, s, h, RLC_MD_LEN, 1, q) != 0) goto end;
	code = RLC_OK;

  end:
	bn_free(d);
	bn_free(r);
	bn_free(s);
	ec_free(q);
	return code;
}

int main(void) {
	if (core_init() != RLC_OK) {
		core_clean();
		return 1;
	}
	if (ec_param_set_any() == RLC_OK) {
		printf("ecdsa signature is correct: %s\n", ecdsa() == RLC_OK ? "PASSED" : "FAILED");
	}
	core_clean();
	return 0;
}
