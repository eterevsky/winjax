"""jax_cuda13_plugin: winjax Windows build.

Registers CUDA DLL directories so the kernel extension modules (.pyd) in this
package can resolve their CUDA library dependencies at import time.
"""

import glob as _glob
import os as _os


def _add_cuda_dll_dirs():
  dirs = []
  for env in ("CUDA_ROOT", "CUDA_PATH"):
    root = _os.environ.get(env)
    if root:
      dirs += [
          _os.path.join(root, "bin", "x64"),
          _os.path.join(root, "bin"),
          _os.path.join(root, "extras", "CUPTI", "lib64"),
      ]
  for env in ("CUDNN_PATH", "CUDNN_HOME"):
    root = _os.environ.get(env)
    if root:
      dirs += [_os.path.join(root, "bin"), root]
  # NVIDIA pip wheels installed next to this package (site-packages/nvidia).
  site_dir = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
  _nv = _os.path.join(site_dir, "nvidia")
  for _pat in ("*/bin", "*/bin/x86_64", "*/*/bin", "*/*/bin/x86_64"):
    dirs += sorted(_glob.glob(_os.path.join(_nv, _pat)))
  for d in dirs:
    if _os.path.isdir(d):
      try:
        _os.add_dll_directory(d)
      except (OSError, AttributeError):
        pass


if _os.name == "nt":
  _add_cuda_dll_dirs()
