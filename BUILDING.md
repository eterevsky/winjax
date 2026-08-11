# Building winjax from source

Complete instructions for building the winjax wheel set on a **fresh Windows
machine**. Read `README.md` first for what winjax is and how the pieces fit
together. Everything below is native Windows — no WSL.

The build produces three distributions (four wheel files):

| Wheel | Built by |
|---|---|
| `winjax` (pure Python loader) | `packaging/winjax/` (setuptools) |
| `winjax-cuda13-pjrt` (the 244 MB PJRT plugin DLL) | Bazel + `packaging/winjax_cuda13_pjrt/build_wheel.py` |
| `winjax-cuda13-plugin` (CUDA kernel extensions, cp313 + cp314) | Bazel + `packaging/winjax_cuda13_plugin/repack.py` |

## 1. Prerequisites

Install once, in any order. Nothing needs to be on `PATH` except Python and
git — `configure.py` finds the rest (every location can also be overridden,
see `python configure.py --help`).

- **Windows 10/11 x64** with **Developer Mode enabled**
  (Settings → System → For developers). Bazel needs it to create symlinks
  without elevation.
- **An NVIDIA GPU + current driver** (CUDA 13-era, i.e. driver ≥ 580).
  `configure.py` reads the GPU's compute capability via `nvidia-smi`; on a
  build machine without a GPU pass `--cuda-archs=sm_120` (or your target)
  instead.
- **Visual Studio 2022** (Community is fine) with the *Desktop development
  with C++* workload — MSVC v143 (14.4x) **and** a Windows 11 SDK. Found via
  `vswhere`; override with `--vs-path`.
- **LLVM ≥ 19** (validated with 22.x): official `clang+llvm-*-x86_64-pc-windows-msvc`
  release archive, extracted anywhere (the reference machine uses
  `<repo>\tools\llvm22`). clang 18 and older **cannot** compile against the
  MSVC 14.4x STL (`STL1000` static assert). Found via `LLVM_DIR` env,
  `<repo>\tools\llvm*`, `C:\Program Files\LLVM`, or `PATH`; override with
  `--llvm-dir`. clang-cl compiles all host code; `clang++ -x cuda` compiles
  the device code (no nvcc in the build).
- **CUDA Toolkit 13.x** (validated with 13.3) — default install location
  `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.x`. Override with
  `--cuda-path` or `CUDA_PATH`. Only headers/libs/`bin` tools are used at
  build time; end users get their CUDA userland from pip wheels.
- **MSYS2** (e.g. `C:\msys64` or `<repo>\tools\msys64`), plus the `patch`
  package: `pacman -S patch`. Bazel needs `bash.exe` (`BAZEL_SH`) for
  genrules; `patch` is used when re-deriving patches.
- **Bazelisk** — download `bazelisk-windows-amd64.exe` and save it as
  `<repo>\tools\bazel.exe` (or have `bazel` on `PATH`). It fetches the Bazel
  version pinned by jax (7.x) automatically.
- **Python 3.13** (64-bit) as the main interpreter, with `pip install wheel build`.
  **Python 3.14** additionally if you want the cp314 kernels wheel.
- **git**.

Hardware: ~64 GB RAM recommended (the link of the plugin DLL and the XLA
compile are heavy), ~50 GB free disk for the Bazel output base.

## 2. Check out the three repositories

```bat
git clone https://github.com/eterevsky/winjax
cd winjax

:: jax at the pinned release tag, plus the winjax kernels-wheel patch
git clone https://github.com/jax-ml/jax.git jax
git -C jax checkout jax-v0.11.0
git -C jax apply ..\patches\jax\windows-kernels-wheel.patch

:: XLA: the winjax Windows-port branch of the fork (already contains the
:: pinned revision for jax-v0.11.0 plus the Windows patches)
git clone --branch winjax-0.11.0 https://github.com/eterevsky/xla.git xla
```

The layout `winjax/{jax,xla}` is the default; other locations work via
`configure.py --jax-dir/--xla-dir` (the generated bazelrc points `@xla` at
the configured path).

