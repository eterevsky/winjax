# Upstream PR queue — XLA bug fixes found porting XLA to native Windows

Prepared 2026-08-11. Five single-commit branches live on the fork
(`git@github.com:eterevsky/xla.git`), each based on `openxla/xla` `main`
@ `4a88636` (fetched 2026-08-11). **No PRs have been opened** — review each
branch and body file, then run the `gh` command from `C:\Users\oleg\winjax\xla`.

Verification level: each patched file was ported by hand onto upstream HEAD and
carefully re-reviewed against the surrounding code (types, member names, macro
style all re-checked at HEAD); no build of upstream HEAD was attempted. All five
fixes are verified in production in the winjax build of XLA at the jax-v0.11.0
pin (branch `winjax-0.11.0`, full jax test-suite audit green).

Ready-to-paste PR bodies: `docs/upstream_pr_bodies/*.md` (paths in the `gh`
commands below are relative to the xla checkout).

---

## 1. PJRT: argument-evaluation-order UB in `LinearizeIntoImpl`

- **Branch:** `upstream-linearize-eval-order` (commit `0dcb896`)
- **File:** `xla/pjrt/common_pjrt_client.cc` — **unchanged** upstream (bug still
  present verbatim at HEAD; only surrounding macros renamed to `ABSL_*`)
- **PR title:** `Fix argument-evaluation-order UB in CommonPjRtClient::LinearizeIntoImpl`
- **PR body:** `docs/upstream_pr_bodies/linearize-eval-order.md` — the
  `ExecuteWhenReady` dependency list is built with `linearized.CopyRCRef()` in
  the same argument list as a lambda capturing `linearized` by move; on
  right-to-left evaluation (MSVC ABI) the move runs first, the dependency is
  null, and the first host-to-device transfer crashes in `RunWhenReady`. Fix:
  hoist the `CopyRCRef()` into a local before the call.

```diff
+      tsl::RCReference<tsl::AsyncValue> linearized_dep = linearized.CopyRCRef();
       async_work_runner()->ExecuteWhenReady(
-          {linearized.CopyRCRef()},
+          {std::move(linearized_dep)},
           [this, linearized = std::move(linearized), copy_event_promise,
```

```sh
gh pr create --repo openxla/xla --head eterevsky:upstream-linearize-eval-order \
  --title "Fix argument-evaluation-order UB in CommonPjRtClient::LinearizeIntoImpl" \
  --body-file ../docs/upstream_pr_bodies/linearize-eval-order.md
```

---

## 2. Host offloading: same UB class in NanoRt `LoadFromProto`

- **Branch:** `upstream-host-offloading-eval-order` (commit `ef66f59`)
- **File:** `xla/core/host_offloading/host_offloading_nanort_executable.cc` —
  **unchanged** upstream (bug present verbatim at HEAD)
- **PR title:** `Fix argument-evaluation-order UB in HostOffloadingNanoRtExecutable::LoadFromProto`
- **PR body:** `docs/upstream_pr_bodies/host-offloading-eval-order.md` — the
  final constructor call evaluates `executable->program_shape()` and
  `std::move(executable)` (a by-value `unique_ptr` parameter) in one argument
  list; right-to-left evaluation moves first and calls through null, crashing
  every `compute_on('device_host')` compilation. Fix: hoist the program-shape
  selection before the call.

```diff
+  ProgramShape executable_program_shape =
+      executable->program_shape() ? *executable->program_shape()
+                                  : std::move(program_shape);
+
   return absl::WrapUnique(new HostOffloadingNanoRtExecutable(
-      hlo_module_proto.name(),
-      executable->program_shape() ? *executable->program_shape()
-                                  : program_shape,
+      hlo_module_proto.name(), std::move(executable_program_shape),
       std::move(alias_config), std::move(executable), needs_layout_conversion,
```

```sh
gh pr create --repo openxla/xla --head eterevsky:upstream-host-offloading-eval-order \
  --title "Fix argument-evaluation-order UB in HostOffloadingNanoRtExecutable::LoadFromProto" \
  --body-file ../docs/upstream_pr_bodies/host-offloading-eval-order.md
```

---

