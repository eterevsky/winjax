load("@rules_cc//cc:defs.bzl", "cc_import", "cc_library")

licenses(["restricted"])  # NVIDIA proprietary license

exports_files([
    "bin/nvcc.exe",
])

filegroup(
    name = "nvvm",
    srcs = ["nvvm/libdevice/libdevice.10.bc"],
    visibility = ["//visibility:public"],
)

filegroup(
    name = "nvdisasm",
    srcs = [
        "bin/nvdisasm.exe",
    ],
    visibility = ["//visibility:public"],
)

filegroup(
    name = "nvlink",
    srcs = [
        "bin/nvlink.exe",
    ],
    visibility = ["//visibility:public"],
)

filegroup(
    name = "fatbinary",
    srcs = [
        "bin/fatbinary.exe",
    ],
    visibility = ["//visibility:public"],
)

filegroup(
    name = "bin2c",
    srcs = [
        "bin/bin2c.exe",
    ],
    visibility = ["//visibility:public"],
)

filegroup(
    name = "ptxas",
    srcs = [
        "bin/ptxas.exe",
    ],
    visibility = ["//visibility:public"],
)

filegroup(
    name = "bin",
    srcs = glob([
        "bin/**",
        "nvvm/bin/**",
    ], allow_empty = True),
    visibility = ["//visibility:public"],
)

filegroup(
    name = "link_stub",
    srcs = [
        "bin/crt/link.stub",
    ],
    visibility = ["//visibility:public"],
)

filegroup(
    name = "header_list",
    srcs = glob([
        "include/fatbinary_section.h",
        "include/nvPTXCompiler.h",
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

cc_import(
    name = "nvptxcompiler_static_library",
    hdrs = [":headers"],
    static_library = None,
)

cc_library(
    name = "nvptxcompiler",
    visibility = ["//visibility:public"],
)
