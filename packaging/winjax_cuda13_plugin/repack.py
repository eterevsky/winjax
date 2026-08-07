r"""Repacks the self-built jax_cuda13_plugin wheel as winjax-cuda13-plugin.

The DISTRIBUTION is renamed (jax-cuda13-plugin -> winjax-cuda13-plugin) so it
can be published without colliding with the upstream project, but the
top-level MODULE stays jax_cuda13_plugin — jax/jaxlib discover the kernel
extensions by that import name.

Changes made:
  * dist-info dir + METADATA Name: renamed
  * Requires-Dist: jax-cuda13-pjrt==X -> winjax-cuda13-pjrt==X
  * jax_cuda13_plugin/__init__.py: the nvidia pip-wheel DLL-dir glob is
    widened to cover the CUDA 13 Windows layout (nvidia/cu13/bin/x86_64)
    so importing e.g. _versions works without a local CUDA toolkit.

Usage: python repack.py [input.whl] [dest_dir]
Defaults: ..\..\dist\jax_cuda13_plugin-0.11.0-cp313-cp313-win_amd64.whl,
          dest ..\dist
"""

import glob
import os
import shutil
import subprocess
import sys

OLD_DIST = "jax_cuda13_plugin"
NEW_DIST = "winjax_cuda13_plugin"
VERSION = "0.11.0"

OLD_GLOB_LINE = (
    '  dirs += sorted(_glob.glob(_os.path.join(site_dir, "nvidia", "*", '
    '"bin")))\n')
NEW_GLOB_LINES = (
    '  _nv = _os.path.join(site_dir, "nvidia")\n'
    '  for _pat in ("*/bin", "*/bin/x86_64", "*/*/bin", "*/*/bin/x86_64"):\n'
    '    dirs += sorted(_glob.glob(_os.path.join(_nv, _pat)))\n')


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    src_whl = (sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        here, "..", "..", "dist",
        f"{OLD_DIST}-{VERSION}-cp313-cp313-win_amd64.whl"))
    dest_dir = (sys.argv[2] if len(sys.argv) > 2 else
                os.path.join(here, "..", "dist"))
    os.makedirs(dest_dir, exist_ok=True)
    build_dir = os.path.join(here, "build")
    shutil.rmtree(build_dir, ignore_errors=True)
    os.makedirs(build_dir)

    subprocess.run([sys.executable, "-m", "wheel", "unpack", src_whl,
                    "--dest", build_dir], check=True)
    tree = os.path.join(build_dir, f"{OLD_DIST}-{VERSION}")
    assert os.path.isdir(tree), tree

    # 1. Rename dist-info dir.
    old_di = os.path.join(tree, f"{OLD_DIST}-{VERSION}.dist-info")
    new_di = os.path.join(tree, f"{NEW_DIST}-{VERSION}.dist-info")
    os.rename(old_di, new_di)

    # 2. Patch METADATA: distribution name + pjrt dependency.
    md_path = os.path.join(new_di, "METADATA")
    with open(md_path, encoding="utf-8") as f:
        md = f.read()
    assert "Name: jax-cuda13-plugin\n" in md
    md = md.replace("Name: jax-cuda13-plugin\n",
                    "Name: winjax-cuda13-plugin\n", 1)
    assert f"Requires-Dist: jax-cuda13-pjrt=={VERSION}\n" in md
    md = md.replace(f"Requires-Dist: jax-cuda13-pjrt=={VERSION}\n",
                    f"Requires-Dist: winjax-cuda13-pjrt=={VERSION}\n", 1)
    with open(md_path, "w", encoding="utf-8", newline="") as f:
        f.write(md)

    # 3. Widen the nvidia DLL-dir glob in the package __init__.py.
    init_path = os.path.join(tree, OLD_DIST, "__init__.py")
    with open(init_path, encoding="utf-8") as f:
        init = f.read()
    assert OLD_GLOB_LINE in init, "expected glob line not found in __init__.py"
    init = init.replace(OLD_GLOB_LINE, NEW_GLOB_LINES, 1)
    with open(init_path, "w", encoding="utf-8", newline="") as f:
        f.write(init)

    # 4. Rename the tree and pack (wheel pack regenerates RECORD).
    new_tree = os.path.join(build_dir, f"{NEW_DIST}-{VERSION}")
    os.rename(tree, new_tree)
    subprocess.run([sys.executable, "-m", "wheel", "pack", new_tree,
                    "--dest-dir", dest_dir], check=True)

    out = glob.glob(os.path.join(dest_dir, f"{NEW_DIST}-{VERSION}-*.whl"))
    assert out, "packed wheel not found"
    print("wrote", out[0])
    print("compressed size:", os.path.getsize(out[0]), "bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
