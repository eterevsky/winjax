r"""Builds the winjax-cuda13-pjrt wheel.

Packs the Windows-built XLA PJRT GPU plugin (pjrt_c_api_gpu_plugin.so, a PE
DLL despite the extension) into a win_amd64 wheel as
winjax_cuda13_pjrt/pjrt_c_api_gpu_plugin.dll.

Usage: python build_wheel.py [path\to\pjrt_c_api_gpu_plugin.so] [dest_dir]
Defaults: ..\..\dist\pjrt_c_api_gpu_plugin.so, dest ..\dist
"""

import base64
import hashlib
import os
import sys
import zipfile

NAME = "winjax_cuda13_pjrt"
VERSION = "0.11.0"
TAG = "py3-none-win_amd64"

METADATA = f"""\
Metadata-Version: 2.1
Name: winjax-cuda13-pjrt
Version: {VERSION}
Summary: XLA CUDA PJRT plugin DLL for JAX on native Windows (winjax)
Home-page: https://github.com/eterevsky/winjax
Author: Oleg Eterevsky
Author-email: oleg@eterevsky.com
License: Apache-2.0
Classifier: Development Status :: 3 - Alpha
Classifier: Environment :: GPU :: NVIDIA CUDA :: 13
Classifier: Operating System :: Microsoft :: Windows
Requires-Python: >=3.13,<3.14
"""

WHEEL = f"""\
Wheel-Version: 1.0
Generator: winjax build_wheel.py
Root-Is-Purelib: false
Tag: {TAG}
"""


def _record_line(arcname: str, data: bytes) -> str:
    digest = base64.urlsafe_b64encode(
        hashlib.sha256(data).digest()).rstrip(b"=").decode()
    return f"{arcname},sha256={digest},{len(data)}"


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    src_dll = (sys.argv[1] if len(sys.argv) > 1 else
               os.path.join(here, "..", "..", "dist",
                            "pjrt_c_api_gpu_plugin.so"))
    dest_dir = (sys.argv[2] if len(sys.argv) > 2 else
                os.path.join(here, "..", "dist"))
    os.makedirs(dest_dir, exist_ok=True)

    with open(os.path.join(here, NAME, "__init__.py"), "rb") as f:
        init_py = f.read()
    print(f"reading {src_dll} ...")
    with open(src_dll, "rb") as f:
        dll = f.read()

    dist_info = f"{NAME}-{VERSION}.dist-info"
    entries = [
        (f"{NAME}/__init__.py", init_py),
        (f"{NAME}/pjrt_c_api_gpu_plugin.dll", dll),
        (f"{dist_info}/METADATA", METADATA.encode()),
        (f"{dist_info}/WHEEL", WHEEL.encode()),
    ]
    record_lines = [_record_line(name, data) for name, data in entries]
    record_lines.append(f"{dist_info}/RECORD,,")
    record = ("\n".join(record_lines) + "\n").encode()

    wheel_path = os.path.join(dest_dir, f"{NAME}-{VERSION}-{TAG}.whl")
    with zipfile.ZipFile(wheel_path, "w", zipfile.ZIP_DEFLATED,
                         compresslevel=9) as zf:
        for name, data in entries:
            zf.writestr(name, data)
        zf.writestr(f"{dist_info}/RECORD", record)

    size = os.path.getsize(wheel_path)
    print(f"wrote {wheel_path}")
    print(f"compressed size: {size} bytes ({size / 1e6:.1f} MB)")
    if size > 100 * 1024 * 1024:
        print("WARNING: exceeds the 100 MB TestPyPI/PyPI default limit!")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
