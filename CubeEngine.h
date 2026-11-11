/* CubeEngine.h -- the per-cube engine boundary for Beam.c.
 *
 * ======================= STUB BOUNDARY =======================
 * Beam.py drives the k=3 Engine (allocator.py) directly. The
 * full k=3 C engine is not yet present in this repository, so
 * this header declares the minimal interface Beam needs, and
 * CubeEngine.c supplies a STUB implementation behind it:
 *
 *   - a 1024-word bitmap store (sector s is bit s, the Cube
 *     store's own convention), standing in for the k=3 Cube;
 *   - allocation by a first-fit contiguous-run search over that
 *     bitmap, standing in for the modes' probe searches;
 *   - mark/unmark with the k=3 commit path's check-then-set
 *     semantics (Commit.c): a flip that would land on wrongly
 *     set bits is K4_FAIL_OVERLAY and changes nothing.
 *
 * The stub keeps the Engine's boundary contract exactly, since
 * that is what Beam observes:
 *   - a request larger than the sectors remaining returns
 *     K4_FAIL before any search (Engine.__call__ step 1);
 *   - a zero request yields no result (the Nothing mode);
 *   - allocate yields a (start, count) pointer result, a bare
 *     status, or nothing -- the three shapes Engine.__call__
 *     can return (MPUPointer, status int, None);
 *   - unmark refuses a block running past the cube end with
 *     K4_FAIL at the boundary, and otherwise returns the commit
 *     status (K4_GEAR_SUCCESS / K4_FAIL_OVERLAY).
 *
 * Placement inside the cube is the stub's own (first fit), NOT
 * the modes' probe placement. When the k=3 C engine lands, it
 * replaces CubeEngine.c behind this header; Beam.c does not
 * change. The test oracle (gen_k4_expected.py) substitutes the
 * identical stub policy on the Python side, so the Beam test
 * compares Beam logic against Beam logic, engine for engine.
 * ============================================================= */

#ifndef ISCANDAR_K4_CUBE_ENGINE_H
#define ISCANDAR_K4_CUBE_ENGINE_H

#include <stdint.h>

#define K4_SECTORS_PER_CUBE 32768u

/* The three shapes an engine call can return. */
#define K4_ENGINE_NONE    0  /* Python: None (Nothing mode) */
#define K4_ENGINE_STATUS  1  /* Python: a bare status int */
#define K4_ENGINE_POINTER 2  /* Python: an MPUPointer */

typedef struct {
    int kind;          /* K4_ENGINE_* */
    int32_t status;    /* valid when kind == K4_ENGINE_STATUS */
    uint32_t start;    /* valid when kind == K4_ENGINE_POINTER */
    uint32_t count;    /* valid when kind == K4_ENGINE_POINTER */
} CubeEngineResult;

typedef struct {
    uint32_t words[1024];    /* stub store: sector s is bit s */
    uint32_t count_overall;  /* Engine.count_overall */
} CubeEngine;

void cube_engine_init(CubeEngine *engine);

/* Engine.__call__(request), boundary contract as above. */
void cube_engine_call(CubeEngine *engine, int32_t request,
                      CubeEngineResult *out);

/* Engine.unmark(pointer) reduced to (start, count): returns
 * K4_GEAR_SUCCESS, K4_FAIL, or K4_FAIL_OVERLAY. */
int32_t cube_engine_unmark(CubeEngine *engine, uint32_t start,
                           uint32_t count);

#endif /* ISCANDAR_K4_CUBE_ENGINE_H */
