load("@rules_cc//cc:defs.bzl", "cc_import", "cc_library")

licenses(["restricted"])  # NVIDIA proprietary license

cc_import(
    name = "cusparse_shared_library",
    hdrs = [":headers"],
    interface_library = "lib/cusparse.lib",
    system_provided = 1,
)

# The cuSPARSE static library is not shipped in the Windows CUDA toolkit.
cc_library(
    name = "cusparse_static_library",
)

cc_library(
    name = "cusparse",
    deps = [":cusparse_shared_library"] + ["@cuda_nvjitlink//:nvjitlink"],
    visibility = ["//visibility:public"],
)

filegroup(
    name = "header_list",
    srcs = ["include/cusparse.h"],
    visibility = ["@local_config_cuda//cuda:__pkg__"],
)

cc_library(
    name = "headers",
    hdrs = [":header_list"],
    include_prefix = "third_party/gpus/cuda/include",
    includes = ["include"],
    strip_include_prefix = "include",
    visibility = ["@local_config_cuda//cuda:__pkg__"],
)
