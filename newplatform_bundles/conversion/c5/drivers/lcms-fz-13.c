/* Category-5 driver for lcms FZ_13.
 *
 * Adapted from testbed/testcms2.c, CheckFloatXYZ (the unit test the exploit runs; it fails at
 * cmsCreateTransform(IdentityMatrixProfile(cmsSigXYZData), TYPE_XYZA_FLT, cmsCreateXYZProfile(),
 * TYPE_XYZA_FLT, INTENT_RELATIVE_COLORIMETRIC, cmsFLAGS_COPY_ALPHA) with "Mismatched alpha channels").
 * What changed: the input format, output format, flags and intent of cmsCreateTransform are read
 * from the PoV (the header layout of the OSS-Fuzz harness cms_transform_all_fuzzer.c: four uint32
 * little-endian values, intent taken % 16 as there), followed by the bytes of the one input pixel
 * (the test uses {1.0, 1.0, 1.0, 0.5} as floats). The two profiles are the test's: an identity-matrix
 * XYZ profile built as IdentityMatrixProfile() builds it (the identity matrix is written out instead of
 * calling the internal _cmsMAT3identity) and cmsCreateXYZProfile(). The driver prints the errors lcms
 * reports, whether the transform was created and, if so, the bytes of the transformed pixel.
 *
 * PoV: uint32 input_format, uint32 output_format, uint32 flags, uint32 intent (% 16), then up to
 * 1024 bytes of input pixel data (missing bytes are zero). At least 16 bytes.
 */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "lcms2.h"

#define PIXBUF 1024

static void log_error(cmsContext ctx, cmsUInt32Number code, const char *text) {
    (void)ctx;
    printf("lcms error %u: %s\n", (unsigned)code, text ? text : "");
}

static cmsHPROFILE identity_matrix_profile(cmsColorSpaceSignature dataSpace) {
    cmsContext ctx = 0;
    cmsFloat64Number identity[9] = {1, 0, 0, 0, 1, 0, 0, 0, 1};
    cmsFloat64Number zero[3] = {0, 0, 0};
    cmsPipeline *forward, *reverse;
    cmsHPROFILE p = cmsCreateProfilePlaceholder(ctx);
    if (!p) return NULL;
    cmsSetProfileVersion(p, 4.3);
    cmsSetDeviceClass(p, cmsSigColorSpaceClass);
    cmsSetColorSpace(p, dataSpace);
    cmsSetPCS(p, cmsSigXYZData);
    cmsSetHeaderRenderingIntent(p, INTENT_RELATIVE_COLORIMETRIC);
    cmsWriteTag(p, cmsSigMediaWhitePointTag, cmsD50_XYZ());
    forward = cmsPipelineAlloc(0, 3, 3);
    cmsPipelineInsertStage(forward, cmsAT_END, cmsStageAllocMatrix(ctx, 3, 3, identity, zero));
    cmsWriteTag(p, cmsSigDToB1Tag, forward);
    cmsPipelineFree(forward);
    reverse = cmsPipelineAlloc(0, 3, 3);
    cmsPipelineInsertStage(reverse, cmsAT_END, cmsStageAllocMatrix(ctx, 3, 3, identity, zero));
    cmsWriteTag(p, cmsSigBToD1Tag, reverse);
    cmsPipelineFree(reverse);
    return p;
}

static uint32_t le32(const uint8_t *b) {
    return (uint32_t)b[0] | (uint32_t)b[1] << 8 | (uint32_t)b[2] << 16 | (uint32_t)b[3] << 24;
}

int main(int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "usage: %s <pov>\n", argv[0]);
        return 2;
    }
    setvbuf(stdout, NULL, _IOLBF, 0);
    FILE *f = fopen(argv[1], "rb");
    if (!f) {
        printf("cannot open the PoV\n");
        return 1;
    }
    static uint8_t data[16 + PIXBUF];
    size_t size = fread(data, 1, sizeof data, f);
    fclose(f);
    if (size < 16) {
        printf("the PoV is shorter than 16 bytes: nothing is run\n");
        return 0;
    }
    uint32_t in_fmt = le32(data), out_fmt = le32(data + 4), flags = le32(data + 8);
    uint32_t intent = le32(data + 12) % 16;
    static uint8_t in[PIXBUF], out[PIXBUF];
    memcpy(in, data + 16, size - 16);
    cmsSetLogErrorHandler(log_error);
    printf("input_format=%08x output_format=%08x flags=%08x intent=%u\n", (unsigned)in_fmt,
           (unsigned)out_fmt, (unsigned)flags, (unsigned)intent);
    cmsHPROFILE input = identity_matrix_profile(cmsSigXYZData);
    cmsHPROFILE xyz = cmsCreateXYZProfile();
    cmsHTRANSFORM xform = cmsCreateTransform(input, in_fmt, xyz, out_fmt, intent, flags);
    cmsCloseProfile(input);
    cmsCloseProfile(xyz);
    if (!xform) {
        printf("xform=NULL\n");
        return 0;
    }
    printf("xform=OK\n");
    cmsDoTransform(xform, in, out, 1);
    unsigned bytes = T_BYTES(out_fmt) ? T_BYTES(out_fmt) : 8;
    unsigned n = (T_CHANNELS(out_fmt) + T_EXTRA(out_fmt)) * bytes;
    if (n > PIXBUF) n = PIXBUF;
    printf("output pixel (%u bytes):", n);
    for (unsigned i = 0; i < n; i++) printf("%s%02x", i % 4 ? "" : " ", out[i]);
    printf("\n");
    cmsDeleteTransform(xform);
    return 0;
}
