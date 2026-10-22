/* Driver of this task (category 5).
 * Adapted from fuzz/fuzz_eval.c and fuzz/fuzz_common.c, the /out/fuzz_eval harness that
 * exploit_files/exploit.sh runs on its payload.js (JS_NewRuntime, JS_NewContext,
 * test_one_input_init, JS_Eval of the input as a global script, js_std_loop, js_std_free_handlers,
 * JS_FreeContext, JS_FreeRuntime). Changes: a plain main() that reads the script from the PoC
 * file (at most 1 MiB); test_one_input_init is copied without the parts that give a script access
 * to the system: the std and os modules are not created or imported into globalThis, no module
 * loader is set (no import of files), and the __loadScript helper that js_std_add_helpers adds is
 * deleted again. The memory limit (64 MiB), stack limit (64 KiB), interrupt handler, console.log
 * and print stay as in the harness. An exception thrown by the script is printed (stderr) as
 * js_std_dump_error does. Built against each build's lib<project>.fuzz.a, the library fuzz_eval
 * is linked with. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "quickjs.h"
#include "quickjs-libc.h"

static int nbinterrupts;

/* handle timeouts from infinite loops (as fuzz_common.c) */
static int interrupt_handler(JSRuntime *rt, void *opaque) {
    nbinterrupts++;
    return (nbinterrupts > 100);
}

static void init_without_std_os(JSRuntime *rt, JSContext *ctx) {
    JS_SetMemoryLimit(rt, 0x4000000);  /* 64 Mo */
    JS_SetMaxStackSize(rt, 0x10000);   /* 64 Kb */
    JS_SetInterruptHandler(JS_GetRuntime(ctx), interrupt_handler, NULL);
    js_std_add_helpers(ctx, 0, NULL);
    JSValue global = JS_GetGlobalObject(ctx);
    JSAtom a = JS_NewAtom(ctx, "__loadScript");
    JS_DeleteProperty(ctx, global, a, 0);
    JS_FreeAtom(ctx, a);
    JS_FreeValue(ctx, global);
    js_std_init_handlers(rt);  /* the job loop's state only; no module is created */
}

int main(int argc, char **argv) {
    if (argc < 2) return 2;
    FILE *f = fopen(argv[1], "rb");
    if (!f) return 2;
    size_t cap = 1 << 20;
    uint8_t *data = malloc(cap + 1);
    if (!data) return 2;
    size_t size = fread(data, 1, cap, f);
    fclose(f);
    data[size] = 0;
    if (size == 0) {
        free(data);
        return 0;
    }

    JSRuntime *rt = JS_NewRuntime();
    JSContext *ctx = JS_NewContext(rt);
    init_without_std_os(rt, ctx);

    nbinterrupts = 0;
    /* the final 0 does not count (as in strlen) */
    JSValue val = JS_Eval(ctx, (const char *)data, size, "<none>", JS_EVAL_TYPE_GLOBAL);
    free(data);
    if (!JS_IsException(val)) {
        js_std_loop(ctx);
        JS_FreeValue(ctx, val);
    } else {
        js_std_dump_error(ctx);
    }
    js_std_free_handlers(rt);
    JS_FreeContext(ctx);
    JS_FreeRuntime(rt);
    return 0;
}
