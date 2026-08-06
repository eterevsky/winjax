# Known issues — winjax on jax/jaxlib 0.11.0

Status after the full single-GPU test sweep of jax v0.11.0's `tests/*_test.py`
(155 files; multi-process/multi-GPU/distributed/mock-GPU and mosaic files
excluded): **0 failing tests**. ~36.4k passed, ~9.3k skipped (RTX 5090,
Windows 11, CUDA 13.3, official PyPI jax==0.11.0 + jaxlib==0.11.0 + our
jax-cuda13-plugin 0.11.0).

No test currently needs a permanent exclusion. The entries below are
observations worth knowing about, not open failures.

## Observations / watch items

- **`scipy_stats_test.py::testMode` (tie-breaking flake under expanded case
  generation).** One run with a larger generated-case count showed a single
  `testMode` failure: `scipy.stats.mode` vs `jax.scipy.stats.mode` disagree by
  one candidate value when the input has a frequency tie (both answers are
  "a mode"; tie-breaking order is implementation-defined and differs between
  the CPU reference and the GPU sort path). All 40 `testMode` cases pass on
  both CPU and GPU when run directly. Not Windows-specific.

- **`clear_backends_test.py` is very slow on the plugin backend (~2 min).**
  `jax.clear_backends()` tears down the PJRT client; re-initialization
  re-creates the CUDA client and re-JITs, which takes ~2 minutes wall time.
  The test passes. Under heavy GPU/CPU contention it can look like a hang.

- **`fused_attention_stablehlo_test.py` all-skips (31 skipped).** Same
  behavior as upstream CUDA-13 builds: cuDNN attention support checks skip
  these on this cuDNN/toolkit combination. Not a winjax defect.

- **`cudnn_fusion_test.py` all-skips (2 skipped).** Requires cuDNN fusion
  autotuning conditions not met on this configuration; skips upstream too.

- **`lax_metal_test.py`, `local_wheel_smoke_test.py`, `sparse_nm_test.py`
  collect zero tests** (pytest exit 5) in this environment: metal-only file,
  Bazel-only wheel-resolution smoke test, and an N:M sparsity file requiring
  unavailable hardware paths, respectively.

## Fixed during the 0.11.0 bring-up (for reference)

- **CUB sort/top_k crash (`ann_test`, large `jnp.sort`)** — MSVC-compat
  overload-resolution trap in `xla::ffi::CallFrameBuilder::AttributesBuilder::
  Insert`: on clang-cl the literal `false` converts to a null `const char*`
  (legacy MSVC extension), selecting the string overload and crashing in
  `strlen(NULL)` during `EstimateCubSortScratchSize`. Fixed on the
  `winjax-0.11.0` XLA branch by adding an exactly-`bool`-constrained overload
  (upstream-worthy; the naive `bool` overload is wrong too, because integral
  attributes would convert to `bool` by a standard conversion).
- **`error_check_test`, `export serialization`** — required the optional
  `flatbuffers` package in the venv.
- **`hypothesis_test_util_test`** — requires the optional `hypothesis`
  package in the venv.
