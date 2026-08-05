load("@rules_cc//cc:defs.bzl", "cc_import", "cc_library")

licenses(["restricted"])  # NVIDIA proprietary license

filegroup(
    name = "header_list",
    srcs = ["include/nvml.h"],
    visibility = ["@local_config_cuda//cuda:__pkg__"],
)

cc_library(
    name = "headers",
    hdrs = [":header_list"],
    include_prefix = "third_party/gpus/cuda/nvml/include",
    includes = ["include"],
    strip_include_prefix = "include",
    visibility = ["@local_config_cuda//cuda:__pkg__"],
)

cc_import(
    name = "nvidia-ml_stub",
    interface_library = "lib/nvml.lib",
    system_provided = 1,
    visibility = ["@cuda_cudart//:__pkg__"],
)

cc_library(
    name = "nvml",
    deps = [":nvidia-ml_stub"],
    visibility = ["//visibility:public"],
)
