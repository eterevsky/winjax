load("@rules_cc//cc:defs.bzl", "cc_import", "cc_library")

licenses(["restricted"])  # NVIDIA proprietary license

cc_import(
    name = "cublas_shared_library",
    hdrs = [":headers"],
    interface_library = "lib/cublas.lib",
    system_provided = 1,
)

cc_import(
    name = "cublasLt_shared_library",
    hdrs = [":headers"],
    interface_library = "lib/cublasLt.lib",
    system_provided = 1,
)

# No static cuBLAS libraries exist on Windows; targets kept name-only.
cc_library(
    name = "cublasLt_static_library",
)

cc_library(
    name = "cublas_static_library",
)

cc_library(
    name = "cublas",
    visibility = ["//visibility:public"],
    deps = [":cublas_shared_library"] + [":cublasLt"],
)

cc_library(
    name = "cublasLt",
    visibility = ["//visibility:public"],
    deps = [":cublasLt_shared_library"],
)

filegroup(
    name = "header_list",
    srcs = [
        "include/cublas.h",
        "include/cublasLt.h",
        "include/cublas_api.h",
        "include/cublas_v2.h",
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
