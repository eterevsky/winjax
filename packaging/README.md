# winjax packaging

Sources and build scripts for the winjax wheel set, plus the release
procedure. How the binaries themselves are built is covered in
[`../BUILDING.md`](../BUILDING.md).

## The wheel set: 3 distributions, 4 files

| Distribution | File(s) | Contents |
|---|---|---|
| `winjax` | `winjax-X.Y.Z-py3-none-any.whl` | Pure-Python loader: the `jax_plugins/winjax_cuda` namespace package. Probes for an NVIDIA driver, registers the CUDA DLL directories from the `nvidia-*` pip wheels, preloads cuDNN (single-family policy), loads the PJRT DLL and registers it with JAX. Carries all dependency pins. |
| `winjax-cuda13-pjrt` | `winjax_cuda13_pjrt-X.Y.Z-py3-none-win_amd64.whl` | The XLA GPU compiler + runtime as one PJRT plugin DLL (`winjax_cuda13_pjrt/pjrt_c_api_gpu_plugin.dll`, ~72 MB compressed — under PyPI's 100 MB default limit, no size exemption needed). `py3-none`: no Python linkage, one file serves all Python versions. |
| `winjax-cuda13-plugin` | `winjax_cuda13_plugin-X.Y.Z-cp313-...whl` and `-cp314-...whl` | The CUDA kernel extension modules (cuSOLVER / linalg / RNG / RNN / sparse / triton FFI `.pyd`s). **Distribution** renamed from upstream's `jax-cuda13-plugin` to avoid a PyPI collision; the **import name stays `jax_cuda13_plugin`** — jax/jaxlib discover the kernels by that module name. CPython-ABI-specific: one wheel per Python version. |

Who builds what:

- `winjax/` — standard setuptools project: `pyproject.toml` (name, version,
  all dependency pins), `README.md` (PyPI long description), and the
  **canonical loader source** `jax_plugins/winjax_cuda/__init__.py`.
  Build: `python -m build --wheel --outdir dist winjax`.
- `winjax_cuda13_pjrt/` — `build_wheel.py` writes the wheel directly
  (zipfile + RECORD; no setuptools). Version lives in the `VERSION`
  constant. Input: `../../dist/pjrt_c_api_gpu_plugin.so` (the Bazel-built
  DLL, renamed to `.dll` inside the wheel). The tiny
  `winjax_cuda13_pjrt/__init__.py` exposes `plugin_path()` for the loader.
- `winjax_cuda13_plugin/` — `repack.py` transforms the Bazel-built
  `jax_cuda13_plugin-*.whl`: renames the distribution in `.dist-info`,
  rewrites the `jax-cuda13-pjrt` dependency to `winjax-cuda13-pjrt`, and
  widens the nvidia DLL-directory glob in the package `__init__` for the
  CUDA 13 Windows wheel layout (`nvidia/*/bin/x86_64` etc.). Version in the
  `VERSION` constant (must match the wheel Bazel produced —
  `ML_WHEEL_TYPE=release`). Requires `pip install wheel`.

Directories:

- `dist/` — build output staging (gitignored).
- `dist-release/` — the published production wheel set, kept as a record
  (tracked). Never rebuild or overwrite these files.

## Version and pin policy

- **Version scheme**: `0.11.x` tracks the jax 0.11 family *loosely* — the
  winjax patch number is not guaranteed to equal jax's. Each winjax release
  pins one exact `jax`/`jaxlib` pair (currently `==0.11.0`).
- **requires-python**: `>=3.13,<3.15` on **all** wheels (matches the
  official Windows jaxlib wheels). New Python support = add a cp31x kernels
  wheel and widen this bound everywhere.
- **Inter-wheel pins**: `winjax` depends on
  `winjax-cuda13-pjrt==X.Y.Z.*` and `winjax-cuda13-plugin==X.Y.Z.*` —
  wildcard, therefore **post-release-tolerant**. Do not use exact `==X.Y.Z`
  pins here: they deadlocked pip's resolver in testing when posts were
  involved. The kernels wheel's own metadata pins
  `winjax-cuda13-pjrt==<the version repack.py stamped>` — when publishing a
  post of the pjrt wheel, re-run `repack.py` so the pair stays resolvable.
- **Post-releases** (`X.Y.Z.postN`): for packaging/loader fixes that don't
  change the jax pinning. Typically only the affected wheel gets the post
  (loader fixes → `winjax` only); the `.*` pins keep the set resolvable.
  Binary rebuilds against the same jax release may also ship as posts of
  the binary wheels.
- **NVIDIA runtime deps** (on the `winjax` wheel only): floors at the
  verified versions, `<next-major` caps (future majors may not ship
  win_amd64 wheels). The cuDNN floor interacts with the loader's
  single-cuDNN-family coexistence policy — keep
  `nvidia-cudnn-cu13>=<version the plugin was compiled against>`.

## Release procedure

1. **Build** the DLL and kernels wheels (BUILDING.md §4), for cp313 **and**
   cp314, and assemble all four files into `dist/` (BUILDING.md §5). Bump
   versions first: `winjax/pyproject.toml`, `winjax_cuda13_pjrt/build_wheel.py`,
   `winjax_cuda13_plugin/repack.py` (+ its default input filename).
2. **Local verify**: fresh venvs for 3.13 and 3.14,
   `pip install --find-links packaging\dist winjax`, then devices/matmul/
   conv/QR checks (see BUILDING.md §6; `coexist_test.py` for the
   torch-coexistence matrix when the loader changed).
3. **TestPyPI**:
   `twine upload --repository testpypi dist/*` (TestPyPI token). Then verify
   the real resolver path in fresh 3.13 **and** 3.14 venvs:
   `pip install --index-url https://test.pypi.org/simple/ --extra-index-url
   https://pypi.org/simple/ winjax`. Expect index/CDN propagation delays of
   minutes — retry before diagnosing.
4. **Production PyPI**: `twine upload dist/*` with the production token
   (owner: Oleg). Verify with a plain `pip install winjax` in a fresh venv.
5. **Record**: copy the published set into `dist-release/`, commit, tag the
   repo, and update README/KNOWN_ISSUES status.

Gotchas:

- Never write TOML/build files with PowerShell `Set-Content -Encoding utf8`
  (writes a BOM that breaks parsers); use `UTF8Encoding($false)` or edit
  with a BOM-free editor.
- All four files must be uploaded together for a coherent set; pip resolves
  the newest matching post across the `.*` pins.
- The pjrt wheel is ~72 MB — safely under the 100 MB PyPI file limit; no
  size-exemption request needed at current sizes.
