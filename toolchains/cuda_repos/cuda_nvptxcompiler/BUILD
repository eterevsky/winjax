load("@rules_cc//cc:defs.bzl", "cc_import", "cc_library")

licenses(["restricted"])  # NVIDIA proprietary license

cc_import(
    name = "nvptxcompiler_static_library",
    hdrs = [":headers"],
    static_library = "lib/nvptxcompiler_static.lib",
)

cc_library(
    name = "nvptxcompiler",
    deps = [":nvptxcompiler_static_library"],
    visibility = ["//visibility:public"],
)

filegroup(
    name = "header_list",
    srcs = [
        "include/nvPTXCompiler.h",
    ],
    visibility = ["@local_config_cuda//cuda:__pkg__"],
)

cc_library(
    name = "headers",
    hdrs = [":header_list"],
    includes = ["include"],
    strip_include_prefix = "include",
)
