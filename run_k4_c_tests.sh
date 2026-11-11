#!/usr/bin/env bash
# run_k4_c_tests.sh -- build the k=4 C transcription and test it
# against the Python-generated oracle.
#
# Python generates the oracle (test_k4_expected.txt); the C
# driver (test_k4.c) runs the identical operation script and its
# output must diff empty against it. Uses the workspace venv
# python (bitstruct) unless $PYTHON says otherwise.
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-$HOME/workspace/.venvs/iscandar-venv/bin/python}"
BUILD_DIR="$(mktemp -d)"
trap 'rm -rf "$BUILD_DIR"' EXIT

cc -std=c99 -Wall -Wextra -o "$BUILD_DIR/test_k4" \
    test_k4.c CPUPointer.c BeamCoordinate.c Beam.c CubeEngine.c

"$PYTHON" gen_k4_expected.py
"$BUILD_DIR/test_k4" > test_k4_actual.txt

if diff test_k4_expected.txt test_k4_actual.txt; then
    echo "k=4 C test: PASS (diff empty, $(wc -l < test_k4_expected.txt) lines)"
else
    echo "k=4 C test: FAIL" >&2
    exit 1
fi
