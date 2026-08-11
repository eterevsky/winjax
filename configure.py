#!/usr/bin/env python3
r"""winjax machine configuration.

Probes this machine for the toolchain (MSVC, Windows SDK, LLVM/clang-cl, CUDA
toolkit, MSYS2, Python, GPU arch) and generates every machine-specific file
the winjax build needs:

  toolchains/local_config_cc/       BUILD, winjax_cl.bat, get_env.bat,
                                    llvm_bin_path.txt, vc_installation_error_*.bat,
                                    builtin_include_directory_paths_mingw
                                    (rendered from toolchains/templates/local_config_cc/)
  toolchains/local_config_cuda_win/ cuda/cuda/cuda_config.h, cuda_config.py
  toolchains/winjax_cuda.bazelrc    override-repository paths for this checkout
  toolchains/cccl_patched/          copy of <CUDA>/include/cccl + patches/cccl/*.patch
  toolchains/cudnn/                 nvidia-cudnn wheel unpacked + generated .lib
                                    import libraries (dumpbin/lib from MSVC)
  toolchains/cuda_repos/*/          NTFS junctions into the CUDA toolkit /
                                    cccl_patched / the cudnn wheel
  toolchains/winjax_env.bat         convenience: sets BAZEL_SH for builds

Then, if jax/ and xla/ checkouts exist next to this script, verifies the
result with an analysis-only Bazel build (no compilation).

--patch-externals additionally materializes the Bazel external repositories
(fetch via `bazel build --nobuild`) and applies the Windows-port patch series
from patches/<repo>/ into <output_base>/external/<repo>/. Bazel keeps
external repos until their definition changes or the output base is expunged;
re-run `configure.py --patch-externals` after `bazel clean --expunge` or an
XLA pin change.

Usage:
  python configure.py                     # generate + smoke-check
  python configure.py --patch-externals   # generate + fetch + patch externals
  python configure.py --skip-smoke        # generate only

All locations can be overridden; see --help.
"""

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
TOOLCHAINS = os.path.join(ROOT, "toolchains")
TEMPLATES = os.path.join(TOOLCHAINS, "templates")
PATCHES = os.path.join(ROOT, "patches")

CUDNN_LIB_PAIRS = [
    ("cudnn64_9.dll", "cudnn.lib"),
    ("cudnn_ops64_9.dll", "cudnn_ops.lib"),
    ("cudnn_cnn64_9.dll", "cudnn_cnn.lib"),
    ("cudnn_adv64_9.dll", "cudnn_adv.lib"),
    ("cudnn_graph64_9.dll", "cudnn_graph.lib"),
    ("cudnn_engines_precompiled64_9.dll", "cudnn_engines_precompiled.lib"),
    ("cudnn_engines_runtime_compiled64_9.dll",
     "cudnn_engines_runtime_compiled.lib"),
    ("cudnn_heuristic64_9.dll", "cudnn_heuristic.lib"),
]

# External repos with a patches/<repo>/windows-port.patch applied into the
# Bazel-materialized tree (--patch-externals). local_config_rocm is a
# full-file override handled separately; patches/jax applies to the jax
# checkout itself (done once at clone time, see BUILDING.md).
EXTERNAL_PATCH_REPOS = [
    "com_google_absl",
    "com_google_protobuf",
    "eigen_archive",
    "raft",
    "rapids_logger",
    "rmm",
    "triton",
]


def info(msg):
    print(f"[configure] {msg}")


