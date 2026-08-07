"""winjax: native Windows CUDA PJRT plugin loader for JAX.

Registers the Windows-built XLA GPU PJRT plugin with stock JAX. Loads the
plugin DLL itself and hands JAX the PJRT_Api* as a PyCapsule, bypassing
jaxlib's (not yet implemented on Windows) dlopen path.

The plugin DLL ships in the winjax-cuda13-pjrt wheel; the CUDA runtime
libraries, ptxas and libdevice come from the nvidia-* pip wheels
(site-packages/nvidia/...). A locally installed CUDA toolkit is honored
via CUDA_ROOT / CUDA_PATH but is not required.
"""

import ctypes
import glob
import importlib
import importlib.util
import os
import sys


def _pjrt_plugin_path():
    """Locates pjrt_c_api_gpu_plugin.dll in the winjax_cuda13_pjrt package."""
    spec = importlib.util.find_spec("winjax_cuda13_pjrt")
    if spec is None:
        return None
    locations = list(spec.submodule_search_locations or [])
    if spec.origin:
        locations.append(os.path.dirname(spec.origin))
    for loc in locations:
        path = os.path.join(loc, "pjrt_c_api_gpu_plugin.dll")
        if os.path.isfile(path):
            return path
    return None


def _nvidia_roots():
    """Yields every site-packages/nvidia directory visible on sys.path."""
    roots = []
    for entry in sys.path:
        candidate = os.path.join(entry or os.getcwd(), "nvidia")
        if os.path.isdir(candidate) and candidate not in roots:
            roots.append(candidate)
    return roots


def _cuda_dll_dirs():
    """DLL directories from NVIDIA pip wheels (plus optional toolkit envs)."""
    dirs = []

    def _add(d):
        if os.path.isdir(d) and d not in dirs:
            dirs.append(d)

    # Optional local-toolkit overrides for development setups.
    for env in ("CUDA_ROOT", "CUDA_PATH"):
        root = os.environ.get(env)
        if root:
            _add(os.path.join(root, "bin", "x64"))
            _add(os.path.join(root, "bin"))
            _add(os.path.join(root, "extras", "CUPTI", "lib64"))
    for env in ("CUDNN_PATH", "CUDNN_HOME"):
        root = os.environ.get(env)
        if root:
            _add(os.path.join(root, "bin"))

    # NVIDIA pip wheels: cu13 wheels put DLLs in nvidia/cu13/bin/x86_64 and
    # tools (ptxas, nvcc) in nvidia/cu13/bin; cuDNN uses nvidia/cudnn/bin.
    # Glob generously to cover nested layouts of other/older wheels too.
    for nv in _nvidia_roots():
        for pattern in ("*/bin", "*/bin/x86_64", "*/*/bin", "*/*/bin/x86_64"):
            for d in sorted(glob.glob(os.path.join(nv, pattern))):
                _add(d)
    return dirs


def _cuda_root():
    """A directory usable as XLA's CUDA data dir (bin/ptxas.exe, nvvm/...)."""
    for env in ("CUDA_ROOT", "CUDA_PATH"):
        root = os.environ.get(env)
        if root and os.path.isdir(root):
            return root
    for nv in _nvidia_roots():
        for sub in sorted(os.listdir(nv)):
            root = os.path.join(nv, sub)
            if (os.path.isfile(os.path.join(root, "bin", "ptxas.exe"))
                    or os.path.isfile(os.path.join(
                        root, "nvvm", "libdevice", "libdevice.10.bc"))):
                return root
    return None


