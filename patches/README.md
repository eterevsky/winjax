# winjax patch series for Bazel external repositories

Each `<repo>/windows-port.patch` contains ONLY the winjax Windows-port changes,
diffed against the repository exactly as Bazel materializes it: the upstream
archive named in the defining workspace stanza **plus** XLA's own fetch-time
`patch_file` series. Apply from the external repo root with either:

    git apply -p1 windows-port.patch
    patch -p1 -E < windows-port.patch   # -E so emptied files (VERSION) are deleted

Pristine bases (all stanzas identical in xla @ cf227a88e7ba467855899e7293334fea8995ee25
and in xla @ 131bf41acb4650e4391a640c3f1859c1c86ad74b, the jax v0.11.0 pin):

| repo                | base archive                                              | defined in |
|---------------------|-----------------------------------------------------------|------------|
| triton              | triton-lang/triton @ 72259b1cc3c543c361dcd185a6ff89662e8ed52f | `xla/third_party/triton/workspace.bzl` (+ common/ and oss_only/ patch series) |
| rmm                 | rapidsai/rmm v26.02.00                                    | `xla/third_party/rmm/workspace.bzl` (`xla_repo`) |
| raft                | rapidsai/raft v26.02.00                                   | `xla/third_party/raft/workspace.bzl` (`xla_repo`) |
| rapids_logger       | rapidsai/rapids-logger v0.2.3                             | `xla/third_party/rapids_logger/workspace.bzl` (`xla_repo`) |
| com_google_absl     | abseil-cpp 20260526.0                                     | `xla/third_party/absl/workspace.bzl` |
| com_google_protobuf | protobuf v6.31.1 (NOT the 34.1 in `workspace2.bzl`; that `maybe()` is a no-op) | `xla/third_party/py/python_init_rules.bzl` |
| local_config_rocm   | machine-generated repo — full-file override, see its README | `rocm_configure` |
| eigen_archive       | eigen mirror archive pinned by `xla/third_party/eigen3/workspace.bzl` | `xla/third_party/eigen3/workspace.bzl` |

Summary of changes:

- **triton** — `BUILD`: add `-fno-delayed-template-parsing` for clang-cl;
  `PartitionLoops.cpp`: disambiguate `getPartition(0u)` under the MSVC ABI;
  `GCNAsmFormat.h`: class/struct forward-declaration mismatch (MSVC ABI).
- **rmm** — guard `<dlfcn.h>` include for `_WIN32`; delete `VERSION`
  (case-insensitive filesystem collides with C++20 `#include <version>`).
- **raft** — guard `<execinfo.h>`; drop 8-byte `long` atomic specializations
  and duplicate `unsigned long long` `IOType` specializations (LLP64: `long`
  is 4 bytes, `uint64_t` IS `unsigned long long`); delete `VERSION` (same
  collision).
- **rapids_logger** — delete `VERSION` (same collision).
- **com_google_absl** / **com_google_protobuf** — don't emit
  `__declspec(thread)` in the `__CUDA_ARCH__` (device) compilation pass.
- **local_config_rocm** — `if_gpu_is_configured` / `if_cuda_or_rocm` keyed on
  `@local_config_cuda//:is_cuda_enabled` (override file, not a patch).
- **eigen_archive** — `Fill.h`: `eigen_zero_impl<..., use_memset=true>` calls
  host-only `memset` in the clang-CUDA device pass; route to the
  assignment-loop impl under `EIGEN_GPU_COMPILE_PHASE` (mirrors the existing
  `eigen_fill_impl` guard; upstream-worthy).