def die(msg):
    print(f"[configure] ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def run(cmd, **kw):
    kw.setdefault("capture_output", True)
    kw.setdefault("text", True)
    return subprocess.run(cmd, **kw)


def fwd(p):
    """Forward-slash form of a path."""
    return p.replace("\\", "/")


def bs2(p):
    """Backslash form with backslashes doubled (for Starlark string literals)."""
    return p.replace("/", "\\").replace("\\", "\\\\")


# ---------------------------------------------------------------------------
# Probing
# ---------------------------------------------------------------------------

def find_vs(args):
    """Locate Visual Studio, the MSVC tools dir and vcvarsall.bat."""
    vs_root = args.vs_path
    if not vs_root:
        vswhere = os.path.join(
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
            "Microsoft Visual Studio", "Installer", "vswhere.exe")
        if os.path.exists(vswhere):
            base = [vswhere, "-products", "*", "-requires",
                    "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                    "-property", "installationPath"]
            # Prefer VS2022 (17.x, MSVC v143) — the toolset winjax is
            # validated against; fall back to whatever is newest.
            r = run(base + ["-version", "[17.0,18.0)", "-latest"])
            if r.returncode == 0 and r.stdout.strip():
                vs_root = r.stdout.strip().splitlines()[0].strip()
            else:
                r = run(base + ["-latest"])
                if r.returncode == 0 and r.stdout.strip():
                    vs_root = r.stdout.strip().splitlines()[0].strip()
                    info(f"WARNING: no VS2022 (17.x) found; using {vs_root} "
                         "— winjax is only validated against VS2022 / "
                         "MSVC 14.4x")
    if not vs_root and os.environ.get("BAZEL_VC"):
        # BAZEL_VC points at <VS>\VC
        vs_root = os.path.dirname(os.environ["BAZEL_VC"].rstrip("\\/"))
    if not vs_root:
        die("Visual Studio 2022 with the 'Desktop development with C++' "
            "workload not found (vswhere probe failed). Install it, or pass "
            "--vs-path <VS installation dir>.")
    vc_root = os.path.join(vs_root, "VC")
    ver_file = os.path.join(vc_root, "Auxiliary", "Build",
                            "Microsoft.VCToolsVersion.default.txt")
    if not os.path.exists(ver_file):
        die(f"MSVC build tools not found under {vc_root} (missing "
            f"{ver_file}). Install the C++ workload (MSVC v143 + Windows SDK).")
    with open(ver_file, encoding="utf-8-sig") as f:
        vc_ver = f.read().strip()
    msvc_dir = os.path.join(vc_root, "Tools", "MSVC", vc_ver)
    cl = os.path.join(msvc_dir, "bin", "HostX64", "x64", "cl.exe")
    if not os.path.exists(cl):
        die(f"cl.exe not found at {cl}; broken MSVC installation?")
    vcvarsall = os.path.join(vc_root, "Auxiliary", "Build", "vcvarsall.bat")
    info(f"Visual Studio : {vs_root}")
    info(f"MSVC tools    : {vc_ver}")
    return {"vs_root": vs_root, "vc_root": vc_root, "vc_ver": vc_ver,
            "msvc_dir": msvc_dir, "vcvarsall": vcvarsall}


def capture_vcvars(vs, arch):
    """Run vcvarsall.bat for `arch` and capture PATH/INCLUDE/LIB etc.

    PATH is seeded minimal so the captured value contains only the
    vcvars-provided entries plus system dirs (mirrors what Bazel's
    cc_configure records).
    """
    env = os.environ.copy()
    env["PATH"] = r"C:\Windows\system32;C:\Windows;C:\Windows\System32\Wbem"
    env.pop("INCLUDE", None)
    env.pop("LIB", None)
    import tempfile
    fd, bat = tempfile.mkstemp(suffix=".bat", prefix="winjax_vcvars_")
    try:
        with os.fdopen(fd, "w", encoding="ascii", newline="\r\n") as f:
            f.write("@echo off\n")
            f.write(f'call "{vs["vcvarsall"]}" {arch} '
                    f'-vcvars_ver={vs["vc_ver"]} >nul\n')
            f.write("if errorlevel 1 exit /b 1\n")
            f.write("set\n")
        r = run(["cmd", "/d", "/c", bat], env=env)
    finally:
        os.unlink(bat)
    if r.returncode != 0:
        die(f"vcvarsall.bat {arch} failed:\n{r.stdout}\n{r.stderr}")
    cap = {}
    for line in r.stdout.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            cap[k.upper()] = v
    for key in ("PATH", "INCLUDE", "LIB", "WINDOWSSDKDIR"):
        if not cap.get(key):
            die(f"vcvarsall.bat {arch} did not set {key}. Is the Windows "
                "SDK installed (VS installer component)?")
    return cap


def find_llvm(args):
    """Locate LLVM (clang-cl / clang / lld-link / llvm-lib), require >= 19."""
    candidates = []
    if args.llvm_dir:
        candidates.append(args.llvm_dir)
    if os.environ.get("LLVM_DIR"):
        candidates.append(os.environ["LLVM_DIR"])
    if os.environ.get("BAZEL_LLVM"):
        candidates.append(os.environ["BAZEL_LLVM"])
    candidates += sorted(glob.glob(os.path.join(ROOT, "tools", "llvm*")),
                         reverse=True)
    candidates.append(r"C:\Program Files\LLVM")
    clang_on_path = shutil.which("clang-cl")
    if clang_on_path:
        candidates.append(os.path.dirname(os.path.dirname(clang_on_path)))

    for cand in candidates:
        clang = os.path.join(cand, "bin", "clang.exe")
        if not os.path.exists(clang):
            continue
        r = run([clang, "--version"])
        m = re.search(r"clang version (\d+)\.(\d+)\.(\d+)", r.stdout)
        if not m:
            continue
        major = int(m.group(1))
        if major < 19:
            info(f"skipping LLVM at {cand}: clang {m.group(0)} is too old")
            continue
        rr = run([clang, "--print-resource-dir"])
        resource_dir = rr.stdout.strip() if rr.returncode == 0 else \
            os.path.join(cand, "lib", "clang", str(major))
        for tool in ("clang-cl.exe", "clang++.exe", "lld-link.exe",
                     "llvm-lib.exe"):
            if not os.path.exists(os.path.join(cand, "bin", tool)):
                die(f"LLVM at {cand} is missing bin\\{tool}")
        info(f"LLVM          : {cand} (clang {m.group(1)}.{m.group(2)}."
             f"{m.group(3)})")
        return {"root": cand, "bin": os.path.join(cand, "bin"),
                "major": major, "resource_dir": resource_dir}
    die("LLVM with clang >= 19 not found. clang 18 and older cannot compile "
        "against the MSVC 14.4x STL (STL1000). Install LLVM >= 19 (e.g. into "
        "tools\\llvm22) and/or pass --llvm-dir or set LLVM_DIR.")


def find_cuda(args):
    """Locate a CUDA >= 13.0 toolkit."""
    candidates = []
    if args.cuda_path:
        candidates.append(args.cuda_path)
    for e in ("CUDA_PATH", "CUDA_ROOT", "CUDA_HOME"):
        if os.environ.get(e):
            candidates.append(os.environ[e])
    std = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA"
    if os.path.isdir(std):
        candidates += sorted(glob.glob(os.path.join(std, "v*")), reverse=True)
    for cand in candidates:
        if not os.path.exists(os.path.join(cand, "include", "cuda.h")):
            continue
        version = None
        vj = os.path.join(cand, "version.json")
        if os.path.exists(vj):
            import json
            try:
                with open(vj, encoding="utf-8") as f:
                    data = json.load(f)
                version = data.get("cuda", {}).get("version")
            except (OSError, ValueError):
                pass
        if not version:
            m = re.search(r"v(\d+\.\d+)", os.path.basename(cand.rstrip("\\/")))
            version = m.group(1) if m else None
        if not version:
            continue
        major, minor = (int(x) for x in version.split(".")[:2])
        if major < 13:
            info(f"skipping CUDA at {cand}: version {version} < 13.0")
            continue
        if not os.path.isdir(os.path.join(cand, "include", "cccl")):
            die(f"CUDA toolkit at {cand} has no include\\cccl directory; "
                "winjax requires the CUDA 13.x toolkit layout.")
        info(f"CUDA toolkit  : {cand} (version {version})")
        return {"root": cand, "version": f"{major}.{minor}"}
    die("CUDA toolkit >= 13.0 not found. Install it (default location "
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.x) or pass "
        "--cuda-path / set CUDA_PATH.")


def find_msys2(args):
    """Locate MSYS2 (usr\\bin\\bash.exe) — required as Bazel's BAZEL_SH."""
    candidates = []
    if args.msys2:
        candidates.append(args.msys2)
    if os.environ.get("BAZEL_SH"):
        # BAZEL_SH = <msys>\usr\bin\bash.exe
        candidates.append(os.path.dirname(os.path.dirname(
            os.path.dirname(os.environ["BAZEL_SH"]))))
    candidates.append(os.path.join(ROOT, "tools", "msys64"))
    candidates.append(r"C:\msys64")
    bash_on_path = shutil.which("bash")
    if bash_on_path and "msys" in bash_on_path.lower():
        candidates.append(os.path.dirname(os.path.dirname(
            os.path.dirname(bash_on_path))))
    for cand in candidates:
        bash = os.path.join(cand, "usr", "bin", "bash.exe")
        if os.path.exists(bash):
            info(f"MSYS2         : {cand}")
            return {"root": cand, "bash": bash}
    die("MSYS2 not found (need usr\\bin\\bash.exe for Bazel's BAZEL_SH). "
        "Install MSYS2 (e.g. into tools\\msys64 or C:\\msys64), run "
        "'pacman -S patch', and/or pass --msys2.")


def find_bazel(args):
    for cand in ([args.bazel] if args.bazel else []) + \
            [os.environ.get("BAZEL", ""),
             os.path.join(ROOT, "tools", "bazel.exe"),
             shutil.which("bazel") or "", shutil.which("bazelisk") or ""]:
        if cand and os.path.exists(cand):
            info(f"Bazel         : {cand}")
            return cand
    info("Bazel         : NOT FOUND (smoke check and --patch-externals "
         "unavailable; install Bazelisk as tools\\bazel.exe)")
    return None


def detect_gpu_archs(args):
    """CUDA compute capabilities of the local GPU(s), as ["sm_120", ...]."""
    if args.cuda_archs:
        archs = [a.strip() for a in args.cuda_archs.split(",") if a.strip()]
        info(f"GPU archs     : {', '.join(archs)} (from --cuda-archs)")
        return archs
    smi = shutil.which("nvidia-smi") or \
        r"C:\Windows\System32\nvidia-smi.exe"
    if os.path.exists(smi):
        r = run([smi, "--query-gpu=compute_cap", "--format=csv,noheader"])
        if r.returncode == 0:
            archs = []
            for line in r.stdout.splitlines():
                line = line.strip()
                m = re.match(r"(\d+)\.(\d+)$", line)
                if m:
                    a = f"sm_{m.group(1)}{m.group(2)}"
                    if a not in archs:
                        archs.append(a)
            if archs:
                info(f"GPU archs     : {', '.join(archs)} (nvidia-smi)")
                return archs
    die("Could not detect the GPU compute capability via nvidia-smi. "
        "Is an NVIDIA driver installed? Otherwise pass e.g. "
        "--cuda-archs=sm_120.")


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def render(template, out, subs, newline="\n"):
    with open(template, encoding="utf-8") as f:
        text = f.read()
    for k, v in subs.items():
        text = text.replace(k, v)
    leftover = re.findall(r"@@[A-Z0-9_]+@@", text)
    if leftover:
        die(f"unsubstituted placeholders {sorted(set(leftover))} rendering "
            f"{template}")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline=newline) as f:
        f.write(text)
    info(f"wrote {os.path.relpath(out, ROOT)}")