def initialize():
    if sys.platform != "win32":
        return

    # No NVIDIA driver -> no GPU. Bail out before registering anything so
    # machines without a GPU fall back to jax's CPU backend silently.
    try:
        ctypes.WinDLL("nvcuda.dll")
    except OSError:
        return

    # Stock JAX's GPU presence check only knows Linux device nodes.
    from jax._src import hardware_utils
    hardware_utils.has_visible_nvidia_gpu = lambda: True

    # All environment/DLL-search changes must happen BEFORE the plugin DLL is
    # loaded: its C runtime snapshots the process environment at load time.
    dll_dirs = _cuda_dll_dirs()
    for d in dll_dirs:
        os.add_dll_directory(d)

    # cuDNN 9's modular sublibraries load each other with plain by-name
    # LoadLibrary calls. Do NOT solve that by putting the cuDNN dir on PATH:
    # that poisons other frameworks' bundled cuDNN (e.g. torch\lib) when jax
    # is imported first. Instead preload our cuDNN DLLs by absolute path —
    # the process module cache then satisfies by-name lookups for us, and
    # other libraries' resolution is untouched.
    cudnn_dirs = [d for d in dll_dirs
                  if glob.glob(os.path.join(d, "cudnn*.dll"))]
    for d in cudnn_dirs:
        for dll in sorted(glob.glob(os.path.join(d, "cudnn*.dll"))):
            try:
                ctypes.WinDLL(dll)
            except OSError:
                pass

    # XLA's ptxas/nvdisasm discovery consults PATH; those tool dirs are
    # harmless to other frameworks. Keep cuDNN dirs OFF PATH (see above).
    path_dirs = [d for d in dll_dirs if d not in cudnn_dirs]
    if path_dirs:
        os.environ["PATH"] = os.pathsep.join(
            path_dirs + [os.environ.get("PATH", "")])

    cuda_root = _cuda_root()
    if cuda_root is not None:
        # XLA's CandidateCudaRoots() consults CUDA_HOME as a fallback.
        os.environ.setdefault("CUDA_HOME", cuda_root)
        # jax sets XLA's xla_gpu_cuda_data_dir (ptxas + libdevice discovery)
        # from jax._src.lib.cuda_path, whose import-time detection does not
        # understand the Windows nvidia wheel layout (it probes for a POSIX
        # 'bin/ptxas' and yields the string "None"). Patch it up.
        from jax._src import lib as _jax_src_lib
        if getattr(_jax_src_lib, "cuda_path", None) in (None, "None"):
            _jax_src_lib.cuda_path = cuda_root

    plugin_path = _pjrt_plugin_path()
    if plugin_path is None:
        raise RuntimeError(
            "winjax: pjrt_c_api_gpu_plugin.dll not found; is the "
            "winjax-cuda13-pjrt package installed?")

    try:
        lib = ctypes.WinDLL(plugin_path)
    except OSError as e:
        print(f"winjax: failed to load {plugin_path}: {e}; "
              "falling back to CPU.", file=sys.stderr)
        return
    get_api = lib.GetPjrtApi
    get_api.restype = ctypes.c_void_p
    api_ptr = get_api()

    capsule_new = ctypes.pythonapi.PyCapsule_New
    capsule_new.restype = ctypes.py_object
    capsule_new.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p]
    capsule = capsule_new(api_ptr, b"pjrt_c_api", None)

    from jax._src import xla_bridge as xb
    c_api = xb.register_plugin("cuda", priority=500, c_api=capsule)

    # Wire the Python-side kernel registrations from the jax_cuda13_plugin
    # kernels wheel (custom-call/FFI handlers for solver/linalg/prng/etc.)
    # into the plugin's PJRT_Api, mirroring jax_plugins/cuda/__init__.py.
    cuda_plugin_extension = None
    for pkg_name in ("jax_cuda13_plugin", "jax_cuda12_plugin", "jaxlib.cuda"):
        try:
            cuda_plugin_extension = importlib.import_module(
                f"{pkg_name}.cuda_plugin_extension")
            break
        except ImportError:
            cuda_plugin_extension = None
    if cuda_plugin_extension is not None:
        import functools
        from jax._src.lib import xla_client
        xla_client.register_custom_type_handler(
            "CUDA",
            functools.partial(
                cuda_plugin_extension.register_custom_type, c_api),
        )
        xla_client.register_custom_call_handler(
            "CUDA",
            functools.partial(
                cuda_plugin_extension.register_custom_call_target, c_api),
        )
        for _name, _value in cuda_plugin_extension.ffi_types().items():
            xla_client.register_custom_type(_name, _value, platform="CUDA")
        for _name, _value in cuda_plugin_extension.ffi_handlers().items():
            xla_client.register_custom_call_target(
                _name, _value, platform="CUDA", api_version=1)
        # The triton dialect module (_triton_ext) is not part of stock
        # Windows jaxlib; skip the triton handler if unavailable.
        try:
            from jax._src.lib import triton
        except ImportError:
            pass
        else:
            triton.register_compilation_handler(
                "CUDA",
                functools.partial(
                    cuda_plugin_extension.compile_triton_to_asm, c_api),
            )
