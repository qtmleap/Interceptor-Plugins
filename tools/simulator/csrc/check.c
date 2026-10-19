// Syntax-only entry point, compiled in the same translation unit as the pinned, unmodified
// bridge.c so it reuses that file's static allocator, UTF-8 validation, deadline and
// classification helpers instead of duplicating them. Drift note: this must mirror the admission
// and bootstrap steps of qjs_run (re-check when the pinned revision changes).
//
// The source is only COMPILED (JS_EVAL_FLAG_COMPILE_ONLY): no JS_EvalFunction, JS_Call, or job
// execution ever happens, so top-level loops and throws are accepted.

#include "bridge.c"

// Returns a QJS_* status: QJS_OK, QJS_INVALID_INPUT, QJS_SCRIPT_ERROR (syntax error), QJS_TIMEOUT,
// QJS_MEMORY_OR_STACK or QJS_INTERNAL. On a compile failure `diag` receives a NUL-terminated,
// bounded message (message plus engine backtrace location lines).
int sim_check_syntax(const QJSLimits *limits, const uint8_t *source, size_t source_len,
                     char *diag, size_t diag_cap) {
    RunState st;
    JSRuntime *rt = NULL;
    JSContext *ctx = NULL;
    uint8_t *src = NULL;
    int status = QJS_INTERNAL;

    if (diag && diag_cap) diag[0] = 0;
    memset(&st, 0, sizeof(st));
    st.deadline_ns = now_ns() + (uint64_t)(limits ? limits->deadline_ms : 0) * 1000000ull;
    if (!limits || limits->deadline_ms == 0 || limits->heap_bytes == 0 || limits->stack_bytes == 0)
        return QJS_INTERNAL;
    if (!source || source_len == 0 || source_len > limits->max_source_bytes) return QJS_INVALID_INPUT;
    if (memchr(source, 0, source_len) != NULL || !utf8_valid(source, source_len)) return QJS_INVALID_INPUT;

    src = copy_z(source, source_len);
    if (!src) return QJS_MEMORY_OR_STACK;

    rt = JS_NewRuntime2(&limited_funcs, &st);
    if (!rt) { status = st.oom ? QJS_MEMORY_OR_STACK : QJS_INTERNAL; goto cleanup; }
    JS_SetMemoryLimit(rt, limits->heap_bytes);
    JS_SetMaxStackSize(rt, limits->stack_bytes);
    JS_UpdateStackTop(rt);
    JS_SetCanBlock(rt, 0);
    JS_SetInterruptHandler(rt, interrupt_cb, &st);

    ctx = JS_NewContextRaw(rt);
    if (!ctx) { status = st.oom ? QJS_MEMORY_OR_STACK : QJS_INTERNAL; goto cleanup; }
    if (JS_AddIntrinsicBaseObjects(ctx) || JS_AddIntrinsicDate(ctx) || JS_AddIntrinsicEval(ctx) ||
        JS_AddIntrinsicStringNormalize(ctx) || JS_AddIntrinsicRegExp(ctx) || JS_AddIntrinsicJSON(ctx) ||
        JS_AddIntrinsicProxy(ctx) || JS_AddIntrinsicMapSet(ctx) || JS_AddIntrinsicPromise(ctx)) {
        status = st.oom ? QJS_MEMORY_OR_STACK : QJS_INTERNAL;
        goto cleanup;
    }

    {
        JSValue code = JS_Eval(ctx, (const char *)src, source_len, "<plugin>",
                               JS_EVAL_TYPE_GLOBAL | JS_EVAL_FLAG_COMPILE_ONLY);
        if (JS_IsException(code)) {
            if (st.stop) status = st.stop;
            else if (st.oom) status = QJS_MEMORY_OR_STACK;
            else {
                // The exception is engine-created by the parser, never user-defined, so reading
                // its string properties runs no user code.
                JSValue ex = JS_GetException(ctx);
                status = QJS_SCRIPT_ERROR;
                if (diag && diag_cap && JS_IsObject(ex)) {
                    static const char *const props[] = {"message", "stack"};
                    size_t used = 0;
                    for (size_t k = 0; k < 2; k++) {
                        JSValue pv = JS_GetPropertyStr(ctx, ex, props[k]);
                        if (JS_IsString(pv)) {
                            size_t n;
                            const char *c = JS_ToCStringLen2(ctx, &n, pv, 0);
                            if (c) {
                                if (k == 1 && n > 0 && used + 1 < diag_cap) diag[used++] = '\n';
                                for (size_t i = 0; i < n && used + 1 < diag_cap; i++) diag[used++] = c[i];
                                JS_FreeCString(ctx, c);
                            }
                        }
                        JS_FreeValue(ctx, pv);
                    }
                    diag[used] = 0;
                }
                JS_FreeValue(ctx, ex);
            }
        } else {
            JS_FreeValue(ctx, code);   // compiled function object is discarded, never run
            status = QJS_OK;
        }
    }

cleanup:
    if (ctx) JS_FreeContext(ctx);
    if (rt) JS_FreeRuntime(rt);
    free(src);
    return status;
}

/* Let the native platform supply its flags: Linux architectures differ. */
#include <fcntl.h>
int sim_open_flags(void) { return O_NOFOLLOW | O_NONBLOCK; }

/* Core's extra pre/post-parse restrictions beyond the bridge's strict JSON scanner. */
int sim_validate_json(const uint8_t *bytes, size_t len, int object_required, int depth) {
    uint8_t *text = copy_z(bytes, len);
    if (!text) return 0;
    int valid = json_check(text, len, depth);
    size_t first = 0;
    while (first < len && strchr(" \t\r\n", text[first])) first++;
    if (object_required && (first == len || text[first] != '{')) valid = 0;
    int quoted = 0, escaped = 0;
    for (size_t i = 0; valid && i < len; i++) {
        const uint8_t ch = text[i];
        if (quoted) {
            if (escaped) escaped = 0;
            else if (ch == '\\') escaped = 1;
            else if (ch == '"') quoted = 0;
        } else if (ch == '"') quoted = 1;
        else if (ch == '-' || (ch >= '0' && ch <= '9')) {
            const size_t start = i;
            int integral = 1;
            while (i < len && !strchr(" \t\r\n,]}", text[i])) {
                if (text[i] == '.' || text[i] == 'e' || text[i] == 'E') integral = 0;
                i++;
            }
            const size_t digits = start + (ch == '-');
            const size_t count = i - digits;
            if (integral && (count > 16 || (count == 16 && memcmp(text + digits, "9007199254740991", 16) > 0))) valid = 0;
            if (i) i--;
        }
    }
    free(text);
    return valid;
}
