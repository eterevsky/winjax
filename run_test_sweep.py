"""Crash-tolerant JAX test sweep on the winjax GPU backend.

Runs each test file in its own pytest process so a native crash in one file
doesn't kill the sweep. Writes per-file logs to test_logs/ and a summary tally
to test_logs/SUMMARY.txt.
"""
import glob
import os
import re
import subprocess
import sys
import time

JAX = r"C:\Users\oleg\winjax\jax"
PY = r"C:\Users\oleg\winjax\.venv\Scripts\python.exe"
LOGS = r"C:\Users\oleg\winjax\test_logs"
PER_FILE_TIMEOUT = 100 * 60  # seconds

# Multi-process / multi-GPU / distributed / mock-GPU / mosaic (not in the
# Windows wheel) test files are out of scope for the single-GPU sweep.
# Single-device pmap/shard_map/pjit ARE in scope.
EXCLUDE = {
    "distributed_initialize_test.py",  # requires jax.distributed multi-process
    "distributed_test.py",             # multi-process distributed service
    "fused_attention_stablehlo_multigpu_test.py",  # needs >= 2 GPUs
    "mock_gpu_test.py",                # mock multi-GPU topology
    "mock_gpu_topology_test.py",       # mock multi-GPU topology
    "mosaic_test.py",                  # mosaic excluded from Windows wheel
    "multi_device_test.py",            # requires multiple devices
    "multiprocess_gpu_test.py",        # multi-process GPU
    "pgle_test.py",                    # profile-guided latency estimation, multi-GPU
}

FILES = sorted(
    "tests/" + os.path.basename(p)
    for p in glob.glob(os.path.join(JAX, "tests", "*_test.py"))
    if os.path.basename(p) not in EXCLUDE
)

os.makedirs(LOGS, exist_ok=True)
env = dict(os.environ)
env["CUDA_ROOT"] = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.3"
# Note: JAX_PLATFORMS is deliberately NOT set: forcing "cuda" hides the CPU
# backend, which some tests legitimately need (causes false failures).

TALLY_RE = re.compile(r"(\d+) (passed|failed|skipped|error|errors|xfailed|xpassed)")

only = sys.argv[1:]  # optional: run just the named files (basenames)
if only:
    FILES = [f for f in FILES if os.path.basename(f) in only]

summary = []
for f in FILES:
    name = os.path.basename(f).replace(".py", "")
    log = os.path.join(LOGS, name + ".log")
    t0 = time.time()
    timed_out = False
    with open(log, "w", encoding="utf-8") as out:
        try:
            proc = subprocess.run(
                [PY, "-m", "pytest", f, "-q", "--no-header",
                 "-p", "no:cacheprovider"],
                cwd=JAX, env=env, stdout=out, stderr=subprocess.STDOUT,
                timeout=PER_FILE_TIMEOUT)
            rc = proc.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            rc = -1
    mins = (time.time() - t0) / 60
    tail = open(log, encoding="utf-8", errors="replace").read()[-3000:]
    counts = dict((k, int(v)) for v, k in TALLY_RE.findall(tail))
    crashed = rc not in (0, 1, 5) and not timed_out  # 5 = no tests collected
    line = (f"{name}: exit={rc}"
            f"{' CRASH' if crashed else ''}{' TIMEOUT' if timed_out else ''} "
            f"{counts} [{mins:.1f} min]")
    summary.append(line)
    with open(os.path.join(LOGS, "SUMMARY.txt"), "w", encoding="utf-8") as s:
        s.write("\n".join(summary) + "\n")
    print(line, flush=True)

print("SWEEP DONE")