def starlark_dir_list(dirs):
    """Render a cxx_builtin_include_directories list body."""
    entries = [f'"{bs2(d)}"' for d in dirs]
    return ("\n        " + ",\n        ".join(entries)) if entries else ""


def split_include(cap):
    return [d for d in cap["INCLUDE"].split(";") if d.strip()]


def gen_local_config_cc(vs, cap64, cap86, llvm, cuda, msys, python_exe):
    tpl_dir = os.path.join(TEMPLATES, "local_config_cc")
    out_dir = os.path.join(TOOLCHAINS, "local_config_cc")
    tmp = (os.environ.get("TEMP") or os.environ.get("TMP") or
           r"C:\Windows\Temp").rstrip("\\/")
    clang_inc = os.path.join(llvm["resource_dir"], "include")
    clang_lib = os.path.join(llvm["resource_dir"], "lib", "windows")
    msvc_bin64 = fwd(os.path.join(vs["msvc_dir"], "bin", "HostX64", "x64"))
    msvc_bin86 = fwd(os.path.join(vs["msvc_dir"], "bin", "HostX64", "x86"))
    wrapper_bat = fwd(os.path.join(out_dir, "winjax_cl.bat"))
    msys_lc = fwd(msys["root"]).lower()

    include64 = split_include(cap64)
    clang_cl_builtin = (
        [os.path.join(cuda["root"], "include"),
         os.path.join(cuda["root"], "include", "cccl"),
         os.path.join(TOOLCHAINS, "cccl_patched")]
        + include64 + [clang_inc])

    subs = {
        "@@MSVC_ENV_TMP_BS@@": bs2(tmp),
        "@@MSVC_ENV_PATH_X64_BS@@": bs2(cap64["PATH"]),
        "@@MSVC_ENV_INCLUDE_X64_BS@@": bs2(cap64["INCLUDE"]),
        "@@MSVC_ENV_LIB_X64_BS@@": bs2(cap64["LIB"]),
        "@@MSVC_ENV_PATH_X86_BS@@": bs2(cap86["PATH"]),
        "@@MSVC_ENV_INCLUDE_X86_BS@@": bs2(cap86["INCLUDE"]),
        "@@MSVC_ENV_LIB_X86_BS@@": bs2(cap86["LIB"]),
        "@@MSVC_BIN_X64_FWD@@": msvc_bin64,
        "@@MSVC_BIN_X86_FWD@@": msvc_bin86,
        "@@MSVC_BUILTIN_DIRS_X64@@": starlark_dir_list(include64),
        "@@MSVC_BUILTIN_DIRS_X86@@": starlark_dir_list(split_include(cap86)),
        "@@CLANG_CL_ENV_INCLUDE_BS@@": bs2(cap64["INCLUDE"] + ";" + clang_inc),
        "@@CLANG_CL_ENV_LIB_X64_BS@@": bs2(cap64["LIB"] + ";" + clang_lib),
        "@@CLANG_CL_BUILTIN_DIRS@@": starlark_dir_list(clang_cl_builtin),
        "@@WINJAX_CL_BAT_FWD@@": wrapper_bat,
        "@@LLVM_BIN_FWD@@": fwd(llvm["bin"]),
        "@@MSYS_ROOT_FWD@@": msys_lc,
    }
    render(os.path.join(tpl_dir, "BUILD.tpl"),
           os.path.join(out_dir, "BUILD"), subs)
    render(os.path.join(tpl_dir, "builtin_include_directory_paths_mingw.tpl"),
           os.path.join(out_dir, "builtin_include_directory_paths_mingw"),
           subs)
    render(os.path.join(tpl_dir, "winjax_cl.bat.tpl"),
           os.path.join(out_dir, "winjax_cl.bat"),
           {"@@PYTHON_EXE@@": python_exe,
            "@@WRAPPER_PY@@": os.path.join(out_dir, "winjax_cc_wrapper.py")},
           newline="\r\n")
    render(os.path.join(tpl_dir, "get_env.bat.tpl"),
           os.path.join(out_dir, "get_env.bat"),
           {"@@VCVARSALL_BAT@@": vs["vcvarsall"],
            "@@VC_TOOLS_VERSION@@": vs["vc_ver"]},
           newline="\r\n")
    for bat in ("vc_installation_error_arm.bat",
                "vc_installation_error_arm64.bat"):
        render(os.path.join(tpl_dir, bat + ".tpl"),
               os.path.join(out_dir, bat),
               {"@@VC_ROOT_BS@@": vs["vc_root"]}, newline="\r\n")


