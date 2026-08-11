# Known issues — winjax on jax/jaxlib 0.11.0

Status after the full single-GPU test sweep of jax v0.11.0's `tests/*_test.py`
(155 files; multi-process/multi-GPU/distributed/mock-GPU and mosaic files
excluded): **0 failing tests**. ~36.4k passed, ~9.3k skipped (RTX 5090,
Windows 11, CUDA 13.3, official PyPI jax==0.11.0 + jaxlib==0.11.0 + our
jax-cuda13-plugin 0.11.0).

The 2026-08-11 full audit (SWEEP_ALL, 164 files) surfaced four problem
areas — a clear_backends/pmap hang, a memories_test native crash, and
profiler failures — all root-caused and fixed (see "Fixed during the 0.11.0
bring-up" below), except one Pallas-dependent test that needs the permanent
exclusion listed next.

## Permanent exclusions

- **`memories_test.py::StreamAnnotationTest::
  test_pallas_kernels_can_overlap_using_multiple_streams`** — fails with
  `NOT_FOUND: No FFI handler registered for mosaic_gpu_v2`. Pallas /
  Mosaic-GPU is excluded from the Windows kernels wheel (POSIX-only code in
  Mosaic GPU / NVSHMEM); the test assumes Mosaic is present on every CUDA
  build and errors instead of skipping. Passes on Linux jax[cuda]; infeasible
  on winjax until Mosaic GPU is ported. (Same category as the excluded
  `tests/pallas/` and `mosaic_test.py` files.)

## Observations / watch items

- **`scipy_stats_test.py::testMode` (tie-breaking flake under expanded case
  generation).** One run with a larger generated-case count showed a single
  `testMode` failure: `scipy.stats.mode` vs `jax.scipy.stats.mode` disagree by
  one candidate value when the input has a frequency tie (both answers are
  "a mode"; tie-breaking order is implementation-defined and differs between
  the CPU reference and the GPU sort path). All 40 `testMode` cases pass on
  both CPU and GPU when run directly. Not Windows-specific.

- **`profiler_session_test.py` fails under pytest (3 failures) — upstream
  test-file defect, not a winjax issue.** The file never calls
  `jax.config.parse_flags_with_absl()`, so `absltest`'s `create_tempdir()`
  raises `UnparsedFlagAccessError: --test_tmpdir` when the file is run under
  pytest. It fails identically on stock `jax[cpu]` on Windows (verified) and
  would on any platform; it only works under Bazel's absltest runner.
  Excluded per the "fails on jax[cpu] too" rule.

- **`pjit_test.py` reports ~682 skips on the GPU backend — expected on any
  single-GPU machine.** The skipped cases require 2/4/8 devices
  ("Test requires N global/local devices, found 1"). The file requests 8
  *CPU* devices via `jtu.request_cpu_devices(8)`, so the same tests run in
  CPU-only sweeps; with a GPU present the default backend has one device and
  they skip, exactly as on a single-GPU Linux jax[cuda] setup.

- **WDDM memory policy: the loader defaults `XLA_PYTHON_CLIENT_PREALLOCATE`
  to `false`.** On Windows display GPUs (WDDM) a preallocated 75%-of-VRAM
  BFC pool is charged against the process host-commit limit, and
  re-initialization after `jax.clear_backends()` races the driver's
  asynchronous release of the old pool: the new pool seizes the entire GPU
  budget and pinned-host (`cuMemHostAlloc`) allocations then fail
  process-wide. On-demand growth avoids both. Set the variable explicitly
  to override the default.

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

- **`clear_backends_test` 100-minute hang / `pmap_test` timeout at
  `testDefaultDeviceOrderingAfterClearBackends`** — two stacked causes.
  (1) After `jax.clear_backends()`, WDDM releases the old client's
  preallocated 23.9 GiB pool *asynchronously*; the immediate re-init
  preallocation races it, seizes the whole GPU budget, and every pinned-host
  `cuMemHostAlloc` then fails. Fixed by the loader's
  `XLA_PYTHON_CLIENT_PREALLOCATE=false` WDDM default (see above).
  (2) A genuine upstream TSL bug turned that failure into an infinite loop:
  `BFCAllocator::Extend`'s 0.9x backpedal rounds *up* to the 256-byte
  allocation unit, so for requests ≤ 2304 bytes the size never decreases and
  the loop spins forever, spewing "could not allocate pinned host" warnings
  (observed: 5 GB of log in minutes; pytest's fd capture absorbed it, which
  is why audit logs were empty). Fixed on the `winjax-0.11.0` XLA branch by
  forcing strict progress in the backpedal (upstream-worthy).
  `clear_backends_test` now passes in ~1-6 s.

- **Loader ignored `XLA_PYTHON_CLIENT_*` entirely** — our
  `register_plugin(c_api=...)` call passed no client-create options, so
  allocator kind / memory fraction / preallocate env vars never reached the
  plugin. The loader now passes
  `xla_client.generate_pjrt_gpu_plugin_options`, like upstream's cuda
  plugin.

- **`memories_test` native crash (0xC0000005) in `ComputeOffload`
  (compute_on `device_host`)** — genuine upstream XLA bug, third instance of
  the MSVC-ABI argument-evaluation-order class:
  `HostOffloadingNanoRtExecutable::LoadFromProto` evaluated
  `executable->program_shape()` and `std::move(executable)` in the same
  constructor argument list. The MSVC ABI evaluates arguments right-to-left,
  so the by-value `unique_ptr` parameter was move-constructed first and the
  later argument dereferenced a null pointer (clang constant-folds it into
  an absolute load at address 0x1d0). Fixed on the `winjax-0.11.0` XLA
  branch by hoisting the program-shape selection before the call
  (upstream-worthy).

- **`pmap_test::testCollectivePermuteGrad` UNIMPLEMENTED ("XLA compiled
  without GPU collectives support")** — jax's `ppermute` gradient on one
  device emits a collective-permute with an *empty* source-target-pairs
  list; the GPU thunk emitter emitted a real collective thunk for it, which
  requires a communicator and fails on the NCCL-less Windows build. The
  correct semantics (what the NCCL runtime does for a rank with no source)
  is zeroing the output; fixed on the `winjax-0.11.0` XLA branch by emitting
  a memzero thunk for the empty-pairs case (upstream-worthy).

- **`jax.profiler` traces had no `/device:GPU` planes (profiler_test 3
  failures)** — jax's `register_plugin()` only calls
  `_profiler.register_plugin_profiler(c_api)` on its `library_path` branch;
  the `c_api` capsule branch that winjax must use (Windows has no dlopen
  path) never registers the plugin profiler, so CUPTI device tracing was
  simply never wired despite working CUPTI. The loader now registers it
  explicitly; all CUPTI profiler tests pass (upstream-worthy jax fix).

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
