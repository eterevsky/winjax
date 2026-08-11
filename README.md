# winjax

Native Windows CUDA backend for [JAX](https://github.com/jax-ml/jax) — no WSL.

winjax builds XLA's GPU PJRT plugin as a native Windows DLL and loads it into
**stock JAX** as an out-of-tree plugin. `jit`, `grad`, convolutions (cuDNN),
matmuls (cuBLAS), linear algebra (cuSOLVER), and XLA's runtime kernel JIT all
run natively on your GPU.

## Installation

```
pip install winjax
```

That's it. The package depends on `jax`/`jaxlib` (official wheels) and pulls
the entire CUDA userland — cuDNN, cuBLAS, cuFFT, CUPTI, NVRTC, `ptxas`,
`libdevice` — from NVIDIA's own pip wheels. No CUDA toolkit installation, no
cuDNN download, no environment variables.

> Until the first production PyPI release lands, install the verified preview
> from TestPyPI:
> `pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ winjax`

### Requirements

- **Windows 10/11 x64**
- **An NVIDIA GPU and a current NVIDIA driver** — the only system
  dependency (the driver provides `nvcuda.dll`; everything else comes from
  pip). CUDA 13-era drivers recommended.
- **Python 3.13 or 3.14** (64-bit)

On machines without an NVIDIA GPU or driver, `import jax` silently falls back
to the normal CPU backend — winjax stays out of the way.

### Verify

```python
import jax
import jax.numpy as jnp

print(jax.devices())            # [CudaDevice(id=0)]
x = jnp.ones((4096, 4096))
print((x @ x)[0, 0])            # runs on the GPU
```

## Status

- Each winjax release is pinned to a specific `jax`/`jaxlib` release
  (currently **0.11.0**) — `pip install winjax` brings the matching pair.
- **JAX's own test suite passes** against this backend: ~36,400 tests,
  0 failures across 155 test files on an RTX 5090 (see `KNOWN_ISSUES.md`
  for watch items).
- **PyTorch in the same process is not supported** (a Windows process can
  hold only one cuDNN family, and torch bundles its own of a different
  version). winjax detects the situation and degrades predictably with a
  clear warning: import torch first and torch works fully while jax's
  cuDNN ops (conv/attention) are unavailable; import jax first and jax
  works fully while `import torch` will fail. Use separate processes when
  you need both.

### Limitations

- **Single GPU.** NCCL does not exist on Windows; multi-GPU collectives and
  distributed execution are out of scope.
- **No Pallas / Mosaic GPU** (POSIX-only for now; excluded from the wheels).
- Python 3.13/3.14 only, matching the official Windows `jaxlib` wheels.
- The GPU runs in WDDM mode (display driver); very long individual kernels
  can hit Windows' GPU watchdog on display GPUs.

## How it works

Three wheels:

| Package | Contents |
|---|---|
| `winjax` | Pure-Python loader (`jax_plugins/winjax_cuda`); depends on everything else |
| `winjax-cuda13-pjrt` | The XLA GPU compiler + runtime as one PJRT plugin DLL |
| `winjax-cuda13-plugin` | The CUDA kernel extension modules (cuSOLVER/RNG/sparse FFI), import name `jax_cuda13_plugin` |

At `import jax`, plugin discovery calls the loader's `initialize()`: it probes
for an NVIDIA driver, registers the CUDA DLL directories from the `nvidia-*`
wheels, preloads cuDNN by absolute path (no global `PATH` mutation), loads the
plugin DLL via `ctypes`, and hands JAX the `PJRT_Api*` as a PyCapsule via
`jax._src.xla_bridge.register_plugin("cuda", ...)` — bypassing jaxlib's
not-yet-implemented Windows dlopen path. No fork of JAX, no patched jaxlib.

**Build side**: the plugin is built with Bazel from the pinned jax release's
XLA revision plus a Windows-port patch series
([eterevsky/xla](https://github.com/eterevsky/xla), branch `winjax-0.11.0`).
A compiler-dispatch wrapper presents one toolchain that compiles MSVC-flavored
host code with clang-cl and CUDA device code with clang's CUDA driver
(sm_120 / Blackwell targeted); hand-authored Bazel override repositories
replace XLA's Linux-only hermetic CUDA rules with the local CUDA toolkit and
generated cuDNN import libraries.

## Repository layout

- `packaging/` — the three wheel sources (`packaging/winjax/` is the loader
  package, including the canonical `jax_plugins/winjax_cuda/__init__.py`;
  `packaging/winjax_cuda13_pjrt/`, `packaging/winjax_cuda13_plugin/` build the
  binary wheels); `packaging/dist-release/` holds the current production
  wheel set.
- `toolchains/` — Bazel override repositories and the compiler wrapper:
  `winjax_cuda.bazelrc` (entry point), `local_config_cc/` (CC toolchain +
  `winjax_cc_wrapper.py`), `local_config_cuda_win/`, `cuda_repos/<name>/`
  (one tiny repo per CUDA component; junction dirs are machine-generated and
  ignored).
- `patches/` — Windows-port patch series for Bazel external repositories
  (triton, rmm, raft, rapids_logger, abseil, protobuf, eigen, jax,
  local_config_rocm). Apply with `git apply` / `patch -p1 -E`; see
  `patches/README.md`.
- `build/` — build & test-sweep drivers (`run_test_sweep.py`; `SWEEP_ALL=1`
  for the no-exclusions audit mode).
- `xla/`, `jax/`, `tools/`, `.venv*/` (ignored) — the XLA checkout (own
  repo/fork), the unmodified JAX build workspace, downloaded toolchains, and
  Python environments.

## Building from source

You need VS2022 (MSVC + Windows SDK), LLVM/clang ≥ 19, a CUDA 13.x toolkit,
MSYS2 (`patch`), and Bazelisk. From the `jax/` checkout at the pinned release
tag:

```
bazel --bazelrc=../toolchains/winjax_cuda.bazelrc build \
    --config=win_clang --config=winjax_cuda \
    @xla//xla/pjrt/c:pjrt_c_api_gpu_plugin.so \
    //jaxlib/tools:jax_cuda13_plugin_wheel
```

A `configure.py` that regenerates the machine-specific toolchain snapshot is
planned; until then the paths in `toolchains/` reflect the reference build
machine.

## Upstream

Several fixes found during this port are being prepared as upstream
contributions: an argument-evaluation-order bug and two MSVC-ABI overload
traps in XLA, Windows `LoadPjrtPlugin` support, COFF weak-symbol handling for
cuDNN/CUPTI, and a clang-version parsing bug in Bazel's Windows toolchain
autoconfiguration.