def gen_llvm_bin_path(llvm, cuda, archs):
    out = os.path.join(TOOLCHAINS, "local_config_cc", "llvm_bin_path.txt")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(llvm["bin"] + "\n")
        f.write(cuda["root"] + "\n")
        f.write(",".join(archs) + "\n")
        f.write(os.path.join(TOOLCHAINS, "cccl_patched") + "\n")
    info(f"wrote {os.path.relpath(out, ROOT)}")


def gen_local_config_cuda_win(cuda, cudnn_major, archs):
    tpl_dir = os.path.join(TEMPLATES, "local_config_cuda_win")
    out_dir = os.path.join(TOOLCHAINS, "local_config_cuda_win", "cuda", "cuda")
    caps_h = ",".join(a.replace("sm_", "") for a in archs)
    caps_py = ", ".join(f'"{a}"' for a in archs)
    subs = {
        "@@CUDA_VERSION@@": cuda["version"],
        "@@CUDNN_MAJOR@@": cudnn_major,
        "@@CUDA_TOOLKIT_PATH_FWD@@": fwd(cuda["root"]),
        "@@COMPUTE_CAPABILITIES_H@@": caps_h,
        "@@COMPUTE_CAPABILITIES_PY@@": caps_py,
    }
    render(os.path.join(tpl_dir, "cuda_config.h.tpl"),
           os.path.join(out_dir, "cuda_config.h"), subs)
    render(os.path.join(tpl_dir, "cuda_config.py.tpl"),
           os.path.join(out_dir, "cuda_config.py"), subs)


