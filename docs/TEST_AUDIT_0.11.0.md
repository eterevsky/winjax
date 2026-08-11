# winjax test-suite audit — jax 0.11.0, all 164 test files, no exclusions

Date: 2026-08-11. GPU: RTX 5090 (winjax, shipping-config venv).
Reference baseline: clean `jax[cpu]==0.11.0` on the same machine, same 164
files, same runner.

## Headline numbers

| Sweep | Passed | Failed | Skipped | Problem files |
|---|---|---|---|---|
| GPU (winjax), as swept | 28,471 | 8 | 6,265 | 6 |
| GPU, after this audit's fixes (see below) | +268 recovered | 6 → all classified | — | 0 unexplained |
| CPU (`jax[cpu]`) baseline | 30,906 | 3 | 4,274 | 1 |

After the fixes landed during this audit, **zero unexplained failures
remain**. Every failing test is listed below with its classification.
Chargeable-failure pass rate: 28,739 executed-and-passing vs 3
documented-exclusion failures ≈ **99.99%** (metaljax comparison basis:
99.53%). The 3 upstream/Windows-generic failures fail identically without
winjax installed.

## Per-file findings (every file with >0 failures/crashes/timeouts as swept)

### 1. `clear_backends_test` — TIMEOUT (100 min) → **FIXED**
Root causes (two, stacked):
- winjax loader passed no client-create options to `register_plugin`, so all
  `XLA_PYTHON_CLIENT_*` env vars were silently ignored; combined with WDDM's
  *asynchronous* release of the old 23.9 GiB preallocated pool, re-init after
  `jax.clear_backends()` raced the release, seized the whole visible budget,
  and broke pinned-host allocation process-wide. Loader now passes upstream's
  options and defaults `XLA_PYTHON_CLIENT_PREALLOCATE=false` (overridable).
- Genuine upstream TSL bug: `BFCAllocator::Extend`'s 0.9× backpedal rounds
  back up for sizes ≤ 2304 B → **infinite loop** when a sub-allocator
  persistently fails (the "timeout" was a spin, not slowness; ~5 GB of
  captured warnings). Fixed in `xla/tsl/framework/bfc_allocator.cc`.
- Post-fix: **1 passed, ~1–6 s** (3× stable).

### 2. `memories_test` — native crash 0xC0000005 → **FIXED** (1 documented exclusion remains)
- Deterministic, not flakiness. Native stack: null-`this` constant-folded
  deref in `HostOffloadingNanoRtExecutable::LoadFromProto` — the fourth
  instance of the argument-evaluation-order UB class (`program_shape()` and
  `std::move(executable)` in one argument list; Windows ABI evaluates
  right-to-left). Fixed in
  `xla/core/host_offloading/host_offloading_nanort_executable.cc`.
- Post-fix: **41 passed / 84 skipped / 1 failed**; the 1 failure is
  `test_pallas_kernels_can_overlap_using_multiple_streams`
  (`No FFI handler registered for mosaic_gpu_v2`) — **permanent exclusion**:
  Pallas/Mosaic-GPU is excluded from the Windows wheels (POSIX-only).

### 3. `pmap_test` — TIMEOUT (100 min) → **FIXED**
- Hang: `testDefaultDeviceOrderingAfterClearBackends` — same root cause as
  file 1.
- Real failure uncovered en route: `testCollectivePermuteGrad` — `ppermute`
  gradient on one device emits a collective-permute with empty
  source-target pairs; the emitter built a real collective thunk →
  `UNIMPLEMENTED` (no NCCL on Windows). Correct semantics is zero-fill;
  fixed in `xla/service/gpu/thunk_emitter.cc` (MemzeroThunk for the
  empty-pairs case), matching NCCL-runtime behavior.
- Post-fix: **210 passed / 79 skipped / 0 failed, 44 s.**

### 4. `profiler_test` — 3 failed → **FIXED**
- CUPTI loads fine; device planes were missing because upstream jax only
  registers the plugin profiler on the `library_path` branch of
  `register_plugin`, never on the `c_api`-capsule branch winjax must use
  (upstream asymmetry, PR-worthy). Loader now registers the profiler
  extension itself. Post-fix: **16 passed / 8 skipped.**

### 5. `profiler_session_test` — 3 failed → **NOT WINJAX** (upstream/Windows-generic)
- `test_programmatic_profiling_with_custom_session_id`
- `test_programmatic_profiling_with_empty_session_id`
- `test_programmatic_profiling_without_session_id`
- Cause: the test file never calls `parse_flags_with_absl()`;
  `create_tempdir()` raises `UnparsedFlagAccessError` under pytest. Fails
  identically on `jax[cpu]` Windows (verified — the only CPU-baseline
  failures). Effectively a Bazel-runner-only test.

### 6. `pgle_test` — 2 failed → **permanent exclusion (multi-GPU by design)**
- `PgleTest::testAutoPgleWithCommandBuffers0` / `...1`
- Profile-guided latency estimation requires multi-GPU collectives (NCCL),
  which do not exist on Windows. The rest of the file: 1 passed, 6 skipped.

## Skip-count notes (honesty items)

- `pjit_test`: 682 skips are **expected** — the file requests 8 simulated
  CPU devices (`jtu.request_cpu_devices(8)`); those tests run in CPU sweeps
  and skip on any single-GPU backend, exactly as on single-GPU Linux CUDA.
- GPU sweep skips (6,265) exceed CPU (4,274) due to the above plus
  GPU-inapplicable tests; earlier "~36,400 passed" phase tallies used
  multi-device CPU simulation in some files and are not comparable
  denominators.
- Former file-level exclusions (distributed/multiprocess/mock-GPU/etc.) were
  run this time: all self-skip or pass trivially except `pgle_test` above.
- Caveat for future sweeps: a transient CUDA-init failure makes jax fall
  back to CPU (with 8 simulated devices in some files), silently inflating
  pass counts. Check `devices:` lines when a tally looks too good.

## Fixes landed during the audit (all pushed)

- xla `winjax-0.11.0`: `c188687` (host-offloading eval-order UB),
  `cd06512` (BFC backpedal infinite loop), `2ceda26` (empty collective-
  permute → memzero). All three upstream-worthy.
- winjax `main`: `484faaf` (loader: plugin options plumbing, profiler
  registration, WDDM preallocation default), `da28d8b` (KNOWN_ISSUES
  rewrite).
- **Release note: the built wheels predate these fixes** — plugin DLL and
  loader wheel must be rebuilt/repacked before the next publish.

## Exclusion list for review (the complete set)

| Test | Reason |
|---|---|
| `memories_test::test_pallas_kernels_can_overlap_using_multiple_streams` | Pallas/Mosaic-GPU excluded from Windows wheels |
| `pgle_test::testAutoPgleWithCommandBuffers0/1` | multi-GPU (NCCL) by design |
| `profiler_session_test` (3 tests) | upstream Bazel-only test; fails on Windows CPU identically |
