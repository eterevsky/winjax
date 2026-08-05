load("@rules_cc//cc:defs.bzl", "cc_import", "cc_library")

licenses(["restricted"])  # NVIDIA proprietary license

cc_import(
    name = "nvjitlink_shared_library",
    hdrs = [":headers"],
    interface_library = "lib/nvJitLink.lib",
    system_provided = 1,
)

cc_import(
    name = "nvjitlink_static_library",
    hdrs = [":headers"],
    static_library = "lib/nvJitLink_static.lib",
)

cc_library(
    name = "nvjitlink",
    deps = [":nvjitlink_shared_library"],
    visibility = ["//visibility:public"],
)

filegroup(
    name = "header_list",
    srcs = ["include/nvJitLink.h"],
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