def gen_bazelrc(xla_dir):
    render(os.path.join(TEMPLATES, "winjax_cuda.bazelrc.tpl"),
           os.path.join(TOOLCHAINS, "winjax_cuda.bazelrc"),
           {"@@REPO_FWD@@": fwd(ROOT), "@@XLA_DIR_FWD@@": fwd(xla_dir)})


def gen_env_bat(msys):
    out = os.path.join(TOOLCHAINS, "winjax_env.bat")
    with open(out, "w", encoding="utf-8", newline="\r\n") as f:
        f.write("@echo off\n")
        f.write(f'set "BAZEL_SH={msys["bash"]}"\n')
    info(f"wrote {os.path.relpath(out, ROOT)}")


# ---------------------------------------------------------------------------
# CCCL patched copy
# ---------------------------------------------------------------------------

def _rmtree_force(path):
    def onerror(func, p, _exc):
        os.chmod(p, 0o700)
        func(p)
    shutil.rmtree(path, onerror=onerror)


def cccl_patch_files():
    return sorted(glob.glob(os.path.join(PATCHES, "cccl", "*.patch")))


def git_apply(cwd, patch, extra=()):
    return run(["git", "apply", "-p1", "--whitespace=nowarn", *extra, patch],
               cwd=cwd)


def build_cccl_patched(cuda, force):
    src = os.path.join(cuda["root"], "include", "cccl")
    dst = os.path.join(TOOLCHAINS, "cccl_patched")
    patches = cccl_patch_files()
    if not patches:
        die(f"no patches found in {os.path.join(PATCHES, 'cccl')}")
    if os.path.isdir(dst) and not force:
        ok = all(git_apply(dst, p, ("--reverse", "--check")).returncode == 0
                 for p in patches)
        if ok:
            info("cccl_patched  : up to date (patches verified applied)")
            return
        info("cccl_patched  : exists but stale/unpatched; rebuilding")
    if os.path.isdir(dst):
        _rmtree_force(dst)
    info(f"copying {src} -> {os.path.relpath(dst, ROOT)}")
    shutil.copytree(src, dst)
    for p in patches:
        r = git_apply(dst, p)
        if r.returncode != 0:
            die(f"failed to apply {os.path.basename(p)} to cccl_patched "
                f"(toolkit CCCL headers drifted from 13.3?):\n{r.stderr}")
        info(f"applied {os.path.relpath(p, ROOT)}")


# ---------------------------------------------------------------------------
# cuDNN import libraries from the nvidia-cudnn wheel
# ---------------------------------------------------------------------------

def _dumpbin_exports(dumpbin, dll_path):
    out = run([dumpbin, "/exports", dll_path]).stdout
    names, in_table = [], False
    for line in out.splitlines():
        parts = line.split()
        if "ordinal" in line and "name" in line:
            in_table = True
            continue
        if in_table:
            if line.strip().startswith("Summary"):
                break
            if len(parts) >= 4 and parts[0].isdigit():
                names.append(parts[3])
            elif len(parts) == 3 and parts[0].isdigit():
                names.append(parts[2])
    return names