## 3. FFI: bool attribute selects `const char*` overload → `strlen(NULL)`

- **Branch:** `upstream-ffi-bool-attr` (commit `a5a8366`; squashes the two
  winjax-0.11.0 commits e22571f + e2fc5e8 into the final form)
- **File:** `xla/ffi/call_frame.h` — **unchanged** upstream (no bool overload at
  HEAD; `EstimateCubSortScratchSize` still calls `attrs.Insert("descending", false)`
  at `xla/backends/gpu/transforms/estimate_cub_sort_scratch_size.cc:90`)
- **PR title:** `FFI: handle bool attributes correctly in AttributesBuilder::Insert`
- **PR body:** `docs/upstream_pr_bodies/ffi-bool-attr.md` — on MSVC-compatible
  compilers the literals `true`/`false` convert to a null pointer (legacy
  extension), so `Insert(name, false)` picked the `const char*` overload and
  crashed in `strlen`; killed every CUB-rewritten sort/top_k. Fix: add a bool
  overload constrained with `enable_if` to *exactly* `bool` — an unconstrained
  one would swallow other integral types (integral-to-bool conversion outranks
  the user-defined conversion to `Attribute`) and silently turn int64 attributes
  like `batch_size` into PRED scalars.

```diff
+    template <typename T,
+              typename = std::enable_if_t<std::is_same_v<T, bool>>>
+    void Insert(std::string name, T attr) {
+      Insert(std::move(name), Attribute{Scalar{attr}});
+    }
```
(plus `#include <type_traits>` and the explanatory comment)

```sh
gh pr create --repo openxla/xla --head eterevsky:upstream-ffi-bool-attr \
  --title "FFI: handle bool attributes correctly in AttributesBuilder::Insert" \
  --body-file ../docs/upstream_pr_bodies/ffi-bool-attr.md
```

---

## 4. TSL: BFC allocator infinite backpedal loop (platform-independent)

- **Branch:** `upstream-bfc-backpedal` (commit `e8b5928`)
- **File:** `xla/tsl/framework/bfc_allocator.cc` — **unchanged** upstream (loop
  identical at HEAD)
- **PR title:** `Fix infinite backpedal loop in BFCAllocator::Extend for small allocations`
- **PR body:** `docs/upstream_pr_bodies/bfc-backpedal.md` — the 0.9x backpedal
  re-rounds with `RoundedBytes`, which rounds *up* to a multiple of
  `kMinAllocationSize` (256 B); for sizes ≤ 2304 B it rounds back to the same
  value, so a persistently failing sub-allocator spins the loop forever with an
  unbounded warning stream (5 GB of log in minutes; 100-minute test timeouts
  instead of clean OOM). Platform-independent bug; reached on Windows/WDDM via
  persistently failing pinned-host `cuMemHostAlloc`. Fix: force strict progress
  (step down by one `kMinAllocationSize` when re-rounding did not shrink).

```diff
     while (mem_addr == nullptr) {
-      bytes = RoundedBytes(bytes * kBackpedalFactor);
+      size_t backpedal_bytes = RoundedBytes(bytes * kBackpedalFactor);
+      if (backpedal_bytes >= bytes) {
+        backpedal_bytes = bytes - kMinAllocationSize;
+      }
+      bytes = backpedal_bytes;
       if (bytes < rounded_bytes) {
         return false;
       }
```

```sh
gh pr create --repo openxla/xla --head eterevsky:upstream-bfc-backpedal \
  --title "Fix infinite backpedal loop in BFCAllocator::Extend for small allocations" \
  --body-file ../docs/upstream_pr_bodies/bfc-backpedal.md
```

---

## 5. GPU: empty collective-permute should memzero, not build a collective thunk

- **Branch:** `upstream-collective-permute-memzero` (commit `d4711fe`)
- **Files:** `xla/service/gpu/thunk_emitter.cc` + `xla/service/gpu/BUILD` —
  **adapted**: upstream refactored `EmitCollectivePermute` into the templated
  `ThunkEmitter::EmitCollective<CollectiveThunkType, HloInstType>` returning
  `Future<ThunkSequence>`. The fix now sits in `EmitCollective` behind
  `if constexpr (is_collective_permute)`, right after `GetCollectiveBuffers`,
  emitting one `MemzeroThunk` per output buffer (mirrors the style of the
  adjacent `EmitDegeneratedCollective` copy path). `MemzeroThunk`'s constructor
  signature (`ThunkInfo`, `ShapedSlice`) is unchanged at HEAD;
  `CollectivePermuteThunk::IsDegenerate` still returns false for the empty list,
  so the bug is live at HEAD.
