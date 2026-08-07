"""winjax_cuda13_pjrt: Windows-built XLA CUDA PJRT plugin DLL for winjax."""

import os


def plugin_path() -> str:
    """Absolute path of the bundled PJRT plugin DLL."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "pjrt_c_api_gpu_plugin.dll")
