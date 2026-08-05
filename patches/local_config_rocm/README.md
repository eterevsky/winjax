# local_config_rocm override

`build_defs.bzl` here is a **full-file override**, not a patch. `@local_config_rocm`
is a machine-generated repository (produced by `rocm_configure` from
`xla/third_party/gpus/rocm/build_defs.bzl.tpl`), so there is no stable pristine
tree to diff against. After Bazel generates the repo, copy this file over
`<output_base>/external/local_config_rocm/rocm/build_defs.bzl`.

What it changes vs. the ROCm-less generated output: `if_gpu_is_configured()` and
`if_cuda_or_rocm()` normally hard-code the "no GPU" branch when the repo is
generated without ROCm. On winjax CUDA is enabled via
`--@local_config_cuda//:enable_cuda`, so both functions are rewritten to
`select()` on `@local_config_cuda//:is_cuda_enabled` instead (see the
`# winjax:` comments in the file).