def gen_cudnn(vs, args, force):
    cudnn_root = os.path.join(TOOLCHAINS, "cudnn")
    unpacked = os.path.join(cudnn_root, "unpacked")
    pkg = os.path.join(unpacked, "nvidia", "cudnn")
    lib_dir = os.path.join(pkg, "lib")
    os.makedirs(cudnn_root, exist_ok=True)

    have_all_libs = all(os.path.exists(os.path.join(lib_dir, libname))
                        for _, libname in CUDNN_LIB_PAIRS)
    if have_all_libs and os.path.exists(
            os.path.join(pkg, "include", "cudnn.h")) and not force:
        info("cudnn         : import libs up to date")
        return _cudnn_major(pkg)

    wheel = args.cudnn_wheel
    if not wheel:
        wheels = sorted(glob.glob(os.path.join(
            cudnn_root, "nvidia_cudnn*-win_amd64.whl")))
        wheel = wheels[-1] if wheels else None
    if not wheel:
        info("downloading nvidia-cudnn-cu13 wheel via pip ...")
        r = run([sys.executable, "-m", "pip", "download", "nvidia-cudnn-cu13",
                 "--no-deps", "-d", cudnn_root])
        if r.returncode != 0:
            die("pip download nvidia-cudnn-cu13 failed (offline?). Download "
                "the win_amd64 wheel manually and pass --cudnn-wheel "
                f"<path>.\n{r.stderr[-2000:]}")
        wheels = sorted(glob.glob(os.path.join(
            cudnn_root, "nvidia_cudnn*-win_amd64.whl")))
        if not wheels:
            die("pip download succeeded but no nvidia_cudnn*-win_amd64.whl "
                f"found in {cudnn_root}")
        wheel = wheels[-1]
    info(f"cudnn wheel   : {os.path.basename(wheel)}")

    if not os.path.exists(os.path.join(pkg, "bin", CUDNN_LIB_PAIRS[0][0])) \
            or force:
        if os.path.isdir(unpacked):
            _rmtree_force(unpacked)
        info(f"unpacking wheel -> {os.path.relpath(unpacked, ROOT)}")
        with zipfile.ZipFile(wheel) as zf:
            zf.extractall(unpacked)

    msvc_bin = os.path.join(vs["msvc_dir"], "bin", "HostX64", "x64")
    dumpbin = os.path.join(msvc_bin, "dumpbin.exe")
    libexe = os.path.join(msvc_bin, "lib.exe")
    os.makedirs(lib_dir, exist_ok=True)
    for dll, libname in CUDNN_LIB_PAIRS:
        dll_path = os.path.join(pkg, "bin", dll)
        if not os.path.exists(dll_path):
            die(f"cuDNN DLL missing from wheel: {dll} (cuDNN major version "
                "changed? update CUDNN_LIB_PAIRS in configure.py)")
        syms = _dumpbin_exports(dumpbin, dll_path)
        if not syms:
            die(f"no exports parsed from {dll}")
        def_path = os.path.join(lib_dir, libname.replace(".lib", ".def"))
        with open(def_path, "w", encoding="ascii", newline="\r\n") as f:
            f.write(f"LIBRARY {dll}\nEXPORTS\n")
            for s in syms:
                f.write(f"    {s}\n")
        r = run([libexe, f"/def:{def_path}", "/machine:x64",
                 f"/out:{os.path.join(lib_dir, libname)}", "/nologo"])
        if r.returncode != 0:
            die(f"lib.exe failed for {libname}:\n{r.stdout}\n{r.stderr}")
        info(f"generated {libname} ({len(syms)} exports)")
    return _cudnn_major(pkg)


def _cudnn_major(pkg):
    hdr = os.path.join(pkg, "include", "cudnn_version.h")
    if os.path.exists(hdr):
        with open(hdr, encoding="utf-8", errors="replace") as f:
            m = re.search(r"#define\s+CUDNN_MAJOR\s+(\d+)", f.read())
        if m:
            return m.group(1)
    return "9"


# ---------------------------------------------------------------------------
# Junction farm for the cuda_repos override repositories
# ---------------------------------------------------------------------------

def junction_manifest(cuda):
    """repo -> {link (relative to the repo dir): target (absolute)}."""
    tk = cuda["root"]
    inc = os.path.join(tk, "include")
    lib = os.path.join(tk, "lib", "x64")
    cccl = os.path.join(TOOLCHAINS, "cccl_patched")
    cudnn = os.path.join(TOOLCHAINS, "cudnn", "unpacked", "nvidia", "cudnn")
    m = {}
    for repo in ("cuda_cublas", "cuda_cudart", "cuda_cufft", "cuda_curand",
                 "cuda_cusolver", "cuda_cusparse", "cuda_nvjitlink",
                 "cuda_nvml", "cuda_nvptxcompiler", "cuda_nvrtc"):
        m[repo] = {"include": inc, "lib": lib}
    m["cuda_nvtx"] = {"include": inc}
    m["cuda_profiler_api"] = {"include": inc}
    m["cuda_nvcc"] = {"bin": os.path.join(tk, "bin"), "include": inc,
                      "nvvm": os.path.join(tk, "nvvm")}
    m["cuda_nvdisasm"] = {"bin": os.path.join(tk, "bin")}
    m["cuda_nvvm"] = {"nvvm": os.path.join(tk, "nvvm")}
    m["cuda_crt"] = {os.path.join("include", "crt"):
                     os.path.join(inc, "crt")}
    m["cuda_cupti"] = {
        "include": os.path.join(tk, "extras", "CUPTI", "include"),
        "lib": os.path.join(tk, "extras", "CUPTI", "lib64")}
    m["cuda_cccl"] = {
        os.path.join("cub", "cub"): os.path.join(cccl, "cub"),
        os.path.join("libcudacxx", "include", "cuda"):
            os.path.join(cccl, "cuda"),
        os.path.join("libcudacxx", "include", "nv"): os.path.join(cccl, "nv"),
        os.path.join("thrust", "thrust"): os.path.join(cccl, "thrust")}
    m["cuda_cudnn"] = {"include": os.path.join(cudnn, "include"),
                       "lib": os.path.join(cudnn, "lib")}
    return m


def _junction_target(link):
    try:
        t = os.readlink(link)
    except OSError:
        return None
    return t[4:] if t.startswith("\\\\?\\") else t


