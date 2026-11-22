#!/usr/bin/env bash
# CPU-only, no-GPU, no-network proof of the DSML token-provenance port.
# Run this ON the GB300 host (docker allowed there, not in the desk session).
# It starts no server and touches no serving port: one pytest container that
# exits.
#
#   bash RUN-TESTS.sh            # full suite
#   RUN_SWITCH_MATRIX=1 bash RUN-TESTS.sh   # + the three kill switches
#
set -uo pipefail

PORT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE="${IMAGE:-vllm/vllm-openai:v0.31.0}"

# Resolve the site-packages vllm path inside the image instead of assuming it.
VLLM_DIR="$(docker run --rm --entrypoint python3 "$IMAGE" \
  -c 'import os, vllm; print(os.path.dirname(vllm.__file__))')"
echo "image:    $IMAGE"
echo "vllm dir: $VLLM_DIR"

MOUNTS=(
  -v ${OVERLAY_1017:?set to your dgx-station-recipes docker/overlay-1017/vllm}/tokenizers/deepseek_v41.py:/usr/local/lib/python3.12/dist-packages/vllm/tokenizers/deepseek_v41.py:ro
  -v ${OVERLAY_1017:?set to your dgx-station-recipes docker/overlay-1017/vllm}/tokenizers/deepseek_v41_encoding.py:/usr/local/lib/python3.12/dist-packages/vllm/tokenizers/deepseek_v41_encoding.py:ro
  -v ${OVERLAY_1017:?set to your dgx-station-recipes docker/overlay-1017/vllm}/renderers/deepseek_v4.py:/usr/local/lib/python3.12/dist-packages/vllm/renderers/deepseek_v4.py:ro
  -v "$PORT:/port:ro"
  -v "$PORT/overlay/vllm/parser/deepseek_v41.py:$VLLM_DIR/parser/deepseek_v41.py:ro"
  -v "$PORT/overlay/vllm/parser/parser_manager.py:$VLLM_DIR/parser/parser_manager.py:ro"
  -v "$PORT/overlay/vllm/parser/engine/token_id_scanner.py:$VLLM_DIR/parser/engine/token_id_scanner.py:ro"
  -v "$PORT/overlay/vllm/parser/engine/incremental_lexer.py:$VLLM_DIR/parser/engine/incremental_lexer.py:ro"
  -v "$PORT/overlay/vllm/parser/engine/streaming_parser_engine.py:$VLLM_DIR/parser/engine/streaming_parser_engine.py:ro"
  -v "$PORT/overlay/vllm/parser/engine/parser_engine.py:$VLLM_DIR/parser/engine/parser_engine.py:ro"
  -v "$PORT/overlay/vllm/parser/engine/parser_engine_config.py:$VLLM_DIR/parser/engine/parser_engine_config.py:ro"
)

run_pytest() {
  local label="$1"; shift
  echo "── $label"
  docker run --rm --network none \
    -e PYTHONDONTWRITEBYTECODE=1 \
    -e VLLM_LOGGING_LEVEL=INFO \
    "$@" \
    --entrypoint python3 \
    "${MOUNTS[@]}" \
    "$IMAGE" \
    -m pytest /port/tests -q -p no:cacheprovider
}

# 1. The delivered configuration.
run_pytest "default (structural closers + token provenance)"

# 2. The three env flips, each a full rollback knob.
if [[ "${RUN_SWITCH_MATRIX:-0}" == "1" ]]; then
  run_pytest "VLLM_DSV41_STRUCTURAL_DSML=0 (provenance only)" \
    -e VLLM_DSV41_STRUCTURAL_DSML=0
  run_pytest "VLLM_DSV41_KEEP_OPEN_ARGS=0 (drop unterminated trailing arg)" \
    -e VLLM_DSV41_KEEP_OPEN_ARGS=0
  # Provenance off is expected to FAIL the new cases on purpose: it is the old
  # behaviour, kept only as a rollback. Run it to see the old bug return.
  echo "── VLLM_DSV41_DSML_TOKEN_PROVENANCE=0 (rollback; failures expected)"
  docker run --rm --network none \
    -e PYTHONDONTWRITEBYTECODE=1 \
    -e VLLM_DSV41_DSML_TOKEN_PROVENANCE=0 \
    --entrypoint python3 \
    "${MOUNTS[@]}" \
    "$IMAGE" \
    -m pytest /port/tests -q -p no:cacheprovider -k "not h_provenance_off" || true
fi

echo "done."