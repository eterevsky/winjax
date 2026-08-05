load("@rules_cc//cc:defs.bzl", "cc_import", "cc_library")

licenses(["restricted"])  # NVIDIA proprietary license

cc_import(
    name = "cufft_shared_library",
    hdrs = [":headers"],
    interface_library = "lib/cufft.lib",
    system_provided = 1,
)

# No static cuFFT libraries exist on Windows; targets kept name-only.
cc_library(
    name = "cufft_static_library",
)

cc_library(
    name = "cufftw_static_library",
)

cc_library(
    name = "cufft_static_nocallback_library",
)

cc_library(
    name = "cufft",
    deps = [":cufft_shared_library"],
    visibility = ["//visibility:public"],
)

filegroup(
    name = "header_list",
    srcs = glob([
        "include/cudalibxt.h",
        "include/cufft*.h",
    ]),
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