def ensure_junction(link, target):
    if not os.path.isdir(target):
        die(f"junction target missing: {target}")
    if os.path.lexists(link):
        cur = _junction_target(link)
        if cur is not None:
            if os.path.normcase(os.path.normpath(cur)) == \
                    os.path.normcase(os.path.normpath(target)):
                return False
            os.rmdir(link)  # remove only the reparse point, never recurse
        elif os.path.isdir(link) and not os.listdir(link):
            os.rmdir(link)
        else:
            die(f"{link} exists and is not a junction/empty dir; remove it "
                "manually")
    os.makedirs(os.path.dirname(link), exist_ok=True)
    r = run(["cmd", "/d", "/c", "mklink", "/J", link, target])
    if r.returncode != 0:
        die(f"mklink /J failed for {link} -> {target}:\n{r.stdout}{r.stderr}")
    return True


def make_junctions(cuda):
    manifest = junction_manifest(cuda)
    created = 0
    for repo, links in sorted(manifest.items()):
        repo_dir = os.path.join(TOOLCHAINS, "cuda_repos", repo)
        if not os.path.isdir(repo_dir):
            die(f"missing override repo dir {repo_dir} (bad checkout?)")
        for rel, target in links.items():
            if ensure_junction(os.path.join(repo_dir, rel), target):
                created += 1
    info(f"junctions     : {created} created/updated, "
         f"{sum(len(v) for v in manifest.values())} total")


# ---------------------------------------------------------------------------
# Smoke check and external patches
# ---------------------------------------------------------------------------

def bazel_cmd(bazel):
    bazelrc = os.path.join(TOOLCHAINS, "winjax_cuda.bazelrc")
    return [bazel, f"--bazelrc={bazelrc}"]


def bazel_env(msys):
    env = os.environ.copy()
    env["BAZEL_SH"] = msys["bash"]
    return env


def check_jax_patch(jax_dir):
    patch = os.path.join(PATCHES, "jax", "windows-kernels-wheel.patch")
    if not os.path.exists(patch):
        return
    r = run(["git", "apply", "-p1", "--reverse", "--check", patch],
            cwd=jax_dir)
    if r.returncode != 0:
        info("WARNING: patches/jax/windows-kernels-wheel.patch does not "
             f"appear to be applied in {jax_dir}. The kernels wheel build "
             f"will fail. Apply it with:\n"
             f"    git -C {jax_dir} apply {patch}")


def run_fetch_analysis(bazel, jax_dir, msys, label):
    pyver = f"{sys.version_info.major}.{sys.version_info.minor}"
    cmd = bazel_cmd(bazel) + [
        "build", "--nobuild", "--config=win_clang", "--config=winjax_cuda",
        f"--repo_env=HERMETIC_PYTHON_VERSION={pyver}",
        "@xla//xla/pjrt/c:pjrt_c_api_gpu_plugin.so",
    ]
    info(f"{label}: {' '.join(cmd[2:])}")
    info("(first run downloads external repositories; this takes a while)")
    r = subprocess.run(cmd, cwd=jax_dir, env=bazel_env(msys))
    if r.returncode != 0:
        die(f"{label} failed (exit {r.returncode}). See Bazel output above.")
    info(f"{label}: PASSED")


def smoke(bazel, jax_dir, xla_dir, msys):
    if not os.path.exists(os.path.join(jax_dir, "WORKSPACE")) or \
            not os.path.exists(os.path.join(xla_dir, "WORKSPACE")):
        info("smoke check   : SKIPPED (jax/ and/or xla/ checkout not found; "
             "clone them as described in BUILDING.md, then re-run "
             "configure.py)")
        return False
    if not bazel:
        info("smoke check   : SKIPPED (bazel not found)")
        return False
    check_jax_patch(jax_dir)
    run_fetch_analysis(bazel, jax_dir, msys, "smoke (analysis-only build)")
    return True


