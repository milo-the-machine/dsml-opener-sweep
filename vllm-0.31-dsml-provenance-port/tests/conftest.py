"""Local-run shim hook (no-op inside the lane image).

The Mac-side harness (build/local) runs these tests against the real parser
tree with small stubs for serving-layer leaves; set VLLM_SHIM_PATH to enable.
"""

import os
import sys

_tests_dir = os.path.dirname(os.path.abspath(__file__))
if _tests_dir not in sys.path:
    sys.path.insert(0, _tests_dir)

_shim = os.environ.get("VLLM_SHIM_PATH")
if _shim and _shim not in sys.path:
    sys.path.insert(0, _shim)