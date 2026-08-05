"""winjax compiler dispatch wrapper.

Bazel's Windows toolchain drives one compiler binary for every C/C++ compile
action with MSVC-style (cl.exe) flags. XLA's cuda_library targets need their
.cu.cc sources compiled by clang's CUDA driver (GCC-style flags), which
clang-cl cannot be forced into for arbitrary file extensions (-x is reordered
after inputs by the clang-cl driver and ignored).

This wrapper is registered as the toolchain compiler. For ordinary compiles it
execs clang-cl with the original args untouched. When it sees the CUDA marker
(-x cuda) in the args it translates the MSVC-style flags to GCC style, appends
the CUDA configuration, and execs clang++ instead. Header-dependency discovery
is preserved by converting a clang -MD depfile back into /showIncludes-style
output that Bazel's msvc toolchain parser understands.
"""

import os
import subprocess
import sys

LLVM_BIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "llvm_bin_path.txt")


def _read_config():
    # llvm_bin_path.txt: first line clang bin dir, second line cuda path,
    # third line cuda gpu archs (comma separated, e.g. "sm_120").
    with open(LLVM_BIN, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip()]
    # Optional 4th line: CCCL include dir override (patched copy); defaults to
    # the toolkit's include/cccl.
    cccl = lines[3] if len(lines) > 3 else os.path.join(lines[1], "include", "cccl")
    return lines[0], lines[1], lines[2], cccl


def _expand_params(argv):
    """Expand @params-file references into a flat arg list."""
    out = []
    for arg in argv:
        if arg.startswith("@"):
            with open(arg[1:], "r", encoding="utf-8-sig") as f:
                for line in f:
                    line = line.rstrip("\n").rstrip("\r")
                    if line:
                        out.append(line.strip('"'))
        else:
            out.append(arg)
    return out


def _is_cuda_compile(args):
    for i, a in enumerate(args):
        if a == "-xcuda":
            return True
        if a == "-x" and i + 1 < len(args) and args[i + 1] == "cuda":
            return True
    return False


_DROP_PREFIXES = (
    "/W", "/w", "/Zc:", "/showIncludes", "/FC", "/Fd", "/FS", "/Gy", "/Gw",
    "/guard", "/bigobj", "/Zi", "/experimental:", "/d2", "/arch:",
    "-Xcompilation-mode", "/EHs-", "/GR-",
)


def _translate(args, clang_bin, cuda_path, gpu_archs, cccl_dir):
    """Translate MSVC-style compile args to a clang++ CUDA command."""
    cmd = [os.path.join(clang_bin, "clang++.exe")]
    out_obj = None
    depfile = None
    show_includes = "/showIncludes" in args
    i = 0
    src = None
    while i < len(args):
        a = args[i]
        if a in ("-x", ):
            i += 2  # consumed marker; language forced below
            continue
        if a == "-xcuda":
            i += 1
            continue
        if a == "/c":
            cmd.append("-c")
        elif a.startswith("/Fo"):
            out_obj = a[3:].lstrip(":")
            cmd += ["-o", out_obj]
        elif a.startswith("/I"):
            cmd += ["-I", a[2:]] if len(a) > 2 else []
        elif a == "-I":
            cmd += ["-I", args[i + 1]]
            i += 1
        elif a.startswith("/D"):
            cmd.append("-D" + a[2:])
        elif a.startswith("/std:"):
            cmd.append("-std=" + a[5:])
        elif a == "/MD":
            cmd.append("-fms-runtime-lib=dll")
        elif a == "/MDd":
            cmd.append("-fms-runtime-lib=dll_dbg")
        elif a == "/MT":
            cmd.append("-fms-runtime-lib=static")
        elif a == "/MTd":
            cmd.append("-fms-runtime-lib=static_dbg")
        elif a in ("/O2", "/O1"):
            cmd.append("-O2")
        elif a in ("/Od",):
            cmd.append("-O0")
        elif a == "/Z7":
            cmd += ["-g", "-gcodeview"]
        elif a == "/EHsc":
            cmd.append("-fexceptions")
        elif a.startswith(_DROP_PREFIXES):
            pass
        elif a.startswith("/"):
            # Unknown MSVC flag: drop, but record for diagnosis.
            print(f"winjax_cc_wrapper: dropped unknown flag {a}", file=sys.stderr)
        elif a.endswith((".cu", ".cu.cc", ".cc", ".cpp", ".c")) and not a.startswith("-"):
            src = a
        else:
            cmd.append(a)
        i += 1

    if src is None or out_obj is None:
        print("winjax_cc_wrapper: could not find source/output in CUDA compile",
              file=sys.stderr)
        sys.exit(1)

    depfile = out_obj + ".winjax.d"
    cmd += ["-MD", "-MF", depfile]
    cmd += ["--cuda-path=" + cuda_path]
    for arch in gpu_archs.split(","):
        cmd.append("--cuda-gpu-arch=" + arch.strip())
    cmd += [
        "-I", cccl_dir,
        "-DNOMINMAX",
        "-Wno-unknown-cuda-version",
        "-x", "cuda", src,
    ]
    return cmd, depfile, show_includes, src


def _emit_show_includes(depfile, src):
    """Convert a make-style depfile into /showIncludes-format stdout lines."""
    try:
        with open(depfile, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return
    # Depfile format: "out: dep1 dep2 \\\n dep3 ..." with backslash-escaped
    # spaces inside paths. Tokenize by whitespace while honoring the escapes.
    body = text.split(":", 1)[1] if ":" in text else ""
    body = body.replace("\\\r\n", " ").replace("\\\n", " ")
    deps = []
    cur = []
    i = 0
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body) and body[i + 1] == " ":
            cur.append(" ")
            i += 2
            continue
        if ch in " \t\r\n":
            if cur:
                deps.append("".join(cur))
                cur = []
        else:
            cur.append(ch)
        i += 1
    if cur:
        deps.append("".join(cur))
    src_norm = os.path.normcase(os.path.abspath(src))
    for d in deps:
        if os.path.normcase(os.path.abspath(d)) == src_norm:
            continue
        print("Note: including file: " + os.path.abspath(d))


def main():
    argv = sys.argv[1:]
    clang_bin, cuda_path, gpu_archs, cccl_dir = _read_config()
    args = _expand_params(argv)

    if not _is_cuda_compile(args):
        # Plain host compile: forward original argv (incl. @params) untouched.
        cl = os.path.join(clang_bin, "clang-cl.exe")
        proc = subprocess.run([cl] + argv)
        sys.exit(proc.returncode)

    cmd, depfile, show_includes, src = _translate(args, clang_bin, cuda_path, gpu_archs, cccl_dir)
    proc = subprocess.run(cmd)
    if proc.returncode == 0 and show_includes:
        _emit_show_includes(depfile, src)
    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
