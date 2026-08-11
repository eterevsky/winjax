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

    # WDDM memory policy: default to on-demand growth instead of
    # preallocating 75% of VRAM. On Windows display GPUs (WDDM) a
    # preallocated device pool is charged against the process' host commit
    # limit, and re-initializing after jax.clear_backends() races the
    # driver's asynchronous release of the old pool: the fresh pool then
    # seizes the entire GPU budget and pinned-host (cuMemHostAlloc)
    # allocations fail process-wide. On-demand growth (the standard
    # XLA_PYTHON_CLIENT_PREALLOCATE=false mode) avoids both. Set the
    # variable explicitly to override.
    os.environ.setdefault("XLA_PYTHON_CLIENT_PREALLOCATE", "false")

    # All environment/DLL-search changes must happen BEFORE the plugin DLL is
    # loaded: its C runtime snapshots the process environment at load time.
    dll_dirs = _cuda_dll_dirs()
    for d in dll_dirs:
        os.add_dll_directory(d)

    # cuDNN policy: exactly ONE cuDNN 9.x family can serve a Windows
    # process. The OS loader resolves modules by NAME process-wide (the
    # first DLL loaded under a name serves every later by-name lookup),
    # cuDNN's dispatcher loads its sublibraries (cudnn_graph, cudnn_cnn,
    # engines, ...) with plain LoadLibrary — which ignores
    # add_dll_directory — and the internal cross-DLL exports differ between
    # 9.x minors, so members of two minors cannot bind to each other
    # (WinError 127 / cudnn status 1008) in EITHER direction. On top of
    # that, XLA requires the runtime cuDNN to be >= the version the plugin
    # was compiled against (same major). Consequences:
    #   * No cuDNN resident yet (jax imported first, or no torch): preload
    #     OUR complete family by full path. Parts of it are already
    #     resident anyway — the kernels wheel's .pyds statically import
    #     cudnn sublibraries during "import jax" — so ours is the only
    #     family the process can still complete consistently.
    #   * A cuDNN main is already resident (torch eagerly loads its whole
    #     bundled family at "import torch"): it cannot be displaced. Adopt
    #     it when it is new enough for the plugin; otherwise warn that jax
    #     cuDNN ops are unavailable (the GPU otherwise works).
    # WINJAX_FORCE_OWN_CUDNN=1 skips adoption and always preloads ours.
    # Never put a cuDNN dir on PATH: PATH is searched by torch's own DLL
    # preloading and by cuDNN's sublibrary loads, and would cross-mix the
    # families in other frameworks too.
    cudnn_dirs = [d for d in dll_dirs
                  if glob.glob(os.path.join(d, "cudnn*.dll"))]

    def _cudnn_ver_str(v):
        return f"{v // 10000}.{v % 10000 // 100}.{v % 100}"

    def _compiled_cudnn_version():
        """cuDNN version the plugin wheels were built against."""
        for pkg in ("jax_cuda13_plugin", "jax_cuda12_plugin"):
            try:
                mod = importlib.import_module(pkg + "._versions")
                return int(mod.cudnn_build_version())
            except Exception:
                continue
        return 92400  # matches the shipped winjax-cuda13 wheels

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetModuleHandleW.restype = ctypes.c_void_p
    kernel32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
    kernel32.GetModuleFileNameW.argtypes = [
        ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint32]

    def _resident_cudnn():
        """(path, version) of the loaded cudnn64_9, else (None, None)."""
        handle = kernel32.GetModuleHandleW("cudnn64_9.dll")
        if not handle:
            return None, None
        buf = ctypes.create_unicode_buffer(2048)
        kernel32.GetModuleFileNameW(handle, buf, 2048)
        try:
            dll = ctypes.WinDLL("cudnn64_9.dll")
            dll.cudnnGetVersion.restype = ctypes.c_size_t
            return buf.value, int(dll.cudnnGetVersion())
        except (OSError, AttributeError):
            return buf.value, None

    def _preload_cudnn_family(directory):
        """Loads every cudnn*.dll in directory by full path (best effort).

        cuDNN 9 loads its sublibraries lazily by plain-LoadLibrary NAME
        lookup; preloading the complete family is what makes those lookups
        resolve — to one consistent family — without touching PATH.
        """
        for dll in sorted(glob.glob(os.path.join(directory, "cudnn*.dll"))):
            try:
                ctypes.WinDLL(dll)
            except OSError:
                pass  # cross-family straggler; nothing actionable here

    def _dll_file_version(path):
        """cuDNN-style int version from a DLL's version resource, or None.

        Reads the file on disk — does NOT load the DLL, so probing never
        commits the process to a family.
        """
        try:
            version = ctypes.WinDLL("version")
            version.GetFileVersionInfoSizeW.argtypes = [
                ctypes.c_wchar_p, ctypes.c_void_p]
            version.GetFileVersionInfoW.argtypes = [
                ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                ctypes.c_void_p]
            version.VerQueryValueW.argtypes = [
                ctypes.c_void_p, ctypes.c_wchar_p,
                ctypes.POINTER(ctypes.c_void_p),
                ctypes.POINTER(ctypes.c_uint)]
            size = version.GetFileVersionInfoSizeW(path, None)
            if not size:
                return None
            data = ctypes.create_string_buffer(size)
            if not version.GetFileVersionInfoW(path, 0, size, data):
                return None
            info = ctypes.c_void_p()
            length = ctypes.c_uint()
            if not version.VerQueryValueW(data, "\\", ctypes.byref(info),
                                          ctypes.byref(length)):
                return None
            # VS_FIXEDFILEINFO: dwFileVersionMS/LS at offsets 8/12.
            ms = ctypes.cast(info.value + 8,
                             ctypes.POINTER(ctypes.c_uint32)).contents.value
            ls = ctypes.cast(info.value + 12,
                             ctypes.POINTER(ctypes.c_uint32)).contents.value
            return (ms >> 16) * 10000 + (ms & 0xFFFF) * 100 + (ls >> 16)
        except OSError:
            return None

    compiled_ver = _compiled_cudnn_version()
    force_own = os.environ.get("WINJAX_FORCE_OWN_CUDNN") == "1"
    resident_path, resident_ver = _resident_cudnn()
    if resident_path is not None and not force_own:
        if (resident_ver is not None
                and resident_ver // 10000 == compiled_ver // 10000
                and resident_ver >= compiled_ver):
            # Adopt: complete the resident family so its lazily-loaded
            # engine sublibraries resolve by name at first use.
            _preload_cudnn_family(os.path.dirname(resident_path))
        else:
            _res = (_cudnn_ver_str(resident_ver)
                    if resident_ver is not None else "of unknown version")
            print(
                f"winjax: cuDNN {_res} is already loaded ({resident_path}) "
                f"but the winjax plugin was built against cuDNN "
                f"{_cudnn_ver_str(compiled_ver)} and needs that version or "
                "newer at runtime. jax cuDNN ops (convolution, attention, "
                "...) will be UNAVAILABLE in this process; other GPU ops "
                "still work. A Windows process can host only one cuDNN: "
                "either upgrade the package that loaded it (usually torch) "
                "to one bundling cuDNN >= "
                f"{_cudnn_ver_str(compiled_ver)}, or keep jax and torch in "
                "separate processes.", file=sys.stderr)
    else:
        if resident_path is not None:
            print(
                "winjax: WINJAX_FORCE_OWN_CUDNN=1, but cuDNN is already "
                f"loaded ({resident_path}) and will keep serving this "
                "process.", file=sys.stderr)
        for d in cudnn_dirs:
            _preload_cudnn_family(d)
        main_path, main_ver = _resident_cudnn()
        if main_ver is not None and main_ver < compiled_ver:
            print(
                f"winjax: the available cuDNN {_cudnn_ver_str(main_ver)} "
                f"({main_path}) is older than the cuDNN "
                f"{_cudnn_ver_str(compiled_ver)} the winjax plugin was "
                "built against; jax cuDNN ops will be unavailable. "
                "Upgrade with: pip install -U nvidia-cudnn-cu13",
                file=sys.stderr)
        # torch bundles its own cuDNN family and hard-loads every DLL in
        # torch\lib at import; if that family differs from the one now
        # resident, a later "import torch" in this process will fail.
        # Probe torch's bundled version from the file's version resource
        # (no DLL load) and give the user a heads-up in advance.
        torch_main = None
        torch_spec = importlib.util.find_spec("torch")
        if torch_spec is not None:
            for loc in (torch_spec.submodule_search_locations or []):
                cand = os.path.join(loc, "lib", "cudnn64_9.dll")
                if os.path.isfile(cand):
                    torch_main = cand
                    break
        if torch_main is not None and main_ver is not None:
            torch_ver = _dll_file_version(torch_main)
            if torch_ver is not None and torch_ver != main_ver:
                print(
                    f"winjax: torch bundles cuDNN "
                    f"{_cudnn_ver_str(torch_ver)} ({torch_main}) but this "
                    f"process now runs cuDNN {_cudnn_ver_str(main_ver)}; a "
                    "Windows process can host only one cuDNN, so importing "
                    "torch here is likely to fail (WinError 127 on its "
                    "cudnn DLLs). To combine torch and jax in one process, "
                    "import torch FIRST: jax then uses torch's cuDNN if it "
                    f"is >= {_cudnn_ver_str(compiled_ver)}, and runs "
                    "without cuDNN ops otherwise.", file=sys.stderr)

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
    from jax._src.lib import xla_client
    # Pass the standard GPU plugin options (allocator kind, memory fraction,
    # preallocation, collective memory size) like upstream's cuda plugin
    # does; without them the plugin ignores XLA_PYTHON_CLIENT_* entirely.
    # The callable defers env reading to client-creation time.
    c_api = xb.register_plugin(
        "cuda", priority=500, c_api=capsule,
        options=xla_client.generate_pjrt_gpu_plugin_options)

    # Register the plugin's PJRT profiler extension (CUPTI device tracing).
    # jax's register_plugin() only does this on its library_path branch, not
    # on the c_api branch used here; without it, jax.profiler traces contain
    # host planes but no /device:GPU planes.
    try:
        from jax._src.lib import _profiler
        _profiler.register_plugin_profiler(c_api)
    except (ImportError, AttributeError) as e:
        print(f"winjax: could not register plugin profiler: {e}",
              file=sys.stderr)

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
