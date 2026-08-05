load("@rules_cc//cc:defs.bzl", "cc_import", "cc_library")

licenses(["restricted"])  # NVIDIA proprietary license

cc_import(
    name = "nvrtc_main",
    hdrs = [":headers"],
    interface_library = "lib/nvrtc.lib",
    system_provided = 1,
)

# There is no import library for the nvrtc-builtins DLL on Windows; the DLL is
# located and loaded at runtime by nvrtc itself.
cc_library(
    name = "nvrtc_builtins",
)

# The ".alt" static library variant is not shipped in the Windows CUDA toolkit.
cc_library(
    name = "nvrtc_builtins_static_alt",
)

cc_import(
    name = "nvrtc_static",
    static_library = "lib/nvrtc_static.lib",
)

cc_import(
    name = "nvrtc_builtins_static",
    static_library = "lib/nvrtc-builtins_static.lib",
)

# The ".alt" static library variant is not shipped in the Windows CUDA toolkit.
cc_library(
    name = "nvrtc_static_alt",
)

cc_library(
    name = "nvrtc",
    deps = [
        ":nvrtc_main",
        ":nvrtc_builtins",
    ],
    visibility = ["//visibility:public"],
)

filegroup(
    name = "header_list",
    srcs = [
        "include/nvrtc.h",
    ],
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