The jax patch (`patches/jax/windows-kernels-wheel.patch`) is applied **once,
in the checkout**: MAGMA dlopen stubs on Windows, Mosaic-GPU exclusion,
Windows DLL-directory setup in the generated kernels-wheel `__init__`, and a
`copysign` fix for the device pass. Without it the kernels wheel does not
build.

## 3. Configure

```bat
python configure.py --patch-externals
```

This probes the machine and generates every machine-specific file (nothing
with absolute local paths is committed — see `toolchains/templates/`):

- `toolchains/local_config_cc/` — the Bazel CC toolchain (MSVC + clang-cl +
  the `winjax_cl.bat` → `winjax_cc_wrapper.py` compiler-dispatch wrapper),
  rendered with your MSVC/SDK/LLVM paths and a captured `vcvarsall`
  environment;
- `toolchains/winjax_cuda.bazelrc` — `--override_repository` wiring for this
  checkout;
- `toolchains/cccl_patched/` — a copy of the toolkit's CCCL headers with
  `patches/cccl/*.patch` applied;
- `toolchains/cudnn/` — the `nvidia-cudnn-cu13` wheel (downloaded via pip if
  not present; `--cudnn-wheel` to point at a file) unpacked, with `.lib`
  import libraries generated from the DLL export tables (the wheel ships no
  `.lib`);
- `toolchains/cuda_repos/*/` — NTFS junctions into the CUDA toolkit /
  `cccl_patched` / the cuDNN wheel (junctions need no admin rights);
- `toolchains/local_config_cuda_win/cuda/cuda/cuda_config.h|py` — toolkit
  path/version and compute capabilities;
- `toolchains/winjax_env.bat` — sets `BAZEL_SH` for build shells.

It then runs an **analysis-only** Bazel build of the plugin target as a
smoke check (a few minutes on first run — it downloads all external repos).

