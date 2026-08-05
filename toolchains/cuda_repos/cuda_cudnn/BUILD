load("@rules_cc//cc:defs.bzl", "cc_import", "cc_library")

licenses(["restricted"])  # NVIDIA proprietary license

cc_import(
    name = "cudnn_ops",
    hdrs = [":headers"],
    interface_library = "lib/cudnn_ops.lib",
    system_provided = 1,
)

cc_import(
    name = "cudnn_cnn",
    hdrs = [":headers"],
    interface_library = "lib/cudnn_cnn.lib",
    system_provided = 1,
)

cc_import(
    name = "cudnn_adv",
    hdrs = [":headers"],
    interface_library = "lib/cudnn_adv.lib",
    system_provided = 1,
)

cc_import(
    name = "cudnn_graph",
    hdrs = [":headers"],
    interface_library = "lib/cudnn_graph.lib",
    system_provided = 1,
)

cc_import(
    name = "cudnn_engines_precompiled",
    hdrs = [":headers"],
    interface_library = "lib/cudnn_engines_precompiled.lib",
    system_provided = 1,
)

cc_import(
    name = "cudnn_engines_runtime_compiled",
    hdrs = [":headers"],
    interface_library = "lib/cudnn_engines_runtime_compiled.lib",
    system_provided = 1,
)

cc_import(
    name = "cudnn_heuristic",
    hdrs = [":headers"],
    interface_library = "lib/cudnn_heuristic.lib",
    system_provided = 1,
)

cc_import(
    name = "cudnn_main",
    hdrs = [":headers"],
    interface_library = "lib/cudnn.lib",
    system_provided = 1,
)

# No static cuDNN libraries exist on Windows; targets kept name-only.
cc_library(
    name = "cudnn_graph_static",
)

cc_library(
    name = "cudnn_adv_static",
)

cc_library(
    name = "cudnn_engines_runtime_compiled_static",
)

cc_library(
    name = "cudnn_engines_precompiled_static",
)

cc_library(
    name = "cudnn_ops_static",
)

cc_library(
    name = "cudnn_heuristic_static",
)

cc_library(
    name = "cudnn_cnn_static",
)

cc_library(
    name = "cudnn",
    hdrs = [":header_list"],
    alwayslink = False,
    deps = [
        "@cuda_cublas//:cublas",
        ":cudnn_engines_precompiled",
        ":cudnn_ops",
        ":cudnn_graph",
        ":cudnn_cnn",
        ":cudnn_adv",
        ":cudnn_engines_runtime_compiled",
        ":cudnn_heuristic",
        ":cudnn_main",
    ] + ["@cuda_nvrtc//:nvrtc"],
    includes = ["include"],
    visibility = ["//visibility:public"],
)

filegroup(
    name = "header_list",
    srcs = glob([
        "include/cudnn*.h",
    ]),
)

cc_library(
    name = "headers",
    hdrs = [":header_list"],
    include_prefix = "third_party/gpus/cudnn",
    includes = ["include"],
    strip_include_prefix = "include",
    visibility = ["@local_config_cuda//cuda:__pkg__"],
)
