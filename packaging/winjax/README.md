# winjax

Native Windows CUDA support for JAX — no WSL2 required. Unofficial.

`winjax` installs a [PJRT](https://openxla.org/xla/pjrt) GPU plugin built
natively for Windows from XLA sources, plus a small loader that registers it
with stock `jax`/`jaxlib`. All CUDA runtime libraries (CUDA 13, cuDNN 9) come
from NVIDIA's pip wheels, so a working NVIDIA driver is the only system
requirement.

## Requirements

- Windows 10/11, x86-64
- Python 3.13
- An NVIDIA GPU with a driver supporting CUDA 13

## Install

```
pip install winjax
```

## Use

```python
import jax
print(jax.devices())  # [CudaDevice(id=0)]
```

Nothing else to configure: `import jax` discovers the plugin through the
`jax_plugins` namespace package.

## Packages

- `winjax` — loader (this package, pure Python)
- `winjax-cuda13-pjrt` — the Windows-built XLA CUDA PJRT plugin DLL
- `winjax-cuda13-plugin` — CUDA kernel extension modules (`jax_cuda13_plugin`)

Source and patches: https://github.com/eterevsky/winjax
