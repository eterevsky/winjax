# winjax

A native Windows CUDA backend for JAX: the XLA GPU PJRT plugin, built on
Windows with clang-cl against the standard CUDA toolkit, loaded into **stock
JAX** as an out-of-tree plugin. No WSL.

## Status

- The GPU plugin (`pjrt_c_api_gpu_plugin.so`, a DLL despite the name) builds
  and runs natively on Windows (RTX 5090, CUDA 13.x).
- First light verified: JAX picks up the `cuda` platform through the
  `jax_plugins.winjax_cuda` loader and runs computations on the GPU.
- cuDNN is not yet linked into the plugin (convolution autotuning falls back
  gracefully; see the XLA `winjax` branch commits).

## Layout

- `toolchains/` — our hand-authored Bazel override repositories:
  - `winjax_cuda.bazelrc` — the entry point: `--bazelrc=... --config=winjax_cuda`.
    Overrides `local_config_cc`, `local_config_cuda`, `xla`, and every
    `cuda_*` redistrib repo with the local Windows equivalents.
  - `local_config_cc/` — CC toolchain with the winjax compiler wrapper
    (`winjax_cc_wrapper.py` / `winjax_cl.bat`), driving clang-cl for host and
    clang for CUDA device code.
  - `local_config_cuda_win/` — Windows replacement for XLA's Linux-only
    hermetic CUDA configuration.
  - `cuda_repos/<name>/` — one tiny Bazel repo per CUDA component (cudart,
    cublas, nvrtc, ...). Only `BUILD`, `WORKSPACE` and `version.bzl` are
    tracked; the `include`/`lib`/`bin` subdirs are machine-generated NTFS
    junctions into the locally installed toolkit / `tools/` and are ignored.
  - `cccl_patched/`, `cudnn/` — machine-local unpacked content, ignored.
- `patches/` — exported Windows-port patch series for Bazel *external*
  repositories that had to be modified (triton, rmm, raft, rapids_logger,
  abseil, protobuf, local_config_rocm). Each patch applies with
  `patch -p1 -E` / `git apply` from the external repo root, on top of what
  Bazel fetches. See `patches/README.md`.
- `winjax/jax_plugins/winjax_cuda/` — the loader package installed into the
  venv's `site-packages`. It registers the plugin with JAX.
- `xla/` (ignored; its own repo) — XLA clone; branch `winjax-0.11.0` on top of
  `131bf41acb4650e4391a640c3f1859c1c86ad74b` (the jax v0.11.0 XLA pin) is the
  current build branch (branch `winjax` is the same series on the older
  `cf227a88e7ba467855899e7293334fea8995ee25`), carrying the Windows-port
  commits (build files, PJRT plugin loading, stream_executor fixes, ...).
- `jax/` (ignored) — unmodified JAX clone, used only as the Bazel build
  workspace for the plugin target.
- `tools/`, `.venv/` (ignored) — downloaded toolchains (msys64, clang, ...)
  and the Python environment.

## How it works

1. **Build**: from the `jax/` workspace, Bazel builds
   `@xla//xla/pjrt/c:pjrt_c_api_gpu_plugin.so` with
   `--bazelrc=toolchains/winjax_cuda.bazelrc --config=winjax_cuda`.
   - The bazelrc points Bazel at our override repos instead of XLA's
     Linux-only hermetic CUDA rules, and at the local `xla/` checkout.
   - The compiler wrapper in `local_config_cc` presents a clang-cl/clang
     toolchain that can compile both MSVC-flavoured host code and CUDA
     device code, linking real CUDA import libraries instead of Linux ELF
     dlopen stubs.
   - A handful of Bazel external repos need Windows fixes that cannot be
     expressed as overrides; those are applied in place and captured as the
     patch series in `patches/`.
2. **Load**: `jax_plugins/winjax_cuda/__init__.py` (installed into
   site-packages) side-steps jaxlib's not-yet-implemented Windows dlopen
   path: it pre-loads the CUDA/cuDNN DLL directories, loads the plugin DLL
   with `ctypes`, wraps `GetPjrtApi()` in a PyCapsule and registers it via
   `jax._src.xla_bridge.register_plugin("cuda", ...)`.