**External-repository patches.** Bazel fetches *pristine* external repos
(triton, rmm, raft, rapids_logger, abseil, protobuf, eigen); the compile
fails without the Windows-port patches in `patches/`. There is no hook in
the workspace stanzas for them (they live in XLA's pinned files), so
`--patch-externals` applies them **into the materialized output base**
(`<output_base>/external/<repo>/`), idempotently, right after the fetch;
`local_config_rocm` gets its `build_defs.bzl` replaced (machine-generated
repo, no stable diff base). This is a property of the *output base*, not the
source tree: **re-run `python configure.py --patch-externals` after
`bazel clean --expunge`, after moving the output base, or after an XLA pin
change** — a plain `bazel clean` or incremental fetch keeps them. The patch
series is designed to survive re-fetches of unrelated repos.

Re-running `configure.py` is always safe (it is idempotent and detects
up-to-date state); use `--force` to rebuild `cccl_patched`/cuDNN artifacts.

## 4. Build

From a plain `cmd` shell:

```bat
call toolchains\winjax_env.bat        :: sets BAZEL_SH
cd jax

:: 4a. The PJRT plugin DLL (~19,500 actions, ~1 h on a fast machine)
..\tools\bazel --bazelrc=..\toolchains\winjax_cuda.bazelrc build ^
    --config=win_clang --config=winjax_cuda ^
    --repo_env=HERMETIC_PYTHON_VERSION=3.13 ^
    @xla//xla/pjrt/c:pjrt_c_api_gpu_plugin.so

:: 4b. The CUDA kernels wheel (cp313)
..\tools\bazel --bazelrc=..\toolchains\winjax_cuda.bazelrc build ^
    --config=win_clang --config=winjax_cuda ^
    --repo_env=HERMETIC_PYTHON_VERSION=3.13 --repo_env=ML_WHEEL_TYPE=release ^
    //jaxlib/tools:jax_cuda13_plugin_wheel
```

Outputs:

- `jax\bazel-bin\external\xla\xla\pjrt\c\pjrt_c_api_gpu_plugin.so`
  (a PE DLL despite the `.so` name, ~244 MB)
- `jax\bazel-bin\jaxlib\tools\dist\jax_cuda13_plugin-0.11.0-cp313-cp313-win_amd64.whl`

For the **cp314** kernels wheel, repeat 4b with
`--repo_env=HERMETIC_PYTHON_VERSION=3.14` (incremental, ~1–2 min).
`ML_WHEEL_TYPE=release` stamps the exact release version (`0.11.0`) instead
of a `.dev` suffix — required for the pip pin chain to resolve.

## 5. Assemble the wheels

```bat
cd <repo root>

:: stable copy of the DLL (bazel-bin copies get locked by running tests)
mkdir dist 2>nul
copy /y jax\bazel-bin\external\xla\xla\pjrt\c\pjrt_c_api_gpu_plugin.so dist\
copy /y jax\bazel-bin\jaxlib\tools\dist\jax_cuda13_plugin-0.11.0-cp313-cp313-win_amd64.whl dist\

:: winjax-cuda13-pjrt: packs dist\pjrt_c_api_gpu_plugin.so
python packaging\winjax_cuda13_pjrt\build_wheel.py

:: winjax-cuda13-plugin: renames the distribution (module stays
:: jax_cuda13_plugin), widens the nvidia DLL-dir glob (needs `pip install wheel`)
python packaging\winjax_cuda13_plugin\repack.py

:: winjax loader wheel (pure Python; needs `pip install build`)
python -m build --wheel --outdir packaging\dist packaging\winjax
```

All three land in `packaging\dist\`. See `packaging/README.md` for the
version/pin policy and the release procedure.

## 6. Verify

Quick check in a fresh venv (offline against your local wheels, online for
jax/nvidia deps):

```bat
py -3.13 -m venv .venv-check
.venv-check\Scripts\pip install --find-links packaging\dist winjax
.venv-check\Scripts\python -c "import jax; print(jax.devices()); import jax.numpy as jnp; x=jnp.ones((1024,1024)); print((x@x)[0,0])"
```

Expect `[CudaDevice(id=0)]` and a GPU matmul.

Full test sweep (the acceptance bar: JAX's own test suite on the winjax
backend — ~36,400 passed / 0 failed on the reference machine):

```bat
.venv-check\Scripts\pip install pytest absl-py numpy scipy pillow flatbuffers cloudpickle
set SWEEP_PYTHON=<repo>\.venv-check\Scripts\python.exe
python build\run_test_sweep.py
```

Per-file logs and `SUMMARY.txt` land in `test_logs\`. Multi-GPU/distributed
files are excluded by default (`SWEEP_ALL=1` for the no-exclusions audit).
Compare against `KNOWN_ISSUES.md`.

## Troubleshooting

- **`LoadPjrtPlugin ... UNIMPLEMENTED` / no `CudaDevice`** — the `winjax`
  loader package isn't installed in the venv, or no NVIDIA driver is
  present (the loader then silently stays out of the way).
- **Compile errors in CCCL headers (`string_view`, `_CCCL_THROW`)** — the
  external patches or `cccl_patched` are missing: re-run
  `python configure.py --patch-externals` (mandatory after
  `bazel clean --expunge`).
- **`VERSION`/`version` include clash, `dlfcn.h`/`execinfo.h` not found** —
  same cause: external patches not applied to the output base.
- **Bazel picks MSVC `cl.exe` and chokes on `-W...` flags** — you dropped
  `--config=win_clang`.
- **`STL1000` static assert** — clang < 19 against MSVC 14.4x STL; install a
  newer LLVM and re-run `configure.py`.
- **Symlink permission errors from Bazel** — enable Windows Developer Mode.
- **Never edit files under Bazel's install base** (`_bazel_<user>\install\...`)
  — the mtime integrity check bricks the installation (delete the install
  dir to recover, after killing lingering `java.exe`).
- **A different VS/toolset gets picked up** — `configure.py` prefers VS2022
  (17.x); pass `--vs-path` to pin an installation (newer/preview MSVC
  toolsets are unvalidated).
