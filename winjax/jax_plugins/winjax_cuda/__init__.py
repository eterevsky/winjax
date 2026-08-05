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
    # XLA's ptxas discovery also consults PATH.
    os.environ["PATH"] = (os.path.join(_CUDA_ROOT, "bin") + os.pathsep +
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
    xb.register_plugin("cuda", priority=500, c_api=capsule)
