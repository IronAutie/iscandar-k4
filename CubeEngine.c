/* CubeEngine.c -- the STUB per-cube engine. See CubeEngine.h
 * for the boundary this file stands behind, and for what is
 * stubbed (placement) versus kept (the boundary contract). */

#include "CubeEngine.h"
#include "K4Status.h"

#include <string.h>

void cube_engine_init(CubeEngine *engine)
{
    memset(engine->words, 0, sizeof(engine->words));
    engine->count_overall = 0;
}

static int stub_bit(const CubeEngine *engine, uint32_t sector)
{
    return (int)((engine->words[sector / 32u] >> (sector % 32u)) & 1u);
}

void cube_engine_call(CubeEngine *engine, int32_t request,
                      CubeEngineResult *out)
{
    uint32_t want;
    uint32_t run_start;
    uint32_t run_length;
    uint32_t s;

    /* Engine.__call__ step 1: the overall admissibility gate. */
    if (request > 0
        && (uint32_t)request > K4_SECTORS_PER_CUBE - engine->count_overall) {
        out->kind = K4_ENGINE_STATUS;
        out->status = K4_FAIL;
        return;
    }

    /* The Nothing mode: a zero request searches to None. A
     * negative request is outside every mode's table (the Error
     * mode's search refuses it); either way Beam sees no
     * pointer, which is all Beam can observe. */
    if (request == 0) {
        out->kind = K4_ENGINE_NONE;
        return;
    }
    if (request < 0) {
        out->kind = K4_ENGINE_STATUS;
        out->status = K4_FAIL;
        return;
    }

    /* STUB PLACEMENT: first fit -- the lowest displacement whose
     * contiguous free run reaches the request. */
    want = (uint32_t)request;
    run_start = 0;
    run_length = 0;
    for (s = 0; s < K4_SECTORS_PER_CUBE; s++) {
        if (stub_bit(engine, s)) {
            run_length = 0;
            run_start = s + 1;
        } else {
            run_length++;
            if (run_length == want) {
                break;
            }
        }
    }
    if (run_length < want) {
        out->kind = K4_ENGINE_STATUS;
        out->status = K4_GEAR_EXHAUST;
        return;
    }

    /* Mark the run (the bits are free by construction). */
    for (s = run_start; s < run_start + want; s++) {
        engine->words[s / 32u] |= (1u << (s % 32u));
    }
    engine->count_overall += want;

    out->kind = K4_ENGINE_POINTER;
    out->start = run_start;
    out->count = want;
}

int32_t cube_engine_unmark(CubeEngine *engine, uint32_t start,
                           uint32_t count)
{
    uint32_t s;

    /* Engine.unmark's boundary guard, and the commit path's
     * refusal of an empty block (Commit.c: count == 0). */
    if (count == 0 || start + count > K4_SECTORS_PER_CUBE) {
        return K4_FAIL;
    }

    /* Check-then-set (Commit.c): every bit in the range must be
     * marked, or nothing changes. */
    for (s = start; s < start + count; s++) {
        if (!stub_bit(engine, s)) {
            return K4_FAIL_OVERLAY;
        }
    }
    for (s = start; s < start + count; s++) {
        engine->words[s / 32u] &= ~(1u << (s % 32u));
    }
    engine->count_overall -= count;
    return K4_GEAR_SUCCESS;
}
