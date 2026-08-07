"""Re-version the cp314 kernels wheel as 0.11.0.post1 with a post-tolerant
pjrt pin (==0.11.0.*), for TestPyPI immutability reasons."""
import os
import shutil
import subprocess
import sys

SRC = r"C:\Users\oleg\winjax\packaging\dist\winjax_cuda13_plugin-0.11.0-cp314-cp314-win_amd64.whl"
WORK = r"C:\Users\oleg\winjax\packaging\repack_tmp"
PY = sys.executable

shutil.rmtree(WORK, ignore_errors=True)
os.makedirs(WORK)
subprocess.run([PY, "-m", "wheel", "unpack", SRC, "-d", WORK], check=True)
tree = os.path.join(WORK, "winjax_cuda13_plugin-0.11.0")
old_info = os.path.join(tree, "winjax_cuda13_plugin-0.11.0.dist-info")
new_tree = os.path.join(WORK, "winjax_cuda13_plugin-0.11.0.post1")
new_info = os.path.join(tree, "winjax_cuda13_plugin-0.11.0.post1.dist-info")

meta = os.path.join(old_info, "METADATA")
with open(meta, encoding="utf-8") as f:
    text = f.read()
text = text.replace("Version: 0.11.0\n", "Version: 0.11.0.post1\n")
text = text.replace("Requires-Dist: winjax-cuda13-pjrt==0.11.0",
                    "Requires-Dist: winjax-cuda13-pjrt==0.11.0.*")
with open(meta, "w", encoding="utf-8", newline="\n") as f:
    f.write(text)
os.rename(old_info, new_info)
os.rename(tree, new_tree)
subprocess.run([PY, "-m", "wheel", "pack", new_tree, "-d",
                r"C:\Users\oleg\winjax\packaging\dist"], check=True)
print("done")
