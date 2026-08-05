load("@rules_cc//cc:defs.bzl", "cc_import", "cc_library")

licenses(["restricted"])  # NVIDIA proprietary license

cc_import(
    name = "cusolver_shared_library",
    hdrs = [":headers"],
    interface_library = "lib/cusolver.lib",
    system_provided = 1,
)

# The cuSOLVER LAPACK static library is not shipped in the Windows CUDA toolkit.
cc_library(
    name = "cusolver_lapack_static_library",
)

# The cuSOLVER METIS static library is not shipped in the Windows CUDA toolkit.
cc_library(
    name = "cusolver_metis_static_library",
)

# The cuSOLVER static library is not shipped in the Windows CUDA toolkit.
cc_library(
    name = "cusolver_static_library",
)

# The METIS static library is not shipped in the Windows CUDA toolkit.
cc_library(
    name = "metis_static_library",
)

cc_library(
    name = "cusolver",
    deps = [":cusolver_shared_library"] + [
        "@cuda_nvjitlink//:nvjitlink",
        "@cuda_cusparse//:cusparse",
        "@cuda_cublas//:cublas",
        "@cuda_cublas//:cublasLt",
    ],
    visibility = ["//visibility:public"],
)

filegroup(
    name = "header_list",
    srcs = glob([
        "include/cusolver*.h",
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
