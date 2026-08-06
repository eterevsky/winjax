"""winjax: native Windows CUDA PJRT plugin loader for JAX.

Registers the Windows-built XLA GPU PJRT plugin with stock JAX. Loads the
plugin DLL itself and hands JAX the PJRT_Api* as a PyCapsule, bypassing
jaxlib's (not yet implemented on Windows) dlopen path.
"""

import ctypes
import os
import sys

_CUDA_ROOT = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.3"
_CUDNN_BIN = r"C:\Users\oleg\winjax\toolchains\cudnn\unpacked\nvidia\cudnn\bin"
_PLUGIN = (r"C:\users\oleg\_bazel_oleg\t4poymkv\execroot\__main__\bazel-out"
           r"\x64_windows-opt\bin\external\xla\xla\pjrt\c\pjrt_c_api_gpu_plugin.so")

_DLL_DIRS = [
    os.path.join(_CUDA_ROOT, "bin", "x64"),
    os.path.join(_CUDA_ROOT, "bin"),
    os.path.join(_CUDA_ROOT, "extras", "CUPTI", "lib64"),
    _CUDNN_BIN,
]


def initialize():
    if sys.platform != "win32":
        return

    # Stock JAX's GPU presence check only knows Linux device nodes.
    from jax._src import hardware_utils
    hardware_utils.has_visible_nvidia_gpu = lambda: True

    for d in _DLL_DIRS:
        if os.path.isdir(d):
            os.add_dll_directory(d)
    # XLA's ptxas discovery consults PATH; cuDNN 9's modular sublibraries load
    # each other via plain LoadLibrary, which searches PATH but ignores
    # add_dll_directory — so the cuDNN and CUDA DLL dirs must be on PATH too.
    os.environ["PATH"] = (os.path.join(_CUDA_ROOT, "bin") + os.pathsep +
                          os.path.join(_CUDA_ROOT, "bin", "x64") + os.pathsep +
                          _CUDNN_BIN + os.pathsep +
                          os.environ.get("PATH", ""))

    lib = ctypes.WinDLL(_PLUGIN)
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
            import importlib
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
        # The triton dialect module (_triton_ext) is not part of the current
        # self-built jaxlib wheel; skip the triton handler if unavailable.
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
