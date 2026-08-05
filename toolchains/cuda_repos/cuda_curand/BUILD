load("@rules_cc//cc:defs.bzl", "cc_import", "cc_library")

licenses(["restricted"])  # NVIDIA proprietary license

cc_import(
    name = "curand_shared_library",
    hdrs = [":headers"],
    interface_library = "lib/curand.lib",
    system_provided = 1,
)

# No static cuRAND library exists on Windows; target kept name-only.
cc_library(
    name = "curand_static_library",
)

cc_library(
    name = "curand",
    deps = [":curand_shared_library"],
    visibility = ["//visibility:public"],
)

filegroup(
    name = "header_list",
    srcs = glob(["include/curand*.h"]),
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