def patch_externals(bazel, jax_dir, msys, fetched_already):
    if not bazel:
        die("--patch-externals requires Bazel (install Bazelisk as "
            "tools\\bazel.exe)")
    if not os.path.exists(os.path.join(jax_dir, "WORKSPACE")):
        die(f"--patch-externals requires the jax checkout at {jax_dir}")
    if not fetched_already:
        run_fetch_analysis(bazel, jax_dir, msys,
                           "fetch (materialize external repos)")
    r = run(bazel_cmd(bazel) + ["info", "output_base"], cwd=jax_dir,
            env=bazel_env(msys))
    if r.returncode != 0:
        die(f"bazel info output_base failed:\n{r.stderr}")
    output_base = r.stdout.strip().splitlines()[-1].strip()
    external = os.path.join(os.path.normpath(output_base), "external")
    info(f"output base   : {output_base}")

    for repo in EXTERNAL_PATCH_REPOS:
        repo_dir = os.path.join(external, repo)
        patch = os.path.join(PATCHES, repo, "windows-port.patch")
        if not os.path.exists(patch):
            die(f"missing patch file {patch}")
        if not os.path.isdir(repo_dir):
            die(f"external repo not materialized: {repo_dir} (fetch first)")
        if git_apply(repo_dir, patch, ("--reverse", "--check")).returncode == 0:
            info(f"external {repo}: already patched")
            continue
        chk = git_apply(repo_dir, patch, ("--check",))
        if chk.returncode != 0:
            die(f"patch does not apply cleanly to external/{repo} (upstream "
                f"archive changed?):\n{chk.stderr}")
        r = git_apply(repo_dir, patch)
        if r.returncode != 0:
            die(f"failed to apply patch to external/{repo}:\n{r.stderr}")
        info(f"external {repo}: patched")

    # local_config_rocm: machine-generated repo, full-file override.
    rocm_dst = os.path.join(external, "local_config_rocm", "rocm",
                            "build_defs.bzl")
    rocm_src = os.path.join(PATCHES, "local_config_rocm", "build_defs.bzl")
    if not os.path.exists(rocm_dst):
        die(f"external/local_config_rocm not materialized ({rocm_dst})")
    with open(rocm_dst, encoding="utf-8") as f:
        current = f.read()
    if "winjax" in current:
        info("external local_config_rocm: already overridden")
    else:
        shutil.copyfile(rocm_src, rocm_dst)
        info("external local_config_rocm: build_defs.bzl overridden")
    info("external patches: done. Re-run 'configure.py --patch-externals' "
         "after 'bazel clean --expunge' or an XLA pin change.")


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Probe this machine and generate winjax's "
                    "machine-specific toolchain files.")
    ap.add_argument("--vs-path", help="Visual Studio installation dir "
                    r"(default: vswhere; e.g. C:\Program Files\Microsoft "
                    r"Visual Studio\2022\Community)")
    ap.add_argument("--llvm-dir", help="LLVM install dir with bin\\clang.exe "
                    "(default: LLVM_DIR env, tools\\llvm*, C:\\Program "
                    "Files\\LLVM, PATH); clang >= 19 required")
    ap.add_argument("--cuda-path", help="CUDA >= 13.0 toolkit root "
                    "(default: CUDA_PATH env or standard install dir)")
    ap.add_argument("--msys2", help="MSYS2 root (default: BAZEL_SH env, "
                    "tools\\msys64, C:\\msys64)")
    ap.add_argument("--cuda-archs", help="comma-separated GPU archs, e.g. "
                    "sm_120 (default: detect via nvidia-smi)")
    ap.add_argument("--cudnn-wheel", help="path to a downloaded "
                    "nvidia_cudnn*-win_amd64.whl (default: reuse/pip "
                    "download into toolchains/cudnn/)")
    ap.add_argument("--jax-dir", default=os.path.join(ROOT, "jax"),
                    help="jax checkout (default: <repo>/jax)")
    ap.add_argument("--xla-dir", default=os.path.join(ROOT, "xla"),
                    help="xla checkout (default: <repo>/xla)")
    ap.add_argument("--bazel", help="bazel/bazelisk executable "
                    "(default: tools\\bazel.exe or PATH)")
    ap.add_argument("--patch-externals", action="store_true",
                    help="after generation, fetch Bazel external repos and "
                    "apply patches/<repo>/windows-port.patch into them")
    ap.add_argument("--skip-smoke", action="store_true",
                    help="skip the analysis-only Bazel verification build")
    ap.add_argument("--force", action="store_true",
                    help="rebuild cccl_patched and cudnn even if up to date")
    args = ap.parse_args()

    if os.name != "nt":
        die("configure.py must run on Windows")

    info(f"repo root     : {ROOT}")
    info(f"python        : {sys.executable} "
         f"({sys.version_info.major}.{sys.version_info.minor})")
    vs = find_vs(args)
    llvm = find_llvm(args)
    cuda = find_cuda(args)
    msys = find_msys2(args)
    bazel = find_bazel(args)
    archs = detect_gpu_archs(args)
    info("capturing MSVC environment (vcvarsall amd64 / amd64_x86) ...")
    cap64 = capture_vcvars(vs, "amd64")
    cap86 = capture_vcvars(vs, "amd64_x86")
    info(f"Windows SDK   : {cap64['WINDOWSSDKDIR']} "
         f"({cap64.get('WINDOWSSDKVERSION', '').rstrip(chr(92)) or 'version n/a'})")

    build_cccl_patched(cuda, args.force)
    cudnn_major = gen_cudnn(vs, args, args.force)
    gen_local_config_cc(vs, cap64, cap86, llvm, cuda, msys, sys.executable)
    gen_llvm_bin_path(llvm, cuda, archs)
    gen_local_config_cuda_win(cuda, cudnn_major, archs)
    gen_bazelrc(args.xla_dir)
    gen_env_bat(msys)
    make_junctions(cuda)

    if not os.path.isdir(args.xla_dir):
        info(f"NOTE: xla checkout not found at {args.xla_dir}; the generated "
             "bazelrc points there — clone it before building "
             "(see BUILDING.md)")

    fetched = False
    if args.skip_smoke:
        info("smoke check   : SKIPPED (--skip-smoke)")
    else:
        fetched = smoke(bazel, args.jax_dir, args.xla_dir, msys)
    if args.patch_externals:
        patch_externals(bazel, args.jax_dir, msys, fetched)

    info("configure complete.")
    info("Next: see BUILDING.md - set BAZEL_SH via "
         r"'call toolchains\winjax_env.bat', then run the two Bazel builds "
         "from the jax/ checkout.")


if __name__ == "__main__":
    main()
