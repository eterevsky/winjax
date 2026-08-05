load("@rules_cc//cc:defs.bzl", "cc_library")
load("@bazel_skylib//rules:common_settings.bzl", "bool_flag")

licenses(["restricted"])  # NVIDIA proprietary license

# On Windows there is no redistributable user-mode driver (libcuda.so /
# libnvidia-ptxjitcompiler.so). The driver is nvcuda.dll in System32 and is
# linked via the cuda.lib import library provided by @cuda_cudart//:cuda_stub.
# Target names are kept for consumers; their bodies are intentionally empty.

cc_library(
    name = "nvidia_driver",
    visibility = ["//visibility:public"],
)

cc_library(
    name = "nvidia_ptxjitcompiler",
    visibility = ["//visibility:public"],
)

# Flag indicating whether we should use hermetic user mode driver.
# It must be enabled for complete CUDA hermeticity.
bool_flag(
    name = "include_cuda_umd_libs",
    build_setting_default = False,
    visibility = ["//visibility:public"],
)

config_setting(
    name = "cuda_umd_libs",
    flag_values = {":include_cuda_umd_libs": "True"},
)

# DEPRECATED: use the flag --@cuda_driver//:include_cuda_umd_libs instead
# See the instructions in the paragraph 5 of the doc
# https://github.com/google-ml-infra/rules_ml_toolchain/blob/main/gpu/README.md#configure-hermetic-cuda-cudnn-and-nccl
alias(
    name = "enable_forward_compatibility",
    actual = ":include_cuda_umd_libs",
)