- **PR title:** `GPU: emit memzero for collective-permute with no source-target pairs`
- **PR body:** `docs/upstream_pr_bodies/collective-permute-memzero.md` — an
  empty source-target-pairs permute (jax emits one for the gradient of
  `ppermute` on a single device) delivers no data; runtimes implement "no source
  for this rank" by zeroing the output, yet the emitter builds a full collective
  thunk that acquires a communicator — `UNIMPLEMENTED` on collectives-less
  builds (no NCCL on Windows). Fix: emit `MemzeroThunk` directly; cheaper
  everywhere, correct without collectives.

```diff
+  if constexpr (is_collective_permute) {
+    if (inst->source_target_pairs().empty()) {
+      ThunkSequence thunks;
+      for (int64_t i = 0; i < buffers.size(); ++i) {
+        thunks.Emplace<MemzeroThunk>(
+            Thunk::ThunkInfo::WithProfileAnnotation(
+                inst, ir_emitter_context_->GetNextThunkId()),
+            ShapedSlice{buffers[i].destination_buffer.slice,
+                        inst->operand(i)->shape()});
+      }
+      return thunks;
+    }
+  }
```
(plus the `memset_thunk.h` include and the `//xla/backends/gpu/runtime:memset_thunk`
dep on the `thunk_emitter` target)

```sh
gh pr create --repo openxla/xla --head eterevsky:upstream-collective-permute-memzero \
  --title "GPU: emit memzero for collective-permute with no source-target pairs" \
  --body-file ../docs/upstream_pr_bodies/collective-permute-memzero.md
```

---

# Future work — non-XLA upstream items (no branches yet)

## jax (repo: jax-ml/jax)

1. **Profiler registration missing on `register_plugin`'s `c_api` branch.**
   `jax/_src/xla_bridge.py`, `register_plugin()` (line 583 at jax-v0.11.0): the
   `library_path` branch calls `_profiler.register_plugin_profiler(c_api)`
   (line ~638), but the `c_api`-capsule branch only calls
   `xla_client.load_pjrt_plugin_with_c_api` — out-of-tree plugins that register
   via a PyCapsule (the only path that works on Windows, since `LoadPjrtPlugin`
   dlopen is POSIX) silently get no profiler. Fix: call
   `register_plugin_profiler` on both branches. winjax works around it in its
   loader (winjax commit `484faaf`).

2. **`hardware_utils` GPU detection is Linux-only.**
   `jax/_src/hardware_utils.py`: `has_visible_nvidia_gpu()` (line 77) checks
   `/dev/nvidia0`, `/dev/nvidiactl`, `/dev/dxg` and `/sys/bus/pci` — always
   False on Windows, which gates CUDA plugin setup in `xla_bridge.py`. Fix:
   add a Windows detection path (e.g. `nvcuda.dll` presence / NVML query).
   winjax works around it by monkeypatching the function in its loader.

## Bazel (repo: bazelbuild/bazel)

3. **`windows_cc_configure.bzl` clang-version last-token parse.**
   `tools/cpp/windows_cc_configure.bzl` (`_get_clang_version`, Bazel 7.7.0)
   takes the *last whitespace token* of the `clang -v` version line as the
   version. LLVM release binaries append
   `(https://github.com/llvm/llvm-project <sha>)`, so the parsed "version" is
   the sha fragment, producing a bogus `lib\clang\<ver>\include` builtin include
   path and "absolute path inclusion" errors for every compile. Fix: parse the
   token following "version" (or regex for `\d+\.\d+\.\d+`). winjax works
   around it with a snapshotted `local_config_cc` repo
   (`winjax/toolchains/local_config_cc`, sha token replaced by `22`) wired via
   `--override_repository`.
